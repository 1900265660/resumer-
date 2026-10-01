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
    ExperienceCandidateScore,
    ExperienceSelectionArtifact,
    ExperienceTier,
    FusionAction,
    FusionArtifact,
    FusionDecision,
    JDAnalysisArtifact,
    JobRequirement,
    JobTaskEvidenceLevel,
    RequirementPriority,
    PortfolioValue,
    ResumeBullet,
    ResumeEntry,
    ResumeSection,
    ResumeSectionName,
    RoleFamily,
    RoleTrack,
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
        schema_version="1.1",
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


def approved_selection() -> ExperienceSelectionArtifact:
    return ExperienceSelectionArtifact(
        schema_version="1.1",
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        candidates=[
            ExperienceCandidateScore(
                experience_id=EXP_ID,
                fact_ids=[FACT_ID],
                responsibility_score=25,
                process_delivery_score=18,
                result_score=12,
                domain_score=6,
                incremental_coverage_score=12,
                evidence_strength_score=8,
                job_task_evidence=JobTaskEvidenceLevel.DIRECT,
                total_score=81,
                tier=ExperienceTier.CORE,
                matched_requirement_ids=["REQ-001"],
                incremental_requirement_ids=["REQ-001"],
                selected=True,
                proposed_bullet_count=1,
                rationale="直接支持 AI 产品评测。",
            )
        ],
        selection_approved=True,
        approved_at=NOW,
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
        schema_version="1.1",
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
    # The private fact library may grow independently of code changes. Guard the
    # migrated baseline without making every confirmed addition break CI.
    assert len(facts) >= 108


def test_v12_education_is_exact_and_ability_categories_are_fixed() -> None:
    education = fact_record(
        "FACT-EDU-001-01",
        "EXP-EDU-001",
        "测试大学，汉语言文学，本科，2022/09–2026/06。",
    )
    skill_facts = [
        fact_record(f"FACT-SKILL-001-{index:02d}", "EXP-SKILL-001", value)
        for index, value in enumerate(
            ("熟悉 RAG。", "具备跨方沟通能力。", "熟悉游戏体验分析。", "英语可用于工作沟通。"),
            start=1,
        )
    ]
    all_facts = {education.fact_id: education, FACT_ID: fact_record()}
    all_facts.update({item.fact_id: item for item in skill_facts})
    experiences = {
        "EXP-EDU-001": ExperienceRecord(
            experience_id="EXP-EDU-001",
            category="EDU",
            heading="测试大学｜汉语言文学｜2022/09–2026/06",
            immutable_tokens=("测试大学", "汉语言文学", "2022/09–2026/06"),
            facts=(education,),
        ),
        EXP_ID: experience_record(),
        "EXP-SKILL-001": ExperienceRecord(
            experience_id="EXP-SKILL-001",
            category="SKILL",
            heading="自我能力",
            immutable_tokens=(),
            facts=tuple(skill_facts),
        ),
    }

    def build(
        education_text: str,
        *,
        schema_version: str = "1.2",
        ability_headings: tuple[str, str, str, str] = (
            "专业硬技能",
            "综合软技能",
            "游戏经历",
            "语言能力",
        ),
    ) -> FusionArtifact:
        specifications = [
            ("EXP-EDU-001", "测试大学｜汉语言文学｜2022/09–2026/06", education.fact_id, education_text, []),
            (EXP_ID, "测试公司｜产品负责人｜2025/04–2025/06", FACT_ID, fact_record().value, ["REQ-001"]),
            *[
                ("EXP-SKILL-001", heading, fact.fact_id, fact.value, [])
                for heading, fact in zip(
                    ability_headings,
                    skill_facts,
                    strict=True,
                )
            ],
        ]
        bullets = []
        decisions = []
        for index, (_, _, fact_id, text, requirement_ids) in enumerate(specifications, start=1):
            bullet = ResumeBullet(
                bullet_id=f"FUSION-{index:03d}",
                text=text,
                fact_ids=[fact_id],
                requirement_ids=requirement_ids,
                primary_value="固定基线",
            )
            bullets.append(bullet)
            decisions.append(
                FusionDecision(
                    decision_id=f"DEC-{index:03d}",
                    action=FusionAction.SELECT_WRITER,
                    source_bullet_ids=[f"WRITER-{index:03d}"],
                    output_bullet_id=bullet.bullet_id,
                    output_text=text,
                    fact_ids=[fact_id],
                    requirement_ids=requirement_ids,
                    rationale="保持事实与固定结构",
                )
            )
        return FusionArtifact(
            schema_version=schema_version,
            run_id=RUN_ID,
            created_at=NOW,
            source_digests=digests(),
            sections=[
                ResumeSection(
                    name=ResumeSectionName.EDUCATION,
                    entries=[
                        ResumeEntry(
                            experience_id=specifications[0][0],
                            heading=specifications[0][1],
                            bullets=[bullets[0]],
                        )
                    ],
                ),
                ResumeSection(name=ResumeSectionName.WORK),
                ResumeSection(
                    name=ResumeSectionName.PRACTICE,
                    entries=[
                        ResumeEntry(
                            experience_id=EXP_ID,
                            heading=specifications[1][1],
                            bullets=[bullets[1]],
                        )
                    ],
                ),
                ResumeSection(
                    name=ResumeSectionName.ABILITIES,
                    entries=[
                        ResumeEntry(
                            experience_id="EXP-SKILL-001",
                            heading=specifications[index][1],
                            bullets=[bullets[index]],
                        )
                        for index in range(2, 6)
                    ],
                ),
            ],
            decisions=decisions,
        )

    selected = ExperienceCandidateScore.model_validate(
        {
            **approved_selection().candidates[0].model_dump(mode="python"),
            "portfolio_value_score": PortfolioValue(
                section_balance=2,
                capability_diversity=4,
                narrative_uniqueness=4,
                non_redundancy=4,
                total=14,
            ).model_dump(mode="python"),
            "similarity_group": "个人AI产品Demo",
            "is_personal_development": True,
        }
    )
    v12_selection = ExperienceSelectionArtifact(
        schema_version="1.2",
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        capability_transfer_map_sha256="d" * 64,
        candidates=[selected],
        selection_approved=True,
        approved_at=NOW,
    )
    valid = validate_fusion_content(
        build(education.value),
        jd_analysis(),
        experiences,
        all_facts,
        experience_selection=v12_selection,
    )
    assert valid.passed is True
    changed = validate_fusion_content(
        build("测试大学，汉语言文学，本科。"),
        jd_analysis(),
        experiences,
        all_facts,
        experience_selection=v12_selection,
    )
    assert "EDUCATION_BASELINE_CHANGED" in finding_codes(changed)

    community_jd = JDAnalysisArtifact.model_validate(
        {
            **jd_analysis().model_dump(mode="python"),
            "schema_version": "1.4",
            "role_family": RoleFamily.COMMUNITY_OPERATIONS,
            "role_track": RoleTrack.CONTENT,
        }
    )
    v14_selection = v12_selection.model_copy(update={"schema_version": "1.4"})
    community_valid = validate_fusion_content(
        build(
            education.value,
            schema_version="1.4",
            ability_headings=("专业硬技能", "综合软技能", "行业/平台经历", "语言能力"),
        ),
        community_jd,
        experiences,
        all_facts,
        experience_selection=v14_selection,
    )
    assert community_valid.passed is True
    community_wrong_heading = validate_fusion_content(
        build(education.value, schema_version="1.4"),
        community_jd,
        experiences,
        all_facts,
        experience_selection=v14_selection,
    )
    assert "ABILITY_CATEGORY_STRUCTURE_CHANGED" in finding_codes(community_wrong_heading)


def test_chinese_and_arabic_numeric_claims_are_normalized() -> None:
    assert extract_numeric_claims("完成三轮评测，准确率 88%。") == extract_numeric_claims(
        "完成 3 轮评测，准确率 88%。"
    )


def test_valid_short_content_passes_without_padding_warnings() -> None:
    experience = experience_record()
    fact = fact_record()
    report = validate_fusion_content(
        fusion(),
        jd_analysis(),
        {EXP_ID: experience},
        {FACT_ID: fact},
        experience_selection=approved_selection(),
    )
    assert report.passed is True
    assert finding_codes(report) == set()


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
