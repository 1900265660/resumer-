from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "custom-resume" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import custom_resume_cli as cli  # noqa: E402
from fact_library import ExperienceRecord, FactRecord  # noqa: E402
from models import (  # noqa: E402
    AgentInvocationReceipt,
    AgentReceiptBundleArtifact,
    AgentRole,
    AgentStage,
    AuditArtifact,
    AuditDisposition,
    BulletIntent,
    CapabilityCategory,
    CapabilityCategoryScan,
    CapabilityStatus,
    CapabilityTransferMapArtifact,
    ContentState,
    CoverageLevel,
    DraftAgent,
    DraftArtifact,
    DraftExperienceQualityReview,
    DraftLaneQualityReview,
    DraftQualityAuditArtifact,
    DraftQualityDimension,
    DraftResultStatus,
    EvidenceMapArtifact,
    EvidenceMapping,
    ExecutionMode,
    ExperienceCandidateScore,
    ExperienceSelectionArtifact,
    ExperienceTier,
    FactDiffArtifact,
    FusionAction,
    FusionArtifact,
    FusionDecision,
    HrDecisionDimension,
    HrExperienceReview,
    HrRecommendation,
    HrReviewArtifact,
    HrReviewDisposition,
    InterviewImpact,
    JDAnalysisArtifact,
    JobRequirement,
    JobTaskEvidenceLevel,
    NormalizedInputPacket,
    OwnershipGuard,
    PortfolioValue,
    PageFillOverride,
    QualityAudit,
    QualityDimension,
    ReferenceResearchArtifact,
    ReferenceResearchMode,
    ResumeBullet,
    ResumeEntry,
    ResumeSection,
    ResumeSectionName,
    RoleFamily,
    RunManifestArtifact,
    RunStatus,
    RunStatusRecord,
    SelectionApprovalArtifact,
    SelectionAuditArtifact,
    SelectionAuditPhase,
    SelectionAuditRow,
    SelectionAuditVerdict,
    SourceDigests,
    SourceType,
    StoryEvidence,
    StoryExperience,
    StoryPlanArtifact,
    TruthAudit,
    UserApprovalRecord,
)
from orchestrator import render_resume_markdown  # noqa: E402
from storage import (  # noqa: E402
    RunIntegrityError,
    approve_run,
    begin_run,
    canonical_json_sha256,
    revoke_run,
    sha256_bytes,
    validate_pointer_consistency,
)
from validators import (  # noqa: E402
    selection_decision_sha256,
    validate_draft_content,
    validate_fusion_content,
    validate_legacy_rendered_resume_text,
)


NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
RUN_ID = "cr_20260903T120000_v15tst"
PROJECT_ID = "EXP-PROJECT-001"
PROJECT_FACTS = (
    "FACT-PROJECT-001-01",
    "FACT-PROJECT-001-02",
    "FACT-PROJECT-001-03",
)


def _digests() -> SourceDigests:
    return SourceDigests(
        jd_sha256="a" * 64,
        fact_snapshot_sha256="b" * 64,
        preferences_sha256="c" * 64,
        reference_cards_sha256="d" * 64,
    )


def _base() -> dict[str, object]:
    return {
        "schema_version": "1.5",
        "run_id": RUN_ID,
        "created_at": NOW,
        "source_digests": _digests(),
    }


def _facts_and_experiences() -> tuple[dict[str, ExperienceRecord], dict[str, FactRecord]]:
    values = {
        PROJECT_FACTS[0]: "目标是验证问答原型在真实需求中的可用性。",
        PROJECT_FACTS[1]: "完成用户调研和问答原型。",
        PROJECT_FACTS[2]: "完成 3 轮评测，准确率提升至 88%。",
        "FACT-EDU-001-01": "测试大学，产品专业，本科，2022/09–2026/06。",
        "FACT-SKILL-001-01": "熟悉 RAG 与 Prompt 工程。",
        "FACT-SKILL-001-02": "具备跨团队协同能力。",
        "FACT-SKILL-001-03": "有游戏产品分析经历。",
        "FACT-SKILL-001-04": "CET-6。",
    }
    facts: dict[str, FactRecord] = {}
    for index, (fact_id, value) in enumerate(values.items(), start=1):
        if fact_id.startswith("FACT-PROJECT"):
            experience_id = PROJECT_ID
        elif fact_id.startswith("FACT-EDU"):
            experience_id = "EXP-EDU-001"
        else:
            experience_id = "EXP-SKILL-001"
        facts[fact_id] = FactRecord(
            fact_id=fact_id,
            experience_id=experience_id,
            value=value,
            provenance="observed",
            line_number=index,
            metadata={"fact_id": fact_id, "provenance": "observed"},
        )
    experiences = {
        PROJECT_ID: ExperienceRecord(
            experience_id=PROJECT_ID,
            category="PROJECT",
            heading="测试 Agent｜产品负责人｜2025/04–2025/06",
            immutable_tokens=("测试 Agent", "产品负责人", "2025/04–2025/06"),
            facts=tuple(facts[fact_id] for fact_id in PROJECT_FACTS),
        ),
        "EXP-EDU-001": ExperienceRecord(
            experience_id="EXP-EDU-001",
            category="EDU",
            heading="测试大学，产品专业，本科，2022/09–2026/06。",
            immutable_tokens=("测试大学", "产品专业", "2022/09–2026/06"),
            facts=(facts["FACT-EDU-001-01"],),
        ),
        "EXP-SKILL-001": ExperienceRecord(
            experience_id="EXP-SKILL-001",
            category="SKILL",
            heading="自我能力",
            immutable_tokens=(),
            facts=tuple(
                facts[f"FACT-SKILL-001-{index:02d}"] for index in range(1, 5)
            ),
        ),
    }
    return experiences, facts


