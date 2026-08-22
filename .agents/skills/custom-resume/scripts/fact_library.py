from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


METADATA_RE = re.compile(r" ?<!--\s*(?P<body>.*?)\s*-->\s*$")
H2_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$")
H3_RE = re.compile(r"^###\s+(?P<title>.+?)\s*$")
BULLET_RE = re.compile(r"^-\s+\S")
ORDERED_RE = re.compile(r"^\d+\.\s+\S")
EXPERIENCE_ID_RE = re.compile(r"^EXP-(?P<category>[A-Z]+)-(?P<number>\d{3})$")
FACT_ID_RE = re.compile(
    r"^FACT-(?P<category>[A-Z]+)-(?P<experience>\d{3})-(?P<number>\d{2})$"
)
ALLOWED_METADATA_KEYS = {
    "experience_id",
    "fact_id",
    "provenance",
    "confirmed_at",
    "source_run",
    "estimate_basis",
}
SECTION_CATEGORIES = {
    "基本信息": "BASIC",
    "教育": "EDU",
    "工作经历": "WORK",
    "项目经历": "PROJECT",
    "技能与兴趣": "SKILL",
}
SYNTHETIC_SECTION_EXPERIENCES = {"BASIC", "SKILL"}
HEADING_EXPERIENCES = {"WORK", "PROJECT"}


class FactLibraryError(ValueError):
    pass


class SourceChangedError(FactLibraryError):
    pass


@dataclass(frozen=True)
class MigrationReport:
    source_path: str
    source_sha256: str
    preview_sha256: str
    generated_at: str
    changed: bool
    experience_count: int
    fact_count: int
    inserted_experience_ids: int
    inserted_fact_ids: int
    body_preserved: bool


@dataclass(frozen=True)
class FactRecord:
    fact_id: str
    experience_id: str
    value: str
    provenance: str
    line_number: int
    metadata: dict[str, str]


@dataclass(frozen=True)
class ExperienceRecord:
    experience_id: str
    category: str
    heading: str
    immutable_tokens: tuple[str, ...]
    facts: tuple[FactRecord, ...]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_utf8(path: Path) -> tuple[str, bytes]:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig"), raw
    except UnicodeDecodeError as error:
        raise FactLibraryError(f"fact library must be UTF-8: {path}") from error


def split_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n") or line.endswith("\r"):
        return line[:-1], line[-1]
    return line, ""


def parse_metadata(line_body: str, line_number: int) -> tuple[str, dict[str, str]]:
    match = METADATA_RE.search(line_body)
    if not match:
        if "<!--" in line_body or "-->" in line_body:
            raise FactLibraryError(f"line {line_number}: damaged inline metadata")
        return line_body, {}
    clean = line_body[: match.start()]
    metadata: dict[str, str] = {}
    for item in match.group("body").split(";"):
        if ":" not in item:
            raise FactLibraryError(f"line {line_number}: malformed metadata item")
        key, value = (part.strip() for part in item.split(":", 1))
        if key not in ALLOWED_METADATA_KEYS:
            raise FactLibraryError(f"line {line_number}: unknown metadata key {key}")
        if not value:
            raise FactLibraryError(f"line {line_number}: empty metadata value for {key}")
        if key in metadata:
            raise FactLibraryError(f"line {line_number}: duplicate metadata key {key}")
        metadata[key] = value
    return clean, metadata


def strip_metadata(text: str) -> str:
    stripped: list[str] = []
    for line_number, line in enumerate(text.splitlines(keepends=True), start=1):
        body, ending = split_line_ending(line)
        clean, _ = parse_metadata(body, line_number)
        stripped.append(clean + ending)
    return "".join(stripped)


def format_metadata(metadata: dict[str, str]) -> str:
    preferred_order = [
        "experience_id",
        "fact_id",
        "provenance",
        "confirmed_at",
        "source_run",
        "estimate_basis",
    ]
    body = "; ".join(
        f"{key}: {metadata[key]}" for key in preferred_order if key in metadata
    )
    return f" <!-- {body} -->"


