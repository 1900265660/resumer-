from __future__ import annotations

import json
import hashlib
import shutil
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "custom-resume" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from eval_harness import (  # noqa: E402
    BlindCaseEvaluation,
    CaseEvaluation,
    CandidateEval,
    QualityScores,
    TraceArtifact,
    TransferExpectation,
    assert_sanitized,
    build_blind_package,
    deterministic_plan,
    evaluate_transfer_diagnostics,
    load_cases,
    load_blind_scores,
    summarize_suite,
    unblind_evaluations,
    validate_markdown_structure,
    validate_trace,
)
from models import (  # noqa: E402
    CapabilityCategory,
    CapabilityStatus,
    CapabilityTransferMapArtifact,
)


FIXTURES = Path(__file__).parent / "fixtures" / "evals"
GAME_FIXTURES = Path(__file__).parent / "fixtures" / "game-production-extension"
COMMUNITY_FIXTURES = Path(__file__).parent / "fixtures" / "community-extension"
GAME_DESIGNER_FIXTURES = Path(__file__).parent / "fixtures" / "game-designer-extension"
EVIDENCE = REPO_ROOT / "docs" / "custom-resume-agent" / "eval-results" / "fixed-v1"
GAME_EVIDENCE = (
    REPO_ROOT
    / "docs"
    / "custom-resume-agent"
    / "eval-results"
    / "game-production-v1.1"
)
TRANSFER_FIXTURE = Path(__file__).parent / "fixtures" / "transfer-v1.3" / "deepblue-translation.json"


def candidate(score: float, truth: bool = True) -> CandidateEval:
    return CandidateEval(
        truth_passed=truth,
        hard_findings=[] if truth else ["UNSUPPORTED_CLAIM"],
        scores=QualityScores(
            jd_coverage=score,
            evidence_depth=score,
            hr_scan=score,
            language_naturalness=score,
        ),
    )


def test_fixed_dataset_has_five_sanitized_categories_and_one_fact_snapshot() -> None:
    cases = load_cases(FIXTURES)
    assert len(cases) == 5
    assert len({item.category for item in cases}) == 5
    assert len({item.fact_snapshot_sha256 for item in cases}) == 1
    assert sum(item.expected_hard_gap for item in cases) == 1