def _packet() -> NormalizedInputPacket:
    return NormalizedInputPacket(
        **_base(),
        application_dir="applications/测试_Schema15",
        source_type=SourceType.DIRECTORY,
        source_locator="applications/测试_Schema15/jd.md",
        role_family=RoleFamily.AI_PRODUCT_MANAGER,
        approved_requirement_ids=["REQ-001"],
        approved_fact_ids=list(PROJECT_FACTS),
        approved_experience_ids=[PROJECT_ID],
    )


def _jd() -> JDAnalysisArtifact:
    return JDAnalysisArtifact(
        **_base(),
        role_family=RoleFamily.AI_PRODUCT_MANAGER,
        job_goal="提升问答产品效果",
        business_problems=["需要把用户需求转化为可验证的产品结果"],
        requirements=[
            JobRequirement(
                requirement_id="REQ-001",
                title="产品验证",
                description="通过调研、原型和评测推动结果",
                priority="must",
                rationale="岗位核心任务",
            )
        ],
    )


def _capability_map() -> CapabilityTransferMapArtifact:
    return CapabilityTransferMapArtifact(
        **_base(),
        experience_ids=[PROJECT_ID],
        scans=[
            CapabilityCategoryScan(
                experience_id=PROJECT_ID,
                category=category,
                status=CapabilityStatus.NONE,
                rationale="本用例不依赖跨经历迁移。",
            )
            for category in CapabilityCategory
        ],
    )


def _selection(capability_sha256: str) -> ExperienceSelectionArtifact:
    return ExperienceSelectionArtifact(
        **_base(),
        capability_transfer_map_sha256=capability_sha256,
        candidates=[
            ExperienceCandidateScore(
                experience_id=PROJECT_ID,
                fact_ids=list(PROJECT_FACTS),
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
                proposed_bullet_count=2,
                rationale="一个强项目已经覆盖岗位核心证据，不添加弱经历凑数。",
                portfolio_value_score=PortfolioValue(
                    section_balance=4,
                    capability_diversity=5,
                    narrative_uniqueness=5,
                    non_redundancy=5,
                    total=19,
                ),
            )
        ],
        selection_approved=True,
        approved_at=NOW,
    )


def _story(selection: ExperienceSelectionArtifact) -> StoryPlanArtifact:
    return StoryPlanArtifact(
        **_base(),
        experience_selection_sha256=selection_decision_sha256(selection),
        experiences=[
            StoryExperience(
                experience_id=PROJECT_ID,
                story_thesis="把用户需求转化为原型，并用连续评测证明产品效果。",
                capability_ids=["CAP-PRODUCT-VALIDATION"],
                evidence=StoryEvidence(
                    context_fact_ids=[PROJECT_FACTS[0]],
                    action_fact_ids=[PROJECT_FACTS[1]],
                    method_fact_ids=[PROJECT_FACTS[2]],
                    result_fact_ids=[PROJECT_FACTS[2]],
                ),
                bullet_intents=[
                    BulletIntent(
                        intent_id="INT-001",
                        purpose="交代真实需求背景与原型落地动作",
                        required_fact_ids=[PROJECT_FACTS[0], PROJECT_FACTS[1]],
                    ),
                    BulletIntent(
                        intent_id="INT-002",
                        purpose="展示连续评测方法与量化结果",
                        required_fact_ids=[PROJECT_FACTS[2]],
                    ),
                ],
                ownership_guard=OwnershipGuard(
                    allowed_claims=["可主张独立完成调研、原型和评测"],
                    prohibited_claims=["不得主张商业化收入"],
                ),
            )
        ],
    )