def validate_metadata(
    metadata: dict[str, str],
    line_number: int,
    experience_ids: set[str],
    fact_ids: set[str],
) -> None:
    experience_id = metadata.get("experience_id")
    fact_id = metadata.get("fact_id")
    if experience_id:
        if not EXPERIENCE_ID_RE.fullmatch(experience_id):
            raise FactLibraryError(f"line {line_number}: invalid experience_id")
        if experience_id in experience_ids:
            raise FactLibraryError(
                f"line {line_number}: duplicate experience_id {experience_id}"
            )
        experience_ids.add(experience_id)
    if fact_id:
        if not FACT_ID_RE.fullmatch(fact_id):
            raise FactLibraryError(f"line {line_number}: invalid fact_id")
        if fact_id in fact_ids:
            raise FactLibraryError(f"line {line_number}: duplicate fact_id {fact_id}")
        fact_ids.add(fact_id)
        provenance = metadata.get("provenance")
        if provenance not in {"observed", "accepted_estimate"}:
            raise FactLibraryError(
                f"line {line_number}: fact_id requires a valid provenance"
            )
        estimate_keys = {"confirmed_at", "source_run", "estimate_basis"}
        if provenance == "accepted_estimate" and not estimate_keys.issubset(metadata):
            raise FactLibraryError(
                f"line {line_number}: accepted_estimate metadata is incomplete"
            )
        if provenance == "observed" and estimate_keys.intersection(metadata):
            raise FactLibraryError(
                f"line {line_number}: observed fact cannot contain estimate metadata"
            )
    elif {"provenance", "confirmed_at", "source_run", "estimate_basis"}.intersection(
        metadata
    ):
        raise FactLibraryError(
            f"line {line_number}: provenance metadata requires fact_id"
        )


def next_id(category: str, used: set[str], prefix: str, width: int) -> str:
    number = 1
    while True:
        candidate = f"{prefix}-{category}-{number:0{width}d}"
        if candidate not in used:
            return candidate
        number += 1


def next_fact_id(experience_id: str, used: set[str]) -> str:
    match = EXPERIENCE_ID_RE.fullmatch(experience_id)
    if not match:
        raise FactLibraryError(f"invalid current experience_id {experience_id}")
    prefix = f"FACT-{match.group('category')}-{match.group('number')}"
    number = 1
    while True:
        candidate = f"{prefix}-{number:02d}"
        if candidate not in used:
            return candidate
        number += 1


def assert_fact_belongs_to_experience(
    fact_id: str, experience_id: str, line_number: int
) -> None:
    fact_match = FACT_ID_RE.fullmatch(fact_id)
    experience_match = EXPERIENCE_ID_RE.fullmatch(experience_id)
    if not fact_match or not experience_match:
        raise FactLibraryError(f"line {line_number}: invalid fact/experience reference")
    if (
        fact_match.group("category") != experience_match.group("category")
        or fact_match.group("experience") != experience_match.group("number")
    ):
        raise FactLibraryError(
            f"line {line_number}: fact_id does not belong to {experience_id}"
        )


def _preflight_metadata(lines: Iterable[str]) -> tuple[set[str], set[str]]:
    experience_ids: set[str] = set()
    fact_ids: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        body, _ = split_line_ending(line)
        _, metadata = parse_metadata(body, line_number)
        validate_metadata(metadata, line_number, experience_ids, fact_ids)
    return experience_ids, fact_ids


def _clean_list_value(value: str) -> str:
    if BULLET_RE.match(value):
        return value[2:].strip()
    if ORDERED_RE.match(value):
        return re.sub(r"^\d+\.\s+", "", value).strip()
    return value.strip()


def _immutable_tokens(category: str, heading: str) -> tuple[str, ...]:
    if category in HEADING_EXPERIENCES:
        return tuple(part.strip() for part in heading.split("｜") if part.strip())
    if category == "EDU":
        parts = [part.strip() for part in re.split(r"[，,]", heading) if part.strip()]
        tokens: list[str] = []
        if parts:
            tokens.append(parts[0])
        if len(parts) >= 3:
            tokens.append(parts[2])
        date = re.search(r"\d{4}/\d{2}\s*[–—~-]\s*(?:\d{4}/\d{2}|至今)", heading)
        if date:
            tokens.append(date.group(0))
        return tuple(tokens)
    return ()


