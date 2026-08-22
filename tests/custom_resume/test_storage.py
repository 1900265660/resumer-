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
        run_id=run_id,
        created_at=NOW,
        source_digests=digests(),
        deterministic_passed=True,
        truth=TruthAudit(passed=True),
        quality=QualityAudit(
            jd_coverage=dimension,
            evidence_depth=dimension,
            hr_scan=dimension,
            language_naturalness=dimension,
            passed=True,
        ),
        disposition=AuditDisposition.PASSED,
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
        run_id=run_id,
        created_at=NOW,
        source_digests=digests(),
        state=ContentState.APPROVED,
        input_packet=packet,
        artifacts=stage.artifact_records(),
    )
    return stage.commit(manifest)


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


def test_approval_pointer_preserves_application_state(tmp_path: Path) -> None:
    application = create_application(tmp_path)
    commit_approved_run(application)
    pointer = approve_run(
        application,
        RUN_ID,
        {"FACT-PROJECT-001-01": "已确认事实"},
        approved_at=NOW,
    )
    validated = validate_pointer_consistency(application)
    job_manifest = json.loads((application / "manifest.json").read_text(encoding="utf-8"))

    assert validated == pointer
    assert job_manifest["status"] == "analyzed"
    assert job_manifest["resume_content"]["status"] == "approved"


def test_only_referenced_fact_changes_mark_current_stale(tmp_path: Path) -> None:
    application = create_application(tmp_path)
    commit_approved_run(application)
    approve_run(
        application,
        RUN_ID,
        {"FACT-PROJECT-001-01": "引用值"},
        approved_at=NOW,
    )

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
    approve_run(
        application,
        RUN_ID,
        {"FACT-PROJECT-001-01": "引用值"},
        approved_at=NOW,
    )
    manifest_path = application / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resume_content"]["transaction_id"] = f"approval_{'0' * 32}"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PointerConsistencyError, match="disagree"):
        validate_pointer_consistency(application)


def test_interrupted_approval_is_recovered_from_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = create_application(tmp_path)
    commit_approved_run(application)
    original_replace = storage._replace_json

    def interrupt_manifest(target: Path, value: dict[str, object]) -> None:
        if target == application.resolve() / "manifest.json":
            raise OSError("simulated interruption")
        original_replace(target, value)

    monkeypatch.setattr(storage, "_replace_json", interrupt_manifest)
    with pytest.raises(OSError, match="simulated interruption"):
        approve_run(
            application,
            RUN_ID,
            {"FACT-PROJECT-001-01": "引用值"},
            approved_at=NOW,
        )
    journal = application / "resume-content" / ".approval-transaction.json"
    assert journal.exists()

    monkeypatch.setattr(storage, "_replace_json", original_replace)
    assert recover_approval(application) is True
    assert not journal.exists()
    assert validate_pointer_consistency(application).status is ContentState.APPROVED
