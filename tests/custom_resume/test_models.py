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
    ContentState,
    CoverageLevel,
    DraftAgent,
    DraftArtifact,
    EvidenceMapping,
    FactDiffArtifact,
    FactDiffOperation,
    FactGapQuestion,
    FactProvenance,
    FactQuestionOption,
    FusionAction,
    FusionDecision,
    InvalidStateTransition,
    NormalizedInputPacket,
    QuestionStatus,
    ResumeSection,
    ResumeSectionName,
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
        "run_id": RUN_ID,
        "created_at": NOW,
        "source_digests": digests(),
    }


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
    assert len(written) == 12
    assert {path.name for path in written} == {
        "input-packet.schema.json",
        "run.schema.json",
        "jd-analysis.schema.json",
        "evidence-map.schema.json",
        "fact-diff.schema.json",
        "draft.schema.json",
        "fusion.schema.json",
        "audit.schema.json",
        "current.schema.json",
        "agent-failure.schema.json",
        "validation.schema.json",
        "reference-research.schema.json",
    }
    for path in written:
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["title"]


def test_documented_audit_disposition_enum_is_stable() -> None:
    assert [item.value for item in AuditDisposition] == [
        "passed",
        "failed",
        "needs_review",
    ]
