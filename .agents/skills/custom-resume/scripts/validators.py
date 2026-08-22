from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Sequence

from fact_library import ExperienceRecord, FactRecord
from models import (
    AuditFinding,
    CandidateSuggestion,
    DeterministicValidationArtifact,
    FusionArtifact,
    JDAnalysisArtifact,
    Severity,
)


ARABIC_NUMBER_RE = re.compile(
    r"(?<![A-Za-z])\d+(?:\.\d+)?(?:\s*(?:%|％|万|千|百|个|位|名|人|份|篇|条|场|款|所|天|周|月|年|次|轮|字|元|分|项|家|类|套|张|本|件|小时|分钟|fps))?",
    re.IGNORECASE,
)
CHINESE_NUMBER_RE = re.compile(
    r"([零〇一二两三四五六七八九十百千万]+)\s*(%|％|万|千|百|个|位|名|人|份|篇|条|场|款|所|天|周|月|年|次|轮|字|元|分|项|家|类|套|张|本|件|小时|分钟)"
)
CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}
REQUIRED_RUN_FILES = {
    "input-packet.json",
    "jd-analysis.json",
    "evidence-map.json",
    "fact-diff.json",
    "draft-writer.json",
    "draft-asu.json",
    "fusion.json",
    "validation.json",
    "audit.json",
    "content-master.md",
    "one-page-density.md",
    "content-review.md",
    "run.json",
}
CATEGORY_SECTION = {
    "EDU": "教育经历",
    "WORK": "实习/工作经历",
    "PROJECT": "实践经历",
    "SKILL": "自我能力",
}


def chinese_number_to_int(value: str) -> int:
    if all(char in CHINESE_DIGITS for char in value):
        return int("".join(str(CHINESE_DIGITS[char]) for char in value))
    total = 0
    section = 0
    number = 0
    for char in value:
        if char in CHINESE_DIGITS:
            number = CHINESE_DIGITS[char]
        elif char in CHINESE_UNITS:
            unit = CHINESE_UNITS[char]
            if unit == 10000:
                section = (section + number) * unit
                total += section
                section = 0
            else:
                section += (number or 1) * unit
            number = 0
    return total + section + number


def normalize_unit(unit: str | None) -> str:
    if not unit:
        return ""
    return unit.replace("％", "%").lower()


def extract_numeric_claims(text: str) -> Counter[tuple[str, str]]:
    claims: Counter[tuple[str, str]] = Counter()
    for match in ARABIC_NUMBER_RE.finditer(text):
        raw = match.group(0).replace(" ", "")
        value_match = re.match(r"\d+(?:\.\d+)?", raw)
        if not value_match:
            continue
        numeric = str(float(value_match.group(0))).rstrip("0").rstrip(".")
        unit = normalize_unit(raw[value_match.end() :])
        claims[(numeric, unit)] += 1
    for match in CHINESE_NUMBER_RE.finditer(text):
        claims[(str(chinese_number_to_int(match.group(1))), normalize_unit(match.group(2)))] += 1
    return claims


def _finding(
    code: str,
    severity: Severity,
    field_path: str,
    message: str,
    artifact: str = "fusion.json",
) -> AuditFinding:
    return AuditFinding(
        error_code=code,
        severity=severity,
        artifact=artifact,
        field_path=field_path,
        message=message,
    )


def _contains_immutable_token(heading: str, token: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"\s+", "", value).replace("—", "–").replace("-", "–").replace("~", "–")

    return normalize(token) in normalize(heading)