def _sections(prefix: str) -> list[ResumeSection]:
    project_bullets = [
        ResumeBullet(
            bullet_id=f"{prefix}-001",
            text="围绕真实需求中的原型可用性目标，开展用户调研并将结论转化为问答原型，建立后续评测对象。",
            fact_ids=[PROJECT_FACTS[0], PROJECT_FACTS[1]],
            requirement_ids=["REQ-001"],
            intent_id="INT-001",
            primary_value="需求洞察与原型落地",
        ),
        ResumeBullet(
            bullet_id=f"{prefix}-002",
            text="基于调研结论迭代问答原型，并通过 3 轮连续评测校准效果，最终将准确率提升至 88%，形成调研、原型与验证闭环。",
            fact_ids=[PROJECT_FACTS[1], PROJECT_FACTS[2]],
            requirement_ids=["REQ-001"],
            intent_id="INT-002",
            primary_value="评测方法与量化结果",
        ),
    ]
    specifications = [
        (
            "EXP-EDU-001",
            "测试大学，产品专业，本科，2022/09–2026/06。",
            "FACT-EDU-001-01",
            "测试大学，产品专业，本科，2022/09–2026/06。",
        ),
        ("EXP-SKILL-001", "专业硬技能", "FACT-SKILL-001-01", "熟悉 RAG 与 Prompt 工程。"),
        ("EXP-SKILL-001", "综合软技能", "FACT-SKILL-001-04", "CET-6，可用于跨语言沟通。"),
        ("EXP-SKILL-001", "个人优势", "FACT-SKILL-001-02", "具备跨团队协同与主动推进能力。"),
    ]
    auxiliary_entries = [
        ResumeEntry(
            experience_id=experience_id,
            heading=heading,
            bullets=[
                ResumeBullet(
                    bullet_id=f"{prefix}-{index:03d}",
                    text=text,
                    fact_ids=[fact_id],
                    primary_value=heading,
                )
            ],
        )
        for index, (experience_id, heading, fact_id, text) in enumerate(
            specifications, start=3
        )
    ]
    return [
        ResumeSection(name=ResumeSectionName.EDUCATION, entries=[auxiliary_entries[0]]),
        ResumeSection(name=ResumeSectionName.WORK),
        ResumeSection(
            name=ResumeSectionName.PRACTICE,
            entries=[
                ResumeEntry(
                    experience_id=PROJECT_ID,
                    heading="测试 Agent｜产品负责人｜2025/04–2025/06",
                    bullets=project_bullets,
                )
            ],
        ),
        ResumeSection(name=ResumeSectionName.ABILITIES, entries=auxiliary_entries[1:]),
    ]


def _draft(agent: DraftAgent) -> DraftArtifact:
    prefix = "WRITER" if agent is DraftAgent.WRITER else "ASU"
    return DraftArtifact(
        **_base(),
        role_family=RoleFamily.AI_PRODUCT_MANAGER,
        agent=agent,
        sections=_sections(prefix),
    )


def _fusion() -> FusionArtifact:
    sections = _sections("FUSION")
    bullets = [
        bullet
        for section in sections
        for entry in section.entries
        for bullet in entry.bullets
    ]
    decisions = [
        FusionDecision(
            decision_id=f"DEC-{index:03d}",
            action=FusionAction.REWRITE_FROM_BOTH,
            source_bullet_ids=[f"WRITER-{index:03d}", f"ASU-{index:03d}"],
            output_bullet_id=bullet.bullet_id,
            output_text=bullet.text,
            fact_ids=bullet.fact_ids,
            requirement_ids=bullet.requirement_ids,
            intent_id=bullet.intent_id,
            rationale="在相同事实边界内选择更完整、凝练的故事表达。",
        )
        for index, bullet in enumerate(bullets, start=1)
    ]
    return FusionArtifact(**_base(), sections=sections, decisions=decisions)


def _draft_audit(writer: DraftArtifact, asu: DraftArtifact) -> DraftQualityAuditArtifact:
    dimension = DraftQualityDimension(score=8.8, evidence=["故事完整且表达凝练。"])
    experience = DraftExperienceQualityReview(
        experience_id=PROJECT_ID,
        bullet_count=2,
        score=8.8,
        developed_elements=["context_or_object", "personal_action", "method_or_decision", "credible_result"],
        result_status=DraftResultStatus.QUANTIFIED,
        result_rationale="引用连续评测和准确率结果。",
        evidence=["两条 bullet 分别覆盖背景行动和方法结果。"],
        passed=True,
    )
    return DraftQualityAuditArtifact(
        **_base(),
        revision_round=0,
        execution_mode=ExecutionMode.BLIND_DUAL,
        lane_reviews=[
            DraftLaneQualityReview(
                agent=agent,
                draft_sha256=canonical_json_sha256(draft.model_dump(mode="json")),
                experience_development=dimension,
                result_backing=dimension,
                information_density=dimension,
                scan_naturalness=dimension,
                experience_reviews=[experience],
                passed=True,
            )
            for agent, draft in ((DraftAgent.WRITER, writer), (DraftAgent.ASU_WRITER, asu))
        ],
        passed=True,
    )


def _audit(quality_gate) -> AuditArtifact:
    dimension = QualityDimension(score=8.8, evidence=["逐经历故事与岗位证据均达到门槛。"])
    return AuditArtifact(
        **_base(),
        deterministic_passed=True,
        deterministic_findings=quality_gate.findings,
        truth=TruthAudit(passed=True),
        quality=QualityAudit(
            jd_coverage=dimension,
            selection_quality=dimension,
            evidence_depth=dimension,
            hr_scan=dimension,
            language_naturalness=dimension,
            passed=True,
        ),
        disposition=AuditDisposition.PASSED,
    )


