from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "custom-resume" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import storage  # noqa: E402
from models import (  # noqa: E402
    AuditArtifact,
    AuditDisposition,
    ContentState,
    HrDecisionDimension,
    HrExperienceReview,
    HrRecommendation,
    HrReviewArtifact,
    HrReviewDisposition,
    InterviewImpact,
    NormalizedInputPacket,
    QualityAudit,
    QualityDimension,
    RunManifestArtifact,
    SourceDigests,
    SourceType,
    TruthAudit,
)
from storage import (  # noqa: E402
    PointerConsistencyError,
    RunAlreadyExistsError,
    RunIntegrityError,
    StorageError,
    approve_run,
    begin_run,
    create_run_id,
    load_run,
    recover_approval,
    refresh_stale_status,
    validate_pointer_consistency,
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


def input_packet(run_id: str = RUN_ID) -> NormalizedInputPacket:
    return NormalizedInputPacket(
        schema_version="1.2",
        run_id=run_id,
        created_at=NOW,
        source_digests=digests(),
        application_dir="applications/测试_AI产品经理",
        source_type=SourceType.DIRECTORY,
        source_locator="applications/测试_AI产品经理/jd.md",
    )


def passed_audit(run_id: str = RUN_ID) -> AuditArtifact:
    dimension = QualityDimension(score=8.5, evidence=["达到门槛"])
    return AuditArtifact(
        schema_version="1.2",
        run_id=run_id,
        created_at=NOW,
        source_digests=digests(),
        deterministic_passed=True,
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


def passed_hr_review(
    *, source_digests: SourceDigests | None = None
) -> HrReviewArtifact:
    dimension = HrDecisionDimension(score=8.5, evidence=["达到高标准"])
    return HrReviewArtifact(
        schema_version="1.3",
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=source_digests or digests(),
        revision_round=0,
        recommendation=HrRecommendation.STRONG_PUSH,
        overall_score=8.5,
        role_fit=dimension,
        narrative_completeness=dimension,
        evidence_specificity=dimension,
        decision_readiness=dimension,
        credibility=dimension,
        experience_reviews=[
            HrExperienceReview(
                experience_id="EXP-PROJECT-001",
                ten_second_impression="招聘证据完整，可推进面试。",
                effective_requirement_ids=["REQ-001"],
                strengths=["事实可追溯"],
                severity_score=0,
                interview_impact=InterviewImpact.NONE,
                recommended_bullet_count=3,
            )
        ],
        existing_fact_revision_sufficient=False,
        fact_questions_required=False,
        reselect_required=False,
        passed=True,
        disposition=HrReviewDisposition.PASSED,
    )


def create_application(tmp_path: Path) -> Path:
    application = tmp_path / "applications" / "测试_AI产品经理"
    application.mkdir(parents=True)
    (application / "manifest.json").write_text(
        json.dumps({"status": "analyzed", "company": "测试公司"}, ensure_ascii=False),
        encoding="utf-8",
    )
    return application


def commit_approved_run(application: Path, run_id: str = RUN_ID) -> Path:
    stage = begin_run(application, run_id)
    stage.write_model("audit.json", passed_audit(run_id))
    packet = input_packet(run_id)
    manifest = RunManifestArtifact(
        schema_version="1.2",
        run_id=run_id,
        created_at=NOW,
        source_digests=digests(),
        state=ContentState.APPROVED,
        input_packet=packet,
        artifacts=stage.artifact_records(),
    )
    return stage.commit(manifest)


def seed_legacy_approved_pointer(
    application: Path, fact_value: str = "引用值"
) -> None:
    """Represent an approval that existed before Schema 1.5 became mandatory."""
    transaction_id = "approval_" + "a" * 32
    pointer, job_manifest = storage._approval_payloads(
        application.resolve(),
        RUN_ID,
        {"FACT-PROJECT-001-01": fact_value},
        NOW,
        transaction_id,
    )
    storage._replace_json(
        application / "resume-content" / "current.json",
        pointer.model_dump(mode="json"),
    )
    storage._replace_json(application / "manifest.json", job_manifest)


def test_run_id_is_validated_and_repeatable_for_tests() -> None:
    assert create_run_id(NOW, "abc123") == RUN_ID
    with pytest.raises(storage.StorageError, match="invalid generated run ID"):
        create_run_id(NOW, "INVALID")


def test_committed_run_cannot_be_overwritten(tmp_path: Path) -> None:
    application = create_application(tmp_path)
    final_path = commit_approved_run(application)
    assert final_path.is_dir()
    assert load_run(application, RUN_ID).state is ContentState.APPROVED

    with pytest.raises(RunAlreadyExistsError, match="already exists"):
        begin_run(application, RUN_ID)


def test_incomplete_inventory_never_creates_final_run(tmp_path: Path) -> None:
    application = create_application(tmp_path)
    stage = begin_run(application, RUN_ID)
    stage.write_model("audit.json", passed_audit())
    manifest = RunManifestArtifact(
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        state=ContentState.APPROVED,
        input_packet=input_packet(),
        artifacts=[],
    )
    with pytest.raises(RunIntegrityError, match="inventory is incomplete"):
        stage.commit(manifest)
    assert not stage.final_path.exists()
    assert stage.path.exists()


def test_committed_artifact_hash_is_verified(tmp_path: Path) -> None:
    application = create_application(tmp_path)
    final_path = commit_approved_run(application)
    (final_path / "audit.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RunIntegrityError, match="integrity failure"):
        load_run(application, RUN_ID)


def test_legacy_run_cannot_create_new_approval_pointer(tmp_path: Path) -> None:
    application = create_application(tmp_path)
    commit_approved_run(application)
    with pytest.raises(StorageError, match="schema 1.5"):
        approve_run(
            application,
            RUN_ID,
            {"FACT-PROJECT-001-01": "已确认事实"},
            approved_at=NOW,
        )
    assert not (application / "resume-content" / "current.json").exists()


@pytest.mark.parametrize("schema_version", ["1.3", "1.4"])
def test_schema_v13_plus_approval_requires_passing_hr_decision_gate(
    tmp_path: Path, schema_version: str
) -> None:
    application = create_application(tmp_path)
    stage = begin_run(application, RUN_ID)
    dimension = QualityDimension(score=8.5, evidence=["基础审计通过"])
    audit = AuditArtifact(
        schema_version=schema_version,
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        deterministic_passed=True,
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
    weak = HrDecisionDimension(score=7.5, evidence=["招聘证据过度压缩"])
    review = HrReviewArtifact(
        schema_version=schema_version,
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        revision_round=0,
        recommendation=HrRecommendation.HESITATE,
        overall_score=7.5,
        role_fit=weak,
        narrative_completeness=weak,
        evidence_specificity=weak,
        decision_readiness=weak,
        credibility=weak,
        experience_reviews=[
            HrExperienceReview(
                experience_id="EXP-PROJECT-001",
                ten_second_impression="事实真实但不足以推进",
                defects=["缺少完整证据链"],
                severity_score=8,
                interview_impact=InterviewImpact.BLOCKING,
                recommended_bullet_count=3,
                revision_instructions=["按已确认事实展开"],
            )
        ],
        issue_codes=["NOT_INTERVIEW_READY"],
        existing_fact_revision_sufficient=True,
        fact_questions_required=False,
        reselect_required=False,
        passed=False,
        disposition=HrReviewDisposition.REVISE,
    )
    stage.write_model("audit.json", audit)
    stage.write_model("hr-review.json", review)
    packet = input_packet().model_copy(update={"schema_version": schema_version})
    manifest = RunManifestArtifact(
        schema_version=schema_version,
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        state=ContentState.NEEDS_CONTENT_REVIEW,
        input_packet=packet,
        artifacts=stage.artifact_records(),
    )
    stage.commit(manifest)
    with pytest.raises(StorageError, match="HR decision gate did not pass"):
        approve_run(
            application,
            RUN_ID,
            {"FACT-PROJECT-001-01": "已确认事实"},
            approved_at=NOW,
        )


def test_schema_v13_approval_rejects_mismatched_hr_review_envelope(
    tmp_path: Path,
) -> None:
    application = create_application(tmp_path)
    stage = begin_run(application, RUN_ID)
    audit = passed_audit().model_copy(update={"schema_version": "1.3"})
    mismatched_digests = SourceDigests(
        jd_sha256="d" * 64,
        fact_snapshot_sha256=HASH_B,
        preferences_sha256=HASH_C,
    )
    stage.write_model("audit.json", audit)
    stage.write_model(
        "hr-review.json", passed_hr_review(source_digests=mismatched_digests)
    )
    packet = input_packet().model_copy(update={"schema_version": "1.3"})
    manifest = RunManifestArtifact(
        schema_version="1.3",
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        state=ContentState.NEEDS_CONTENT_REVIEW,
        input_packet=packet,
        artifacts=stage.artifact_records(),
    )
    stage.commit(manifest)
    with pytest.raises(RunIntegrityError, match="HR review envelope"):
        approve_run(
            application,
            RUN_ID,
            {"FACT-PROJECT-001-01": "已确认事实"},
            approved_at=NOW,
        )


def test_only_referenced_fact_changes_mark_current_stale(tmp_path: Path) -> None:
    application = create_application(tmp_path)
    commit_approved_run(application)
    seed_legacy_approved_pointer(application)

    unrelated = {
        "FACT-PROJECT-001-01": "引用值",
        "FACT-WORK-001-01": "无关事实已变化",
    }
    assert refresh_stale_status(application, unrelated) is False
    assert validate_pointer_consistency(application).status is ContentState.APPROVED

    assert refresh_stale_status(
        application,
        {"FACT-PROJECT-001-01": "引用值已变化"},
        updated_at=datetime(2026, 8, 22, 13, 0, tzinfo=timezone.utc),
    ) is True
    assert validate_pointer_consistency(application).status is ContentState.STALE


def test_pointer_manifest_disagreement_is_rejected(tmp_path: Path) -> None:
    application = create_application(tmp_path)
    commit_approved_run(application)
    seed_legacy_approved_pointer(application)
    manifest_path = application / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resume_content"]["transaction_id"] = f"approval_{'0' * 32}"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PointerConsistencyError, match="disagree"):
        validate_pointer_consistency(application)


def test_interrupted_approval_is_recovered_from_journal(tmp_path: Path) -> None:
    application = create_application(tmp_path)
    commit_approved_run(application)
    transaction_id = "approval_" + "d" * 32
    pointer, job_manifest = storage._approval_payloads(
        application.resolve(),
        RUN_ID,
        {"FACT-PROJECT-001-01": "引用值"},
        NOW,
        transaction_id,
    )
    journal = application / "resume-content" / ".approval-transaction.json"
    storage._replace_json(
        journal,
        {
            "transaction_id": transaction_id,
            "current": pointer.model_dump(mode="json"),
            "manifest": job_manifest,
        },
    )
    assert journal.exists()
    assert recover_approval(application) is True
    assert not journal.exists()
    assert validate_pointer_consistency(application).status is ContentState.APPROVED