def validate_fusion_content(
    fusion: FusionArtifact,
    jd_analysis: JDAnalysisArtifact,
    experiences: dict[str, ExperienceRecord],
    facts: dict[str, FactRecord],
    candidate_suggestions: Sequence[CandidateSuggestion] = (),
) -> DeterministicValidationArtifact:
    findings: list[AuditFinding] = []
    known_requirements = {item.requirement_id for item in jd_analysis.requirements}
    all_text: list[str] = []
    experience_bullets = 0
    total_bullets = 0
    seen_experiences: set[str] = set()

    for section_index, section in enumerate(fusion.sections):
        all_text.append(section.name.value)
        for entry_index, entry in enumerate(section.entries):
            entry_path = f"sections.{section_index}.entries.{entry_index}"
            all_text.append(entry.heading)
            experience = experiences.get(entry.experience_id)
            if not experience:
                findings.append(
                    _finding(
                        "UNKNOWN_EXPERIENCE_ID",
                        Severity.HARD,
                        f"{entry_path}.experience_id",
                        f"unknown experience_id {entry.experience_id}",
                    )
                )
            else:
                if entry.experience_id in seen_experiences:
                    findings.append(
                        _finding(
                            "DUPLICATE_EXPERIENCE_ENTRY",
                            Severity.HARD,
                            f"{entry_path}.experience_id",
                            f"experience appears more than once: {entry.experience_id}",
                        )
                    )
                seen_experiences.add(entry.experience_id)
                expected_section = CATEGORY_SECTION.get(experience.category)
                if expected_section and section.name.value != expected_section:
                    findings.append(
                        _finding(
                            "EXPERIENCE_SECTION_MISMATCH",
                            Severity.HARD,
                            f"{entry_path}.experience_id",
                            f"{entry.experience_id} belongs in {expected_section}",
                        )
                    )
                missing_tokens = [
                    token
                    for token in experience.immutable_tokens
                    if not _contains_immutable_token(entry.heading, token)
                ]
                if missing_tokens:
                    findings.append(
                        _finding(
                            "IMMUTABLE_FIELD_CHANGED",
                            Severity.HARD,
                            f"{entry_path}.heading",
                            f"heading changed immutable values: {missing_tokens}",
                        )
                    )
            for bullet_index, bullet in enumerate(entry.bullets):
                bullet_path = f"{entry_path}.bullets.{bullet_index}"
                total_bullets += 1
                if section.name.value in {"实习/工作经历", "实践经历"}:
                    experience_bullets += 1
                all_text.append(bullet.text)
                cited: list[FactRecord] = []
                for fact_id in bullet.fact_ids:
                    fact = facts.get(fact_id)
                    if not fact:
                        findings.append(
                            _finding(
                                "UNKNOWN_FACT_ID",
                                Severity.HARD,
                                f"{bullet_path}.fact_ids",
                                f"unknown fact_id {fact_id}",
                            )
                        )
                        continue
                    cited.append(fact)
                    if fact.experience_id != entry.experience_id:
                        findings.append(
                            _finding(
                                "CROSS_EXPERIENCE_FACT",
                                Severity.HARD,
                                f"{bullet_path}.fact_ids",
                                f"{fact_id} belongs to {fact.experience_id}",
                            )
                        )
                    if fact.provenance not in {"observed", "accepted_estimate"}:
                        findings.append(
                            _finding(
                                "UNCONFIRMED_FACT_PROVENANCE",
                                Severity.HARD,
                                f"{bullet_path}.fact_ids",
                                f"{fact_id} has unsupported provenance {fact.provenance}",
                            )
                        )
                unknown_requirements = set(bullet.requirement_ids).difference(
                    known_requirements
                )
                if unknown_requirements:
                    findings.append(
                        _finding(
                            "UNKNOWN_REQUIREMENT_ID",
                            Severity.HARD,
                            f"{bullet_path}.requirement_ids",
                            f"unknown requirements: {sorted(unknown_requirements)}",
                        )
                    )
                source_numbers: Counter[tuple[str, str]] = Counter()
                for fact in cited:
                    source_numbers.update(extract_numeric_claims(fact.value))
                output_numbers = extract_numeric_claims(bullet.text)
                unsupported_numbers = output_numbers - source_numbers
                if unsupported_numbers:
                    findings.append(
                        _finding(
                            "UNSUPPORTED_NUMERIC_CLAIM",
                            Severity.HARD,
                            f"{bullet_path}.text",
                            f"numeric claims lack cited support: {list(unsupported_numbers.elements())}",
                        )
                    )

    clean_text = "\n".join(all_text)
    for suggestion_index, suggestion in enumerate(candidate_suggestions):
        if suggestion.suggested_text in clean_text:
            findings.append(
                _finding(
                    "UNCONFIRMED_CANDIDATE_LEAK",
                    Severity.HARD,
                    f"candidate_suggestions.{suggestion_index}",
                    "candidate suggestion leaked into clean content",
                )
            )

    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", clean_text))
    if not 1200 <= chinese_chars <= 1500:
        findings.append(
            _finding(
                "CONTENT_DENSITY_BUDGET",
                Severity.WARNING,
                "sections",
                f"Chinese character count {chinese_chars} is outside 1200–1500",
            )
        )
    if not 10 <= experience_bullets <= 14:
        findings.append(
            _finding(
                "EXPERIENCE_BULLET_BUDGET",
                Severity.WARNING,
                "sections",
                f"experience bullet count {experience_bullets} is outside 10–14",
            )
        )
    hard_failure = any(item.severity is Severity.HARD for item in findings)
    return DeterministicValidationArtifact(
        run_id=fusion.run_id,
        created_at=fusion.created_at,
        source_digests=fusion.source_digests,
        passed=not hard_failure,
        findings=findings,
        metrics={
            "chinese_character_count": chinese_chars,
            "experience_bullet_count": experience_bullets,
            "total_bullet_count": total_bullets,
        },
    )


def validate_run_artifact_completeness(run_dir: Path) -> list[AuditFinding]:
    existing = {
        item.relative_to(run_dir).as_posix()
        for item in run_dir.rglob("*")
        if item.is_file()
    }
    return [
        _finding(
            "MISSING_RUN_ARTIFACT",
            Severity.HARD,
            filename,
            f"required run artifact is missing: {filename}",
            artifact="run.json",
        )
        for filename in sorted(REQUIRED_RUN_FILES.difference(existing))
    ]