def _hr() -> HrReviewArtifact:
    dimension = HrDecisionDimension(
        score=9.2,
        evidence=["最终稿以完整产品验证故事支持岗位匹配。"],
        evidence_bullet_ids=["FUSION-002"],
    )
    return HrReviewArtifact(
        **_base(),
        revision_round=0,
        recommendation=HrRecommendation.STRONG_PUSH,
        overall_score=9.2,
        role_fit=dimension,
        narrative_completeness=dimension,
        evidence_specificity=dimension,
        decision_readiness=dimension,
        credibility=dimension,
        content_fullness=dimension,
        experience_reviews=[
            HrExperienceReview(
                experience_id=PROJECT_ID,
                ten_second_impression="调研、原型、评测和量化结果形成完整故事。",
                effective_requirement_ids=["REQ-001"],
                evidence_bullet_ids=["FUSION-001", "FUSION-002"],
                strengths=["能力证据具体且可追溯"],
                severity_score=0,
                interview_impact=InterviewImpact.NONE,
                recommended_bullet_count=2,
            )
        ],
        existing_fact_revision_sufficient=False,
        fact_questions_required=False,
        reselect_required=False,
        passed=True,
        disposition=HrReviewDisposition.PASSED,
    )


def test_v15_hr_requires_independent_content_fullness_dimension() -> None:
    payload = _hr().model_dump(mode="python")
    payload.pop("content_fullness")
    with pytest.raises(ValidationError, match="requires content_fullness"):
        HrReviewArtifact.model_validate(payload)

    weak_fullness = HrDecisionDimension(
        score=7.9,
        evidence=["字符达标但事实展开仍有重复。"],
        evidence_bullet_ids=["FUSION-002"],
    )
    payload = _hr().model_dump(mode="python")
    payload["content_fullness"] = weak_fullness.model_dump(mode="python")
    with pytest.raises(ValidationError, match="HR pass requires"):
        HrReviewArtifact.model_validate(payload)


def _artifacts() -> dict[str, object]:
    experiences, facts = _facts_and_experiences()
    capability_map = _capability_map()
    selection = _selection(
        canonical_json_sha256(capability_map.model_dump(mode="json"))
    )
    story = _story(selection)
    writer = _draft(DraftAgent.WRITER)
    asu = _draft(DraftAgent.ASU_WRITER)
    draft_audit = _draft_audit(writer, asu)
    fusion = _fusion()
    quality_gate = validate_fusion_content(
        fusion,
        _jd(),
        experiences,
        facts,
        experience_selection=selection,
        story_plan=story,
    )
    assert quality_gate.passed
    audit = _audit(quality_gate)
    hr = _hr()
    selection_approval = SelectionApprovalArtifact(
        **_base(),
        selection_approval_id="selection_approval_" + "e" * 32,
        experience_selection_sha256=selection_decision_sha256(selection),
        story_plan_sha256=canonical_json_sha256(story.model_dump(mode="json")),
        approved_at=NOW,
    )
    artifacts: dict[str, object] = {
        "input-packet.json": _packet(),
        "reference-research.json": ReferenceResearchArtifact(
            **_base(),
            mode=ReferenceResearchMode.DEGRADED,
            local_card_sha256="d" * 64,
            error="测试环境无外部参考。",
            degradation_approved_at=NOW,
            degradation_approval_reason="测试明确批准降级。",
        ),
        "jd-analysis.json": _jd(),
        "evidence-map.json": EvidenceMapArtifact(
            **_base(),
            mappings=[
                EvidenceMapping(
                    requirement_id="REQ-001",
                    coverage=CoverageLevel.COMPOSITE,
                    fact_ids=list(PROJECT_FACTS),
                    rationale="调研、原型与评测共同支持岗位要求。",
                )
            ],
        ),
        "fact-diff.json": FactDiffArtifact(
            **_base(), source_fact_sha256=_digests().fact_snapshot_sha256
        ),
        "capability-transfer-map.json": capability_map,
        "experience-selection.json": selection,
        "selection-audit-pre.json": SelectionAuditArtifact(
            **_base(),
            phase=SelectionAuditPhase.PRE_DRAFT,
            rows=[
                SelectionAuditRow(
                    experience_id=PROJECT_ID,
                    verdict=SelectionAuditVerdict.KEEP,
                    rationale="单段强经历完整覆盖核心岗位证据。",
                )
            ],
            passed=True,
        ),
        "selection-user-approval.json": selection_approval,
        "story-plan.json": story,
        "draft-writer.json": writer,
        "draft-asu.json": asu,
        "draft-quality-audit.json": draft_audit,
        "fusion.json": fusion,
        "validation.json": quality_gate,
        "quality-gate.json": quality_gate,
        "audit.json": audit,
        "hr-review.json": hr,
    }
    role_by_stage = {
        AgentStage.JD_ANALYSIS: AgentRole.COORDINATOR,
        AgentStage.CAPABILITY_TRANSFER: AgentRole.COORDINATOR,
        AgentStage.EXPERIENCE_SELECTION: AgentRole.COORDINATOR,
        AgentStage.SELECTION_AUDIT: AgentRole.AUDITOR,
        AgentStage.STORY_PLAN: AgentRole.WRITER,
        AgentStage.WRITER: AgentRole.WRITER,
        AgentStage.ASU_WRITER: AgentRole.ASU_WRITER,
        AgentStage.DRAFT_AUDIT: AgentRole.AUDITOR,
        AgentStage.FUSION: AgentRole.COORDINATOR,
        AgentStage.POST_FUSION_AUDIT: AgentRole.AUDITOR,
        AgentStage.HR_REVIEW: AgentRole.HR_REVIEWER,
    }
    output_by_stage = {
        AgentStage.JD_ANALYSIS: artifacts["jd-analysis.json"],
        AgentStage.CAPABILITY_TRANSFER: capability_map,
        AgentStage.EXPERIENCE_SELECTION: selection,
        AgentStage.SELECTION_AUDIT: artifacts["selection-audit-pre.json"],
        AgentStage.STORY_PLAN: story,
        AgentStage.WRITER: writer,
        AgentStage.ASU_WRITER: asu,
        AgentStage.DRAFT_AUDIT: draft_audit,
        AgentStage.FUSION: fusion,
        AgentStage.POST_FUSION_AUDIT: audit,
        AgentStage.HR_REVIEW: hr,
    }
    artifacts["agent-receipts.json"] = AgentReceiptBundleArtifact(
        **_base(),
        receipts=[
            AgentInvocationReceipt(
                stage=stage,
                role=role_by_stage[stage],
                invocation_id=f"invocation-{index}",
                model="codex-hosted-test-model",
                reasoning_effort="high",
                prompt_sha256="1" * 64,
                input_sha256="2" * 64,
                output_sha256=canonical_json_sha256(
                    output.model_dump(mode="json")
                ),
                created_at=NOW,
            )
            for index, (stage, output) in enumerate(output_by_stage.items(), start=1)
        ],
    )
    return artifacts


