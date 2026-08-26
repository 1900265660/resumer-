from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "custom-resume" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from models import (  # noqa: E402
    AuditDisposition,
    CapabilityCategory,
    CapabilityCategoryScan,
    CapabilityStatus,
    CapabilityTransfer,
    CapabilityTransferMapArtifact,
    ContentState,
    CoverageLevel,
    DraftAgent,
    DraftArtifact,
    EvidenceMapping,
    ExperienceCandidateScore,
    ExperienceSelectionArtifact,
    ExperienceTier,
    FactDiffArtifact,
    FactDiffOperation,
    FactGapQuestion,
    FactProvenance,
    FactQuestionOption,
    FusionAction,
    FusionDecision,
    HrDecisionDimension,
    HrExperienceReview,
    HrRecommendation,
    HrReviewArtifact,
    HrReviewDisposition,
    InterviewImpact,
    InvalidStateTransition,
    JobTaskEvidenceLevel,
    NormalizedInputPacket,
    QualityAudit,
    QualityDimension,
    QuestionStatus,
    ResumeSection,
    ResumeSectionName,
    PortfolioValue,
    SectionBalanceOverride,
    TransferConfidence,
    TransferDistance,
    RoleFamily,
    SourceDigests,
    SourceType,
    assert_state_transition,
    export_json_schemas,
)


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
RUN_ID = "cr_20260822T120000_abc123"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def digests() -> SourceDigests:
    return SourceDigests(
        jd_sha256=HASH_A,
        fact_snapshot_sha256=HASH_B,
        preferences_sha256=HASH_C,
    )


def artifact_base() -> dict[str, object]:
    return {
        "schema_version": "1.1",
        "run_id": RUN_ID,
        "created_at": NOW,
        "source_digests": digests(),
    }


def artifact_base_v12() -> dict[str, object]:
    return {**artifact_base(), "schema_version": "1.2"}


def empty_sections() -> list[ResumeSection]:
    return [ResumeSection(name=name, entries=[]) for name in ResumeSectionName]


def test_models_reject_unknown_fields_and_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        NormalizedInputPacket(
            **artifact_base(),
            application_dir="applications/测试_AI产品经理",
            source_type=SourceType.DIRECTORY,
            source_locator="applications/测试_AI产品经理/jd.md",
            unexpected=True,
        )


def test_role_family_defaults_to_ai_and_accepts_game_production() -> None:
    default_packet = NormalizedInputPacket(
        **artifact_base(),
        application_dir="applications/测试_AI产品经理",
        source_type=SourceType.TEXT,
        source_locator="inline:text",
    )
    assert default_packet.role_family is RoleFamily.AI_PRODUCT_MANAGER
    game_packet = default_packet.model_copy(
        update={"role_family": RoleFamily.GAME_PRODUCTION_PM}
    )
    assert game_packet.role_family is RoleFamily.GAME_PRODUCTION_PM

    with pytest.raises(ValidationError, match="timezone"):
        NormalizedInputPacket(
            **{**artifact_base(), "created_at": datetime(2026, 8, 22, 12, 0)},
            application_dir="applications/测试_AI产品经理",
            source_type=SourceType.DIRECTORY,
            source_locator="applications/测试_AI产品经理/jd.md",
        )


def test_state_machine_accepts_only_documented_transitions() -> None:
    assert_state_transition(ContentState.NOT_STARTED, ContentState.ANALYZING)
    assert_state_transition(ContentState.NEEDS_CONTENT_REVIEW, ContentState.APPROVED)
    assert_state_transition(ContentState.APPROVED, ContentState.STALE)

    with pytest.raises(InvalidStateTransition, match="not_started -> approved"):
        assert_state_transition(ContentState.NOT_STARTED, ContentState.APPROVED)
    with pytest.raises(InvalidStateTransition, match="stale -> analyzing"):
        assert_state_transition(ContentState.STALE, ContentState.ANALYZING)


