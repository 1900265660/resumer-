from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fact_library import parse_fact_records
from validators import extract_numeric_claims


FIXED_CATEGORIES = {
    "agent_application",
    "ai_platform_tool",
    "data_strategy",
    "consumer_commerce_content",
    "technical_capability_gap",
}
DIMENSIONS = ("jd_coverage", "evidence_depth", "hr_scan", "language_naturalness")
FIXED_SECTIONS = ("教育经历", "实习/工作经历", "实践经历", "自我能力")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


class EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvalCase(EvalModel):
    case_id: str = Field(pattern=r"^[a-z0-9-]+$")
    category: str
    company: str
    role: str
    expected_hard_gap: bool
    jd_path: Path
    jd_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fact_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class QualityScores(EvalModel):
    jd_coverage: float = Field(ge=0, le=10)
    evidence_depth: float = Field(ge=0, le=10)
    hr_scan: float = Field(ge=0, le=10)
    language_naturalness: float = Field(ge=0, le=10)


class CandidateEval(EvalModel):
    truth_passed: bool
    hard_findings: list[str] = Field(default_factory=list)
    scores: QualityScores

    @model_validator(mode="after")
    def truth_matches_findings(self) -> "CandidateEval":
        if self.truth_passed == bool(self.hard_findings):
            raise ValueError("truth_passed must be the inverse of hard_findings")
        return self


class CaseEvaluation(EvalModel):
    case_id: str
    fact_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_mode: Literal["blind"] = "blind"
    legacy: CandidateEval
    new: CandidateEval
    evaluator_notes: list[str] = Field(default_factory=list)


class BlindCaseEvaluation(EvalModel):
    case_id: str
    fact_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_a: CandidateEval
    candidate_b: CandidateEval
    evaluator_notes: list[str] = Field(default_factory=list)


class TraceBullet(EvalModel):
    bullet_text: str = Field(min_length=1)
    experience_id: str = Field(pattern=r"^EXP-[A-Z]+-[0-9]{3}$")
    fact_ids: list[str] = Field(min_length=1)


class TraceArtifact(EvalModel):
    case_id: str
    lane: Literal["legacy", "new"]
    bullets: list[TraceBullet] = Field(min_length=1)


class BlindTraceArtifact(EvalModel):
    bullets: list[TraceBullet] = Field(min_length=1)


class SuiteSummary(EvalModel):
    passed: bool
    truth_gate_passed: bool
    quality_gate_passed: bool
    improved_dimensions: list[str]
    averages_legacy: QualityScores
    averages_new: QualityScores
    failures: list[str]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def assert_sanitized(value: str, source: str) -> None:
    if PHONE_RE.search(value) or EMAIL_RE.search(value):
        raise ValueError(f"sensitive contact data found in {source}")


