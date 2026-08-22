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
    ArtifactRecord,
    AuditArtifact,
    AuditDisposition,
    ContentState,
    CurrentPointer,
    ReferencedFactDigest,
    ResumeContentSummary,
    RunManifestArtifact,
    RunId,
)


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


def _approval_payloads(
    application_dir: Path,
    run_id: str,
    referenced_fact_values: dict[str, str],
    approved_at: datetime,
    transaction_id: str,
) -> tuple[CurrentPointer, dict[str, Any]]:
    if not referenced_fact_values:
        raise StorageError("approval requires referenced fact values")
    manifest_path = application_dir / "manifest.json"
    if not manifest_path.is_file():
        raise StorageError(f"application manifest is missing: {manifest_path}")
    job_manifest = _read_json(manifest_path)
    pointer = CurrentPointer(
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
) -> CurrentPointer:
    application_dir = application_dir.resolve()
    recover_approval(application_dir)
    manifest = load_run(application_dir, run_id)
    if manifest.state not in {
        ContentState.NEEDS_CONTENT_REVIEW,
        ContentState.APPROVED,
    }:
        raise StorageError("only a review-ready run can become current")
    audit_path = application_dir / "resume-content" / "runs" / run_id / "audit.json"
    try:
        audit = AuditArtifact.model_validate(_read_json(audit_path))
    except ValidationError as error:
        raise RunIntegrityError("approved run has an invalid audit artifact") from error
    if audit.disposition is not AuditDisposition.PASSED:
        raise StorageError("run audit did not pass")
    timestamp = approved_at or utc_now()
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise StorageError("approval timestamp must include a timezone")
    transaction_id = f"approval_{uuid.uuid4().hex}"
    pointer, job_manifest = _approval_payloads(
        application_dir,
        run_id,
        referenced_fact_values,
        timestamp,
        transaction_id,
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
    return pointer


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
    load_run(application_dir, pointer.approved_run_id)
    return pointer


def refresh_stale_status(
    application_dir: Path,
    current_fact_values: dict[str, str],
    updated_at: datetime | None = None,
) -> bool:
    application_dir = application_dir.resolve()
    recover_approval(application_dir)
    pointer = validate_pointer_consistency(application_dir)
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