def test_supported_evidence_requires_facts_and_gaps_forbid_them() -> None:
    with pytest.raises(ValidationError, match="requires fact_ids"):
        EvidenceMapping(
            requirement_id="REQ-001",
            coverage=CoverageLevel.DIRECT,
            rationale="直接匹配",
        )

    with pytest.raises(ValidationError, match="cannot cite"):
        EvidenceMapping(
            requirement_id="REQ-001",
            coverage=CoverageLevel.UNSUPPORTED,
            fact_ids=["FACT-WORK-001-01"],
            rationale="没有支持",
            gap_summary="缺少平台经历",
        )


def test_accepted_estimate_requires_basis_and_confirmation_timestamp() -> None:
    with pytest.raises(ValidationError, match="estimate_basis"):
        FactDiffOperation(
            operation_id="FD-001",
            action="add",
            experience_id="EXP-WORK-001",
            proposed_fact_id="FACT-WORK-001-01",
            new_value="效率提升约 10%–20%",
            provenance=FactProvenance.ACCEPTED_ESTIMATE,
        )


def test_five_question_limit_does_not_limit_diff_operations() -> None:
    questions = [
        FactGapQuestion(
            question_id=f"Q-{index:03d}",
            requirement_ids=["REQ-001"],
            prompt=f"问题 {index}",
            options=[
                FactQuestionOption(option_id="A", label="有", description="能够确认"),
                FactQuestionOption(option_id="B", label="无", description="无法确认"),
            ],
        )
        for index in range(1, 6)
    ]
    operations = [
        FactDiffOperation(
            operation_id=f"FD-{index:03d}",
            action="add",
            experience_id="EXP-WORK-001",
            proposed_fact_id=f"FACT-WORK-001-{index:02d}",
            new_value=f"确认事实 {index}",
            provenance=FactProvenance.OBSERVED,
        )
        for index in range(1, 7)
    ]
    artifact = FactDiffArtifact(
        **artifact_base(),
        source_fact_sha256=HASH_B,
        questions=questions,
        operations=operations,
    )
    assert len(artifact.questions) == 5
    assert len(artifact.operations) == 6

    with pytest.raises(ValidationError, match="at most 5"):
        FactDiffArtifact(
            **artifact_base(),
            source_fact_sha256=HASH_B,
            questions=[
                *questions,
                FactGapQuestion(
                    question_id="Q-006",
                    requirement_ids=["REQ-001"],
                    prompt="问题 6",
                    options=[
                        FactQuestionOption(
                            option_id="A", label="有", description="能够确认"
                        ),
                        FactQuestionOption(
                            option_id="B", label="无", description="无法确认"
                        ),
                    ],
                ),
            ],
            operations=operations,
        )


def test_empty_fact_diff_represents_no_proposed_changes() -> None:
    artifact = FactDiffArtifact(
        **artifact_base(),
        source_fact_sha256=HASH_B,
    )
    assert artifact.operations == []

    with pytest.raises(ValidationError, match="without questions must remain pending"):
        FactDiffArtifact(
            **artifact_base(),
            source_fact_sha256=HASH_B,
            confirmation_status="approved",
        )


def test_fact_question_answer_state_is_explicit() -> None:
    with pytest.raises(ValidationError, match="require an option"):
        FactGapQuestion(
            question_id="Q-001",
            requirement_ids=["REQ-001"],
            prompt="是否使用过评测工具？",
            options=[
                FactQuestionOption(option_id="A", label="是", description="使用过"),
                FactQuestionOption(option_id="B", label="否", description="没有使用"),
            ],
            status=QuestionStatus.ANSWERED,
        )

    with pytest.raises(ValidationError, match="confirmed_at"):
        FactDiffOperation(
            operation_id="FD-001",
            action="add",
            experience_id="EXP-WORK-001",
            proposed_fact_id="FACT-WORK-001-01",
            new_value="效率提升约 10%–20%",
            provenance=FactProvenance.ACCEPTED_ESTIMATE,
            estimate_basis="用户接受模型估值区间",
            confirmation_status="approved",
        )