def _commit_v15(application: Path, *, drop_hr_receipt: bool = False) -> Path:
    artifacts = _artifacts()
    if drop_hr_receipt:
        bundle = artifacts["agent-receipts.json"]
        assert isinstance(bundle, AgentReceiptBundleArtifact)
        artifacts["agent-receipts.json"] = bundle.model_copy(
            update={
                "receipts": [
                    item
                    for item in bundle.receipts
                    if item.stage is not AgentStage.HR_REVIEW
                ]
            }
        )
    stage = begin_run(application, RUN_ID)
    for filename, artifact in artifacts.items():
        stage.write_model(filename, artifact)
    fusion = artifacts["fusion.json"]
    assert isinstance(fusion, FusionArtifact)
    content = render_resume_markdown(fusion)
    stage.write_text("content-master.md", content)
    stage.write_text("one-page-density.md", content)
    stage.write_text("content-review.md", "# 内容审核\n\n等待用户明确批准。\n")
    manifest = RunManifestArtifact(
        **_base(),
        state=ContentState.READY_FOR_USER_REVIEW,
        execution_mode=ExecutionMode.BLIND_DUAL,
        input_packet=_packet(),
        artifacts=stage.artifact_records(),
        producer="official_coordinator",
    )
    return stage.commit(manifest)


def test_v15_allows_one_strong_experience_without_a_bullet_count_quota() -> None:
    capability = _capability_map()
    selection = _selection(canonical_json_sha256(capability.model_dump(mode="json")))
    assert len([item for item in selection.candidates if item.selected]) == 1
    single_unit = selection.model_dump(mode="python")
    single_unit["candidates"][0]["proposed_bullet_count"] = 1
    reparsed = ExperienceSelectionArtifact.model_validate(single_unit)
    assert reparsed.candidates[0].proposed_bullet_count == 1


def test_v15_page_fill_override_allows_at_most_two_fact_backed_low_score_entries() -> None:
    capability = _capability_map()
    selection = _selection(canonical_json_sha256(capability.model_dump(mode="json")))
    payload = selection.model_dump(mode="python")
    low_score = payload["candidates"][0].copy()
    low_score.update(
        {
            "experience_id": "EXP-PROJECT-002",
            "responsibility_score": 15,
            "process_delivery_score": 12,
            "result_score": 8,
            "domain_score": 4,
            "incremental_coverage_score": 6,
            "evidence_strength_score": 5,
            "total_score": 50,
            "tier": ExperienceTier.EXCLUDED,
            "selected": True,
            "proposed_bullet_count": 2,
            "user_override_reason": "单页仍有留白，已扩展全部高分经历的独立事实。",
        }
    )
    payload["candidates"].append(low_score)
    with pytest.raises(ValidationError, match="page fill override"):
        ExperienceSelectionArtifact.model_validate(payload)

    payload["page_fill_override"] = PageFillOverride(
        experience_ids=["EXP-PROJECT-002"],
        reason="单页仍有留白，已扩展全部高分经历的独立事实。",
        expanded_selected_evidence_exhausted=True,
        approved_at=NOW,
    ).model_dump(mode="python")
    reparsed = ExperienceSelectionArtifact.model_validate(payload)
    assert reparsed.page_fill_override is not None
    assert reparsed.page_fill_override.experience_ids == ["EXP-PROJECT-002"]

    payload["candidates"][-1]["proposed_bullet_count"] = 1
    with pytest.raises(ValidationError, match="at least two complementary bullets"):
        ExperienceSelectionArtifact.model_validate(payload)