def load_cases(fixtures_root: Path) -> list[EvalCase]:
    fixtures_root = fixtures_root.resolve()
    fact_path = fixtures_root / "fact-snapshot.md"
    fact_bytes = fact_path.read_bytes()
    assert_sanitized(fact_bytes.decode("utf-8"), str(fact_path))
    fact_sha = sha256_bytes(fact_bytes)
    cases: list[EvalCase] = []
    for case_path in sorted(fixtures_root.glob("*/case.json")):
        payload = json.loads(case_path.read_text(encoding="utf-8"))
        jd_path = case_path.with_name("jd.md")
        jd_bytes = jd_path.read_bytes()
        assert_sanitized(jd_bytes.decode("utf-8"), str(jd_path))
        cases.append(
            EvalCase(
                **payload,
                jd_path=jd_path,
                jd_sha256=sha256_bytes(jd_bytes),
                fact_snapshot_sha256=fact_sha,
            )
        )
    if len(cases) != 5:
        raise ValueError(f"expected exactly 5 fixed eval cases, got {len(cases)}")
    categories = {item.category for item in cases}
    if categories != FIXED_CATEGORIES:
        raise ValueError(f"fixed eval categories mismatch: {sorted(categories)}")
    ids = [item.case_id for item in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("fixed eval case IDs must be unique")
    return cases


def deterministic_plan(
    fixtures_root: Path,
    legacy_prompt: Path,
    new_skill: Path,
) -> dict[str, object]:
    cases = load_cases(fixtures_root)
    repo_root = new_skill.resolve().parents[3]
    prompt_root = repo_root / ".agents" / "prompts" / "custom-resume"
    rubric_path = fixtures_root.resolve() / "quality-rubric.md"
    prompt_hashes = {
        path.name: sha256_bytes(path.read_bytes())
        for path in sorted(prompt_root.glob("*.md"))
    }
    return {
        "schema_version": "1.0",
        "fact_snapshot_sha256": cases[0].fact_snapshot_sha256,
        "legacy_prompt_sha256": sha256_bytes(legacy_prompt.read_bytes()),
        "new_skill_sha256": sha256_bytes(new_skill.read_bytes()),
        "new_prompt_sha256": prompt_hashes,
        "quality_rubric_sha256": sha256_bytes(rubric_path.read_bytes()),
        "cases": [
            {
                "case_id": item.case_id,
                "category": item.category,
                "jd_sha256": item.jd_sha256,
                "legacy_artifact": f"{item.case_id}/legacy.md",
                "new_artifact": f"{item.case_id}/new.md",
            }
            for item in cases
        ],
    }


def validate_markdown_structure(content: str) -> list[str]:
    headings = [
        (len(match.group(1)), match.group(2).strip())
        for match in MARKDOWN_HEADING_RE.finditer(content)
    ]
    section_headings = [(level, title) for level, title in headings if title in FIXED_SECTIONS]
    findings: list[str] = []
    if [title for _, title in section_headings] != list(FIXED_SECTIONS):
        findings.append("FIXED_SECTION_ORDER_MISMATCH")
    if any(level != 2 for level, _ in section_headings):
        findings.append("FIXED_SECTION_LEVEL_MISMATCH")
    extras = [title for level, title in headings if level <= 2 and title not in FIXED_SECTIONS]
    if extras:
        findings.append(f"EXTRA_TOP_LEVEL_STRUCTURE {extras}")
    return findings


def validate_trace(trace: TraceArtifact, fact_snapshot: str) -> list[str]:
    _, facts = parse_fact_records(fact_snapshot)
    findings: list[str] = []
    for index, bullet in enumerate(trace.bullets):
        cited = []
        for fact_id in bullet.fact_ids:
            fact = facts.get(fact_id)
            if not fact:
                findings.append(f"bullet {index}: UNKNOWN_FACT_ID {fact_id}")
                continue
            cited.append(fact)
            if fact.experience_id != bullet.experience_id:
                findings.append(
                    f"bullet {index}: CROSS_EXPERIENCE_FACT {fact_id} belongs to {fact.experience_id}"
                )
        source_numbers = sum(
            (extract_numeric_claims(item.value) for item in cited),
            start=extract_numeric_claims(""),
        )
        unsupported = extract_numeric_claims(bullet.bullet_text) - source_numbers
        if unsupported:
            findings.append(
                f"bullet {index}: UNSUPPORTED_NUMERIC_CLAIM {list(unsupported.elements())}"
            )
    return findings


def build_blind_package(
    generated_root: Path,
    fixtures_root: Path,
    blind_root: Path,
) -> dict[str, object]:
    cases = load_cases(fixtures_root)
    fact_path = fixtures_root / "fact-snapshot.md"
    rubric_path = fixtures_root / "quality-rubric.md"
    fact_text = fact_path.read_text(encoding="utf-8")
    rubric_text = rubric_path.read_text(encoding="utf-8")
    assert_sanitized(rubric_text, str(rubric_path))
    blind_root.mkdir(parents=True, exist_ok=True)
    mappings: dict[str, object] = {
        "schema_version": "1.0",
        "fact_snapshot_sha256": cases[0].fact_snapshot_sha256,
        "cases": {},
    }
    for case in cases:
        source = generated_root / case.case_id
        lane_payload: dict[str, dict[str, object]] = {}
        for lane in ("legacy", "new"):
            content = (source / f"{lane}.md").read_text(encoding="utf-8")
            assert_sanitized(content, f"{case.case_id}/{lane}.md")
            trace = TraceArtifact.model_validate_json(
                (source / f"{lane}-trace.json").read_text(encoding="utf-8")
            )
            if trace.case_id != case.case_id or trace.lane != lane:
                raise ValueError(f"trace identity mismatch for {case.case_id}/{lane}")
            lane_payload[lane] = {
                "content": content,
                "trace": trace,
                "deterministic_findings": [
                    *validate_trace(trace, fact_text),
                    *validate_markdown_structure(content),
                ],
            }
        new_is_a = int(hashlib.sha256(case.case_id.encode()).hexdigest(), 16) % 2 == 0
        assignment = {"candidate_a": "new", "candidate_b": "legacy"} if new_is_a else {
            "candidate_a": "legacy",
            "candidate_b": "new",
        }
        case_blind = blind_root / case.case_id
        case_blind.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(case.jd_path, case_blind / "jd.md")
        shutil.copyfile(fact_path, case_blind / "fact-snapshot.md")
        shutil.copyfile(rubric_path, case_blind / "quality-rubric.md")
        for candidate, lane in assignment.items():
            (case_blind / f"{candidate}.md").write_text(
                lane_payload[lane]["content"], encoding="utf-8", newline=""
            )
            blind_trace = BlindTraceArtifact(bullets=lane_payload[lane]["trace"].bullets)
            (case_blind / f"{candidate}-trace.json").write_text(
                blind_trace.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
                newline="",
            )
        mappings["cases"][case.case_id] = {
            "assignment": assignment,
            "deterministic_findings": {
                lane: lane_payload[lane]["deterministic_findings"]
                for lane in ("legacy", "new")
            },
        }
    (blind_root / "_private-mapping.json").write_text(
        json.dumps(mappings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )
    return mappings


def unblind_evaluations(
    blind_scores: list[BlindCaseEvaluation],
    mapping: dict[str, object],
) -> list[CaseEvaluation]:
    results: list[CaseEvaluation] = []
    mapping_cases = mapping["cases"]
    for score in blind_scores:
        case_mapping = mapping_cases[score.case_id]
        assignment = case_mapping["assignment"]
        candidates = {
            "candidate_a": score.candidate_a,
            "candidate_b": score.candidate_b,
        }
        lanes: dict[str, CandidateEval] = {}
        for candidate_name, lane in assignment.items():
            evaluated = candidates[candidate_name]
            deterministic = case_mapping["deterministic_findings"][lane]
            hard_findings = [*evaluated.hard_findings, *deterministic]
            lanes[lane] = CandidateEval(
                truth_passed=not hard_findings and evaluated.truth_passed,
                hard_findings=hard_findings,
                scores=evaluated.scores,
            )
        results.append(
            CaseEvaluation(
                case_id=score.case_id,
                fact_snapshot_sha256=score.fact_snapshot_sha256,
                legacy=lanes["legacy"],
                new=lanes["new"],
                evaluator_notes=score.evaluator_notes,
            )
        )
    return results


def load_blind_scores(scores_root: Path, fixture_cases: list[EvalCase]) -> list[BlindCaseEvaluation]:
    scores: list[BlindCaseEvaluation] = []
    for case in fixture_cases:
        score_path = scores_root / case.case_id / "blind-score.json"
        if not score_path.is_file():
            raise ValueError(f"missing blind score: {score_path}")
        score = BlindCaseEvaluation.model_validate_json(score_path.read_text(encoding="utf-8"))
        if score.case_id != case.case_id:
            raise ValueError(f"blind score case mismatch: {score_path}")
        if score.fact_snapshot_sha256 != case.fact_snapshot_sha256:
            raise ValueError(f"blind score fact snapshot mismatch: {score_path}")
        scores.append(score)
    return scores


def summarize_suite(cases: list[CaseEvaluation], fixture_cases: list[EvalCase]) -> SuiteSummary:
    expected = {item.case_id: item for item in fixture_cases}
    actual_ids = {item.case_id for item in cases}
    if actual_ids != set(expected) or len(cases) != len(expected):
        raise ValueError("suite results must contain each fixed case exactly once")
    failures: list[str] = []
    for item in cases:
        if item.fact_snapshot_sha256 != expected[item.case_id].fact_snapshot_sha256:
            failures.append(f"{item.case_id}: fact snapshot mismatch")
        if not item.new.truth_passed:
            failures.append(f"{item.case_id}: new truth gate failed")
        if item.legacy.truth_passed and not item.new.truth_passed:
            failures.append(f"{item.case_id}: truth regressed")
        for dimension in DIMENSIONS:
            if getattr(item.new.scores, dimension) < 8:
                failures.append(f"{item.case_id}: new {dimension} below 8")
    averages: dict[str, dict[str, float]] = {"legacy": {}, "new": {}}
    for lane in ("legacy", "new"):
        for dimension in DIMENSIONS:
            averages[lane][dimension] = round(
                sum(getattr(getattr(item, lane).scores, dimension) for item in cases)
                / len(cases),
                3,
            )
    improved = [
        dimension
        for dimension in DIMENSIONS
        if averages["new"][dimension] > averages["legacy"][dimension]
    ]
    if len(improved) < 3:
        failures.append("new flow improves fewer than 3 quality dimensions")
    truth_gate = all(item.new.truth_passed for item in cases)
    quality_gate = all(
        getattr(item.new.scores, dimension) >= 8
        for item in cases
        for dimension in DIMENSIONS
    ) and len(improved) >= 3
    return SuiteSummary(
        passed=not failures,
        truth_gate_passed=truth_gate,
        quality_gate_passed=quality_gate,
        improved_dimensions=improved,
        averages_legacy=QualityScores(**averages["legacy"]),
        averages_new=QualityScores(**averages["new"]),
        failures=failures,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Custom-resume fixed evaluation harness")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-fixtures")
    validate.add_argument("--fixtures", required=True, type=Path)
    plan = subparsers.add_parser("write-plan")
    plan.add_argument("--fixtures", required=True, type=Path)
    plan.add_argument("--legacy-prompt", required=True, type=Path)
    plan.add_argument("--new-skill", required=True, type=Path)
    plan.add_argument("--output", required=True, type=Path)
    blind = subparsers.add_parser("build-blind")
    blind.add_argument("--generated", required=True, type=Path)
    blind.add_argument("--fixtures", required=True, type=Path)
    blind.add_argument("--output", required=True, type=Path)
    unblind = subparsers.add_parser("unblind")
    unblind.add_argument("--fixtures", required=True, type=Path)
    unblind.add_argument("--mapping", required=True, type=Path)
    unblind.add_argument("--scores", required=True, type=Path)
    unblind.add_argument("--output", required=True, type=Path)
    summary = subparsers.add_parser("summarize")
    summary.add_argument("--fixtures", required=True, type=Path)
    summary.add_argument("--results", required=True, type=Path)
    summary.add_argument("--output", type=Path)
    args = parser.parse_args()
    fixtures = load_cases(args.fixtures)
    if args.command == "validate-fixtures":
        print(json.dumps([item.model_dump(mode="json") for item in fixtures], ensure_ascii=False, indent=2))
    elif args.command == "write-plan":
        payload = deterministic_plan(args.fixtures, args.legacy_prompt, args.new_skill)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif args.command == "build-blind":
        mapping = build_blind_package(args.generated, args.fixtures, args.output)
        print(json.dumps({"cases": sorted(mapping["cases"])}, ensure_ascii=False))
    elif args.command == "unblind":
        mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
        scores = load_blind_scores(args.scores, fixtures)
        payload = [
            item.model_dump(mode="json")
            for item in unblind_evaluations(scores, mapping)
        ]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="",
        )
    else:
        payload = json.loads(args.results.read_text(encoding="utf-8"))
        evaluations = [CaseEvaluation.model_validate(item) for item in payload]
        rendered = summarize_suite(evaluations, fixtures).model_dump_json(indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8", newline="")
        else:
            print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