def test_draft_requires_exact_section_order() -> None:
    sections = empty_sections()
    valid = DraftArtifact(
        **artifact_base(),
        agent=DraftAgent.WRITER,
        sections=sections,
    )
    assert [item.name for item in valid.sections] == list(ResumeSectionName)

    with pytest.raises(ValidationError, match="sections must appear exactly"):
        DraftArtifact(
            **artifact_base(),
            agent=DraftAgent.WRITER,
            sections=list(reversed(sections)),
        )


def test_fusion_drop_and_output_shapes_are_mutually_exclusive() -> None:
    drop = FusionDecision(
        decision_id="DEC-001",
        action=FusionAction.DROP,
        source_bullet_ids=["WRITER-001"],
        rationale="与岗位无关",
    )
    assert drop.output_text is None

    with pytest.raises(ValidationError, match="cannot include output"):
        FusionDecision(
            decision_id="DEC-002",
            action=FusionAction.DROP,
            source_bullet_ids=["ASU-001"],
            output_bullet_id="FUSION-001",
            output_text="错误输出",
            fact_ids=["FACT-WORK-001-01"],
            rationale="错误形状",
        )


def test_schema_export_produces_valid_json_for_all_artifacts(tmp_path: Path) -> None:
    written = export_json_schemas(tmp_path)
    assert len(written) == 17
    assert {path.name for path in written} == {
        "input-packet.schema.json",
        "run.schema.json",
        "jd-analysis.schema.json",
        "evidence-map.schema.json",
        "capability-transfer-map.schema.json",
        "experience-selection.schema.json",
        "selection-audit.schema.json",
        "fact-diff.schema.json",
        "draft.schema.json",
        "fusion.schema.json",
        "audit.schema.json",
        "hr-review.schema.json",
        "current.schema.json",
        "agent-failure.schema.json",
        "validation.schema.json",
        "reference-research.schema.json",
        "run-checkpoint.schema.json",
    }
    for path in written:
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["title"]


def hr_experience_review(
    *, questions: list[str] | None = None, passed: bool = False
) -> HrExperienceReview:
    return HrExperienceReview(
        experience_id="EXP-PROJECT-001",
        ten_second_impression=(
            "项目证据完整，足以支持推进。"
            if passed
            else "项目真实，但需要更完整的招聘证据。"
        ),
        effective_requirement_ids=["REQ-001"],
        strengths=["有可验证交付"],
        defects=[] if passed else ["个人边界不够具体"],
        severity_score=0 if passed else 7.5,
        interview_impact=(
            InterviewImpact.NONE if passed else InterviewImpact.MATERIAL
        ),
        recommended_bullet_count=3,
        revision_instructions=[] if passed else ["补足情境、方法和结果口径"],
        missing_fact_questions=questions or [],
    )


def test_v13_hr_review_enforces_strong_push_and_8_5_gate() -> None:
    dimension = HrDecisionDimension(score=8.5, evidence=["达到高标准"])
    passing = HrReviewArtifact(
        **{**artifact_base(), "schema_version": "1.3"},
        revision_round=0,
        recommendation=HrRecommendation.STRONG_PUSH,
        overall_score=8.5,
        role_fit=dimension,
        narrative_completeness=dimension,
        evidence_specificity=dimension,
        decision_readiness=dimension,
        credibility=dimension,
        experience_reviews=[hr_experience_review(passed=True)],
        existing_fact_revision_sufficient=False,
        fact_questions_required=False,
        reselect_required=False,
        passed=True,
        disposition=HrReviewDisposition.PASSED,
    )
    assert passing.passed is True

    with pytest.raises(ValidationError, match="strong_push"):
        HrReviewArtifact.model_validate(
            passing.model_copy(
                update={
                    "recommendation": HrRecommendation.PUSH,
                    "passed": True,
                }
            ).model_dump()
        )


