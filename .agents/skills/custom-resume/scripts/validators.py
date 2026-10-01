from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Sequence

from fact_library import ExperienceRecord, FactRecord
from models import (
    AuditFinding,
    CandidateSuggestion,
    DeterministicValidationArtifact,
    DraftArtifact,
    ExperienceSelectionArtifact,
    ExperienceTier,
    FusionAction,
    FusionArtifact,
    FusionDecision,
    JDAnalysisArtifact,
    Severity,
    StoryPlanArtifact,
    self_ability_headings_for_role,
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
REQUIRED_RUN_FILES_V11 = {
    "reference-research.json",
    "experience-selection.json",
    "selection-audit-pre.json",
}
REQUIRED_RUN_FILES_V12 = {"capability-transfer-map.json"}
REQUIRED_RUN_FILES_V13 = {"hr-review.json"}
REQUIRED_RUN_FILES_V15 = {
    "story-plan.json",
    "selection-user-approval.json",
    "quality-gate.json",
    "agent-receipts.json",
}
CATEGORY_SECTION = {
    "EDU": "教育经历",
    "WORK": "实习/工作经历",
    "PROJECT": "实践经历",
    "SKILL": "自我能力",
}
PROHIBITED_RESUME_PHRASES = (
    "不负责",
    "不承担",
    "未参与",
    "仅负责",
    "只负责",
    "不涉及",
    "不声称",
    "事实快照",
    "本稿",
    "未提供证据",
)


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


def _artifact_sha256(value: object) -> str:
    payload = (
        value.model_dump(mode="json")
        if hasattr(value, "model_dump")
        else value
    )
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def selection_decision_sha256(value: ExperienceSelectionArtifact) -> str:
    payload = value.model_dump(mode="json")
    payload["selection_approved"] = False
    payload["approved_at"] = None
    return _artifact_sha256(payload)


def _normalize_similarity_text(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.casefold())


def _source_similarity(left: str, right: str) -> float:
    normalized_left = _normalize_similarity_text(left)
    normalized_right = _normalize_similarity_text(right)
    if not normalized_left or not normalized_right:
        return 0
    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


def validate_fusion_content(
    fusion: FusionArtifact,
    jd_analysis: JDAnalysisArtifact,
    experiences: dict[str, ExperienceRecord],
    facts: dict[str, FactRecord],
    candidate_suggestions: Sequence[CandidateSuggestion] = (),
    experience_selection: ExperienceSelectionArtifact | None = None,
    story_plan: StoryPlanArtifact | None = None,
) -> DeterministicValidationArtifact:
    findings: list[AuditFinding] = []
    known_requirements = {item.requirement_id for item in jd_analysis.requirements}
    all_text: list[str] = []
    experience_bullets = 0
    total_bullets = 0
    seen_experiences: set[str] = set()
    selected_by_id = {
        item.experience_id: item
        for item in experience_selection.candidates
        if item.selected
    } if experience_selection else {}
    actual_experience_bullets: Counter[str] = Counter()
    experience_chinese_characters: Counter[str] = Counter()
    auxiliary_bullets = 0
    education_fact_ids_seen: set[str] = set()
    story_by_id = {
        item.experience_id: item for item in story_plan.experiences
    } if story_plan else {}
    experience_failure_codes: dict[str, list[str]] = {
        experience_id: [] for experience_id in selected_by_id
    }
    experience_intent_ids: dict[str, list[str]] = {
        experience_id: [] for experience_id in selected_by_id
    }
    experience_covered_elements: dict[str, set[str]] = {
        experience_id: set() for experience_id in selected_by_id
    }
    experience_max_similarity: dict[str, float] = {
        experience_id: 0 for experience_id in selected_by_id
    }
    if fusion.schema_version in {"1.1", "1.2", "1.3", "1.4", "1.5"} and (
        experience_selection is None or not experience_selection.selection_approved
    ):
        findings.append(
            _finding(
                "UNAPPROVED_EXPERIENCE_SELECTION",
                Severity.HARD,
                "experience-selection.json",
                "schema 1.1+ fusion requires an approved experience selection",
            )
        )

    if fusion.schema_version == "1.5":
        if story_plan is None:
            findings.append(
                _finding(
                    "MISSING_STORY_PLAN",
                    Severity.HARD,
                    "story-plan.json",
                    "schema 1.5 fusion requires a story plan",
                )
            )
        elif story_plan.experience_selection_sha256 != selection_decision_sha256(
            experience_selection
        ):
            findings.append(
                _finding(
                    "STALE_STORY_PLAN",
                    Severity.HARD,
                    "story-plan.json.experience_selection_sha256",
                    "story plan is not bound to the approved selection",
                )
            )
        elif set(story_by_id) != set(selected_by_id):
            findings.append(
                _finding(
                    "STORY_PLAN_SELECTION_MISMATCH",
                    Severity.HARD,
                    "story-plan.json.experiences",
                    "story plan must cover every selected experience exactly once",
                )
            )

    if fusion.schema_version in {"1.2", "1.3", "1.4", "1.5"}:
        ability_headings = [entry.heading for entry in fusion.sections[3].entries]
        expected_ability_headings = list(
            self_ability_headings_for_role(
                jd_analysis.role_family, fusion.schema_version
            )
            if fusion.schema_version in {"1.4", "1.5"}
            else ("专业硬技能", "综合软技能", "游戏经历", "语言能力")
        )
        if ability_headings != expected_ability_headings:
            findings.append(
                _finding(
                    "ABILITY_CATEGORY_STRUCTURE_CHANGED",
                    Severity.HARD,
                    "sections.3.entries",
                    "self-ability entries do not match the role-family structure",
                )
            )

    for section_index, section in enumerate(fusion.sections):
        all_text.append(section.name.value)
        for entry_index, entry in enumerate(section.entries):
            entry_path = f"sections.{section_index}.entries.{entry_index}"
            all_text.append(entry.heading)
            experience = experiences.get(entry.experience_id)
            story = story_by_id.get(entry.experience_id)
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
                if experience.category in {"WORK", "PROJECT"} and entry.experience_id not in selected_by_id:
                    findings.append(
                        _finding(
                            "UNAPPROVED_EXPERIENCE_USED",
                            Severity.HARD,
                            f"{entry_path}.experience_id",
                            f"experience was not approved for drafting: {entry.experience_id}",
                        )
                    )
                if (
                    entry.experience_id in seen_experiences
                    and experience.category != "SKILL"
                ):
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
                if fusion.schema_version == "1.5" and experience.category in {
                    "WORK",
                    "PROJECT",
                }:
                    actual_intents = [
                        bullet.intent_id
                        for bullet in entry.bullets
                        if bullet.intent_id is not None
                    ]
                    experience_intent_ids[entry.experience_id] = actual_intents
                    if story:
                        planned_intents = {
                            item.intent_id for item in story.bullet_intents
                        }
                        if (
                            len(actual_intents) != len(entry.bullets)
                            or len(actual_intents) != len(set(actual_intents))
                            or set(actual_intents) != planned_intents
                        ):
                            code = "STORY_INTENT_COVERAGE_INVALID"
                            experience_failure_codes[entry.experience_id].append(code)
                            findings.append(
                                _finding(
                                    code,
                                    Severity.HARD,
                                    f"{entry_path}.bullets",
                                    "fusion bullets must cover each approved story intent exactly once",
                                )
                            )
            for bullet_index, bullet in enumerate(entry.bullets):
                bullet_path = f"{entry_path}.bullets.{bullet_index}"
                total_bullets += 1
                if section.name.value in {"实习/工作经历", "实践经历"}:
                    experience_bullets += 1
                    actual_experience_bullets[entry.experience_id] += 1
                    experience_chinese_characters[entry.experience_id] += len(
                        re.findall(r"[\u4e00-\u9fff]", bullet.text)
                    )
                    selected_candidate = selected_by_id.get(entry.experience_id)
                    if selected_candidate and selected_candidate.tier is ExperienceTier.AUXILIARY:
                        auxiliary_bullets += 1
                all_text.append(bullet.text)
                if fusion.schema_version == "1.5" and experience and experience.category in {
                    "WORK",
                    "PROJECT",
                }:
                    if not re.sub(r"[\s\u200b\u200c\u200d\ufeff]+", "", bullet.text):
                        code = "EMPTY_EXPERIENCE_BULLET"
                        experience_failure_codes[entry.experience_id].append(code)
                        findings.append(
                            _finding(
                                code,
                                Severity.HARD,
                                f"{bullet_path}.text",
                                "WORK/PROJECT bullet contains no visible content",
                            )
                        )
                    prohibited = [
                        phrase
                        for phrase in PROHIBITED_RESUME_PHRASES
                        if phrase in bullet.text
                    ]
                    if prohibited:
                        code = "NEGATIVE_BOUNDARY_OR_AUDIT_LANGUAGE"
                        experience_failure_codes[entry.experience_id].append(code)
                        findings.append(
                            _finding(
                                code,
                                Severity.HARD,
                                f"{bullet_path}.text",
                                f"clean resume content contains prohibited phrases: {prohibited}",
                            )
                        )
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
                if fusion.schema_version == "1.5" and experience and experience.category in {
                    "WORK",
                    "PROJECT",
                }:
                    if story and bullet.intent_id:
                        planned_intent = next(
                            (
                                item
                                for item in story.bullet_intents
                                if item.intent_id == bullet.intent_id
                            ),
                            None,
                        )
                        if planned_intent and not set(
                            planned_intent.required_fact_ids
                        ).issubset(bullet.fact_ids):
                            code = "STORY_INTENT_FACTS_MISSING"
                            experience_failure_codes[entry.experience_id].append(code)
                            findings.append(
                                _finding(
                                    code,
                                    Severity.HARD,
                                    f"{bullet_path}.fact_ids",
                                    "bullet does not cite every fact required by its story intent",
                                )
                            )
                    if story:
                        categories = {
                            "context": set(story.evidence.context_fact_ids),
                            "action": set(story.evidence.action_fact_ids),
                            "method": set(story.evidence.method_fact_ids),
                            "challenge": set(story.evidence.challenge_fact_ids),
                            "result": set(story.evidence.result_fact_ids),
                        }
                        for category, category_fact_ids in categories.items():
                            if category_fact_ids.intersection(bullet.fact_ids):
                                experience_covered_elements[entry.experience_id].add(
                                    category
                                )
                    similarities = [
                        _source_similarity(bullet.text, fact.value) for fact in cited
                    ]
                    maximum_similarity = max(similarities, default=0)
                    experience_max_similarity[entry.experience_id] = max(
                        experience_max_similarity[entry.experience_id],
                        maximum_similarity,
                    )
                    exact_copy = any(
                        _normalize_similarity_text(bullet.text)
                        == _normalize_similarity_text(fact.value)
                        for fact in cited
                    )
                    covered_count = sum(
                        bool(set(bullet.fact_ids).intersection(category_fact_ids))
                        for category_fact_ids in (
                            set(story.evidence.context_fact_ids) if story else set(),
                            set(story.evidence.action_fact_ids) if story else set(),
                            set(story.evidence.method_fact_ids) if story else set(),
                            set(story.evidence.challenge_fact_ids) if story else set(),
                            set(story.evidence.result_fact_ids) if story else set(),
                        )
                    )
                    if exact_copy:
                        code = "RAW_FACT_VERBATIM_COPY"
                        experience_failure_codes[entry.experience_id].append(code)
                        findings.append(
                            _finding(
                                code,
                                Severity.HARD,
                                f"{bullet_path}.text",
                                "WORK/PROJECT bullet copies one confirmed fact verbatim",
                            )
                        )
                    elif (
                        maximum_similarity >= 0.90
                        and len(bullet.fact_ids) == 1
                        and covered_count <= 1
                    ):
                        code = "RAW_FACT_NEAR_COPY"
                        experience_failure_codes[entry.experience_id].append(code)
                        findings.append(
                            _finding(
                                code,
                                Severity.HARD,
                                f"{bullet_path}.text",
                                f"single-fact bullet similarity {maximum_similarity:.3f} lacks synthesis",
                            )
                        )
                    elif maximum_similarity >= 0.80:
                        findings.append(
                            _finding(
                                "RAW_FACT_HIGH_SIMILARITY",
                                Severity.WARNING,
                                f"{bullet_path}.text",
                                f"bullet similarity {maximum_similarity:.3f} requires audit attention",
                            )
                        )
                if fusion.schema_version in {"1.2", "1.3", "1.4", "1.5"} and section.name.value == "教育经历":
                    if len(bullet.fact_ids) != 1:
                        findings.append(
                            _finding(
                                "EDUCATION_BASELINE_CHANGED",
                                Severity.HARD,
                                f"{bullet_path}.fact_ids",
                                "education baseline bullet must cite exactly one education fact",
                            )
                        )
                    elif bullet.fact_ids[0] in facts:
                        education_fact = facts[bullet.fact_ids[0]]
                        if education_fact.experience_id.startswith("EXP-EDU-"):
                            if education_fact.fact_id in education_fact_ids_seen:
                                findings.append(
                                    _finding(
                                        "EDUCATION_BASELINE_DUPLICATED",
                                        Severity.HARD,
                                        f"{bullet_path}.fact_ids",
                                        "education baseline fact may appear exactly once",
                                    )
                                )
                            education_fact_ids_seen.add(education_fact.fact_id)
                            if bullet.text != education_fact.value:
                                findings.append(
                                    _finding(
                                        "EDUCATION_BASELINE_CHANGED",
                                        Severity.HARD,
                                        f"{bullet_path}.text",
                                        "education text must exactly copy the confirmed baseline fact",
                                    )
                                )
                        else:
                            findings.append(
                                _finding(
                                    "EDUCATION_BASELINE_CHANGED",
                                    Severity.HARD,
                                    f"{bullet_path}.fact_ids",
                                    "education baseline bullet must cite an education fact",
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

    if fusion.schema_version == "1.5":
        for experience_id in selected_by_id:
            if experience_id not in story_by_id:
                experience_failure_codes[experience_id].append(
                    "STORY_PLAN_EXPERIENCE_MISSING"
                )
                continue
            missing_elements = {"context", "action", "result"}.difference(
                experience_covered_elements[experience_id]
            )
            if missing_elements:
                code = "STORY_ELEMENTS_INCOMPLETE"
                experience_failure_codes[experience_id].append(code)
                findings.append(
                    _finding(
                        code,
                        Severity.HARD,
                        f"story-plan.json.experiences.{experience_id}",
                        "experience bullets do not cover required story elements: "
                        f"{sorted(missing_elements)}",
                    )
                )

    if experience_selection and experience_selection.selection_approved:
        missing_selected = set(selected_by_id).difference(actual_experience_bullets)
        if missing_selected:
            for experience_id in missing_selected:
                experience_failure_codes.setdefault(experience_id, []).append(
                    "SELECTED_EXPERIENCE_OMITTED"
                )
            findings.append(
                _finding(
                    "SELECTED_EXPERIENCE_OMITTED",
                    Severity.HARD,
                    "sections",
                    f"approved experiences are absent from fusion: {sorted(missing_selected)}",
                )
            )
        over_budget = {
            experience_id: count
            for experience_id, count in actual_experience_bullets.items()
            if experience_id in selected_by_id
            and fusion.schema_version != "1.5"
            and count > selected_by_id[experience_id].proposed_bullet_count
        }
        if over_budget:
            findings.append(
                _finding(
                    "EXPERIENCE_BULLET_ALLOCATION_EXCEEDED",
                    Severity.HARD,
                    "sections",
                    f"actual bullets exceed approved budgets: {over_budget}",
                )
            )
        if (
            fusion.schema_version != "1.5"
            and experience_bullets
            and auxiliary_bullets / experience_bullets > 0.25
        ):
            findings.append(
                _finding(
                    "AUXILIARY_BULLET_QUOTA_EXCEEDED",
                    Severity.HARD,
                    "sections",
                    f"auxiliary bullets {auxiliary_bullets}/{experience_bullets} exceed 25%",
                )
            )

    if fusion.schema_version in {"1.2", "1.3", "1.4", "1.5"}:
        expected_education_fact_ids = {
            fact.fact_id
            for fact in facts.values()
            if fact.experience_id.startswith("EXP-EDU-")
        }
        missing_education = expected_education_fact_ids.difference(
            education_fact_ids_seen
        )
        extra_education = education_fact_ids_seen.difference(
            expected_education_fact_ids
        )
        if missing_education or extra_education:
            findings.append(
                _finding(
                    "EDUCATION_BASELINE_INCOMPLETE",
                    Severity.HARD,
                    "sections.0",
                    f"education baseline mismatch; missing={sorted(missing_education)}, extra={sorted(extra_education)}",
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
    completion_diagnostic_triggered = (
        fusion.schema_version == "1.5" and chinese_chars < 1200
    )
    if completion_diagnostic_triggered:
        findings.append(
            _finding(
                "CONTENT_COMPLETENESS_DIAGNOSTIC",
                Severity.WARNING,
                "sections",
                "draft is below the content-fullness character threshold: "
                f"Chinese characters {chinese_chars}/1200. "
                "Auditor and HR must compare semantic elements inside every selected fact, "
                "not merely fact-ID citation coverage.",
            )
        )
        underdeveloped_core = {
            experience_id: {
                "bullets": actual_experience_bullets.get(experience_id, 0),
                "chinese_characters": experience_chinese_characters.get(
                    experience_id, 0
                ),
            }
            for experience_id, candidate in selected_by_id.items()
            if candidate.tier is ExperienceTier.CORE
            and (
                experience_chinese_characters.get(experience_id, 0) < 180
            )
        }
        if underdeveloped_core:
            findings.append(
                _finding(
                    "CORE_EXPERIENCE_UNDERDEVELOPED",
                    Severity.WARNING,
                    "sections",
                    "core experiences require element-level completeness review: "
                    f"{underdeveloped_core}",
                )
            )
    if chinese_chars > 1500:
        findings.append(
            _finding(
                "CONTENT_DENSITY_BUDGET",
                Severity.WARNING,
                "sections",
                f"Chinese character count {chinese_chars} exceeds 1500",
            )
        )
    hard_failure = any(item.severity is Severity.HARD for item in findings)
    per_experience_results = []
    if fusion.schema_version == "1.5":
        per_experience_results = [
            {
                "experience_id": experience_id,
                "bullet_count": actual_experience_bullets.get(experience_id, 0),
                "intent_ids": experience_intent_ids.get(experience_id, []),
                "covered_elements": sorted(
                    experience_covered_elements.get(experience_id, set())
                ),
                "max_source_similarity": experience_max_similarity.get(
                    experience_id, 0
                ),
                "failure_codes": list(
                    dict.fromkeys(experience_failure_codes.get(experience_id, []))
                ),
                "passed": not bool(experience_failure_codes.get(experience_id)),
            }
            for experience_id in selected_by_id
        ]
    return DeterministicValidationArtifact(
        schema_version=fusion.schema_version,
        run_id=fusion.run_id,
        created_at=fusion.created_at,
        source_digests=fusion.source_digests,
        candidate_sha256=(
            _artifact_sha256(fusion) if fusion.schema_version == "1.5" else None
        ),
        story_plan_sha256=(
            _artifact_sha256(story_plan)
            if fusion.schema_version == "1.5" and story_plan is not None
            else "0" * 64
            if fusion.schema_version == "1.5"
            else None
        ),
        passed=not hard_failure,
        findings=findings,
        hard_failures=[
            item.error_code for item in findings if item.severity is Severity.HARD
        ],
        warnings=[
            item.error_code for item in findings if item.severity is Severity.WARNING
        ],
        per_experience_results=per_experience_results,
        metrics={
            "chinese_character_count": chinese_chars,
            "experience_bullet_count": experience_bullets,
            "total_bullet_count": total_bullets,
        },
    )


def validate_draft_content(
    draft: DraftArtifact,
    jd_analysis: JDAnalysisArtifact,
    experiences: dict[str, ExperienceRecord],
    facts: dict[str, FactRecord],
    *,
    experience_selection: ExperienceSelectionArtifact,
    story_plan: StoryPlanArtifact,
) -> DeterministicValidationArtifact:
    """Apply the final deterministic content contract to one independent draft."""
    sections_payload = [section.model_dump(mode="python") for section in draft.sections]
    decisions: list[FusionDecision] = []
    bullet_index = 0
    for section in sections_payload:
        for entry in section["entries"]:
            for bullet in entry["bullets"]:
                bullet_index += 1
                source_bullet_id = bullet["bullet_id"]
                output_bullet_id = f"FUSION-{bullet_index:03d}"
                bullet["bullet_id"] = output_bullet_id
                decisions.append(
                    FusionDecision(
                        decision_id=f"DEC-{bullet_index:03d}",
                        action=(
                            FusionAction.SELECT_WRITER
                            if draft.agent.value == "writer"
                            else FusionAction.SELECT_ASU
                        ),
                        source_bullet_ids=[source_bullet_id],
                        output_bullet_id=output_bullet_id,
                        output_text=bullet["text"],
                        fact_ids=bullet["fact_ids"],
                        requirement_ids=bullet["requirement_ids"],
                        intent_id=bullet.get("intent_id"),
                        rationale="deterministic pre-fusion validation adapter",
                    )
                )
    synthetic_fusion = FusionArtifact(
        schema_version=draft.schema_version,
        run_id=draft.run_id,
        created_at=draft.created_at,
        source_digests=draft.source_digests,
        sections=sections_payload,
        decisions=decisions,
    )
    return validate_fusion_content(
        synthetic_fusion,
        jd_analysis,
        experiences,
        facts,
        experience_selection=experience_selection,
        story_plan=story_plan,
    )


def validate_run_artifact_completeness(run_dir: Path) -> list[AuditFinding]:
    existing = {
        item.relative_to(run_dir).as_posix()
        for item in run_dir.rglob("*")
        if item.is_file()
    }
    required = set(REQUIRED_RUN_FILES)
    run_path = run_dir / "run.json"
    if run_path.is_file():
        try:
            import json

            schema_version = json.loads(run_path.read_text(encoding="utf-8")).get(
                "schema_version"
            )
            if schema_version in {"1.1", "1.2", "1.3", "1.4", "1.5"}:
                required.update(REQUIRED_RUN_FILES_V11)
            if schema_version in {"1.2", "1.3", "1.4", "1.5"}:
                required.update(REQUIRED_RUN_FILES_V12)
            if schema_version in {"1.3", "1.4", "1.5"}:
                audit_path = run_dir / "audit.json"
                if audit_path.is_file():
                    audit_disposition = json.loads(
                        audit_path.read_text(encoding="utf-8")
                    ).get("disposition")
                    if audit_disposition == "passed":
                        required.update(REQUIRED_RUN_FILES_V13)
            if schema_version == "1.5":
                required.update(REQUIRED_RUN_FILES_V15)
        except (OSError, json.JSONDecodeError):
            pass
    return [
        _finding(
            "MISSING_RUN_ARTIFACT",
            Severity.HARD,
            filename,
            f"required run artifact is missing: {filename}",
            artifact="run.json",
        )
        for filename in sorted(required.difference(existing))
    ]


def validate_legacy_rendered_resume_text(
    text: str,
    facts: Sequence[FactRecord] = (),
) -> list[AuditFinding]:
    """Quarantine a rendered legacy draft before Schema 1.5 import.

    Rendered Markdown has no experience/intent/fact bindings, so it can be used as
    a regression input but cannot itself become an approvable Schema 1.5 artifact.
    The additional checks preserve concrete failure evidence from historical drafts.
    """
    findings = [
        _finding(
            "MISSING_SCHEMA15_PROVENANCE",
            Severity.HARD,
            "content-master.md",
            "rendered text has no experience_id, intent_id, and fact_ids bindings",
        )
    ]
    bullet_lines = [
        match.group(1).strip()
        for line in text.splitlines()
        if (match := re.match(r"^\s*[-*•]\s*(.*)$", line))
    ]
    if any(not bullet for bullet in bullet_lines):
        findings.append(
            _finding(
                "EMPTY_EXPERIENCE_BULLET",
                Severity.HARD,
                "content-master.md",
                "rendered text contains an empty bullet",
            )
        )
    for phrase in PROHIBITED_RESUME_PHRASES:
        if phrase in text:
            findings.append(
                _finding(
                    "NEGATIVE_BOUNDARY_OR_AUDIT_LANGUAGE",
                    Severity.HARD,
                    "content-master.md",
                    f"rendered text contains forbidden phrase: {phrase}",
                )
            )
    for bullet_index, bullet in enumerate(bullet_lines):
        for fact in facts:
            similarity = _source_similarity(bullet, fact.value)
            if similarity == 1:
                findings.append(
                    _finding(
                        "RAW_FACT_VERBATIM_COPY",
                        Severity.HARD,
                        f"content-master.md.bullets[{bullet_index}]",
                        f"rendered bullet copies {fact.fact_id}",
                    )
                )
                break
            if similarity >= 0.90:
                findings.append(
                    _finding(
                        "RAW_FACT_NEAR_COPY",
                        Severity.HARD,
                        f"content-master.md.bullets[{bullet_index}]",
                        f"rendered bullet is {similarity:.2f} similar to {fact.fact_id}",
                    )
                )
                break
    return findings
