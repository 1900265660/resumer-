from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from typing import Any


class ExemplarLibraryError(RuntimeError):
    pass


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _required_string(value: dict[str, Any], field: str, context: str) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item.strip():
        raise ExemplarLibraryError(f"{context} missing non-empty string: {field}")
    return item.strip()


def _required_string_list(
    value: dict[str, Any], field: str, context: str
) -> tuple[str, ...]:
    items = value.get(field)
    if (
        not isinstance(items, list)
        or not items
        or any(not isinstance(item, str) or not item.strip() for item in items)
    ):
        raise ExemplarLibraryError(f"{context} missing non-empty string list: {field}")
    normalized = tuple(item.strip() for item in items)
    if len(normalized) != len(set(normalized)):
        raise ExemplarLibraryError(f"{context} contains duplicate values: {field}")
    return normalized


@dataclass(frozen=True)
class ResumeExemplarMatch:
    exemplar_id: str
    title: str
    role_family: str
    matched_keywords: tuple[str, ...]
    content_sha256: str
    content_snapshot: str
    approved_at: str
    source_run_id: str
    source_fact_snapshot_sha256: str
    allowed_uses: tuple[str, ...]
    forbidden_uses: tuple[str, ...]
    quality: dict[str, Any]
    role_track: str | None = None

    def packet(self) -> dict[str, Any]:
        return {
            "exemplar_id": self.exemplar_id,
            "title": self.title,
            "role_family": self.role_family,
            "role_track": self.role_track,
            "matched_keywords": list(self.matched_keywords),
            "approved_at": self.approved_at,
            "source_run_id": self.source_run_id,
            "source_fact_snapshot_sha256": self.source_fact_snapshot_sha256,
            "content_sha256": self.content_sha256,
            "content_snapshot": self.content_snapshot,
            "quality": self.quality,
            "allowed_uses": list(self.allowed_uses),
            "forbidden_uses": list(self.forbidden_uses),
            "fact_source": False,
            "selection_approval": False,
        }