def test_v13_hr_review_routes_missing_facts_without_revision() -> None:
    weak = HrDecisionDimension(score=7, evidence=["缺少风险处理事实"])
    review = HrReviewArtifact(
        **{**artifact_base(), "schema_version": "1.3"},
        revision_round=0,
        recommendation=HrRecommendation.HESITATE,
        overall_score=7,
        role_fit=weak,
        narrative_completeness=weak,
        evidence_specificity=weak,
        decision_readiness=weak,
        credibility=weak,
        experience_reviews=[
            hr_experience_review(questions=["请确认一次真实的风险处理案例。"])
        ],
        issue_codes=["MISSING_RISK_CASE"],
        existing_fact_revision_sufficient=False,
        fact_questions_required=True,
        reselect_required=False,
        passed=False,
        disposition=HrReviewDisposition.NEEDS_INPUT,
    )
    assert review.disposition is HrReviewDisposition.NEEDS_INPUT


def test_v13_hr_review_routes_are_mutually_exclusive() -> None:
    weak = HrDecisionDimension(score=7, evidence=["需要补充招聘证据"])
    with pytest.raises(ValidationError, match="mutually exclusive"):
        HrReviewArtifact(
            **{**artifact_base(), "schema_version": "1.3"},
            revision_round=0,
            recommendation=HrRecommendation.HESITATE,
            overall_score=7,
            role_fit=weak,
            narrative_completeness=weak,
            evidence_specificity=weak,
            decision_readiness=weak,
            credibility=weak,
            experience_reviews=[
                hr_experience_review(questions=["请补充风险处理事实。"])
            ],
            issue_codes=["AMBIGUOUS_ROUTE"],
            existing_fact_revision_sufficient=True,
            fact_questions_required=True,
            reselect_required=False,
            passed=False,
            disposition=HrReviewDisposition.NEEDS_INPUT,
        )


def test_v13_failed_hr_review_allows_unaffected_experience_without_fake_defects() -> None:
    unaffected = HrExperienceReview(
        experience_id="EXP-SKILL-001",
        ten_second_impression="能力分类清晰，无阻断问题。",
        severity_score=0,
        interview_impact=InterviewImpact.NONE,
        recommended_bullet_count=1,
    )
    assert unaffected.defects == []
    assert unaffected.revision_instructions == []


def test_v13_hr_revision_round_two_must_stop_for_manual_review() -> None:
    weak = HrDecisionDimension(score=7.5, evidence=["仍未达到招聘门槛"])
    review = HrReviewArtifact(
        **{**artifact_base(), "schema_version": "1.3"},
        revision_round=2,
        recommendation=HrRecommendation.HESITATE,
        overall_score=7.5,
        role_fit=weak,
        narrative_completeness=weak,
        evidence_specificity=weak,
        decision_readiness=weak,
        credibility=weak,
        experience_reviews=[hr_experience_review()],
        issue_codes=["REVISION_LIMIT_REACHED"],
        existing_fact_revision_sufficient=True,
        fact_questions_required=False,
        reselect_required=False,
        passed=False,
        disposition=HrReviewDisposition.NEEDS_REVIEW,
    )
    assert review.disposition is HrReviewDisposition.NEEDS_REVIEW
    with pytest.raises(ValidationError, match="needs_review"):
        HrReviewArtifact.model_validate(
            review.model_copy(
                update={"disposition": HrReviewDisposition.REVISE}
            ).model_dump()
        )