def parse_fact_records(source_text: str) -> tuple[dict[str, ExperienceRecord], dict[str, FactRecord]]:
    lines = source_text.splitlines(keepends=True)
    _preflight_metadata(lines)
    current_category: str | None = None
    current_experience_id: str | None = None
    headings: dict[str, tuple[str, str, tuple[str, ...]]] = {}
    facts_by_experience: dict[str, list[FactRecord]] = {}
    facts: dict[str, FactRecord] = {}

    for line_number, line in enumerate(lines, start=1):
        body, _ = split_line_ending(line)
        clean, metadata = parse_metadata(body, line_number)
        h2 = H2_RE.fullmatch(clean)
        h3 = H3_RE.fullmatch(clean)
        if h2:
            current_category = SECTION_CATEGORIES.get(h2.group("title"))
            current_experience_id = metadata.get("experience_id")
            if current_experience_id:
                heading = h2.group("title")
                headings[current_experience_id] = (
                    current_category or "UNKNOWN",
                    heading,
                    _immutable_tokens(current_category or "UNKNOWN", heading),
                )
        elif h3 and current_category in HEADING_EXPERIENCES:
            current_experience_id = metadata.get("experience_id")
            if current_experience_id:
                heading = h3.group("title")
                headings[current_experience_id] = (
                    current_category,
                    heading,
                    _immutable_tokens(current_category, heading),
                )
        elif current_category == "EDU" and ORDERED_RE.match(clean):
            current_experience_id = metadata.get("experience_id")
            if current_experience_id:
                heading = _clean_list_value(clean)
                headings[current_experience_id] = (
                    current_category,
                    heading,
                    _immutable_tokens(current_category, heading),
                )
        fact_id = metadata.get("fact_id")
        if fact_id:
            if current_experience_id is None:
                raise FactLibraryError(
                    f"line {line_number}: fact_id has no current experience"
                )
            assert_fact_belongs_to_experience(
                fact_id, current_experience_id, line_number
            )
            record = FactRecord(
                fact_id=fact_id,
                experience_id=current_experience_id,
                value=_clean_list_value(clean),
                provenance=metadata["provenance"],
                line_number=line_number,
                metadata=dict(metadata),
            )
            facts[fact_id] = record
            facts_by_experience.setdefault(current_experience_id, []).append(record)

    missing_headings = set(facts_by_experience).difference(headings)
    if missing_headings:
        raise FactLibraryError(
            f"facts reference experiences without headings: {sorted(missing_headings)}"
        )
    experiences = {
        experience_id: ExperienceRecord(
            experience_id=experience_id,
            category=category,
            heading=heading,
            immutable_tokens=tokens,
            facts=tuple(facts_by_experience.get(experience_id, [])),
        )
        for experience_id, (category, heading, tokens) in headings.items()
    }
    return experiences, facts