def _load_entry(
    metadata_path: Path,
    *,
    role_family: str,
    role_track: str | None,
    normalized_jd: str,
) -> ResumeExemplarMatch | None:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExemplarLibraryError(f"invalid exemplar metadata: {metadata_path}") from error
    context = str(metadata_path)
    metadata_schema = metadata.get("schema_version")
    if metadata_schema not in {"1.0", "1.1"}:
        raise ExemplarLibraryError(f"unsupported exemplar schema: {metadata_path}")
    if metadata.get("status") != "approved_reference":
        return None
    if _required_string(metadata, "role_family", context) != role_family:
        return None
    metadata_role_track = metadata.get("role_track")
    if metadata_schema == "1.0" and "role_track" in metadata:
        raise ExemplarLibraryError(f"{context} schema 1.0 must not define role_track")
    if metadata_role_track is not None and (
        not isinstance(metadata_role_track, str) or not metadata_role_track.strip()
    ):
        raise ExemplarLibraryError(f"{context} has invalid role_track")
    normalized_track = metadata_role_track.strip() if metadata_role_track else None
    if normalized_track != role_track:
        return None
    exemplar_id = _required_string(metadata, "exemplar_id", context)
    if exemplar_id != metadata_path.parent.name:
        raise ExemplarLibraryError(
            f"exemplar_id must match directory name: {metadata_path}"
        )
    match = metadata.get("match")
    if not isinstance(match, dict):
        raise ExemplarLibraryError(f"{context} missing match object")
    keywords = _required_string_list(match, "keywords", context)
    minimum = match.get("minimum_keyword_matches")
    if not isinstance(minimum, int) or minimum < 1 or minimum > len(keywords):
        raise ExemplarLibraryError(f"{context} has invalid minimum_keyword_matches")
    matched = tuple(keyword for keyword in keywords if keyword.casefold() in normalized_jd)
    if len(matched) < minimum:
        return None

    source = metadata.get("source")
    if not isinstance(source, dict):
        raise ExemplarLibraryError(f"{context} missing source object")
    content_path = metadata_path.parent / "content-master.md"
    if not content_path.is_file():
        raise ExemplarLibraryError(f"missing exemplar content: {content_path}")
    content_bytes = content_path.read_bytes()
    content_hash = _sha256(content_bytes)
    expected_hash = _required_string(source, "content_sha256", context).lower()
    if content_hash != expected_hash:
        raise ExemplarLibraryError(
            f"exemplar content hash mismatch: {content_path}"
        )
    fact_hash = _required_string(source, "fact_snapshot_sha256", context).lower()
    if len(fact_hash) != 64 or any(character not in "0123456789abcdef" for character in fact_hash):
        raise ExemplarLibraryError(f"{context} has invalid fact_snapshot_sha256")
    quality = metadata.get("quality")
    if not isinstance(quality, dict):
        raise ExemplarLibraryError(f"{context} missing quality object")
    if (
        quality.get("truth_passed") is not True
        or quality.get("audit_disposition") != "passed"
        or quality.get("hr_recommendation") != "strong_push"
        or not isinstance(quality.get("hr_overall_score"), (int, float))
        or float(quality["hr_overall_score"]) < 8.5
    ):
        raise ExemplarLibraryError(
            f"{context} does not meet exemplar truth/audit/HR quality gates"
        )
    approved_at = _required_string(metadata, "approved_at", context)
    try:
        approved_time = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ExemplarLibraryError(f"{context} has invalid approved_at") from error
    if approved_time.tzinfo is None or approved_time.utcoffset() is None:
        raise ExemplarLibraryError(f"{context} approved_at must include timezone")
    source_run_id = _required_string(source, "run_id", context)
    if not re.fullmatch(r"cr_[0-9]{8}T[0-9]{6}_[a-z0-9]{6}", source_run_id):
        raise ExemplarLibraryError(f"{context} has invalid source run_id")
    return ResumeExemplarMatch(
        exemplar_id=exemplar_id,
        title=_required_string(metadata, "title", context),
        role_family=role_family,
        role_track=role_track,
        matched_keywords=matched,
        content_sha256=content_hash,
        content_snapshot=content_bytes.decode("utf-8-sig"),
        approved_at=approved_at,
        source_run_id=source_run_id,
        source_fact_snapshot_sha256=fact_hash,
        allowed_uses=_required_string_list(metadata, "allowed_uses", context),
        forbidden_uses=_required_string_list(metadata, "forbidden_uses", context),
        quality=quality,
    )


def load_matching_resume_exemplars(
    repo_root: Path,
    *,
    role_family: str,
    role_track: str | None = None,
    jd_text: str,
    limit: int = 2,
) -> tuple[ResumeExemplarMatch, ...]:
    if limit < 1:
        raise ExemplarLibraryError("exemplar match limit must be positive")
    library_root = repo_root / "profile" / "resume-exemplars"
    if not library_root.is_dir():
        return ()
    normalized_jd = jd_text.casefold()
    matches = []
    for metadata_path in sorted(library_root.glob("*/metadata.json")):
        match = _load_entry(
            metadata_path,
            role_family=role_family,
            role_track=role_track,
            normalized_jd=normalized_jd,
        )
        if match is not None:
            matches.append(match)
    matches.sort(
        key=lambda item: (
            -len(item.matched_keywords),
            -float(item.quality.get("hr_overall_score", 0)),
            item.exemplar_id,
        )
    )
    return tuple(matches[:limit])


def exemplar_bundle_sha256(
    method_card_bytes: bytes,
    exemplars: tuple[ResumeExemplarMatch, ...],
) -> str:
    if not exemplars:
        return _sha256(method_card_bytes)
    frozen = [
        {
            "exemplar_id": item.exemplar_id,
            "role_family": item.role_family,
            "role_track": item.role_track,
            "content_sha256": item.content_sha256,
            "matched_keywords": list(item.matched_keywords),
            "allowed_uses": list(item.allowed_uses),
            "forbidden_uses": list(item.forbidden_uses),
        }
        for item in exemplars
    ]
    payload = json.dumps(
        frozen,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256(method_card_bytes + b"\n--resume-exemplars--\n" + payload)