def test_v12_capability_map_scans_all_categories_and_keeps_candidates_non_writable() -> None:
    supported = CapabilityTransfer(
        transfer_id="TR-001",
        experience_id="EXP-PROJECT-001",
        category=CapabilityCategory.PLANNING_DELIVERY,
        fact_ids=["FACT-PROJECT-001-01"],
        source_action="拆分范围并按时交付",
        target_capability="项目推进",
        requirement_ids=["REQ-001"],
        distance=TransferDistance.ADJACENT,
        confidence=TransferConfidence.HIGH,
        credit_multiplier=0.8,
        writable_scope="可写范围拆分和交付推进，不可写正式研发排期",
    )
    candidate = CapabilityTransfer(
        transfer_id="TR-002",
        experience_id="EXP-PROJECT-001",
        category=CapabilityCategory.STAKEHOLDER_COLLABORATION,
        source_action="可能进行人员分工",
        target_capability="团队协作",
        requirement_ids=["REQ-001"],
        distance=TransferDistance.CANDIDATE,
        confidence=TransferConfidence.LOW,
        credit_multiplier=0,
        candidate_question_id="Q-001",
    )
    scans = []
    for category in CapabilityCategory:
        if category is CapabilityCategory.PLANNING_DELIVERY:
            status, transfer_ids = CapabilityStatus.SUPPORTED, ["TR-001"]
        elif category is CapabilityCategory.STAKEHOLDER_COLLABORATION:
            status, transfer_ids = CapabilityStatus.CANDIDATE, ["TR-002"]
        else:
            status, transfer_ids = CapabilityStatus.NONE, []
        scans.append(
            CapabilityCategoryScan(
                experience_id="EXP-PROJECT-001",
                category=category,
                status=status,
                transfer_ids=transfer_ids,
                rationale="逐类扫描结果",
            )
        )
    artifact = CapabilityTransferMapArtifact(
        **artifact_base_v12(),
        experience_ids=["EXP-PROJECT-001"],
        transfers=[supported, candidate],
        scans=scans,
    )
    assert len(artifact.scans) == 8
    assert artifact.transfers[1].writable_scope is None
    with pytest.raises(ValidationError, match="candidate transfer forbids"):
        CapabilityTransfer.model_validate(
            {
                **candidate.model_dump(mode="python"),
                "fact_ids": ["FACT-PROJECT-001-01"],
                "writable_scope": "错误地允许写入",
            }
        )


def _v12_candidate(
    experience_id: str,
    *,
    score: int,
    selected: bool,
    bullets: int,
    personal: bool = False,
    group: str | None = None,
    override_reason: str | None = None,
) -> ExperienceCandidateScore:
    remaining = score
    components_list = []
    for maximum in (30, 20, 15, 10, 15, 10):
        value = min(remaining, maximum)
        components_list.append(value)
        remaining -= value
    components = tuple(components_list)
    return ExperienceCandidateScore(
        experience_id=experience_id,
        fact_ids=[f"FACT-{experience_id.removeprefix('EXP-')}-01"],
        responsibility_score=components[0],
        process_delivery_score=components[1],
        result_score=components[2],
        domain_score=components[3],
        incremental_coverage_score=components[4],
        evidence_strength_score=components[5],
        job_task_evidence=JobTaskEvidenceLevel.DIRECT,
        total_score=score,
        tier=(
            ExperienceTier.CORE
            if score >= 70
            else ExperienceTier.AUXILIARY
            if score >= 55
            else ExperienceTier.EXCLUDED
        ),
        matched_requirement_ids=["REQ-001"],
        selected=selected,
        proposed_bullet_count=bullets,
        rationale="V1.3 双轴选材测试",
        user_override_reason=override_reason,
        portfolio_value_score=PortfolioValue(
            section_balance=5,
            capability_diversity=4,
            narrative_uniqueness=3,
            non_redundancy=2,
            total=14,
        ),
        similarity_group=group,
        is_personal_development=personal,
    )


