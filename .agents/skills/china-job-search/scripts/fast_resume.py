"""Deterministic fast-assemble resume pipeline.

The module keeps facts and approved wording separate. It never writes the
candidate profile; raw resumes only produce a reviewable fact-diff report.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from xml.etree import ElementTree


SCHEMA_VERSION = "1.0"
CONTENT_PIPELINE = "fast-assemble"
ALLOWED_SOURCE_EXTENSIONS = {".pdf", ".md", ".html", ".htm", ".docx"}
SKIP_DIRECTORY_NAMES = {
    ".chrome-profile-resume-merge",
    ".pdf-render-chrome-profile",
    ".workbuddy",
    "旧简历",
    "_inspection-final",
}
GAME_ROLE_FAMILIES = {"game_designer", "game_production_pm"}
GAME_EXPERIENCE_IDS = {
    "EXP-PROJECT-007",
    "EXP-PROJECT-008",
    "EXP-PROJECT-009",
    "EXP-PROJECT-010",
    "EXP-PROJECT-011",
    "EXP-PROJECT-014",
}
GAME_TEXT = re.compile(
    r"游戏|玩家|卡牌|Rogueli|MOD|Mewgenics|杀戮尖塔|本地化|汉化|品类|全剧情|段位|Steam",
    re.I,
)
FORBIDDEN_TEXT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("stale_email", re.compile(r"1900265660\s*@\s*shu\.edu\.cn", re.I)),
    ("withdrawn_growth_claim", re.compile(r"环比增长\s*300\s*%")),
    ("stale_editor_title", re.compile(r"《?收获》?.{0,24}实习编辑", re.S)),
    ("removed_social_work_courses", re.compile(r"社会心理学|消费社会学|市场调研方法|文化研究")),
    ("unsupported_error_rate", re.compile(r"错漏率.{0,12}0\.5\s*%")),
    ("removed_recruiting_bot", re.compile(r"聚能媒体.{0,20}招聘.{0,20}(智能问答|助手)", re.S)),
)
DISALLOWED_YAML_KEYS = {"photo", "image", "images", "path", "template", "icon"}
HR_GATES = (
    "position_context",
    "relevance",
    "truth_and_contact",
    "supported_capability_coverage",
)
STRATEGY_PRIORITY = {
    "直接复用": 1,
    "快速生成": 2,
    "待补事实": 3,
    "暂缓完整重写": 4,
    "排除": 5,
    "": 6,
}


class FastResumeError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def comparable_pdf_text(value: str) -> str:
    """Normalize layout and Markdown-only differences for PDF consistency checks."""
    value = re.sub(r"[*_`]", "", value)
    value = value.replace("<", "").replace(">", "")
    return re.sub(r"\s+", "", value)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_json_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FastResumeError(f"cannot read JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise FastResumeError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_profile_fact_ids(profile_text: str) -> set[str]:
    return set(re.findall(r"fact_id:\s*(FACT-[A-Z0-9-]+)", profile_text))


def parse_profile_fact_texts(profile_text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in profile_text.splitlines():
        match = re.search(r"fact_id:\s*(FACT-[A-Z0-9-]+)", line)
        if not match:
            continue
        text = re.sub(r"<!--.*?-->", "", line).strip()
        text = re.sub(r"^[\-•·●▪◆▶\s]+", "", text)
        if text:
            result[match.group(1)] = canonical_text(text)
    return result


def parse_answers(answers_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in answers_text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] in {"name", "phone", "email", "location"}:
            values[cells[0]] = cells[2]
    missing = {"name", "phone", "email", "location"} - values.keys()
    if missing:
        raise FastResumeError(f"application answers missing: {sorted(missing)}")
    return values


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:  # pragma: no cover
        raise FastResumeError("pypdf is required") from error
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        payload = archive.read("word/document.xml")
    root = ElementTree.fromstring(payload)
    return "\n".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))


def extract_html_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    raw = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", raw, flags=re.I | re.S)
    return html.unescape(re.sub(r"<[^>]+>", "\n", raw))


def extract_source_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(path)
    if suffix == ".docx":
        return extract_docx_text(path)
    if suffix in {".html", ".htm"}:
        return extract_html_text(path)
    return path.read_text(encoding="utf-8-sig", errors="replace")


def discover_source_files(source_root: Path) -> list[Path]:
    if not source_root.is_dir():
        raise FastResumeError(f"source root not found: {source_root}")
    result = []
    for path in source_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_SOURCE_EXTENSIONS:
            continue
        relative = path.relative_to(source_root)
        if any(
            part in SKIP_DIRECTORY_NAMES or part.startswith(".")
            for part in relative.parts[:-1]
        ):
            continue
        result.append(path)
    return sorted(result, key=lambda item: str(item).lower())


def forbidden_codes(text: str) -> list[str]:
    compact = canonical_text(text)
    return [code for code, pattern in FORBIDDEN_TEXT_PATTERNS if pattern.search(compact)]


def candidate_lines(text: str) -> list[str]:
    logical_lines: list[str] = []
    buffer = ""
    for raw in text.splitlines():
        stripped = raw.lstrip()
        if stripped.startswith(("#", ">", "|", "```", "<!--")) or "�" in raw:
            continue
        value = canonical_text(raw)
        if not value:
            continue
        is_section_title = len(value) <= 12 and bool(
            re.search(r"经历|能力|技能|教育|实践|项目|工作", value)
        )
        is_dated_heading = bool(re.search(r"20\d{2}/\d{2}", value))
        buffer_is_heading = bool(re.search(r"20\d{2}/\d{2}", buffer)) or (
            len(buffer) <= 12
            and bool(re.search(r"经历|能力|技能|教育|实践|项目|工作", buffer))
        )
        if buffer and (
            re.search(r"[。；！？.!?;：:]$", buffer)
            or buffer_is_heading
            or is_section_title
            or is_dated_heading
        ):
            logical_lines.append(buffer)
            buffer = value
        elif buffer:
            buffer = canonical_text(buffer + " " + value)
        else:
            buffer = value
    if buffer:
        logical_lines.append(buffer)

    lines = []
    for raw in logical_lines:
        value = canonical_text(re.sub(r"^[\-•·●▪◆▶\d.、)）\s]+", "", raw))
        if ((18 <= len(value) <= 500) or forbidden_codes(value)) and not re.fullmatch(r"[\W_]+", value):
            lines.append(value)
    return lines


def likely_fact_candidate(text: str) -> bool:
    if re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", text) or re.search(
        r"(?<!\d)1\d{10}(?!\d)", re.sub(r"\s", "", text)
    ):
        return False
    return bool(
        re.search(r"\d", text)
        or re.search(
            r"负责|完成|设计|开发|搭建|组织|推进|交付|验证|运营|撰写|翻译|测试|分析|协调|获得|提出|维护|发布|覆盖|缩短|降低|提升",
            text,
        )
    )


def load_fact_confirmations(drafts_dir: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    confirmations: dict[str, dict[str, Any]] = {}
    files: list[str] = []
    if not drafts_dir.is_dir():
        return confirmations, files
    for path in sorted(drafts_dir.glob("fast-assemble-fact-confirmation-*.json")):
        payload = read_json(path)
        if payload.get("status") != "confirmed_and_mapped":
            continue
        confirmed_at = str(payload.get("confirmed_at", ""))
        for item in payload.get("items", []):
            candidate_id = str(item.get("candidate_id", ""))
            fact_ids = sorted(set(str(value) for value in item.get("fact_ids", [])))
            if not candidate_id.startswith("FACT-CAND-") or not fact_ids:
                raise FastResumeError(f"invalid fact confirmation record: {path}")
            confirmations[candidate_id] = {
                "fact_ids": fact_ids,
                "confirmed_at": confirmed_at,
                "confirmation_file": str(path.resolve()),
            }
        files.append(str(path.resolve()))
    return confirmations, files


def scan_fact_candidates(
    source_root: Path,
    profile_text: str,
    eligible_source_hashes: set[str] | None = None,
    approved_claim_texts: Sequence[str] = (),
    confirmed_candidates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    confirmed_candidates = confirmed_candidates or {}
    profile_compact = canonical_text(profile_text)
    approved_normalized = {
        re.sub(r"[^\w\u4e00-\u9fff]", "", canonical_text(value)).lower()
        for value in approved_claim_texts
        if len(canonical_text(value)) >= 8
    }
    unique_files: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, str]] = []
    facts: list[dict[str, Any]] = []
    seen_lines: set[str] = set()
    for path in discover_source_files(source_root):
        digest = sha256_file(path)
        if digest in unique_files:
            duplicates.append({"path": str(path.resolve()), "duplicate_of": unique_files[digest]["path"], "sha256": digest})
            continue
        try:
            text = extract_source_text(path)
            extraction_error = None
        except Exception as error:  # keep batch scan usable
            text = ""
            extraction_error = str(error)
        record = {
            "path": str(path.resolve()),
            "sha256": digest,
            "size": path.stat().st_size,
            "extraction_error": extraction_error,
            "forbidden_codes": forbidden_codes(text),
            "eligible_for_claims": eligible_source_hashes is None
            or digest in eligible_source_hashes,
        }
        unique_files[digest] = record
        for line in candidate_lines(text):
            key = canonical_text(line).lower()
            if key in seen_lines:
                continue
            seen_lines.add(key)
            candidate_id = "FACT-CAND-" + sha256_bytes(key.encode("utf-8"))[:12]
            issues = forbidden_codes(line)
            normalized_line = re.sub(
                r"[^\w\u4e00-\u9fff]", "", canonical_text(line)
            ).lower()
            expression_covered = len(normalized_line) >= 16 and any(
                normalized_line in claim_text or claim_text in normalized_line
                for claim_text in approved_normalized
            )
            if issues:
                classification = "conflict_or_withdrawn"
            elif candidate_id in confirmed_candidates:
                classification = "confirmed_existing_fact"
            elif key in profile_compact.lower():
                classification = "already_confirmed"
            elif expression_covered:
                classification = "approved_expression_covered"
            else:
                classification = "new_candidate"
            facts.append(
                {
                    "candidate_id": candidate_id,
                    "text": line,
                    "classification": classification,
                    "issues": issues,
                    "source_path": str(path.resolve()),
                    "source_sha256": digest,
                    "eligible_for_fact_review": eligible_source_hashes is None
                    or digest in eligible_source_hashes,
                    "confirmation_required": classification == "new_candidate"
                    and (
                        eligible_source_hashes is None
                        or digest in eligible_source_hashes
                    ),
                    "mapped_fact_ids": confirmed_candidates.get(candidate_id, {}).get(
                        "fact_ids", []
                    ),
                }
            )
    counts: dict[str, int] = defaultdict(int)
    for item in facts:
        counts[item["classification"]] += 1
    review_queue = [
        item
        for item in facts
        if item["classification"] == "new_candidate"
        and item["eligible_for_fact_review"]
        and likely_fact_candidate(str(item["text"]))
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "source_root": str(source_root.resolve()),
        "profile_sha256": sha256_bytes(profile_text.encode("utf-8")),
        "summary": {
            "unique_files": len(unique_files),
            "duplicate_files": len(duplicates),
            "candidate_counts": dict(sorted(counts.items())),
            "review_queue_count": len(review_queue),
            "profile_was_modified": False,
        },
        "files": list(unique_files.values()),
        "duplicates": duplicates,
        "fact_diff_candidates": facts,
        "review_queue": review_queue,
    }


def _baseline_sources_for_application(
    baseline_index: dict[str, Any], application_dir: Path, source_root: Path
) -> list[dict[str, Any]]:
    sources = []
    discovered_by_hash: dict[str, Path] = {}
    for candidate in discover_source_files(source_root):
        try:
            discovered_by_hash.setdefault(sha256_file(candidate), candidate)
        except OSError:
            continue
    for item in baseline_index.get("items", []):
        if item.get("status") != "reusable":
            continue
        dirs = {str(Path(value).resolve()).lower() for value in item.get("application_dirs", [])}
        if str(application_dir.resolve()).lower() not in dirs:
            continue
        for source in item.get("source_files", []):
            path = Path(str(source.get("path", "")))
            expected_hash = str(source.get("sha256", "")).lower()
            try:
                path.resolve().relative_to(source_root.resolve())
            except (OSError, ValueError):
                path = discovered_by_hash.get(expected_hash, path)
            if not path.is_file() or sha256_file(path) != expected_hash:
                path = discovered_by_hash.get(expected_hash, path)
            if path.is_file() and sha256_file(path) == expected_hash:
                sources.append({"path": str(path.resolve()), "sha256": sha256_file(path)})
    return sources


def infer_claim_context(experience_id: str, heading: str, text: str) -> str:
    if experience_id in GAME_EXPERIENCE_IDS or GAME_TEXT.search(f"{heading} {text}"):
        return "game"
    return "both"


def _claim_role_families(source_family: str, context: str) -> list[str]:
    return [source_family]


def build_claim_library(
    applications_root: Path,
    baseline_index: dict[str, Any],
    source_root: Path,
    profile_text: str,
) -> dict[str, Any]:
    fact_ids = parse_profile_fact_ids(profile_text)
    claims_by_key: dict[str, dict[str, Any]] = {}
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    for baseline in baseline_index.get("items", []):
        if baseline.get("status") != "reusable":
            continue
        for directory_value in baseline.get("application_dirs", []):
            application_dir = Path(str(directory_value))
            try:
                application_dir.resolve().relative_to(applications_root.resolve())
            except ValueError:
                continue
            source_files = _baseline_sources_for_application(baseline_index, application_dir, source_root)
            if not source_files:
                continue
            current_path = application_dir / "resume-content" / "current.json"
            run_id = None
            provenance = "passed_baseline"
            if current_path.is_file():
                current = read_json(current_path)
                if current.get("status") == "approved" and isinstance(current.get("approved_run_id"), str):
                    run_id = current["approved_run_id"]
                    provenance = "user_approved_current"
            if run_id is None:
                hr_record = baseline.get("hr_review", {})
                hr_record_path = Path(str(hr_record.get("path", "")))
                if hr_record.get("passed") is True and hr_record_path.name == "hr-review.json":
                    run_id = hr_record_path.parent.name
            if not run_id:
                continue
            candidates[(str(application_dir.resolve()).lower(), run_id)] = {
                "application_dir": application_dir,
                "run_id": run_id,
                "source_files": source_files,
                "source_family": str(baseline.get("role_family") or "general"),
                "provenance": provenance,
            }
    for candidate in candidates.values():
        application_dir = candidate["application_dir"]
        run_id = candidate["run_id"]
        source_files = candidate["source_files"]
        run_dir = application_dir / "resume-content" / "runs" / run_id
        fusion_path = run_dir / "fusion.json"
        hr_path = run_dir / "hr-review.json"
        if not fusion_path.is_file() or not hr_path.is_file():
            continue
        hr = read_json(hr_path)
        if hr.get("passed") is not True:
            continue
        fusion = read_json(fusion_path)
        source_family = candidate["source_family"]
        jd_analysis_path = run_dir / "jd-analysis.json"
        if jd_analysis_path.is_file():
            source_family = str(read_json(jd_analysis_path).get("role_family") or "general")
        for section in fusion.get("sections", []):
            section_name = str(section.get("name", "")).strip()
            for entry in section.get("entries", []):
                experience_id = str(entry.get("experience_id", "")).strip()
                heading = str(entry.get("heading", "")).strip()
                for bullet in entry.get("bullets", []):
                    text = canonical_text(str(bullet.get("text", "")))
                    bullet_facts = sorted(set(str(value) for value in bullet.get("fact_ids", [])))
                    if not text or not bullet_facts or not set(bullet_facts) <= fact_ids:
                        continue
                    if forbidden_codes(text):
                        continue
                    primary_value = canonical_text(str(bullet.get("primary_value") or "已批准表达"))
                    context = infer_claim_context(experience_id, heading, text)
                    key = canonical_json_sha256({"text": text, "fact_ids": bullet_facts})
                    claim = {
                        "claim_id": "CLAIM-" + key[:12],
                        "experience_id": experience_id,
                        "fact_ids": bullet_facts,
                        "text": text,
                        "capability_tags": [primary_value],
                        "role_families": _claim_role_families(source_family, context),
                        "context": context,
                        "section": section_name,
                        "heading": heading,
                        "source": {
                            "application_dir": str(application_dir.resolve()),
                            "run_id": run_id,
                            "fusion_sha256": sha256_file(fusion_path),
                            "source_files": source_files,
                            "approval_basis": candidate["provenance"],
                        },
                        "status": "active",
                    }
                    existing = claims_by_key.get(key)
                    if existing is None:
                        claims_by_key[key] = claim
                    else:
                        existing["role_families"] = sorted(
                            set(existing["role_families"]) | set(claim["role_families"])
                        )
                        if (
                            existing["source"].get("approval_basis") != "user_approved_current"
                            and claim["source"].get("approval_basis") == "user_approved_current"
                        ):
                            existing["source"] = claim["source"]
    claims = sorted(claims_by_key.values(), key=lambda item: item["claim_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "profile_sha256": sha256_bytes(profile_text.encode("utf-8")),
        "claims_sha256": canonical_json_sha256(claims),
        "claims": claims,
    }


def import_library(
    source_root: Path,
    applications_root: Path,
    baseline_index_path: Path,
    profile_path: Path,
    claims_output: Path,
    report_output: Path,
) -> dict[str, Any]:
    profile_text = profile_path.read_text(encoding="utf-8-sig")
    baseline_index = read_json(baseline_index_path)
    claims = build_claim_library(applications_root, baseline_index, source_root, profile_text)
    confirmed_candidates, confirmation_files = load_fact_confirmations(
        profile_path.parent / "drafts"
    )
    confirmed_fact_ids = {
        fact_id
        for record in confirmed_candidates.values()
        for fact_id in record["fact_ids"]
    }
    missing_confirmed_facts = sorted(
        confirmed_fact_ids - parse_profile_fact_ids(profile_text)
    )
    if missing_confirmed_facts:
        raise FastResumeError(
            f"fact confirmation maps to missing profile facts: {missing_confirmed_facts}"
        )
    eligible_source_hashes = {
        str(source.get("sha256", ""))
        for claim in claims["claims"]
        for source in claim.get("source", {}).get("source_files", [])
        if source.get("sha256")
    }
    approved_claim_texts = [
        str(value)
        for claim in claims["claims"]
        for value in (claim.get("text", ""), claim.get("heading", ""))
        if value
    ]
    report = scan_fact_candidates(
        source_root,
        profile_text,
        eligible_source_hashes,
        approved_claim_texts,
        confirmed_candidates,
    )
    report["confirmation_files"] = confirmation_files
    report["approved_claim_import"] = {
        "claim_count": len(claims["claims"]),
        "claims_sha256": claims["claims_sha256"],
        "claims_output": str(claims_output.resolve()),
        "rule": "only approved current runs linked to reusable, hash-valid source files",
    }
    write_json(claims_output, claims)
    write_json(report_output, report)
    return {
        "status": "ok",
        "claims": len(claims["claims"]),
        "claims_sha256": claims["claims_sha256"],
        "fact_candidates": len(report["fact_diff_candidates"]),
        "fact_review_queue": len(report["review_queue"]),
        "profile_modified": False,
        "claims_output": str(claims_output.resolve()),
        "report_output": str(report_output.resolve()),
    }


def _context_matches(claim: dict[str, Any], target_context: str) -> bool:
    return claim.get("context") in {"both", target_context}


def _role_matches(claim: dict[str, Any], role_family: str) -> bool:
    return role_family in claim.get("role_families", [])


def _claim_to_bullet(claim: dict[str, Any], requirement_ids: Sequence[str]) -> dict[str, Any]:
    return {
        "text": claim["text"],
        "experience_id": claim["experience_id"],
        "fact_ids": list(claim["fact_ids"]),
        "requirement_ids": sorted(set(requirement_ids)),
        "claim_id": claim["claim_id"],
        "capability_tags": list(claim["capability_tags"]),
    }


def assemble_fast_content(
    jd: dict[str, Any],
    selection: dict[str, Any],
    claims_library: dict[str, Any],
    profile_text: str,
    contact: dict[str, str],
) -> dict[str, Any]:
    company = canonical_text(str(jd.get("company", "")))
    target_role = canonical_text(str(jd.get("target_role", "")))
    role_family = canonical_text(str(jd.get("role_family", "")))
    context = str(jd.get("context", ""))
    if not company or not target_role or not role_family or context not in {"game", "non_game"}:
        raise FastResumeError("JD requires company, target_role, role_family and game|non_game context")
    selected = [str(value) for value in selection.get("selected_experience_ids", [])]
    if not 1 <= len(selected) <= 4 or len(selected) != len(set(selected)):
        raise FastResumeError("selection must contain 1-4 unique experience IDs")
    if context == "non_game" and any(value in GAME_EXPERIENCE_IDS for value in selected):
        raise FastResumeError("non-game route cannot select game experiences")
    fact_ids = parse_profile_fact_ids(profile_text)
    claims = []
    for claim in claims_library.get("claims", []):
        if claim.get("status") != "active" or not _context_matches(claim, context) or not _role_matches(claim, role_family):
            continue
        experience_id = claim.get("experience_id")
        if experience_id.startswith("EXP-EDU-") or experience_id == "EXP-SKILL-001" or experience_id in selected:
            if set(claim.get("fact_ids", [])) <= fact_ids and not forbidden_codes(str(claim.get("text", ""))):
                claims.append(claim)
    if context == "non_game" and any(claim.get("context") == "game" or GAME_TEXT.search(str(claim.get("text", ""))) for claim in claims):
        raise FastResumeError("non-game content contains game-specific claim")
    by_entry: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    requirements = list(jd.get("requirements", []))
    covered_requirement_ids: set[str] = set()
    fact_gaps = []
    supported_gaps = []
    for requirement in requirements:
        requirement_id = str(requirement.get("requirement_id", ""))
        requirement_facts = set(str(value) for value in requirement.get("fact_ids", [])) & fact_ids
        if not requirement_facts:
            fact_gaps.append({"requirement_id": requirement_id, "text": str(requirement.get("text", "")), "fact_ids": []})
            continue
        matching = [claim for claim in claims if requirement_facts & set(claim.get("fact_ids", []))]
        if matching:
            covered_requirement_ids.add(requirement_id)
        ability_matching = [claim for claim in matching if claim.get("section") == "自我能力"]
        if not ability_matching:
            supported_gaps.append({"requirement_id": requirement_id, "text": str(requirement.get("text", "")), "fact_ids": sorted(requirement_facts)})
    for claim in claims:
        req_ids = []
        claim_facts = set(claim.get("fact_ids", []))
        for requirement in requirements:
            if claim_facts & set(requirement.get("fact_ids", [])):
                req_ids.append(str(requirement.get("requirement_id", "")))
        key = (claim["section"], claim["experience_id"], claim["heading"])
        by_entry[key].append(_claim_to_bullet(claim, req_ids))
    section_order = ["教育经历", "实习/工作经历", "实践经历", "自我能力"]
    sections = []
    for section_name in section_order:
        entries = [
            {"experience_id": exp_id, "heading": heading, "bullets": bullets}
            for (name, exp_id, heading), bullets in by_entry.items()
            if name == section_name
        ]
        if entries:
            sections.append({"name": section_name, "entries": entries})
    if not sections:
        raise FastResumeError("no approved claims cover the selection")
    content = {
        "schema_version": SCHEMA_VERSION,
        "content_pipeline": CONTENT_PIPELINE,
        "company": company,
        "target_role": target_role,
        "role_family": role_family,
        "role_track": jd.get("role_track"),
        "context": context,
        "contact": contact,
        "source_hashes": {
            "profile_sha256": sha256_bytes(profile_text.encode("utf-8")),
            "claims_sha256": str(claims_library.get("claims_sha256", "")),
            "jd_sha256": canonical_json_sha256(jd),
            "selection_sha256": canonical_json_sha256(selection),
        },
        "sections": sections,
        "covered_requirement_ids": sorted(covered_requirement_ids),
        "fact_gaps": fact_gaps,
        "supported_coverage_gaps": supported_gaps,
        "writer_additions": [],
    }
    deterministic_content_check(content, fact_ids)
    return content


def iter_bullets(content: dict[str, Any]) -> Iterable[dict[str, Any]]:
    seen: set[tuple[str, tuple[str, ...], tuple[str, ...]]] = set()
    for section in content.get("sections", []):
        for entry in section.get("entries", []):
            for bullet in entry.get("bullets", []):
                key = (
                    str(bullet.get("text", "")),
                    tuple(sorted(str(value) for value in bullet.get("fact_ids", []))),
                    tuple(sorted(str(value) for value in bullet.get("requirement_ids", []))),
                )
                if key not in seen:
                    seen.add(key)
                    yield bullet
    for bullet in content.get("writer_additions", []):
        key = (
            str(bullet.get("text", "")),
            tuple(sorted(str(value) for value in bullet.get("fact_ids", []))),
            tuple(sorted(str(value) for value in bullet.get("requirement_ids", []))),
        )
        if key not in seen:
            seen.add(key)
            yield bullet


def apply_writer_additions(
    content: dict[str, Any], additions_payload: dict[str, Any], profile_text: str
) -> dict[str, Any]:
    """Apply the single fast-writer result without creating new facts.

    Every sentence must close an existing supported coverage gap and bind only to
    confirmed fact IDs. The function is deterministic and deliberately refuses a
    second writer pass.
    """
    if content.get("writer_additions"):
        raise FastResumeError("fast_writer may be applied only once")
    additions = additions_payload.get("writer_additions")
    if not isinstance(additions, list) or not additions:
        raise FastResumeError("writer_additions must be a non-empty array")
    fact_ids = parse_profile_fact_ids(profile_text)
    gaps = {
        str(item.get("requirement_id", "")): item
        for item in content.get("supported_coverage_gaps", [])
    }
    if not gaps:
        raise FastResumeError("content has no supported coverage gap for fast_writer")

    normalized: list[dict[str, Any]] = []
    for addition in additions:
        text = canonical_text(str(addition.get("text", "")))
        bound_facts = sorted(set(str(value) for value in addition.get("fact_ids", [])))
        requirement_ids = sorted(
            set(str(value) for value in addition.get("requirement_ids", []))
        )
        capability_tags = [
            canonical_text(str(value)) for value in addition.get("capability_tags", [])
        ]
        if not text or not bound_facts or not requirement_ids or not capability_tags:
            raise FastResumeError(
                "each writer addition requires text, fact_ids, requirement_ids and capability_tags"
            )
        if not set(bound_facts) <= fact_ids:
            raise FastResumeError("fast_writer addition references unconfirmed fact_ids")
        if not set(requirement_ids) <= set(gaps):
            raise FastResumeError("fast_writer addition may only close supported coverage gaps")
        for requirement_id in requirement_ids:
            gap_facts = set(str(value) for value in gaps[requirement_id].get("fact_ids", []))
            if not gap_facts.intersection(bound_facts):
                raise FastResumeError(
                    f"fast_writer addition is not fact-bound to requirement {requirement_id}"
                )
        if content.get("context") == "non_game" and GAME_TEXT.search(text):
            raise FastResumeError("non-game fast_writer addition contains game-specific text")
        issues = forbidden_codes(text)
        if issues:
            raise FastResumeError(f"fast_writer addition contains forbidden content: {issues}")
        normalized.append(
            {
                "text": text,
                "experience_id": str(addition.get("experience_id") or "EXP-SKILL-001"),
                "fact_ids": bound_facts,
                "requirement_ids": requirement_ids,
                "claim_id": None,
                "capability_tags": capability_tags,
                "heading": canonical_text(str(addition.get("heading") or "专业硬技能")),
            }
        )

    ability_section = next(
        (section for section in content.get("sections", []) if section.get("name") == "自我能力"),
        None,
    )
    if ability_section is None:
        ability_section = {"name": "自我能力", "entries": []}
        content.setdefault("sections", []).append(ability_section)
    for addition in normalized:
        heading = addition["heading"]
        experience_id = addition["experience_id"]
        entry = next(
            (
                item
                for item in ability_section["entries"]
                if item.get("heading") == heading
                and item.get("experience_id") == experience_id
            ),
            None,
        )
        if entry is None:
            entry = {"experience_id": experience_id, "heading": heading, "bullets": []}
            ability_section["entries"].append(entry)
        display_bullet = {key: value for key, value in addition.items() if key != "heading"}
        entry["bullets"].append(display_bullet)

    closed = {
        requirement_id
        for addition in normalized
        for requirement_id in addition["requirement_ids"]
    }
    content["covered_requirement_ids"] = sorted(
        set(content.get("covered_requirement_ids", [])) | closed
    )
    content["supported_coverage_gaps"] = [
        item
        for item in content.get("supported_coverage_gaps", [])
        if str(item.get("requirement_id", "")) not in closed
    ]
    content["writer_additions"] = normalized
    deterministic_content_check(content, fact_ids)
    return content


def build_fast_writer_packet(
    content: dict[str, Any], profile_text: str
) -> dict[str, Any]:
    gaps = content.get("supported_coverage_gaps", [])
    if not gaps:
        raise FastResumeError("content has no supported coverage gap for fast_writer")
    fact_texts = parse_profile_fact_texts(profile_text)
    packet_gaps = []
    for gap in gaps:
        allowed_facts = []
        for fact_id in gap.get("fact_ids", []):
            fact_id = str(fact_id)
            if fact_id not in fact_texts:
                raise FastResumeError(
                    f"supported coverage gap references missing fact text: {fact_id}"
                )
            allowed_facts.append({"fact_id": fact_id, "text": fact_texts[fact_id]})
        if not allowed_facts:
            raise FastResumeError("supported coverage gap must expose confirmed facts")
        packet_gaps.append(
            {
                "requirement_id": str(gap.get("requirement_id", "")),
                "requirement_text": str(gap.get("text", "")),
                "allowed_facts": allowed_facts,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "content_pipeline": CONTENT_PIPELINE,
        "company": content["company"],
        "target_role": content["target_role"],
        "role_family": content["role_family"],
        "context": content["context"],
        "content_sha256": canonical_json_sha256(content),
        "supported_coverage_gaps": packet_gaps,
        "rules": {
            "max_writer_calls": 1,
            "new_facts_forbidden": True,
            "rewrite_existing_bullets_forbidden": True,
            "non_game_game_content_forbidden": content["context"] == "non_game",
        },
    }


def deterministic_content_check(content: dict[str, Any], fact_ids: set[str]) -> None:
    errors = []
    if content.get("content_pipeline") != CONTENT_PIPELINE:
        errors.append("content_pipeline must be fast-assemble")
    if content.get("context") == "non_game":
        for section in content.get("sections", []):
            if section.get("name") == "游戏经历":
                errors.append("non-game resume contains 游戏经历 section")
            for entry in section.get("entries", []):
                if entry.get("experience_id") in GAME_EXPERIENCE_IDS:
                    errors.append(f"non-game resume contains game experience {entry.get('experience_id')}")
                if GAME_TEXT.search(canonical_text(json.dumps(entry, ensure_ascii=False))):
                    errors.append(f"non-game resume contains game-specific text in {entry.get('heading')}")
    for bullet in iter_bullets(content):
        bound = set(bullet.get("fact_ids", []))
        if not bound or not bound <= fact_ids:
            errors.append(f"bullet has invalid fact_ids: {bullet.get('text', '')[:40]}")
        issues = forbidden_codes(str(bullet.get("text", "")))
        if issues:
            errors.append(f"forbidden claim {issues}: {bullet.get('text', '')[:40]}")
    contact = content.get("contact", {})
    if not re.fullmatch(r"1\d{10}", re.sub(r"\D", "", str(contact.get("phone", "")))):
        errors.append("invalid phone")
    if "@" not in str(contact.get("email", "")):
        errors.append("invalid email")
    if errors:
        raise FastResumeError("; ".join(errors))


def validate_hr_review(review: dict[str, Any]) -> dict[str, Any]:
    if review.get("schema_version") != SCHEMA_VERSION:
        raise FastResumeError("HR review schema_version must be 1.0")
    generation_round = review.get("generation_round")
    if generation_round not in {1, 2}:
        raise FastResumeError("generation_round must be 1 or 2")
    checks = review.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(HR_GATES):
        raise FastResumeError("HR review must contain exactly four gates")
    all_passed = all(checks[name].get("passed") is True and not checks[name].get("findings") for name in HR_GATES)
    repairs = review.get("exact_repairs")
    if not isinstance(repairs, list):
        raise FastResumeError("exact_repairs must be an array")
    decision = review.get("decision")
    if all_passed:
        if decision != "pass" or repairs or review.get("requires_manual_review") is not False:
            raise FastResumeError("passing four-gate review must be pass with no repairs")
        status = "passed"
    else:
        if decision != "repair" or not repairs:
            raise FastResumeError("failed gate requires repair and exact repair items")
        expected_manual = generation_round == 2
        if review.get("requires_manual_review") is not expected_manual:
            raise FastResumeError("second failed review must require manual review")
        status = "manual_required" if expected_manual else "repair_once"
    return {"status": status, "decision": decision, "generation_round": generation_round}


def _pdf_matches_existing(path: Path, expected_hash: str | None, target_role: str) -> tuple[bool, str]:
    if not path.is_file():
        return False, "existing PDF missing"
    actual_hash = sha256_file(path)
    if expected_hash and actual_hash.lower() != expected_hash.lower():
        return False, "existing PDF hash mismatch"
    text = canonical_text(extract_pdf_text(path))
    if canonical_text(target_role).lower() not in text.lower():
        return False, "target role not found in PDF text"
    return True, actual_hash


def route_job(job: dict[str, Any], claims_library: dict[str, Any]) -> dict[str, Any]:
    if any(job.get(flag) is True for flag in ("excluded", "is_internship", "is_expired", "is_pure_hard_tech", "has_success_receipt")):
        return {"resume_strategy": "排除", "content_pipeline": None, "reason": "job meets an exclusion rule"}
    target_role = canonical_text(str(job.get("target_role", "")))
    existing_path = job.get("existing_resume_path")
    if existing_path:
        ok, detail = _pdf_matches_existing(Path(existing_path), job.get("existing_resume_sha256"), target_role)
        if ok:
            return {"resume_strategy": "直接复用", "content_pipeline": "existing-material", "reason": "existing PDF file, hash and target role verified", "resume_sha256": detail}
    if job.get("jd_complete") is not True:
        return {"resume_strategy": "暂缓完整重写", "content_pipeline": None, "material_status": "待读取JD", "reason": "complete JD unavailable"}
    requirements = job.get("requirements", [])
    if any(not item.get("fact_ids") for item in requirements if item.get("required", True)):
        return {"resume_strategy": "待补事实", "content_pipeline": None, "reason": "a required JD capability has no confirmed fact evidence"}
    selected = set(str(value) for value in job.get("selected_experience_ids", []))
    if not 1 <= len(selected) <= 4:
        return {"resume_strategy": "暂缓完整重写", "content_pipeline": None, "reason": "no valid 1-4 experience selection"}
    context = str(job.get("context", ""))
    role_family = str(job.get("role_family", ""))
    covered = {
        claim.get("experience_id")
        for claim in claims_library.get("claims", [])
        if claim.get("status") == "active" and _context_matches(claim, context) and _role_matches(claim, role_family)
    }
    if selected <= covered:
        return {"resume_strategy": "快速生成", "content_pipeline": CONTENT_PIPELINE, "reason": "complete JD and approved claims cover the selected experiences"}
    return {"resume_strategy": "暂缓完整重写", "content_pipeline": None, "reason": "selected experiences lack approved expression coverage"}


def prioritize_job_batch(batch: dict[str, Any]) -> dict[str, Any]:
    positions = batch.get("positions")
    if batch.get("schema_version") != SCHEMA_VERSION or not isinstance(positions, list):
        raise FastResumeError("job batch requires schema_version 1.0 and positions array")
    unknown = sorted(
        {
            str(item.get("resume_strategy", ""))
            for item in positions
            if str(item.get("resume_strategy", "")) not in STRATEGY_PRIORITY
        }
    )
    if unknown:
        raise FastResumeError(f"unknown resume strategies: {unknown}")
    return {
        **batch,
        "positions": sorted(
            positions,
            key=lambda item: (
                STRATEGY_PRIORITY[str(item.get("resume_strategy", ""))],
                canonical_text(str(item.get("company", ""))).lower(),
                canonical_text(str(item.get("concrete_job", ""))).lower(),
            ),
        ),
    }


def content_from_approved_fusion(
    application_dir: Path,
    company: str,
    target_role: str,
    context: str,
    role_family: str,
    contact: dict[str, str],
    profile_text: str,
    run_id_override: str | None = None,
) -> dict[str, Any]:
    if run_id_override:
        run_id = run_id_override
    else:
        current_path = application_dir / "resume-content" / "current.json"
        current = read_json(current_path)
        if current.get("status") != "approved":
            raise FastResumeError(f"application has no approved current content: {application_dir}")
        run_id = str(current["approved_run_id"])
    fusion_path = application_dir / "resume-content" / "runs" / run_id / "fusion.json"
    fusion = read_json(fusion_path)
    sections = []
    selected = []
    for section in fusion.get("sections", []):
        entries = []
        for entry in section.get("entries", []):
            exp_id = str(entry.get("experience_id", ""))
            if exp_id.startswith(("EXP-WORK-", "EXP-PROJECT-")):
                selected.append(exp_id)
            bullets = [
                {
                    "text": canonical_text(str(bullet.get("text", ""))),
                    "experience_id": exp_id,
                    "fact_ids": list(bullet.get("fact_ids", [])),
                    "requirement_ids": list(bullet.get("requirement_ids", [])),
                    "claim_id": None,
                    "capability_tags": [canonical_text(str(bullet.get("primary_value") or "已批准表达"))],
                }
                for bullet in entry.get("bullets", [])
            ]
            if bullets:
                entries.append({"experience_id": exp_id, "heading": str(entry.get("heading", "")), "bullets": bullets})
        if entries:
            sections.append({"name": str(section.get("name", "")), "entries": entries})
    selection = {"selected_experience_ids": sorted(set(selected))}
    content = {
        "schema_version": SCHEMA_VERSION,
        "content_pipeline": CONTENT_PIPELINE,
        "company": company,
        "target_role": target_role,
        "role_family": role_family,
        "role_track": None,
        "context": context,
        "contact": contact,
        "source_hashes": {
            "profile_sha256": sha256_bytes(profile_text.encode("utf-8")),
            "claims_sha256": "0" * 64,
            "jd_sha256": sha256_file(application_dir / "jd.md") if (application_dir / "jd.md").is_file() else "0" * 64,
            "selection_sha256": canonical_json_sha256(selection),
        },
        "sections": sections,
        "covered_requirement_ids": [],
        "fact_gaps": [],
        "supported_coverage_gaps": [],
        "writer_additions": [],
    }
    deterministic_content_check(content, parse_profile_fact_ids(profile_text))
    return content


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _yaml_lines(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            rendered_key = str(key) if re.fullmatch(r"[A-Za-z0-9_\-\u4e00-\u9fff/]+", str(key)) else _yaml_scalar(key)
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{prefix}{rendered_key}:")
                lines.extend(_yaml_lines(item, indent + 2))
            elif isinstance(item, (dict, list)):
                lines.append(f"{prefix}{rendered_key}: {'{}' if isinstance(item, dict) else '[]'}")
            else:
                lines.append(f"{prefix}{rendered_key}: {_yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict) and item:
                first_key = next(iter(item))
                first_value = item[first_key]
                rendered_key = str(first_key) if re.fullmatch(r"[A-Za-z0-9_\-\u4e00-\u9fff/]+", str(first_key)) else _yaml_scalar(first_key)
                if isinstance(first_value, (dict, list)):
                    lines.append(f"{prefix}- {rendered_key}:")
                    lines.extend(_yaml_lines(first_value, indent + 4))
                else:
                    lines.append(f"{prefix}- {rendered_key}: {_yaml_scalar(first_value)}")
                for key, subvalue in list(item.items())[1:]:
                    rendered_subkey = str(key) if re.fullmatch(r"[A-Za-z0-9_\-\u4e00-\u9fff/]+", str(key)) else _yaml_scalar(key)
                    if isinstance(subvalue, (dict, list)) and subvalue:
                        lines.append(f"{' ' * (indent + 2)}{rendered_subkey}:")
                        lines.extend(_yaml_lines(subvalue, indent + 4))
                    elif isinstance(subvalue, (dict, list)):
                        lines.append(f"{' ' * (indent + 2)}{rendered_subkey}: {'{}' if isinstance(subvalue, dict) else '[]'}")
                    else:
                        lines.append(f"{' ' * (indent + 2)}{rendered_subkey}: {_yaml_scalar(subvalue)}")
            elif isinstance(item, list):
                lines.append(f"{prefix}-")
                lines.extend(_yaml_lines(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return lines
    return [f"{prefix}{_yaml_scalar(value)}"]


def _assert_safe_yaml(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in DISALLOWED_YAML_KEYS:
                raise FastResumeError(f"disallowed RenderCV field: {path}.{key}")
            _assert_safe_yaml(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_safe_yaml(item, f"{path}[{index}]")


def build_rendercv_document(content: dict[str, Any], target_pages: int = 1) -> dict[str, Any]:
    if target_pages not in {1, 2}:
        raise FastResumeError("target_pages must be 1 or 2")
    body_characters = sum(len(str(bullet.get("text", ""))) for bullet in iter_bullets(content))
    dense_one_page = target_pages == 1 and body_characters > 1800
    page_margin = "0.75in" if target_pages == 2 else ("0.45in" if dense_one_page else "0.60in")
    body_size = "12.5pt" if target_pages == 2 else ("8.5pt" if dense_one_page else "9.5pt")
    line_spacing = "0.65em" if target_pages == 2 else ("0.38em" if dense_one_page else "0.46em")
    sections: dict[str, list[dict[str, Any]]] = {}
    for section in content.get("sections", []):
        rendered_entries = []
        for entry in section.get("entries", []):
            heading_parts = [part.strip() for part in str(entry.get("heading", "")).split("｜") if part.strip()]
            date = heading_parts[-1] if len(heading_parts) >= 3 and re.search(r"\d{4}", heading_parts[-1]) else None
            name_parts = heading_parts[:-1] if date else heading_parts
            rendered = {
                "name": "｜".join(name_parts) or str(entry.get("heading", "")),
                "date": date,
                "highlights": [str(bullet.get("text", "")) for bullet in entry.get("bullets", [])],
            }
            rendered_entries.append(rendered)
        if rendered_entries:
            sections[str(section.get("name", ""))] = rendered_entries
    document = {
        "cv": {
            "name": content["contact"]["name"],
            "headline": content["target_role"],
            "location": content["contact"]["location"],
            "email": content["contact"]["email"],
            "phone": "+86 " + re.sub(r"\D", "", content["contact"]["phone"]),
            "sections": sections,
        },
        "design": {
            "theme": "classic",
            "page": {
                "size": "a4",
                "top_margin": page_margin,
                "bottom_margin": page_margin,
                "left_margin": page_margin,
                "right_margin": page_margin,
                "show_footer": False,
                "show_top_note": False,
            },
            "typography": {
                "font_family": "Microsoft YaHei",
                "line_spacing": line_spacing,
                "font_size": {"body": body_size, "name": "21pt", "headline": "10pt", "connections": "9pt", "section_titles": "1.15em"},
            },
            "header": {"alignment": "center", "space_below_name": "0.25cm", "space_below_headline": "0.2cm", "space_below_connections": "0.35cm", "connections": {"show_icons": False, "separator": " | ", "space_between_connections": "0.15cm"}},
            "section_titles": {"type": "with_full_line", "space_above": "0.25cm", "space_below": "0.12cm", "line_thickness": "0.5pt"},
            "sections": {"allow_page_break": True, "space_between_regular_entries": "0.55em", "space_between_text_based_entries": "0.25em"},
            "entries": {"allow_page_break": False, "date_and_location_width": "3.2cm", "highlights": {"bullet": "•", "space_left": "0.12cm", "space_above": "0cm", "space_between_items": "0.08cm", "space_between_bullet_and_text": "0.45em"}},
            "links": {"underline": False, "show_external_link_icon": False},
        },
        "locale": {"language": "mandarin_chinese"},
        "settings": {"current_date": "today", "bold_keywords": [], "pdf_title": f"{content['contact']['name']} - {content['target_role']}"},
    }
    _assert_safe_yaml(document)
    return document


def write_rendercv_yaml(content: dict[str, Any], output: Path, target_pages: int = 1) -> dict[str, Any]:
    document = build_rendercv_document(content, target_pages)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("# yaml-language-server: $schema=https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/schema.json\n" + "\n".join(_yaml_lines(document)) + "\n", encoding="utf-8")
    return {"status": "ok", "yaml": str(output.resolve()), "sha256": sha256_file(output), "target_pages": target_pages}


def _render_pngs(pdf: Path, directory: Path) -> list[str]:
    executable = Path(r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe")
    if not executable.is_file():
        raise FastResumeError("pdftoppm not found")
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.glob("page-*.png"):
        old.unlink()
    subprocess.run([str(executable), "-png", "-r", "150", str(pdf), str(directory / "page")], check=True)
    return [str(path.resolve()) for path in sorted(directory.glob("page-*.png"))]


def _pdf_page_text_counts(pdf: Path) -> list[int]:
    from pypdf import PdfReader

    return [len(comparable_pdf_text(page.extract_text() or "")) for page in PdfReader(pdf).pages]


def _vertical_coverage_from_positions(
    page_height: float, positions: list[tuple[float, float]]
) -> float | None:
    """Return the vertical share occupied by text, including the first/last glyph height."""
    if page_height <= 0 or not positions:
        return None
    lower = min(y - font_size for y, font_size in positions)
    upper = max(y + font_size for y, font_size in positions)
    return max(0.0, min(1.0, (upper - lower) / page_height))


def _text_position_y(cm: Sequence[Any], tm: Sequence[Any]) -> float:
    """Return a text fragment's y position in page user space.

    ``visitor_text`` supplies the current transformation matrix separately
    from the text matrix. RenderCV keeps the text matrix at the origin and
    puts the page translation in the current matrix, so reading ``tm[5]``
    alone collapses every fragment to y=0.
    """
    from pypdf import mult

    return float(mult(tm, cm)[5])


def _pdf_page_vertical_coverages(reader: Any) -> list[float | None]:
    coverages: list[float | None] = []
    for page in reader.pages:
        positions: list[tuple[float, float]] = []

        def collect_text(text: str, cm: Any, tm: Any, font_dict: Any, font_size: Any) -> None:
            if text and text.strip() and len(cm) >= 6 and len(tm) >= 6:
                try:
                    positions.append((_text_position_y(cm, tm), float(font_size or 0)))
                except (TypeError, ValueError):
                    pass

        try:
            page.extract_text(visitor_text=collect_text)
            page_height = float(page.mediabox.height)
        except (AttributeError, TypeError, ValueError):
            coverages.append(None)
            continue
        coverages.append(_vertical_coverage_from_positions(page_height, positions))
    return coverages


def qa_pdf(pdf: Path, content: dict[str, Any], max_pages: int, visual_mode: str) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except ImportError as error:  # pragma: no cover
        raise FastResumeError("pypdf is required") from error
    reader = PdfReader(pdf)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    compact = canonical_text(text)
    comparable = comparable_pdf_text(text)
    expected = [content["contact"][key] for key in ("name", "email")] + [content["target_role"]]
    expected.extend(str(bullet.get("text", "")) for bullet in iter_bullets(content))
    missing = [value for value in expected if comparable_pdf_text(value) not in comparable]
    expected_phone = re.sub(r"\D", "", content["contact"]["phone"])
    if expected_phone not in re.sub(r"\D", "", text):
        missing.append(content["contact"]["phone"])
    forbidden = [code for code, pattern in FORBIDDEN_TEXT_PATTERNS if pattern.search(compact)]
    page_text_counts = _pdf_page_text_counts(pdf)
    page_vertical_coverages = _pdf_page_vertical_coverages(reader)
    density_ratio = (
        min(page_text_counts) / max(page_text_counts)
        if page_text_counts and max(page_text_counts)
        else 0
    )
    anomalies = []
    if len(reader.pages) > max_pages:
        anomalies.append(f"page_count={len(reader.pages)} exceeds {max_pages}")
    if missing:
        anomalies.append(f"missing_text_count={len(missing)}")
    if "�" in text:
        anomalies.append("replacement_character_detected")
    if forbidden:
        anomalies.append("forbidden_text=" + ",".join(forbidden))
    if len(page_text_counts) > 1 and density_ratio < 0.45:
        anomalies.append(f"unbalanced_pages={density_ratio:.4f}")
    if len(reader.pages) == 1 and page_vertical_coverages[0] is not None and page_vertical_coverages[0] < 0.68:
        anomalies.append(f"sparse_single_page={page_vertical_coverages[0]:.4f}")
    renders: list[str] = []
    if visual_mode == "always" or (visual_mode == "anomaly" and anomalies):
        renders = _render_pngs(pdf, pdf.parent / "rendered")
    return {
        "status": "pass" if not anomalies else "fail",
        "pdf": str(pdf.resolve()),
        "sha256": sha256_file(pdf),
        "pages": len(reader.pages),
        "page_text_characters": page_text_counts,
        "page_density_ratio": round(density_ratio, 4),
        "page_vertical_coverage": [
            round(coverage, 4) if coverage is not None else None
            for coverage in page_vertical_coverages
        ],
        "text_characters": len(compact),
        "missing_text": missing,
        "forbidden_codes": forbidden,
        "anomalies": anomalies,
        "visual_mode": visual_mode,
        "renders": renders,
    }


def render_pdf(yaml_path: Path, pdf_path: Path, content: dict[str, Any], rendercv_bin: Path, max_pages: int, visual_mode: str) -> dict[str, Any]:
    if not rendercv_bin.is_file():
        raise FastResumeError(f"RenderCV executable not found: {rendercv_bin}")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if yaml_path.parent.resolve() != pdf_path.parent.resolve():
        raise FastResumeError("resume.yaml and PDF must share a directory for deterministic output paths")
    typst_name = ".rendercv-fast-temp.typ"
    command = [str(rendercv_bin), "render", yaml_path.name, "-q", "-nomd", "-nohtml", "-nopng", "-typ", typst_name, "-pdf", pdf_path.name]
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=yaml_path.parent, capture_output=True, text=True, encoding="utf-8", errors="replace")
    elapsed = time.perf_counter() - started
    typst_path = yaml_path.parent / typst_name
    if completed.returncode != 0 or not pdf_path.is_file():
        if typst_path.exists():
            typst_path.unlink()
        raise FastResumeError(f"RenderCV failed: {completed.stdout}\n{completed.stderr}")
    qa = qa_pdf(pdf_path, content, max_pages, visual_mode)
    if typst_path.exists():
        typst_path.unlink()
    qa["render_seconds"] = round(elapsed, 4)
    qa["rendercv_version"] = "2.8"
    qa["intermediate_typst_removed"] = not typst_path.exists()
    return qa


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fast-assemble resume pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    importer = sub.add_parser("import-library")
    importer.add_argument("--source-root", required=True, type=Path)
    importer.add_argument("--applications-root", default="applications", type=Path)
    importer.add_argument("--baseline-index", default="profile/resume-baselines/index.json", type=Path)
    importer.add_argument("--profile", default="profile/01-candidate-profile.md", type=Path)
    importer.add_argument("--claims-output", default="profile/resume-claims.json", type=Path)
    importer.add_argument("--report-output", default="outputs/fast-assemble-library-report.json", type=Path)
    assemble = sub.add_parser("assemble")
    assemble.add_argument("--jd-analysis", required=True, type=Path)
    assemble.add_argument("--selection", required=True, type=Path)
    assemble.add_argument("--claims", default="profile/resume-claims.json", type=Path)
    assemble.add_argument("--profile", default="profile/01-candidate-profile.md", type=Path)
    assemble.add_argument("--answers", default="profile/application-answers.md", type=Path)
    assemble.add_argument("--output", required=True, type=Path)
    writer = sub.add_parser("apply-writer")
    writer.add_argument("--content", required=True, type=Path)
    writer.add_argument("--additions", required=True, type=Path)
    writer.add_argument("--profile", default="profile/01-candidate-profile.md", type=Path)
    writer.add_argument("--output", required=True, type=Path)
    writer_packet = sub.add_parser("writer-packet")
    writer_packet.add_argument("--content", required=True, type=Path)
    writer_packet.add_argument("--profile", default="profile/01-candidate-profile.md", type=Path)
    writer_packet.add_argument("--output", required=True, type=Path)
    route = sub.add_parser("route")
    route.add_argument("--job", required=True, type=Path)
    route.add_argument("--claims", default="profile/resume-claims.json", type=Path)
    prioritize = sub.add_parser("prioritize")
    prioritize.add_argument("--batch", required=True, type=Path)
    prioritize.add_argument("--output", required=True, type=Path)
    hr = sub.add_parser("validate-hr")
    hr.add_argument("--review", required=True, type=Path)
    fusion = sub.add_parser("from-fusion")
    fusion.add_argument("--application-dir", required=True, type=Path)
    fusion.add_argument("--company", required=True)
    fusion.add_argument("--target-role", required=True)
    fusion.add_argument("--context", choices=("game", "non_game"), required=True)
    fusion.add_argument("--role-family", required=True)
    fusion.add_argument("--run-id")
    fusion.add_argument("--profile", default="profile/01-candidate-profile.md", type=Path)
    fusion.add_argument("--answers", default="profile/application-answers.md", type=Path)
    fusion.add_argument("--output", required=True, type=Path)
    yaml_parser = sub.add_parser("yaml")
    yaml_parser.add_argument("--content", required=True, type=Path)
    yaml_parser.add_argument("--output", required=True, type=Path)
    yaml_parser.add_argument("--target-pages", choices=(1, 2), default=1, type=int)
    render = sub.add_parser("render")
    render.add_argument("--yaml", required=True, type=Path)
    render.add_argument("--content", required=True, type=Path)
    render.add_argument("--pdf", required=True, type=Path)
    render.add_argument("--rendercv-bin", default=Path(".tmp/rendercv-2.8/Scripts/rendercv.exe"), type=Path)
    render.add_argument("--max-pages", type=int, default=2)
    render.add_argument("--visual-mode", choices=("never", "anomaly", "always"), default="anomaly")
    render.add_argument("--qa-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "import-library":
            result = import_library(args.source_root, args.applications_root, args.baseline_index, args.profile, args.claims_output, args.report_output)
        elif args.command == "assemble":
            profile_text = args.profile.read_text(encoding="utf-8-sig")
            result = assemble_fast_content(read_json(args.jd_analysis), read_json(args.selection), read_json(args.claims), profile_text, parse_answers(args.answers.read_text(encoding="utf-8-sig")))
            write_json(args.output, result)
            result = {"status": "ok", "output": str(args.output.resolve()), "content_sha256": sha256_file(args.output), "supported_coverage_gaps": len(result["supported_coverage_gaps"]), "fact_gaps": len(result["fact_gaps"])}
        elif args.command == "route":
            result = route_job(read_json(args.job), read_json(args.claims))
        elif args.command == "apply-writer":
            profile_text = args.profile.read_text(encoding="utf-8-sig")
            content = apply_writer_additions(
                read_json(args.content), read_json(args.additions), profile_text
            )
            write_json(args.output, content)
            result = {
                "status": "ok",
                "output": str(args.output.resolve()),
                "content_sha256": sha256_file(args.output),
                "remaining_supported_coverage_gaps": len(
                    content["supported_coverage_gaps"]
                ),
            }
        elif args.command == "writer-packet":
            packet = build_fast_writer_packet(
                read_json(args.content), args.profile.read_text(encoding="utf-8-sig")
            )
            write_json(args.output, packet)
            result = {
                "status": "ok",
                "output": str(args.output.resolve()),
                "packet_sha256": sha256_file(args.output),
                "supported_coverage_gaps": len(packet["supported_coverage_gaps"]),
            }
        elif args.command == "prioritize":
            batch = prioritize_job_batch(read_json(args.batch))
            write_json(args.output, batch)
            result = {
                "status": "ok",
                "output": str(args.output.resolve()),
                "positions": len(batch["positions"]),
                "batch_sha256": sha256_file(args.output),
            }
        elif args.command == "validate-hr":
            result = validate_hr_review(read_json(args.review))
        elif args.command == "from-fusion":
            profile_text = args.profile.read_text(encoding="utf-8-sig")
            content = content_from_approved_fusion(args.application_dir, args.company, args.target_role, args.context, args.role_family, parse_answers(args.answers.read_text(encoding="utf-8-sig")), profile_text, args.run_id)
            write_json(args.output, content)
            result = {"status": "ok", "output": str(args.output.resolve()), "content_sha256": sha256_file(args.output)}
        elif args.command == "yaml":
            result = write_rendercv_yaml(read_json(args.content), args.output, args.target_pages)
        else:
            qa = render_pdf(args.yaml.resolve(), args.pdf.resolve(), read_json(args.content), args.rendercv_bin.resolve(), args.max_pages, args.visual_mode)
            if args.qa_output:
                write_json(args.qa_output, qa)
            result = qa
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") not in {"fail", "error"} else 2
    except (FastResumeError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