def test_v15_quality_gate_rejects_negative_boundary_and_raw_fact_copy() -> None:
    experiences, facts = _facts_and_experiences()
    capability = _capability_map()
    selection = _selection(canonical_json_sha256(capability.model_dump(mode="json")))
    story = _story(selection)
    base_fusion = _fusion()

    negative_payload = base_fusion.model_dump(mode="python")
    negative_payload["sections"][2]["entries"][0]["bullets"][0]["text"] = (
        "仅负责用户调研和问答原型。"
    )
    negative_payload["decisions"][1]["output_text"] = negative_payload["sections"][2]["entries"][0]["bullets"][0]["text"]
    negative = FusionArtifact.model_validate(negative_payload)
    negative_report = validate_fusion_content(
        negative,
        _jd(),
        experiences,
        facts,
        experience_selection=selection,
        story_plan=story,
    )
    assert "NEGATIVE_BOUNDARY_OR_AUDIT_LANGUAGE" in negative_report.hard_failures

    copied_payload = base_fusion.model_dump(mode="python")
    copied_payload["sections"][2]["entries"][0]["bullets"][1]["text"] = facts[PROJECT_FACTS[2]].value
    copied_payload["sections"][2]["entries"][0]["bullets"][1]["fact_ids"] = [PROJECT_FACTS[2]]
    copied_payload["decisions"][2]["output_text"] = facts[PROJECT_FACTS[2]].value
    copied_payload["decisions"][2]["fact_ids"] = [PROJECT_FACTS[2]]
    copied = FusionArtifact.model_validate(copied_payload)
    copied_report = validate_fusion_content(
        copied,
        _jd(),
        experiences,
        facts,
        experience_selection=selection,
        story_plan=story,
    )
    assert "RAW_FACT_VERBATIM_COPY" in copied_report.hard_failures


def test_v15_each_independent_draft_passes_deterministic_gate() -> None:
    experiences, facts = _facts_and_experiences()
    capability = _capability_map()
    selection = _selection(canonical_json_sha256(capability.model_dump(mode="json")))
    story = _story(selection)
    payload = _draft(DraftAgent.WRITER).model_dump(mode="python")
    payload["sections"][2]["entries"][0]["bullets"][0]["text"] = (
        "本稿仅负责用户调研。"
    )
    broken = DraftArtifact.model_validate(payload)
    report = validate_draft_content(
        broken,
        _jd(),
        experiences,
        facts,
        experience_selection=selection,
        story_plan=story,
    )
    assert report.passed is False
    assert "NEGATIVE_BOUNDARY_OR_AUDIT_LANGUAGE" in report.hard_failures


def test_v15_short_core_experience_emits_completion_warnings() -> None:
    experiences, facts = _facts_and_experiences()
    capability = _capability_map()
    selection = _selection(canonical_json_sha256(capability.model_dump(mode="json")))
    story = _story(selection)

    report = validate_fusion_content(
        _fusion(),
        _jd(),
        experiences,
        facts,
        experience_selection=selection,
        story_plan=story,
    )

    assert report.passed is True
    assert "CONTENT_COMPLETENESS_DIAGNOSTIC" in report.warnings
    assert "CORE_EXPERIENCE_UNDERDEVELOPED" in report.warnings


def test_official_record_preserves_validated_agent_json_for_hash_binding(
    tmp_path: Path,
) -> None:
    application = tmp_path / "application"
    official = application / "resume-content" / ".official" / RUN_ID
    official.mkdir(parents=True)
    packet = _packet().model_dump(mode="json")
    (official / "input-packet.json").write_text(
        json.dumps(packet, ensure_ascii=False), encoding="utf-8"
    )
    raw_artifact = {
        **_base(),
        "created_at": NOW.isoformat(),
        "source_digests": _digests().model_dump(mode="json"),
        "mode": "degraded",
        "local_card_sha256": "d" * 64,
        "error": "测试环境没有外部参考。",
    }
    artifact_path = tmp_path / "reference-research.json"
    artifact_path.write_text(
        json.dumps(raw_artifact, ensure_ascii=False), encoding="utf-8"
    )

    cli.command_record(
        SimpleNamespace(
            application_dir=application,
            run_id=RUN_ID,
            artifact_name="reference-research.json",
            artifact=artifact_path,
            receipt=None,
            prompt_file=None,
            input_file=None,
        )
    )

    stored = json.loads(
        (official / "reference-research.json").read_text(encoding="utf-8")
    )
    assert stored == raw_artifact
    assert canonical_json_sha256(stored) == canonical_json_sha256(raw_artifact)


def test_v15_official_run_uses_hash_bound_frozen_fact_snapshot(
    tmp_path: Path,
) -> None:
    official = tmp_path / "resume-content" / ".official" / RUN_ID
    official.mkdir(parents=True)
    snapshot = (
        "# 候选人事实库（已确认）\n\n"
        "## 项目经历\n\n"
        "### 测试项目｜负责人｜2026/01–至今 "
        "<!-- experience_id: EXP-PROJECT-999 -->\n\n"
        "- 完成测试交付。 "
        "<!-- fact_id: FACT-PROJECT-999-01; provenance: observed -->\n"
    ).encode("utf-8")
    (official / "fact-snapshot.md").write_bytes(snapshot)
    packet = _packet().model_copy(
        update={
            "source_digests": _digests().model_copy(
                update={"fact_snapshot_sha256": sha256_bytes(snapshot)}
            )
        }
    )

    experiences, facts = cli._load_frozen_fact_records(official, packet)

    assert "EXP-PROJECT-999" in experiences
    assert "FACT-PROJECT-999-01" in facts
    assert "fact-snapshot.md" in cli.COMMIT_ARTIFACTS

    (official / "fact-snapshot.md").write_bytes(snapshot + b"\n")
    with pytest.raises(cli.CliError, match="snapshot hash"):
        cli._load_frozen_fact_records(official, packet)