def test_v12_work_minimum_similarity_limit_and_auditable_override() -> None:
    work_core = _v12_candidate("EXP-WORK-001", score=70, selected=True, bullets=2)
    work_low = _v12_candidate(
        "EXP-WORK-002",
        score=30,
        selected=True,
        bullets=2,
        override_reason="补足真实工作板块与协作场景",
    )
    override = SectionBalanceOverride(
        experience_id="EXP-WORK-002",
        reason="补足真实工作板块与协作场景",
        compared_alternative_ids=["EXP-PROJECT-001"],
        approved_at=NOW,
    )
    selection = ExperienceSelectionArtifact(
        **artifact_base_v12(),
        capability_transfer_map_sha256=HASH_A,
        section_balance_override=override,
        candidates=[work_core, work_low],
        selection_approved=True,
        approved_at=NOW,
    )
    assert selection.candidates[1].tier is ExperienceTier.EXCLUDED
    assert selection.candidates[1].total_score == 30

    with pytest.raises(ValidationError, match="at least two WORK"):
        ExperienceSelectionArtifact(
            **artifact_base_v12(),
            capability_transfer_map_sha256=HASH_A,
            candidates=[
                work_core,
                work_low.model_copy(
                    update={
                        "selected": False,
                        "proposed_bullet_count": 0,
                        "user_override_reason": None,
                    }
                ),
            ],
            selection_approved=True,
            approved_at=NOW,
        )

    projects = [
        _v12_candidate(
            f"EXP-PROJECT-{index:03d}",
            score=70,
            selected=True,
            bullets=1,
            personal=True,
            group="个人对话型Agent",
        )
        for index in range(1, 4)
    ]
    with pytest.raises(ValidationError, match="at most two"):
        ExperienceSelectionArtifact(
            **artifact_base_v12(),
            capability_transfer_map_sha256=HASH_A,
            candidates=projects,
            selection_approved=True,
            approved_at=NOW,
        )


def test_documented_audit_disposition_enum_is_stable() -> None:
    assert [item.value for item in AuditDisposition] == [
        "passed",
        "failed",
        "needs_review",
    ]


def test_experience_score_recomputes_tier_and_caps_affinity_only() -> None:
    base = dict(
        experience_id="EXP-PROJECT-001",
        fact_ids=["FACT-PROJECT-001-01"],
        responsibility_score=25,
        process_delivery_score=18,
        result_score=12,
        domain_score=10,
        incremental_coverage_score=12,
        evidence_strength_score=8,
        matched_requirement_ids=["REQ-001"],
        incremental_requirement_ids=["REQ-001"],
        selected=False,
        proposed_bullet_count=0,
        rationale="完整分项测试。",
    )
    direct = ExperienceCandidateScore(
        **base,
        job_task_evidence=JobTaskEvidenceLevel.DIRECT,
        total_score=85,
        tier=ExperienceTier.CORE,
    )
    assert direct.tier is ExperienceTier.CORE

    affinity = ExperienceCandidateScore(
        **base,
        job_task_evidence=JobTaskEvidenceLevel.AFFINITY_ONLY,
        total_score=54,
        tier=ExperienceTier.EXCLUDED,
    )
    assert affinity.total_score == 54
    with pytest.raises(ValidationError, match="deterministic component total 54"):
        ExperienceCandidateScore(
            **base,
            job_task_evidence=JobTaskEvidenceLevel.AFFINITY_ONLY,
            total_score=85,
            tier=ExperienceTier.CORE,
        )


