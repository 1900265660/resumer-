from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "custom-resume" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from fact_library import ExperienceRecord, FactRecord, parse_fact_records  # noqa: E402
from models import (  # noqa: E402
    CandidateSuggestion,
    FusionAction,
    FusionArtifact,
    FusionDecision,
    JDAnalysisArtifact,
    JobRequirement,
    RequirementPriority,
    ResumeBullet,
    ResumeEntry,
    ResumeSection,
    ResumeSectionName,
    Severity,
    SourceDigests,
)
from validators import (  # noqa: E402
    REQUIRED_RUN_FILES,
    extract_numeric_claims,
    validate_fusion_content,
    validate_run_artifact_completeness,
)


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
RUN_ID = "cr_20260822T120000_abc123"
FACT_ID = "FACT-PROJECT-001-01"
EXP_ID = "EXP-PROJECT-001"


def digests() -> SourceDigests:
    return SourceDigests(
        jd_sha256="a" * 64,
        fact_snapshot_sha256="b" * 64,
        preferences_sha256="c" * 64,
    )


def jd_analysis() -> JDAnalysisArtifact:
    return JDAnalysisArtifact(
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        job_goal="提升 AI 产品问答质量",
        business_problems=["问答准确性不足"],
        requirements=[
            JobRequirement(
                requirement_id="REQ-001",
                title="AI 产品评测",
                description="建立评测集并迭代效果",
                priority=RequirementPriority.MUST,
                rationale="岗位核心职责",
            )
        ],
    )


def fact_record(
    fact_id: str = FACT_ID,
    experience_id: str = EXP_ID,
    value: str = "完成 3 轮评测，准确率提升至 88%。",
) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        experience_id=experience_id,
        value=value,
        provenance="observed",
        line_number=1,
        metadata={"fact_id": fact_id, "provenance": "observed"},
    )


def experience_record() -> ExperienceRecord:
    fact = fact_record()
    return ExperienceRecord(
        experience_id=EXP_ID,
        category="PROJECT",
        heading="测试公司｜产品负责人｜2025/04–2025/06",
        immutable_tokens=("测试公司", "产品负责人", "2025/04–2025/06"),
        facts=(fact,),
    )


def fusion(
    text: str = "完成三轮评测，准确率提升至 88%。",
    fact_id: str = FACT_ID,
    heading: str = "测试公司｜产品负责人｜2025/04-2025/06",
) -> FusionArtifact:
    bullet = ResumeBullet(
        bullet_id="FUSION-001",
        text=text,
        fact_ids=[fact_id],
        requirement_ids=["REQ-001"],
        primary_value="AI 产品评测",
    )
    return FusionArtifact(
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        sections=[
            ResumeSection(name=ResumeSectionName.EDUCATION),
            ResumeSection(name=ResumeSectionName.WORK),
            ResumeSection(
                name=ResumeSectionName.PRACTICE,
                entries=[
                    ResumeEntry(
                        experience_id=EXP_ID,
                        heading=heading,
                        bullets=[bullet],
                    )
                ],
            ),
            ResumeSection(name=ResumeSectionName.ABILITIES),
        ],
        decisions=[
            FusionDecision(
                decision_id="DEC-001",
                action=FusionAction.REWRITE_FROM_BOTH,
                source_bullet_ids=["WRITER-001", "ASU-001"],
                output_bullet_id="FUSION-001",
                output_text=text,
                fact_ids=[fact_id],
                requirement_ids=["REQ-001"],
                rationale="保留事实支持且更易扫读的表达",
            )
        ],
    )


def finding_codes(report: object) -> set[str]:
    return {item.error_code for item in report.findings}


def test_real_fact_library_parses_all_migrated_ids() -> None:
    source = REPO_ROOT / "profile" / "01-candidate-profile.md"
    if not source.exists():
        return
    experiences, facts = parse_fact_records(source.read_text(encoding="utf-8"))
    assert len(experiences) == 26
    assert len(facts) == 74


def test_chinese_and_arabic_numeric_claims_are_normalized() -> None:
    assert extract_numeric_claims("完成三轮评测，准确率 88%。") == extract_numeric_claims(
        "完成 3 轮评测，准确率 88%。"
    )


def test_valid_content_passes_hard_gates_with_soft_budget_warnings() -> None:
    experience = experience_record()
    fact = fact_record()
    report = validate_fusion_content(
        fusion(),
        jd_analysis(),
        {EXP_ID: experience},
        {FACT_ID: fact},
    )
    assert report.passed is True
    assert finding_codes(report) == {
        "CONTENT_DENSITY_BUDGET",
        "EXPERIENCE_BULLET_BUDGET",
    }
    assert all(item.severity is Severity.WARNING for item in report.findings)


def test_unknown_cross_experience_and_changed_heading_are_hard_failures() -> None:
    unknown = validate_fusion_content(
        fusion(fact_id="FACT-PROJECT-001-99"),
        jd_analysis(),
        {EXP_ID: experience_record()},
        {FACT_ID: fact_record()},
    )
    assert "UNKNOWN_FACT_ID" in finding_codes(unknown)

    other_fact = fact_record(
        fact_id="FACT-PROJECT-002-01", experience_id="EXP-PROJECT-002"
    )
    cross = validate_fusion_content(
        fusion(fact_id=other_fact.fact_id),
        jd_analysis(),
        {EXP_ID: experience_record()},
        {other_fact.fact_id: other_fact},
    )
    assert "CROSS_EXPERIENCE_FACT" in finding_codes(cross)

    changed = validate_fusion_content(
        fusion(heading="另一家公司｜产品负责人｜2025/04–2025/06"),
        jd_analysis(),
        {EXP_ID: experience_record()},
        {FACT_ID: fact_record()},
    )
    assert "IMMUTABLE_FIELD_CHANGED" in finding_codes(changed)

    wrong_section_fusion = fusion().model_copy(deep=True)
    practice_entry = wrong_section_fusion.sections[2].entries.pop()
    wrong_section_fusion.sections[1].entries.append(practice_entry)
    wrong_section = validate_fusion_content(
        wrong_section_fusion,
        jd_analysis(),
        {EXP_ID: experience_record()},
        {FACT_ID: fact_record()},
    )
    assert "EXPERIENCE_SECTION_MISMATCH" in finding_codes(wrong_section)


def test_new_number_and_candidate_leak_are_hard_failures() -> None:
    numeric = validate_fusion_content(
        fusion(text="完成四轮评测，准确率提升至 92%。"),
        jd_analysis(),
        {EXP_ID: experience_record()},
        {FACT_ID: fact_record()},
    )
    assert "UNSUPPORTED_NUMERIC_CLAIM" in finding_codes(numeric)

    suggestion = CandidateSuggestion(
        suggestion_id="CAND-001",
        category="process",
        question="是否做过增长实验？",
        suggested_text="设计增长实验",
    )
    leaked = validate_fusion_content(
        fusion(text="设计增长实验并完成评测。"),
        jd_analysis(),
        {EXP_ID: experience_record()},
        {FACT_ID: fact_record(value="完成评测。")},
        [suggestion],
    )
    assert "UNCONFIRMED_CANDIDATE_LEAK" in finding_codes(leaked)


def test_run_artifact_completeness_reports_exact_missing_files(tmp_path: Path) -> None:
    for filename in REQUIRED_RUN_FILES - {"audit.json", "content-review.md"}:
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    findings = validate_run_artifact_completeness(tmp_path)
    assert {item.field_path for item in findings} == {
        "audit.json",
        "content-review.md",
    }
    assert all(item.error_code == "MISSING_RUN_ARTIFACT" for item in findings)