def test_v15_empty_or_newline_bullet_cannot_evade_structure_gate() -> None:
    experiences, facts = _facts_and_experiences()
    capability = _capability_map()
    selection = _selection(canonical_json_sha256(capability.model_dump(mode="json")))
    story = _story(selection)
    payload = _fusion().model_dump(mode="python")
    payload["sections"][2]["entries"][0]["bullets"][1]["text"] = "\n\u200b\t"
    payload["decisions"][2]["output_text"] = "\n\u200b\t"
    report = validate_fusion_content(
        FusionArtifact.model_validate(payload),
        _jd(),
        experiences,
        facts,
        experience_selection=selection,
        story_plan=story,
    )
    assert report.passed is False
    assert "EMPTY_EXPERIENCE_BULLET" in report.hard_failures


def test_v15_retry_loop_stops_after_three_generation_rounds(tmp_path: Path) -> None:
    official = tmp_path / "resume-content" / ".official" / RUN_ID
    official.mkdir(parents=True)
    (official / "control.json").write_text(
        json.dumps(
            {
                "schema_version": "1.5",
                "run_id": RUN_ID,
                "state": ContentState.AUDITING.value,
                "generation_round": 0,
                "rewrite_target": None,
                "issue_codes": [],
            }
        ),
        encoding="utf-8",
    )
    result = None
    for _ in range(3):
        (official / "fusion.json").write_text("{}", encoding="utf-8")
        result = cli._route_retry(
            official,
            target="fusion",
            state=ContentState.AUDITING,
            issue_codes=["LANGUAGE_NOT_CONCISE"],
            archive=("fusion.json",),
        )
    assert result is not None
    assert result["state"] == ContentState.QUALITY_FAILED.value
    assert result["generation_round"] == 2
    assert (official / "history" / "round-01" / "fusion.json").is_file()
    assert (official / "history" / "round-02" / "fusion.json").is_file()


def test_v15_retry_routes_preserve_unaffected_lane_and_reset_story(tmp_path: Path) -> None:
    official = tmp_path / "resume-content" / ".official" / RUN_ID
    official.mkdir(parents=True)
    (official / "control.json").write_text(
        json.dumps(
            {
                "schema_version": "1.5",
                "run_id": RUN_ID,
                "state": ContentState.DRAFTING.value,
                "generation_round": 0,
                "rewrite_target": None,
                "issue_codes": [],
            }
        ),
        encoding="utf-8",
    )
    (official / "draft-writer.json").write_text("{}", encoding="utf-8")
    (official / "draft-asu.json").write_text("{}", encoding="utf-8")
    result = cli._route_retry(
        official,
        target="writer",
        state=ContentState.DRAFTING,
        issue_codes=["RAW_FACT_VERBATIM_COPY"],
        archive=("draft-writer.json",),
    )
    assert result["rewrite_target"] == "writer"
    assert not (official / "draft-writer.json").exists()
    assert (official / "draft-asu.json").is_file()

    (official / "story-plan.json").write_text("{}", encoding="utf-8")
    (official / "selection-user-approval.json").write_text("{}", encoding="utf-8")
    result = cli._route_retry(
        official,
        target="story_plan",
        state=ContentState.ANALYZING,
        issue_codes=["STORY_PLAN_MISSES_HIGH_VALUE_FACT"],
        archive=("story-plan.json", "selection-user-approval.json"),
    )
    assert result["rewrite_target"] == "story_plan"
    assert result["state"] == ContentState.ANALYZING.value
    assert not (official / "selection-user-approval.json").exists()


def test_v15_fact_conflicts_pause_instead_of_rewriting() -> None:
    assert cli._quality_failure_target(["UNSUPPORTED_NUMERIC_CLAIM"]) == "needs_input"
    assert cli._quality_failure_target(["RAW_FACT_VERBATIM_COPY"]) == "fusion"


def test_v15_needs_input_route_replaces_stale_control_reasons(tmp_path: Path) -> None:
    official = tmp_path / "resume-content" / ".official" / RUN_ID
    official.mkdir(parents=True)
    (official / "control.json").write_text(
        json.dumps(
            {
                "schema_version": "1.5",
                "run_id": RUN_ID,
                "state": ContentState.HR_REVIEWING.value,
                "generation_round": 2,
                "rewrite_target": "writers",
                "issue_codes": ["DRAFT_QUALITY_GATE_FAILED"],
            }
        ),
        encoding="utf-8",
    )

    cli._set_state_with_route(
        official,
        ContentState.NEEDS_INPUT,
        rewrite_target="needs_input",
        issue_codes=["CAMPUS_CASE_METHOD_GAP", "AMBIGUOUS_GROWTH_BASELINE"],
    )

    control = json.loads((official / "control.json").read_text(encoding="utf-8"))
    assert control["state"] == ContentState.NEEDS_INPUT.value
    assert control["rewrite_target"] == "needs_input"
    assert control["issue_codes"] == [
        "CAMPUS_CASE_METHOD_GAP",
        "AMBIGUOUS_GROWTH_BASELINE",
    ]


