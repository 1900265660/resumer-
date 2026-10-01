from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from models import (
    AgentReceiptBundleArtifact,
    AgentRole,
    AgentStage,
    ArtifactRecord,
    AuditArtifact,
    AuditDisposition,
    ContentState,
    CurrentPointer,
    DeterministicValidationArtifact,
    ExperienceSelectionArtifact,
    FusionArtifact,
    HrReviewArtifact,
    ReferencedFactDigest,
    ResumeContentSummary,
    RunCheckpointArtifact,
    RunManifestArtifact,
    RunStatus,
    RunStatusRecord,
    RunId,
    SelectionApprovalArtifact,
    StoryPlanArtifact,
    UserApprovalRecord,
)
from rendering import render_resume_markdown
from validators import selection_decision_sha256, validate_run_artifact_completeness


class StorageError(RuntimeError):
    pass


class RunAlreadyExistsError(StorageError):
    pass


class RunIntegrityError(StorageError):
    pass


class PointerConsistencyError(StorageError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_run_id(now: datetime | None = None, suffix: str | None = None) -> str:
    timestamp = now or utc_now()
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise StorageError("run timestamp must include a timezone")
    token = suffix or secrets.token_hex(3)
    candidate = f"cr_{timestamp.astimezone(timezone.utc):%Y%m%dT%H%M%S}_{token}"
    try:
        return TypeAdapter(RunId).validate_python(candidate)
    except ValidationError as error:
        raise StorageError(f"invalid generated run ID: {candidate}") from error


def _json_bytes(value: BaseModel | dict[str, Any]) -> bytes:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json")
    else:
        payload = value
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RunIntegrityError(f"cannot read valid JSON from {path}") from error


def canonical_json_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


def run_status_path(application_dir: Path) -> Path:
    return application_dir.resolve() / "resume-content" / "run-status.jsonl"


def read_run_statuses(application_dir: Path) -> list[RunStatusRecord]:
    path = run_status_path(application_dir)
    if not path.exists():
        return []
    records: list[RunStatusRecord] = []
    try:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                records.append(RunStatusRecord.model_validate_json(line))
            except ValidationError as error:
                raise RunIntegrityError(
                    f"invalid run status record at line {line_number}: {path}"
                ) from error
    except OSError as error:
        raise RunIntegrityError(f"cannot read run status ledger: {path}") from error
    return records


def latest_run_status(
    application_dir: Path, run_id: str
) -> RunStatusRecord | None:
    matching = [
        item for item in read_run_statuses(application_dir) if item.run_id == run_id
    ]
    return matching[-1] if matching else None


def append_run_status(
    application_dir: Path, record: RunStatusRecord
) -> Path:
    path = run_status_path(application_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n"
    try:
        with path.open("a", encoding="utf-8", newline="") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        raise StorageError(f"cannot append run status ledger: {path}") from error
    return path


def _run_is_blocked(application_dir: Path, run_id: str) -> bool:
    status = latest_run_status(application_dir, run_id)
    return bool(
        status
        and status.status
        in {
            RunStatus.SUPERSEDED,
            RunStatus.USER_REJECTED,
            RunStatus.SCHEMA_INVALID,
            RunStatus.REVOKED,
        }
    )


def _safe_relative_path(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise StorageError(f"unsafe artifact path: {value}")
    return candidate


def _replace_json(target: Path, value: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(_json_bytes(value))
    os.replace(temporary, target)


def _write_json_once(target: Path, value: BaseModel | dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _json_bytes(value)
    try:
        with target.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if target.read_bytes() != payload:
            raise StorageError(f"immutable approval record already exists: {target}")


@dataclass
class RunStage:
    application_dir: Path
    run_id: str
    path: Path
    _records: dict[str, ArtifactRecord] = field(default_factory=dict)
    _committed: bool = False

    @property
    def final_path(self) -> Path:
        return self.application_dir / "resume-content" / "runs" / self.run_id

    def write_model(self, relative_path: str, model: BaseModel) -> ArtifactRecord:
        if self._committed:
            raise StorageError("cannot write to a committed run")
        relative = _safe_relative_path(relative_path)
        normalized = relative.as_posix()
        if normalized == "run.json":
            raise StorageError("run.json is written only by commit")
        if normalized in self._records:
            raise StorageError(f"artifact already written: {normalized}")
        model_run_id = getattr(model, "run_id", None)
        if model_run_id != self.run_id:
            raise RunIntegrityError(
                f"artifact run_id {model_run_id!r} does not match {self.run_id}"
            )
        target = self.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = _json_bytes(model)
        target.write_bytes(payload)
        record = ArtifactRecord(
            name=Path(normalized).with_suffix("").as_posix().replace("/", "::"),
            relative_path=normalized,
            sha256=sha256_bytes(payload),
        )
        self._records[normalized] = record
        return record

    def write_text(self, relative_path: str, content: str) -> ArtifactRecord:
        if self._committed:
            raise StorageError("cannot write to a committed run")
        relative = _safe_relative_path(relative_path)
        normalized = relative.as_posix()
        if normalized in self._records or normalized == "run.json":
            raise StorageError(f"artifact already written: {normalized}")
        target = self.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = content.encode("utf-8")
        target.write_bytes(payload)
        record = ArtifactRecord(
            name=Path(normalized).with_suffix("").as_posix().replace("/", "::"),
            relative_path=normalized,
            sha256=sha256_bytes(payload),
        )
        self._records[normalized] = record
        return record

    def artifact_records(self) -> list[ArtifactRecord]:
        return [self._records[key] for key in sorted(self._records)]

    def commit(self, manifest: RunManifestArtifact) -> Path:
        if self._committed:
            raise StorageError("run stage was already committed")
        if manifest.run_id != self.run_id:
            raise RunIntegrityError("run manifest does not match staged run_id")
        expected = {
            item.relative_path: item.model_dump(mode="json")
            for item in self.artifact_records()
        }
        actual = {
            item.relative_path: item.model_dump(mode="json")
            for item in manifest.artifacts
        }
        if expected != actual:
            raise RunIntegrityError("run manifest artifact inventory is incomplete")
        for record in manifest.artifacts:
            artifact_path = self.path / _safe_relative_path(record.relative_path)
            if not artifact_path.is_file():
                raise RunIntegrityError(f"missing staged artifact {record.relative_path}")
            if sha256_bytes(artifact_path.read_bytes()) != record.sha256:
                raise RunIntegrityError(f"artifact hash changed: {record.relative_path}")
        run_path = self.path / "run.json"
        run_path.write_bytes(_json_bytes(manifest))
        if self.final_path.exists():
            raise RunAlreadyExistsError(f"run already exists: {self.run_id}")
        self.final_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(self.path, self.final_path)
        self._committed = True
        return self.final_path


def begin_run(application_dir: Path, run_id: str) -> RunStage:
    application_dir = application_dir.resolve()
    final_path = application_dir / "resume-content" / "runs" / run_id
    if final_path.exists():
        raise RunAlreadyExistsError(f"run already exists: {run_id}")
    staging_root = application_dir / "resume-content" / ".staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    stage_path = staging_root / f"{run_id}_{uuid.uuid4().hex}"
    stage_path.mkdir()
    return RunStage(application_dir=application_dir, run_id=run_id, path=stage_path)


def checkpoint_path(application_dir: Path, run_id: str) -> Path:
    try:
        validated = TypeAdapter(RunId).validate_python(run_id)
    except ValidationError as error:
        raise StorageError(f"invalid checkpoint run ID: {run_id}") from error
    return (
        application_dir.resolve()
        / "resume-content"
        / ".pending"
        / f"{validated}.json"
    )


def save_checkpoint(
    application_dir: Path, checkpoint: RunCheckpointArtifact
) -> Path:
    application_dir = application_dir.resolve()
    final_path = application_dir / "resume-content" / "runs" / checkpoint.run_id
    if final_path.exists():
        raise RunAlreadyExistsError(f"run already exists: {checkpoint.run_id}")
    target = checkpoint_path(application_dir, checkpoint.run_id)
    _replace_json(target, checkpoint.model_dump(mode="json"))
    return target


def load_checkpoint(application_dir: Path, run_id: str) -> RunCheckpointArtifact:
    path = checkpoint_path(application_dir, run_id)
    try:
        return RunCheckpointArtifact.model_validate(_read_json(path))
    except ValidationError as error:
        raise RunIntegrityError(f"invalid run checkpoint: {path}") from error


def remove_checkpoint(application_dir: Path, run_id: str) -> bool:
    path = checkpoint_path(application_dir, run_id)
    if not path.exists():
        return False
    if not path.is_file():
        raise RunIntegrityError(f"checkpoint path is not a file: {path}")
    path.unlink()
    return True


def load_run(application_dir: Path, run_id: str) -> RunManifestArtifact:
    path = application_dir / "resume-content" / "runs" / run_id / "run.json"
    try:
        manifest = RunManifestArtifact.model_validate(_read_json(path))
    except ValidationError as error:
        raise RunIntegrityError(f"invalid run manifest: {path}") from error
    for record in manifest.artifacts:
        artifact = path.parent / _safe_relative_path(record.relative_path)
        if not artifact.is_file() or sha256_bytes(artifact.read_bytes()) != record.sha256:
            raise RunIntegrityError(f"run artifact integrity failure: {record.relative_path}")
    return manifest


def _verify_v15_agent_receipts(
    run_dir: Path,
    manifest: RunManifestArtifact,
    bundle: AgentReceiptBundleArtifact,
) -> None:
    expected: dict[AgentStage, set[str]] = {
        AgentStage.JD_ANALYSIS: {
            canonical_json_sha256(_read_json(run_dir / "jd-analysis.json"))
        },
        AgentStage.CAPABILITY_TRANSFER: {
            canonical_json_sha256(
                _read_json(run_dir / "capability-transfer-map.json")
            )
        },
        AgentStage.EXPERIENCE_SELECTION: {
            canonical_json_sha256(_read_json(run_dir / "experience-selection.json"))
        },
        AgentStage.SELECTION_AUDIT: {
            canonical_json_sha256(_read_json(run_dir / "selection-audit-pre.json"))
        },
        AgentStage.STORY_PLAN: {
            canonical_json_sha256(_read_json(run_dir / "story-plan.json"))
        },
        AgentStage.WRITER: {
            canonical_json_sha256(_read_json(run_dir / "draft-writer.json"))
        },
        AgentStage.DRAFT_AUDIT: {
            canonical_json_sha256(_read_json(run_dir / "draft-quality-audit.json"))
        },
        AgentStage.FUSION: {
            canonical_json_sha256(_read_json(run_dir / "fusion.json"))
        },
        AgentStage.POST_FUSION_AUDIT: {
            canonical_json_sha256(_read_json(run_dir / "audit.json"))
        },
        AgentStage.HR_REVIEW: {
            canonical_json_sha256(_read_json(run_dir / "hr-review.json"))
        },
    }
    if manifest.execution_mode.value == "blind_dual":
        expected[AgentStage.ASU_WRITER] = {
            canonical_json_sha256(_read_json(run_dir / "draft-asu.json"))
        }
    historical_patterns = {
        AgentStage.EXPERIENCE_SELECTION: (
            "history/round-*/experience-selection.json",
        ),
        AgentStage.SELECTION_AUDIT: (
            "history/round-*/selection-audit-pre.json",
        ),
        AgentStage.STORY_PLAN: (
            "history/round-*/story-plan.json",
        ),
        AgentStage.WRITER: (
            "history/round-*/draft-writer.json",
        ),
        AgentStage.ASU_WRITER: (
            "history/round-*/draft-asu.json",
        ),
        AgentStage.DRAFT_AUDIT: (
            "draft-quality-reviews/round-*.json",
            "history/round-*/draft-quality-audit.json",
        ),
        AgentStage.FUSION: (
            "revisions/*/fusion.json",
            "history/round-*/fusion.json",
        ),
        AgentStage.POST_FUSION_AUDIT: (
            "revisions/*/audit.json",
            "history/round-*/audit.json",
        ),
        AgentStage.HR_REVIEW: (
            "hr-reviews/round-*.json",
            "history/round-*/hr-review.json",
        ),
    }
    for stage, patterns in historical_patterns.items():
        for pattern in patterns:
            expected.setdefault(stage, set()).update(
                canonical_json_sha256(_read_json(path))
                for path in run_dir.glob(pattern)
            )
    actual: dict[AgentStage, set[str]] = {}
    roles_by_stage = {
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
    for receipt in bundle.receipts:
        expected_role = roles_by_stage.get(receipt.stage)
        if expected_role is not None and receipt.role is not expected_role:
            raise RunIntegrityError(
                f"schema 1.5 receipt role does not match stage: {receipt.stage.value}"
            )
        actual.setdefault(receipt.stage, set()).add(receipt.output_sha256)
    missing = {
        stage.value: sorted(hashes.difference(actual.get(stage, set())))
        for stage, hashes in expected.items()
        if hashes.difference(actual.get(stage, set()))
    }
    if missing:
        raise RunIntegrityError(
            f"schema 1.5 agent receipts do not cover committed outputs: {missing}"
        )
    unexpected = {
        stage.value: sorted(hashes.difference(expected.get(stage, set())))
        for stage, hashes in actual.items()
        if hashes.difference(expected.get(stage, set()))
    }
    if unexpected:
        raise RunIntegrityError(
            f"schema 1.5 agent receipts reference uncommitted outputs: {unexpected}"
        )


def validate_v15_approval_evidence(
    application_dir: Path,
    manifest: RunManifestArtifact,
    user_approval: UserApprovalRecord,
) -> None:
    if manifest.schema_version != "1.5":
        raise StorageError(
            "new approvals require a complete schema 1.5 run; legacy runs are read-only"
        )
    if manifest.producer != "official_coordinator":
        raise RunIntegrityError("schema 1.5 run lacks official coordinator provenance")
    if _run_is_blocked(application_dir, manifest.run_id):
        raise StorageError("revoked or invalid run cannot be approved")
    run_dir = (
        application_dir.resolve()
        / "resume-content"
        / "runs"
        / manifest.run_id
    )
    incomplete = validate_run_artifact_completeness(run_dir)
    if incomplete:
        raise RunIntegrityError(
            "schema 1.5 run is incomplete: "
            f"{[item.field_path for item in incomplete]}"
        )
    required = {
        "experience-selection.json",
        "selection-user-approval.json",
        "story-plan.json",
        "quality-gate.json",
        "agent-receipts.json",
        "hr-review.json",
        "content-master.md",
    }
    missing = sorted(name for name in required if not (run_dir / name).is_file())
    if missing:
        raise RunIntegrityError(
            f"schema 1.5 approval evidence is incomplete: {missing}"
        )
    try:
        selection = ExperienceSelectionArtifact.model_validate(
            _read_json(run_dir / "experience-selection.json")
        )
        selection_approval = SelectionApprovalArtifact.model_validate(
            _read_json(run_dir / "selection-user-approval.json")
        )
        story_plan = StoryPlanArtifact.model_validate(
            _read_json(run_dir / "story-plan.json")
        )
        fusion = FusionArtifact.model_validate(_read_json(run_dir / "fusion.json"))
        hr_review = HrReviewArtifact.model_validate(
            _read_json(run_dir / "hr-review.json")
        )
        quality_gate = DeterministicValidationArtifact.model_validate(
            _read_json(run_dir / "quality-gate.json")
        )
        receipt_bundle = AgentReceiptBundleArtifact.model_validate(
            _read_json(run_dir / "agent-receipts.json")
        )
    except ValidationError as error:
        raise RunIntegrityError("schema 1.5 approval evidence is invalid") from error
    if not quality_gate.passed:
        raise StorageError("deterministic quality gate did not pass")
    selection_sha256 = selection_decision_sha256(selection)
    if (
        selection_approval.experience_selection_sha256 != selection_sha256
        or story_plan.experience_selection_sha256 != selection_sha256
        or selection_approval.story_plan_sha256
        != canonical_json_sha256(story_plan.model_dump(mode="json"))
    ):
        raise RunIntegrityError(
            "selection approval or story plan does not match final selection"
        )
    if quality_gate.candidate_sha256 != canonical_json_sha256(
        fusion.model_dump(mode="json")
    ):
        raise RunIntegrityError("quality gate candidate hash does not match fusion")
    if quality_gate.story_plan_sha256 != canonical_json_sha256(
        story_plan.model_dump(mode="json")
    ):
        raise RunIntegrityError("quality gate story-plan hash does not match")
    rendered_content = render_resume_markdown(fusion).encode("utf-8")
    if (run_dir / "content-master.md").read_bytes() != rendered_content:
        raise RunIntegrityError("content-master.md does not match the validated fusion")
    if _read_json(run_dir / "quality-gate.json") != _read_json(
        run_dir / "validation.json"
    ):
        raise RunIntegrityError("quality-gate.json and validation.json disagree")
    fusion_bullet_ids = {
        bullet.bullet_id
        for section in fusion.sections
        for entry in section.entries
        for bullet in entry.bullets
    }
    cited_bullet_ids = {
        bullet_id
        for dimension in (
            hr_review.role_fit,
            hr_review.narrative_completeness,
            hr_review.evidence_specificity,
            hr_review.decision_readiness,
            hr_review.credibility,
            hr_review.content_fullness,
        )
        if dimension is not None
        for bullet_id in dimension.evidence_bullet_ids
    }
    cited_bullet_ids.update(
        bullet_id
        for review in hr_review.experience_reviews
        for bullet_id in review.evidence_bullet_ids
    )
    if not cited_bullet_ids or not cited_bullet_ids.issubset(fusion_bullet_ids):
        raise RunIntegrityError("HR evidence references unknown or no final bullets")
    _verify_v15_agent_receipts(run_dir, manifest, receipt_bundle)
    if user_approval.run_id != manifest.run_id:
        raise StorageError("user approval record targets another run")
    content_sha256 = sha256_bytes((run_dir / "content-master.md").read_bytes())
    if user_approval.content_sha256 != content_sha256:
        raise StorageError("user approval record does not match final content")


def _approval_payloads(
    application_dir: Path,
    run_id: str,
    referenced_fact_values: dict[str, str],
    approved_at: datetime,
    transaction_id: str,
    user_approval: UserApprovalRecord | None = None,
) -> tuple[CurrentPointer, dict[str, Any]]:
    if not referenced_fact_values:
        raise StorageError("approval requires referenced fact values")
    manifest_path = application_dir / "manifest.json"
    if not manifest_path.is_file():
        raise StorageError(f"application manifest is missing: {manifest_path}")
    job_manifest = _read_json(manifest_path)
    pointer = CurrentPointer(
        schema_version="1.5" if user_approval else "1.4",
        status=ContentState.APPROVED,
        approved_run_id=run_id,
        run_relative_path=f"resume-content/runs/{run_id}",
        approved_at=approved_at,
        updated_at=approved_at,
        transaction_id=transaction_id,
        referenced_facts=[
            ReferencedFactDigest(fact_id=fact_id, value_sha256=sha256_text(value))
            for fact_id, value in sorted(referenced_fact_values.items())
        ],
        user_approval_id=(
            user_approval.user_approval_id if user_approval else None
        ),
        content_sha256=(user_approval.content_sha256 if user_approval else None),
    )
    summary = ResumeContentSummary(
        status=pointer.status,
        approved_run_id=run_id,
        updated_at=approved_at,
        transaction_id=transaction_id,
    )
    job_manifest["resume_content"] = summary.model_dump(mode="json")
    return pointer, job_manifest


def approve_run(
    application_dir: Path,
    run_id: str,
    referenced_fact_values: dict[str, str],
    approved_at: datetime | None = None,
    user_approval: UserApprovalRecord | None = None,
) -> CurrentPointer:
    application_dir = application_dir.resolve()
    recover_approval(application_dir)
    manifest = load_run(application_dir, run_id)
    review_ready_states = (
        {ContentState.READY_FOR_USER_REVIEW, ContentState.APPROVED}
        if manifest.schema_version == "1.5"
        else {ContentState.NEEDS_CONTENT_REVIEW, ContentState.APPROVED}
    )
    if manifest.state not in review_ready_states:
        raise StorageError("only a review-ready run can become current")
    artifact_paths = {item.relative_path for item in manifest.artifacts}
    if "audit.json" not in artifact_paths:
        raise RunIntegrityError("approved run manifest does not inventory audit.json")
    audit_path = application_dir / "resume-content" / "runs" / run_id / "audit.json"
    try:
        audit = AuditArtifact.model_validate(_read_json(audit_path))
    except ValidationError as error:
        raise RunIntegrityError("approved run has an invalid audit artifact") from error
    if (
        audit.run_id != manifest.run_id
        or audit.schema_version != manifest.schema_version
        or audit.source_digests != manifest.source_digests
    ):
        raise RunIntegrityError("approved run audit envelope does not match run.json")
    if len(audit.revisions) != manifest.revision_count:
        raise RunIntegrityError("approved run audit revision count does not match run.json")
    if audit.disposition is not AuditDisposition.PASSED:
        raise StorageError("run audit did not pass")
    if manifest.schema_version in {"1.3", "1.4", "1.5"}:
        if "hr-review.json" not in artifact_paths:
            raise RunIntegrityError(
                "schema 1.3+ run manifest does not inventory hr-review.json"
            )
        hr_review_path = (
            application_dir
            / "resume-content"
            / "runs"
            / run_id
            / "hr-review.json"
        )
        try:
            hr_review = HrReviewArtifact.model_validate(_read_json(hr_review_path))
        except (ValidationError, OSError, json.JSONDecodeError) as error:
            raise RunIntegrityError(
                "schema 1.3+ approval requires a valid HR review artifact"
            ) from error
        if (
            hr_review.run_id != manifest.run_id
            or hr_review.schema_version != manifest.schema_version
            or hr_review.source_digests != manifest.source_digests
        ):
            raise RunIntegrityError(
                "schema 1.3+ HR review envelope does not match run.json"
            )
        if hr_review.revision_round != manifest.revision_count:
            raise RunIntegrityError(
                "schema 1.3+ HR review revision round does not match run.json"
            )
        if not hr_review.passed:
            raise StorageError("run HR decision gate did not pass")
    if manifest.schema_version != "1.5":
        raise StorageError(
            "new approvals require schema 1.5; schema 1.0-1.4 runs are read-only"
        )
    if user_approval is None:
        raise StorageError(
            "schema 1.5 approval requires an explicit user approval record"
        )
    validate_v15_approval_evidence(application_dir, manifest, user_approval)
    approval_record_path = (
        application_dir
        / "resume-content"
        / "approvals"
        / f"{user_approval.user_approval_id}.json"
    )
    _write_json_once(approval_record_path, user_approval)
    timestamp = (
        user_approval.approved_at
        if user_approval is not None
        else approved_at or utc_now()
    )
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise StorageError("approval timestamp must include a timezone")
    transaction_id = f"approval_{uuid.uuid4().hex}"
    pointer, job_manifest = _approval_payloads(
        application_dir,
        run_id,
        referenced_fact_values,
        timestamp,
        transaction_id,
        user_approval,
    )
    content_root = application_dir / "resume-content"
    journal_path = content_root / ".approval-transaction.json"
    journal = {
        "transaction_id": transaction_id,
        "current": pointer.model_dump(mode="json"),
        "manifest": job_manifest,
    }
    _replace_json(journal_path, journal)
    _replace_json(content_root / "current.json", journal["current"])
    _replace_json(application_dir / "manifest.json", job_manifest)
    journal_path.unlink()
    validate_pointer_consistency(application_dir)
    append_run_status(
        application_dir,
        RunStatusRecord(
            run_id=run_id,
            content_sha256=pointer.content_sha256,
            status=RunStatus.APPROVED,
            reason_code="USER_APPROVED",
            recorded_at=timestamp,
        ),
    )
    return pointer


def clear_current_pointer(
    application_dir: Path,
    *,
    updated_at: datetime | None = None,
) -> CurrentPointer:
    application_dir = application_dir.resolve()
    timestamp = updated_at or utc_now()
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise StorageError("pointer timestamp must include a timezone")
    transaction_id = f"approval_{uuid.uuid4().hex}"
    pointer = CurrentPointer(
        schema_version="1.5",
        status=ContentState.NO_APPROVED_CONTENT,
        updated_at=timestamp,
        transaction_id=transaction_id,
    )
    manifest_path = application_dir / "manifest.json"
    job_manifest = _read_json(manifest_path)
    summary = ResumeContentSummary(
        status=ContentState.NO_APPROVED_CONTENT,
        approved_run_id=None,
        updated_at=timestamp,
        transaction_id=transaction_id,
    )
    job_manifest["resume_content"] = summary.model_dump(mode="json")
    content_root = application_dir / "resume-content"
    journal_path = content_root / ".approval-transaction.json"
    journal = {
        "transaction_id": transaction_id,
        "current": pointer.model_dump(mode="json"),
        "manifest": job_manifest,
    }
    _replace_json(journal_path, journal)
    _replace_json(content_root / "current.json", journal["current"])
    _replace_json(manifest_path, job_manifest)
    journal_path.unlink()
    validate_pointer_consistency(application_dir)
    return pointer


def revoke_run(
    application_dir: Path,
    record: RunStatusRecord,
) -> bool:
    application_dir = application_dir.resolve()
    if record.status not in {
        RunStatus.USER_REJECTED,
        RunStatus.SCHEMA_INVALID,
        RunStatus.REVOKED,
    }:
        raise StorageError("revoke_run requires a blocking run status")
    run_dir = application_dir / "resume-content" / "runs" / record.run_id
    content_path = run_dir / "content-master.md"
    if content_path.is_file():
        actual_sha256 = sha256_bytes(content_path.read_bytes())
        if record.content_sha256 and record.content_sha256 != actual_sha256:
            raise StorageError("run status content hash does not match immutable run")
    append_run_status(application_dir, record)
    current_path = application_dir / "resume-content" / "current.json"
    if current_path.is_file():
        raw_pointer = _read_json(current_path)
        try:
            pointer = CurrentPointer.model_validate(raw_pointer)
            current_run_id = pointer.approved_run_id
        except ValidationError:
            current_run_id = raw_pointer.get("approved_run_id") or raw_pointer.get(
                "run_id"
            )
        if current_run_id == record.run_id:
            clear_current_pointer(application_dir, updated_at=record.recorded_at)
            return True
    return False


def recover_approval(application_dir: Path) -> bool:
    application_dir = application_dir.resolve()
    journal_path = application_dir / "resume-content" / ".approval-transaction.json"
    if not journal_path.is_file():
        return False
    journal = _read_json(journal_path)
    if set(journal) != {"transaction_id", "current", "manifest"}:
        raise PointerConsistencyError("approval transaction journal is malformed")
    try:
        pointer = CurrentPointer.model_validate(journal["current"])
        summary = ResumeContentSummary.model_validate(
            journal["manifest"].get("resume_content")
        )
    except ValidationError as error:
        raise PointerConsistencyError("approval transaction journal is invalid") from error
    if pointer.transaction_id != journal["transaction_id"]:
        raise PointerConsistencyError("journal transaction IDs do not match")
    if summary.transaction_id != journal["transaction_id"]:
        raise PointerConsistencyError("manifest journal transaction IDs do not match")
    _replace_json(application_dir / "resume-content" / "current.json", journal["current"])
    _replace_json(application_dir / "manifest.json", journal["manifest"])
    journal_path.unlink()
    return True


def validate_pointer_consistency(application_dir: Path) -> CurrentPointer:
    application_dir = application_dir.resolve()
    current_path = application_dir / "resume-content" / "current.json"
    manifest_path = application_dir / "manifest.json"
    try:
        pointer = CurrentPointer.model_validate(_read_json(current_path))
        summary = ResumeContentSummary.model_validate(
            _read_json(manifest_path).get("resume_content")
        )
    except ValidationError as error:
        raise PointerConsistencyError("current pointer or manifest summary is invalid") from error
    comparable = (
        pointer.status,
        pointer.approved_run_id,
        pointer.updated_at,
        pointer.transaction_id,
    )
    summary_values = (
        summary.status,
        summary.approved_run_id,
        summary.updated_at,
        summary.transaction_id,
    )
    if comparable != summary_values:
        raise PointerConsistencyError("current pointer and manifest summary disagree")
    if pointer.status is ContentState.NO_APPROVED_CONTENT:
        return pointer
    assert pointer.approved_run_id is not None
    if _run_is_blocked(application_dir, pointer.approved_run_id):
        raise PointerConsistencyError("current pointer references a revoked or invalid run")
    load_run(application_dir, pointer.approved_run_id)
    if pointer.schema_version == "1.5":
        assert pointer.user_approval_id is not None
        approval_path = (
            application_dir
            / "resume-content"
            / "approvals"
            / f"{pointer.user_approval_id}.json"
        )
        try:
            approval = UserApprovalRecord.model_validate(_read_json(approval_path))
        except (ValidationError, RunIntegrityError) as error:
            raise PointerConsistencyError("user approval record is invalid") from error
        if (
            approval.run_id != pointer.approved_run_id
            or approval.content_sha256 != pointer.content_sha256
        ):
            raise PointerConsistencyError(
                "user approval record does not match current pointer"
            )
        content_path = (
            application_dir
            / "resume-content"
            / "runs"
            / pointer.approved_run_id
            / "content-master.md"
        )
        if sha256_bytes(content_path.read_bytes()) != pointer.content_sha256:
            raise PointerConsistencyError("current content hash no longer matches approval")
    return pointer


def refresh_stale_status(
    application_dir: Path,
    current_fact_values: dict[str, str],
    updated_at: datetime | None = None,
) -> bool:
    application_dir = application_dir.resolve()
    recover_approval(application_dir)
    pointer = validate_pointer_consistency(application_dir)
    if pointer.status is ContentState.NO_APPROVED_CONTENT:
        return False
    changed = any(
        fact.fact_id not in current_fact_values
        or sha256_text(current_fact_values[fact.fact_id]) != fact.value_sha256
        for fact in pointer.referenced_facts
    )
    if not changed or pointer.status is ContentState.STALE:
        return changed
    timestamp = updated_at or utc_now()
    transaction_id = f"approval_{uuid.uuid4().hex}"
    stale_pointer = pointer.model_copy(
        update={
            "status": ContentState.STALE,
            "updated_at": timestamp,
            "transaction_id": transaction_id,
        }
    )
    job_manifest = _read_json(application_dir / "manifest.json")
    summary = ResumeContentSummary(
        status=ContentState.STALE,
        approved_run_id=pointer.approved_run_id,
        updated_at=timestamp,
        transaction_id=transaction_id,
    )
    job_manifest["resume_content"] = summary.model_dump(mode="json")
    journal_path = application_dir / "resume-content" / ".approval-transaction.json"
    journal = {
        "transaction_id": transaction_id,
        "current": stale_pointer.model_dump(mode="json"),
        "manifest": job_manifest,
    }
    _replace_json(journal_path, journal)
    _replace_json(application_dir / "resume-content" / "current.json", journal["current"])
    _replace_json(application_dir / "manifest.json", job_manifest)
    journal_path.unlink()
    validate_pointer_consistency(application_dir)
    return True