def test_selection_enforces_auxiliary_quota_and_core_omission_reason() -> None:
    def candidate(
        experience_id: str,
        tier: ExperienceTier,
        selected: bool,
        bullets: int,
        omission_reason: str | None = None,
    ) -> ExperienceCandidateScore:
        components = (
            (25, 15, 10, 5, 10, 5)
            if tier is ExperienceTier.CORE
            else (20, 10, 8, 5, 7, 5)
        )
        score = sum(components)
        return ExperienceCandidateScore(
            experience_id=experience_id,
            fact_ids=[f"FACT-{experience_id.removeprefix('EXP-')}-01"],
            responsibility_score=components[0],
            process_delivery_score=components[1],
            result_score=components[2],
            domain_score=components[3],
            incremental_coverage_score=components[4],
            evidence_strength_score=components[5],
            job_task_evidence=JobTaskEvidenceLevel.DIRECT,
            total_score=score,
            tier=tier,
            matched_requirement_ids=["REQ-001"],
            incremental_requirement_ids=["REQ-001"] if tier is ExperienceTier.AUXILIARY else [],
            selected=selected,
            proposed_bullet_count=bullets,
            rationale="配额测试。",
            omission_reason=omission_reason,
        )

    core = candidate("EXP-WORK-001", ExperienceTier.CORE, True, 3)
    auxiliary = candidate("EXP-PROJECT-001", ExperienceTier.AUXILIARY, True, 1)
    valid = ExperienceSelectionArtifact(
        **artifact_base(),
        candidates=[core, auxiliary],
        selection_approved=True,
        approved_at=NOW,
    )
    assert sum(item.proposed_bullet_count for item in valid.candidates) == 4

    with pytest.raises(ValidationError, match="cannot exceed 25%"):
        ExperienceSelectionArtifact(
            **artifact_base(),
            candidates=[
                core.model_copy(update={"proposed_bullet_count": 2}),
                auxiliary.model_copy(update={"proposed_bullet_count": 1}),
            ],
            selection_approved=True,
            approved_at=NOW,
        )
    omitted_core = candidate("EXP-WORK-002", ExperienceTier.CORE, False, 0)
    with pytest.raises(ValidationError, match="omitted core experiences require reasons"):
        ExperienceSelectionArtifact(
            **artifact_base(),
            candidates=[core, omitted_core],
            selection_approved=True,
            approved_at=NOW,
        )


def test_interference_fixture_prefers_strong_transferable_pm_evidence() -> None:
    path = (
        Path(__file__).parent
        / "fixtures"
        / "selection-v1.2"
        / "interference-case.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    candidates = [
        ExperienceCandidateScore.model_validate(item)
        for item in payload["candidates"]
    ]
    by_id = {item.experience_id: item for item in candidates}
    assert by_id["EXP-PROJECT-101"].tier is ExperienceTier.EXCLUDED
    assert by_id["EXP-PROJECT-101"].total_score == 54
    assert by_id["EXP-PROJECT-102"].tier is ExperienceTier.CORE
    assert by_id["EXP-PROJECT-102"].selected is True


def test_gap_disclosure_cannot_compensate_for_selection_quality() -> None:
    passing = QualityDimension(score=8, evidence=["正向证据达到门槛"])
    weak = QualityDimension(score=5, evidence=["弱经历挤占强经历"])
    audit = QualityAudit(
        jd_coverage=passing,
        selection_quality=weak,
        evidence_depth=passing,
        hr_scan=passing,
        language_naturalness=passing,
        gap_disclosure_passed=True,
        passed=False,
    )
    assert audit.passed is False
    with pytest.raises(ValidationError, match="quality below 8"):
        QualityAudit(
            jd_coverage=passing,
            selection_quality=weak,
            evidence_depth=passing,
            hr_scan=passing,
            language_naturalness=passing,
            gap_disclosure_passed=True,
            passed=True,
        )


def test_deepblue_v11_truthful_draft_still_fails_selection_quality() -> None:
    path = (
        Path(__file__).parent
        / "fixtures"
        / "selection-v1.2"
        / "deepblue-v1.1-negative.json"
    )
    case = json.loads(path.read_text(encoding="utf-8"))
    selected_below_threshold = [
        item for item in case["selected"] if item["score"] < 55
    ]
    omitted_core_without_reason = [
        item
        for item in case["omitted"]
        if item["score"] >= 70 and not item["reason"]
    ]
    assert case["truth_expected"] is True
    assert selected_below_threshold
    assert omitted_core_without_reason
    assert case["selection_quality_expected"] is False