def migrate_text(source_text: str) -> tuple[str, MigrationReport]:
    lines = source_text.splitlines(keepends=True)
    used_experience_ids, used_fact_ids = _preflight_metadata(lines)
    all_experience_ids = set(used_experience_ids)
    all_fact_ids = set(used_fact_ids)
    current_category: str | None = None
    current_experience_id: str | None = None
    inserted_experiences = 0
    inserted_facts = 0
    migrated: list[str] = []

    for line_number, line in enumerate(lines, start=1):
        body, ending = split_line_ending(line)
        clean, metadata = parse_metadata(body, line_number)
        h2 = H2_RE.fullmatch(clean)
        h3 = H3_RE.fullmatch(clean)
        if h2:
            current_category = SECTION_CATEGORIES.get(h2.group("title"))
            current_experience_id = None
            if current_category in SYNTHETIC_SECTION_EXPERIENCES:
                current_experience_id = metadata.get("experience_id")
                if not current_experience_id:
                    current_experience_id = next_id(
                        current_category, all_experience_ids, "EXP", 3
                    )
                    metadata["experience_id"] = current_experience_id
                    all_experience_ids.add(current_experience_id)
                    inserted_experiences += 1
        elif h3 and current_category in HEADING_EXPERIENCES:
            current_experience_id = metadata.get("experience_id")
            if not current_experience_id:
                current_experience_id = next_id(
                    current_category, all_experience_ids, "EXP", 3
                )
                metadata["experience_id"] = current_experience_id
                all_experience_ids.add(current_experience_id)
                inserted_experiences += 1
        elif current_category == "EDU" and ORDERED_RE.match(clean):
            current_experience_id = metadata.get("experience_id")
            if not current_experience_id:
                current_experience_id = next_id(
                    current_category, all_experience_ids, "EXP", 3
                )
                metadata["experience_id"] = current_experience_id
                all_experience_ids.add(current_experience_id)
                inserted_experiences += 1
            if "fact_id" not in metadata:
                metadata["fact_id"] = next_fact_id(
                    current_experience_id, all_fact_ids
                )
                metadata["provenance"] = "observed"
                all_fact_ids.add(metadata["fact_id"])
                inserted_facts += 1
        elif BULLET_RE.match(clean) and current_category is not None:
            if current_experience_id is None:
                raise FactLibraryError(
                    f"line {line_number}: fact appears before an experience heading"
                )
            if "fact_id" not in metadata:
                metadata["fact_id"] = next_fact_id(
                    current_experience_id, all_fact_ids
                )
                metadata["provenance"] = "observed"
                all_fact_ids.add(metadata["fact_id"])
                inserted_facts += 1
        if "fact_id" in metadata:
            if current_experience_id is None:
                raise FactLibraryError(
                    f"line {line_number}: fact_id has no current experience_id"
                )
            assert_fact_belongs_to_experience(
                metadata["fact_id"], current_experience_id, line_number
            )
        migrated.append(clean + (format_metadata(metadata) if metadata else "") + ending)

    migrated_text = "".join(migrated)
    body_preserved = strip_metadata(migrated_text) == strip_metadata(source_text)
    if not body_preserved:
        raise FactLibraryError("migration changed non-metadata body text")
    report = MigrationReport(
        source_path="",
        source_sha256=sha256_bytes(source_text.encode("utf-8")),
        preview_sha256=sha256_bytes(migrated_text.encode("utf-8")),
        generated_at=datetime.now(timezone.utc).isoformat(),
        changed=migrated_text != source_text,
        experience_count=len(all_experience_ids),
        fact_count=len(all_fact_ids),
        inserted_experience_ids=inserted_experiences,
        inserted_fact_ids=inserted_facts,
        body_preserved=body_preserved,
    )
    return migrated_text, report


def assert_source_unchanged(source: Path, expected_sha256: str) -> None:
    actual = sha256_bytes(source.read_bytes())
    if actual != expected_sha256:
        raise SourceChangedError(
            f"source hash changed: expected {expected_sha256}, got {actual}"
        )


def write_preview(source: Path, output_dir: Path) -> MigrationReport:
    source_text, raw = read_utf8(source)
    migrated_text, report = migrate_text(source_text)
    report = MigrationReport(
        **{
            **asdict(report),
            "source_path": str(source.resolve()),
            "source_sha256": sha256_bytes(raw),
            "preview_sha256": sha256_bytes(migrated_text.encode("utf-8")),
        }
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_path = output_dir / "candidate-profile.with-ids.md"
    diff_path = output_dir / "migration.diff"
    report_path = output_dir / "migration-report.json"
    preview_path.write_bytes(migrated_text.encode("utf-8"))
    diff = "".join(
        difflib.unified_diff(
            source_text.splitlines(keepends=True),
            migrated_text.splitlines(keepends=True),
            fromfile=str(source),
            tofile=str(preview_path),
        )
    )
    diff_path.write_text(diff, encoding="utf-8", newline="")
    report_path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )
    return report