def test_eval_plan_is_byte_repeatable() -> None:
    first = deterministic_plan(
        FIXTURES,
        REPO_ROOT / ".agents" / "prompts" / "campus-resume-optimizer.md",
        REPO_ROOT / ".agents" / "skills" / "custom-resume" / "SKILL.md",
    )
    second = deterministic_plan(
        FIXTURES,
        REPO_ROOT / ".agents" / "prompts" / "campus-resume-optimizer.md",
        REPO_ROOT / ".agents" / "skills" / "custom-resume" / "SKILL.md",
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert set(first["new_prompt_sha256"]) == {
        "asu-writer.md",
        "auditor.md",
        "fusion.md",
        "jd-analysis.md",
        "experience-selection.md",
        "selection-audit.md",
        "writer.md",
        "capability-transfer.md",
    }


def test_deepblue_translation_transfer_fixture_has_full_recall_and_precision() -> None:
    payload = json.loads(TRANSFER_FIXTURE.read_text(encoding="utf-8"))
    artifact = CapabilityTransferMapArtifact.model_validate(payload["artifact"])
    expectations = [
        TransferExpectation.model_validate(item)
        for item in payload["expected_supported"]
    ]
    diagnostics = evaluate_transfer_diagnostics(artifact, expectations)
    assert diagnostics.transfer_recall == 1
    assert diagnostics.transfer_precision == 1
    candidate = next(
        item for item in artifact.transfers if item.transfer_id == "TR-004"
    )
    assert candidate.fact_ids == []
    assert candidate.writable_scope is None
    assert candidate.credit_multiplier == 0

    false_positive = artifact.model_copy(
        update={
            "transfers": [
                *artifact.transfers,
                artifact.transfers[0].model_copy(
                    update={
                        "transfer_id": "TR-005",
                        "category": CapabilityCategory.USER_RESEARCH,
                        "target_capability": "未经事实支持的玩家研究",
                    }
                ),
            ],
            "scans": [
                scan.model_copy(
                    update={
                        "status": CapabilityStatus.SUPPORTED,
                        "transfer_ids": ["TR-005"],
                    }
                )
                if scan.category.value == "user_research"
                else scan
                for scan in artifact.scans
            ],
        }
    )
    false_positive = CapabilityTransferMapArtifact.model_validate(
        false_positive.model_dump(mode="python")
    )
    assert evaluate_transfer_diagnostics(
        false_positive, expectations
    ).transfer_precision < 1


def test_game_extension_uses_one_sanitized_case_and_role_specific_prompts() -> None:
    cases = load_cases(GAME_FIXTURES)
    assert len(cases) == 1
    assert cases[0].category == "game_production_pm"
    assert cases[0].expected_hard_gap is True
    plan = deterministic_plan(
        GAME_FIXTURES,
        REPO_ROOT / ".agents" / "prompts" / "campus-resume-optimizer.md",
        REPO_ROOT / ".agents" / "skills" / "custom-resume" / "SKILL.md",
    )
    assert set(plan["new_prompt_sha256"]) == {
        "asu-writer-game-production.md",
        "auditor.md",
        "fusion.md",
        "jd-analysis-game-production.md",
        "experience-selection.md",
        "selection-audit.md",
        "writer-game-production.md",
        "capability-transfer.md",
    }


def test_t26_community_extension_has_five_routes_and_shared_prompt_plan() -> None:
    cases = load_cases(COMMUNITY_FIXTURES)
    assert len(cases) == 5
    assert {item.category for item in cases} == {
        "community_operations_community",
        "community_operations_content",
        "community_operations_growth",
        "community_operations_integrated",
        "community_product_manager",
    }
    assert {item.role_track.value if item.role_track else None for item in cases} == {
        "community",
        "content",
        "growth",
        "integrated",
        None,
    }
    plan = deterministic_plan(
        COMMUNITY_FIXTURES,
        REPO_ROOT / ".agents" / "prompts" / "campus-resume-optimizer.md",
        REPO_ROOT / ".agents" / "skills" / "custom-resume" / "SKILL.md",
    )
    assert set(plan["new_prompt_sha256"]) == {
        "asu-writer.md",
        "auditor.md",
        "fusion.md",
        "jd-analysis-community.md",
        "writer.md",
        "capability-transfer.md",
        "experience-selection.md",
        "selection-audit.md",
        "hr-reviewer.md",
    }


def test_t26_community_acceptance_and_boundary_fixtures_meet_release_gates() -> None:
    cases = load_cases(COMMUNITY_FIXTURES)
    for case in cases:
        acceptance_path = case.jd_path.with_name("acceptance.json")
        acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
        assert acceptance["truth_passed"] is True
        assert set(acceptance["quality"]) == {
            "jd_coverage",
            "selection_quality",
            "evidence_depth",
            "hr_scan",
            "language_naturalness",
        }
        assert min(acceptance["quality"].values()) >= 8
        assert acceptance["hr"]["recommendation"] == "strong_push"
        assert acceptance["hr"]["overall_score"] >= 8.5
        assert acceptance["hr"]["minimum_dimension_score"] >= 8.5
        assert len(acceptance["required_fact_ids"]) >= 2
        assert acceptance["forbidden_inferences"]

    boundary_cases = json.loads(
        (COMMUNITY_FIXTURES / "boundary-cases.json").read_text(encoding="utf-8")
    )
    assert {item["case_id"] for item in boundary_cases} == {
        "community-growth-gap",
        "community-growth-adversarial",
        "community-product-gap",
        "community-product-adversarial",
    }
    assert {item["role_family"] for item in boundary_cases} == {
        "community_operations",
        "community_product_manager",
    }
    assert all(item["expected_outcome"] != "pass" for item in boundary_cases)
    assert all(item["forbidden_claim"] for item in boundary_cases)


def test_t27_game_designer_extension_has_five_directions_and_prompt_plan() -> None:
    cases = load_cases(GAME_DESIGNER_FIXTURES)
    assert len(cases) == 5
    assert {item.category for item in cases} == {
        "game_designer_system",
        "game_designer_combat",
        "game_designer_writing",
        "game_designer_narrative",
        "game_designer_general",
    }
    assert {item.role_track.value for item in cases if item.role_track} == {
        "system",
        "combat",
        "writing",
        "narrative",
        "general",
    }
    plan = deterministic_plan(
        GAME_DESIGNER_FIXTURES,
        REPO_ROOT / ".agents" / "prompts" / "campus-resume-optimizer.md",
        REPO_ROOT / ".agents" / "skills" / "custom-resume" / "SKILL.md",
    )
    assert set(plan["new_prompt_sha256"]) == {
        "asu-writer-game-designer.md",
        "auditor.md",
        "fusion.md",
        "jd-analysis-game-designer.md",
        "writer-game-designer.md",
        "capability-transfer.md",
        "experience-selection.md",
        "selection-audit.md",
        "hr-reviewer.md",
    }


def test_t27_game_designer_acceptance_and_adversarial_fixtures_meet_gates() -> None:
    cases = load_cases(GAME_DESIGNER_FIXTURES)
    for case in cases:
        acceptance = json.loads(
            case.jd_path.with_name("acceptance.json").read_text(encoding="utf-8")
        )
        assert acceptance["truth_passed"] is True
        assert min(acceptance["quality"].values()) >= 8
        assert acceptance["hr"]["recommendation"] == "strong_push"
        assert acceptance["hr"]["overall_score"] >= 8.5
        assert acceptance["hr"]["minimum_dimension_score"] >= 8.5
        assert len(acceptance["required_fact_ids"]) >= 2
        assert acceptance["forbidden_inferences"]

    boundary_cases = json.loads(
        (GAME_DESIGNER_FIXTURES / "boundary-cases.json").read_text(encoding="utf-8")
    )
    assert {item["role_track"] for item in boundary_cases} == {
        "system",
        "combat",
        "writing",
        "narrative",
        "general",
    }
    assert any(item["expected_outcome"] == "needs_input_or_narrow" for item in boundary_cases)
    assert sum(item["expected_outcome"] == "truth_failure" for item in boundary_cases) == 4
    assert all(item["forbidden_claim"] for item in boundary_cases)


@pytest.mark.parametrize("fixtures_root", [COMMUNITY_FIXTURES, GAME_DESIGNER_FIXTURES])
def test_t28_synthetic_extension_scorecards_exercise_blind_summary_contract(
    fixtures_root: Path,
) -> None:
    fixture_cases = load_cases(fixtures_root)
    mapping: dict[str, object] = {
        "schema_version": "1.0",
        "fact_snapshot_sha256": fixture_cases[0].fact_snapshot_sha256,
        "cases": {},
    }
    blind_scores: list[BlindCaseEvaluation] = []
    for case in fixture_cases:
        acceptance = json.loads(
            case.jd_path.with_name("acceptance.json").read_text(encoding="utf-8")
        )
        new_candidate = CandidateEval(
            truth_passed=True,
            scores=QualityScores(**acceptance["quality"]),
        )
        legacy_candidate = CandidateEval(
            truth_passed=True,
            scores=QualityScores(
                jd_coverage=7.2,
                selection_quality=7.0,
                evidence_depth=7.1,
                hr_scan=7.2,
                language_naturalness=7.4,
            ),
        )
        new_is_a = int(hashlib.sha256(case.case_id.encode()).hexdigest(), 16) % 2 == 0
        assignment = (
            {"candidate_a": "new", "candidate_b": "legacy"}
            if new_is_a
            else {"candidate_a": "legacy", "candidate_b": "new"}
        )
        candidates = {"new": new_candidate, "legacy": legacy_candidate}
        blind_scores.append(
            BlindCaseEvaluation(
                case_id=case.case_id,
                fact_snapshot_sha256=case.fact_snapshot_sha256,
                candidate_a=candidates[assignment["candidate_a"]],
                candidate_b=candidates[assignment["candidate_b"]],
                evaluator_notes=[
                    "Synthetic contract fixture: candidate labels contain no role-strategy or lane identity."
                ],
            )
        )
        mapping["cases"][case.case_id] = {
            "assignment": assignment,
            "deterministic_findings": {"legacy": [], "new": []},
        }

    unblinded = unblind_evaluations(blind_scores, mapping)
    summary = summarize_suite(unblinded, fixture_cases)
    assert summary.passed is True
    assert summary.truth_gate_passed is True
    assert summary.quality_gate_passed is True
    assert len(summary.improved_dimensions) == 5


def test_eval_suite_rejects_unknown_role_category(tmp_path: Path) -> None:
    fixture = tmp_path / "fixtures"
    shutil.copytree(GAME_FIXTURES, fixture)
    (fixture / "suite.json").write_text(
        '{"categories":["unsupported_role"]}\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unsupported eval categories"):
        load_cases(fixture)


def test_markdown_structure_requires_only_four_level_two_sections() -> None:
    valid = "\n".join(f"## {name}\n\n### 示例" for name in ("教育经历", "实习/工作经历", "实践经历", "自我能力"))
    assert validate_markdown_structure(valid) == []
    invalid = "# 候选人\n\n" + valid.replace("## 教育经历", "# 教育经历")
    findings = validate_markdown_structure(invalid)
    assert "FIXED_SECTION_LEVEL_MISMATCH" in findings
    assert any(item.startswith("EXTRA_TOP_LEVEL_STRUCTURE") for item in findings)


def test_suite_gate_requires_truth_scores_and_three_improved_dimensions() -> None:
    fixtures = load_cases(FIXTURES)
    passing = [
        CaseEvaluation(
            case_id=item.case_id,
            fact_snapshot_sha256=item.fact_snapshot_sha256,
            legacy=candidate(7.5),
            new=candidate(8.5),
        )
        for item in fixtures
    ]
    summary = summarize_suite(passing, fixtures)
    assert summary.passed is True
    assert len(summary.improved_dimensions) == 4

    failing = list(passing)
    failing[0] = CaseEvaluation(
        case_id=fixtures[0].case_id,
        fact_snapshot_sha256=fixtures[0].fact_snapshot_sha256,
        legacy=candidate(8.5),
        new=candidate(7.5, truth=False),
    )
    failed_summary = summarize_suite(failing, fixtures)
    assert failed_summary.passed is False
    assert failed_summary.truth_gate_passed is False
    assert failed_summary.quality_gate_passed is False


def test_blind_package_hides_lane_names_and_unblinds_scores(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    for case in load_cases(FIXTURES):
        case_dir = generated / case.case_id
        case_dir.mkdir(parents=True)
        for lane, wording in (("legacy", "旧稿"), ("new", "新稿")):
            (case_dir / f"{lane}.md").write_text(
                f"## 教育经历\n\n{wording}\n", encoding="utf-8"
            )
            trace = {
                "case_id": case.case_id,
                "lane": lane,
                "bullets": [
                    {
                        "bullet_text": "围绕企业知识问答场景访谈 12 位一线员工。",
                        "experience_id": "EXP-WORK-001",
                        "fact_ids": ["FACT-WORK-001-01"],
                    }
                ],
            }
            (case_dir / f"{lane}-trace.json").write_text(
                json.dumps(trace, ensure_ascii=False), encoding="utf-8"
            )
    blind_root = tmp_path / "blind"
    mapping = build_blind_package(generated, FIXTURES, blind_root)
    for case in load_cases(FIXTURES):
        names = {item.name for item in (blind_root / case.case_id).iterdir()}
        assert "legacy.md" not in names
        assert "new.md" not in names
        assert "candidate_a.md" in names
        assert "candidate_b.md" in names
        assert "quality-rubric.md" in names
        for trace_name in ("candidate_a-trace.json", "candidate_b-trace.json"):
            trace_payload = json.loads((blind_root / case.case_id / trace_name).read_text(encoding="utf-8"))
            assert "lane" not in trace_payload
            assert "case_id" not in trace_payload

    blind_scores = [
        BlindCaseEvaluation(
            case_id=case.case_id,
            fact_snapshot_sha256=case.fact_snapshot_sha256,
            candidate_a=candidate(8.2),
            candidate_b=candidate(8.1),
        )
        for case in load_cases(FIXTURES)
    ]
    unblinded = unblind_evaluations(blind_scores, mapping)
    assert len(unblinded) == 5
    assert all(item.evaluation_mode == "blind" for item in unblinded)

    scores_root = tmp_path / "scores"
    for score in blind_scores:
        score_path = scores_root / score.case_id / "blind-score.json"
        score_path.parent.mkdir(parents=True)
        score_path.write_text(score.model_dump_json(indent=2), encoding="utf-8")
    loaded = load_blind_scores(scores_root, load_cases(FIXTURES))
    assert [item.case_id for item in loaded] == [item.case_id for item in blind_scores]


def test_tracked_fixed_eval_evidence_remains_valid_historical_baseline() -> None:
    fixture_cases = load_cases(FIXTURES)
    tracked_plan = json.loads((EVIDENCE / "eval-plan.json").read_text(encoding="utf-8"))
    current_plan = deterministic_plan(
        FIXTURES,
        REPO_ROOT / ".agents" / "prompts" / "campus-resume-optimizer.md",
        REPO_ROOT / ".agents" / "skills" / "custom-resume" / "SKILL.md",
    )
    assert tracked_plan["fact_snapshot_sha256"] == current_plan["fact_snapshot_sha256"]
    assert tracked_plan["new_skill_sha256"] != current_plan["new_skill_sha256"]

    fact_text = (FIXTURES / "fact-snapshot.md").read_text(encoding="utf-8")
    blind_scores: list[BlindCaseEvaluation] = []
    for case in fixture_cases:
        case_root = EVIDENCE / "cases" / case.case_id
        generation = json.loads((case_root / "generation.json").read_text(encoding="utf-8"))
        assert generation["revision_round"] in {3, 4}
        generation_prompt_hashes = {
            Path(path).name: digest
            for path, digest in generation["custom_resume_prompt_sha256"].items()
        }
        assert generation_prompt_hashes == tracked_plan["new_prompt_sha256"]
        for lane in ("legacy", "new"):
            content = (case_root / f"{lane}.md").read_text(encoding="utf-8")
            assert_sanitized(content, f"{case.case_id}/{lane}.md")
            trace = TraceArtifact.model_validate_json(
                (case_root / f"{lane}-trace.json").read_text(encoding="utf-8")
            )
            assert validate_trace(trace, fact_text) == []
            if lane == "new":
                assert validate_markdown_structure(content) == []
        blind_scores.append(
            BlindCaseEvaluation.model_validate_json(
                (case_root / "blind-score.json").read_text(encoding="utf-8")
            )
        )

    mapping = json.loads((EVIDENCE / "blind-mapping.json").read_text(encoding="utf-8"))
    expected_results = [
        item.model_dump(mode="json", exclude_none=True)
        for item in unblind_evaluations(blind_scores, mapping)
    ]
    tracked_results = json.loads((EVIDENCE / "suite-results.json").read_text(encoding="utf-8"))
    assert tracked_results == expected_results
    evaluations = [CaseEvaluation.model_validate(item) for item in tracked_results]
    summary = summarize_suite(evaluations, fixture_cases)
    assert summary.passed is True
    assert json.loads((EVIDENCE / "suite-summary.json").read_text(encoding="utf-8")) == summary.model_dump(mode="json", exclude_none=True)


def test_tracked_game_extension_evidence_remains_valid_historical_baseline() -> None:
    fixture_cases = load_cases(GAME_FIXTURES)
    tracked_plan = json.loads(
        (GAME_EVIDENCE / "eval-plan.json").read_text(encoding="utf-8")
    )
    current_plan = deterministic_plan(
        GAME_FIXTURES,
        REPO_ROOT / ".agents" / "prompts" / "campus-resume-optimizer.md",
        REPO_ROOT / ".agents" / "skills" / "custom-resume" / "SKILL.md",
    )
    assert tracked_plan["fact_snapshot_sha256"] == current_plan["fact_snapshot_sha256"]
    assert tracked_plan["new_skill_sha256"] != current_plan["new_skill_sha256"]
    fact_text = (GAME_FIXTURES / "fact-snapshot.md").read_text(encoding="utf-8")
    case = fixture_cases[0]
    case_root = GAME_EVIDENCE / "cases" / case.case_id
    for lane in ("legacy", "new"):
        trace = TraceArtifact.model_validate_json(
            (case_root / f"{lane}-trace.json").read_text(encoding="utf-8")
        )
        assert validate_trace(trace, fact_text) == []
        content = (case_root / f"{lane}.md").read_text(encoding="utf-8")
        assert_sanitized(content, f"{case.case_id}/{lane}.md")
        assert validate_markdown_structure(content) == []
    blind_scores = load_blind_scores(GAME_EVIDENCE / "cases", fixture_cases)
    mapping = json.loads(
        (GAME_EVIDENCE / "blind-mapping.json").read_text(encoding="utf-8")
    )
    expected = [
        item.model_dump(mode="json", exclude_none=True)
        for item in unblind_evaluations(blind_scores, mapping)
    ]
    tracked = json.loads(
        (GAME_EVIDENCE / "suite-results.json").read_text(encoding="utf-8")
    )
    assert tracked == expected
    summary = summarize_suite(
        [CaseEvaluation.model_validate(item) for item in tracked], fixture_cases
    )
    assert summary.passed is True
    assert json.loads(
        (GAME_EVIDENCE / "suite-summary.json").read_text(encoding="utf-8")
    ) == summary.model_dump(mode="json", exclude_none=True)