def test_v15_approval_binds_receipts_content_and_revocation(tmp_path: Path) -> None:
    application = tmp_path / "applications" / "测试_Schema15"
    application.mkdir(parents=True)
    (application / "manifest.json").write_text(
        json.dumps({"status": "analyzed"}), encoding="utf-8"
    )
    run_dir = _commit_v15(application)
    content_sha256 = sha256_bytes((run_dir / "content-master.md").read_bytes())
    approval = UserApprovalRecord(
        user_approval_id="user_approval_" + "f" * 32,
        run_id=RUN_ID,
        content_sha256=content_sha256,
        approved_at=NOW,
    )
    pointer = approve_run(
        application,
        RUN_ID,
        {PROJECT_FACTS[0]: "目标事实"},
        user_approval=approval,
    )
    assert pointer.content_sha256 == content_sha256
    assert validate_pointer_consistency(application) == pointer
    status = cli.command_status(
        SimpleNamespace(
            application_dir=application,
            require_approved_current=True,
            run_id=None,
        )
    )
    assert status["current_valid"] is True
    assert (
        application
        / "resume-content"
        / "approvals"
        / f"{approval.user_approval_id}.json"
    ).is_file()

    cleared = revoke_run(
        application,
        RunStatusRecord(
            run_id=RUN_ID,
            content_sha256=content_sha256,
            status=RunStatus.USER_REJECTED,
            reason_code="USER_REJECTED_CONTENT",
            recorded_at=NOW,
        ),
    )
    assert cleared is True
    assert validate_pointer_consistency(application).status is ContentState.NO_APPROVED_CONTENT
    with pytest.raises(cli.CliError, match="no valid approved"):
        cli.command_status(
            SimpleNamespace(
                application_dir=application,
                require_approved_current=True,
                run_id=None,
            )
        )


def test_v15_revoke_clears_invalid_legacy_current_pointer(tmp_path: Path) -> None:
    application = tmp_path / "applications" / "测试_旧指针"
    content_root = application / "resume-content"
    content_root.mkdir(parents=True)
    (application / "manifest.json").write_text(
        json.dumps(
            {
                "resume_content": {
                    "status": "approved",
                    "run_id": RUN_ID,
                    "content_file": f"resume-content/runs/{RUN_ID}/content-master.md",
                }
            }
        ),
        encoding="utf-8",
    )
    (content_root / "current.json").write_text(
        json.dumps(
            {
                "run_id": RUN_ID,
                "status": "approved",
                "content_file": f"runs/{RUN_ID}/content-master.md",
            }
        ),
        encoding="utf-8",
    )
    cleared = revoke_run(
        application,
        RunStatusRecord(
            run_id=RUN_ID,
            status=RunStatus.SCHEMA_INVALID,
            reason_code="INVALID_LEGACY_CURRENT",
            recorded_at=NOW,
        ),
    )
    assert cleared is True
    pointer = validate_pointer_consistency(application)
    assert pointer.status is ContentState.NO_APPROVED_CONTENT


def test_v15_handwritten_hr_cannot_bypass_missing_receipt(tmp_path: Path) -> None:
    application = tmp_path / "applications" / "测试_Schema15"
    application.mkdir(parents=True)
    (application / "manifest.json").write_text(
        json.dumps({"status": "analyzed"}), encoding="utf-8"
    )
    run_dir = _commit_v15(application, drop_hr_receipt=True)
    approval = UserApprovalRecord(
        user_approval_id="user_approval_" + "9" * 32,
        run_id=RUN_ID,
        content_sha256=sha256_bytes((run_dir / "content-master.md").read_bytes()),
        approved_at=NOW,
    )
    with pytest.raises(RunIntegrityError, match="receipts do not cover"):
        approve_run(
            application,
            RUN_ID,
            {PROJECT_FACTS[0]: "目标事实"},
            user_approval=approval,
        )


@pytest.mark.parametrize(
    "relative_path",
    [
        Path("applications/回响科技_社区运营_7478600356101474611/resume-content/runs/cr_20260901T020649_echoct/content-master.md"),
        Path("applications/回响科技_社区运营_7478600356101474611/resume-content/runs/cr_20260901T034747_echo02/content-master.md"),
        Path("applications/盛趣游戏_代号Meme-AI游戏制作线上实践项目/resume-content/runs/cr_20260902T165644_c9e31f/content-master.md"),
    ],
)
def test_actual_rejected_or_invalid_drafts_fail_v15_import(
    relative_path: Path,
) -> None:
    content = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    findings = validate_legacy_rendered_resume_text(content)
    hard_codes = {item.error_code for item in findings if item.severity.value == "hard"}
    assert "MISSING_SCHEMA15_PROVENANCE" in hard_codes