def apply_preview(
    source: Path,
    preview: Path,
    preview_report: Path,
    apply_report: Path,
    *,
    approval_granted: bool,
) -> dict[str, object]:
    if not approval_granted:
        raise FactLibraryError("explicit approval is required before writing fact IDs")
    try:
        expected = json.loads(preview_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FactLibraryError("migration preview report is missing or invalid") from error
    required_report_fields = {
        "source_sha256",
        "preview_sha256",
        "body_preserved",
        "experience_count",
        "fact_count",
    }
    if not required_report_fields.issubset(expected):
        raise FactLibraryError("migration preview report is incomplete")
    if expected["body_preserved"] is not True:
        raise FactLibraryError("migration preview did not prove body preservation")
    source_text, source_raw = read_utf8(source)
    preview_text, preview_raw = read_utf8(preview)
    source_hash = sha256_bytes(source_raw)
    preview_hash = sha256_bytes(preview_raw)
    if source_hash != expected["source_sha256"]:
        raise SourceChangedError(
            f"source hash changed: expected {expected['source_sha256']}, got {source_hash}"
        )
    if preview_hash != expected["preview_sha256"]:
        raise FactLibraryError("preview hash does not match migration report")
    if strip_metadata(preview_text) != strip_metadata(source_text):
        raise FactLibraryError("preview changes non-metadata fact body")
    validated_text, validated_report = migrate_text(preview_text)
    if validated_text != preview_text:
        raise FactLibraryError("preview is missing required IDs or is not idempotent")
    if validated_report.experience_count != expected["experience_count"]:
        raise FactLibraryError("preview experience count does not match report")
    if validated_report.fact_count != expected["fact_count"]:
        raise FactLibraryError("preview fact count does not match report")

    temporary = source.with_name(f".{source.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(preview_raw)
    if sha256_bytes(temporary.read_bytes()) != preview_hash:
        raise FactLibraryError("temporary migration write failed hash verification")
    os.replace(temporary, source)

    written_text, written_raw = read_utf8(source)
    if sha256_bytes(written_raw) != preview_hash:
        raise FactLibraryError("written fact library hash does not match preview")
    if strip_metadata(written_text) != strip_metadata(source_text):
        raise FactLibraryError("written fact library changed non-metadata body")
    remigrated, final_validation = migrate_text(written_text)
    if remigrated != written_text:
        raise FactLibraryError("written fact library failed ID validation")

    result: dict[str, object] = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(source.resolve()),
        "original_sha256": source_hash,
        "applied_sha256": preview_hash,
        "original_body_sha256": sha256_bytes(
            strip_metadata(source_text).encode("utf-8")
        ),
        "applied_body_sha256": sha256_bytes(
            strip_metadata(written_text).encode("utf-8")
        ),
        "experience_count": final_validation.experience_count,
        "fact_count": final_validation.fact_count,
        "body_preserved": True,
        "approval_record": "explicit_user_confirmation",
    }
    apply_report.parent.mkdir(parents=True, exist_ok=True)
    apply_report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and preview stable IDs for the custom-resume fact library"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    preview = subparsers.add_parser("preview")
    preview.add_argument("--source", required=True, type=Path)
    preview.add_argument("--output-dir", required=True, type=Path)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--source", required=True, type=Path)
    apply = subparsers.add_parser("apply")
    apply.add_argument("--source", required=True, type=Path)
    apply.add_argument("--preview", required=True, type=Path)
    apply.add_argument("--preview-report", required=True, type=Path)
    apply.add_argument("--apply-report", required=True, type=Path)
    apply.add_argument("--approval-token", required=True)
    args = parser.parse_args()

    if args.command == "preview":
        report = write_preview(args.source, args.output_dir)
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
        return 0
    if args.command == "apply":
        if args.approval_token != "ID_ONLY_DIFF_APPROVED":
            raise FactLibraryError("invalid approval token")
        result = apply_preview(
            args.source,
            args.preview,
            args.preview_report,
            args.apply_report,
            approval_granted=True,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    source_text, _ = read_utf8(args.source)
    migrated_text, report = migrate_text(source_text)
    if migrated_text != source_text:
        raise FactLibraryError("fact library is valid UTF-8 but is missing stable IDs")
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
