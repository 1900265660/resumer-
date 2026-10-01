"""Audit reusable resume baselines and route JD-specific resume work.

The module deliberately keeps the confirmed candidate profile as the only fact
source.  A baseline is an immutable, private content snapshot plus provenance;
it is never treated as permission to invent or silently retain stale claims.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


SCHEMA_VERSION = "1.0"
REUSABLE_STATUSES = {"reusable"}
SKIP_DIRECTORY_NAMES = {
    ".chrome-profile-resume-merge",
    "旧简历",
    "_inspection-final",
}
SUPPORTED_EXTENSIONS = {".pdf"}


@dataclass(frozen=True)
class TextIssue:
    code: str
    severity: str
    message: str
    pattern: re.Pattern[str]


KNOWN_TEXT_ISSUES: tuple[TextIssue, ...] = (
    TextIssue(
        "stale_email",
        "repair_required",
        "使用了已停用邮箱 1900265660@shu.edu.cn。",
        re.compile(r"1900265660\s*@\s*shu\.edu\.cn", re.I),
    ),
    TextIssue(
        "removed_growth_claim",
        "blocked",
        "包含已从事实库删除的“环比增长 300%”。",
        re.compile(r"环比增长\s*300\s*%"),
    ),
    TextIssue(
        "stale_editor_title",
        "repair_required",
        "《收获》岗位名称仍为“实习编辑”，当前确认名称为“实习助理”。",
        re.compile(r"《?收获》?.{0,24}实习编辑", re.S),
    ),
    TextIssue(
        "removed_social_work_courses",
        "repair_required",
        "展示了已按偏好删除的社会工作课程。",
        re.compile(r"社会心理学|消费社会学|市场调研方法|文化研究"),
    ),
    TextIssue(
        "unsupported_error_rate",
        "blocked",
        "包含事实库未支持的“错漏率 0.5%”口径。",
        re.compile(r"错漏率.{0,12}0\.5\s*%"),
    ),
    TextIssue(
        "removed_recruiting_bot",
        "blocked",
        "包含已被事实库明确撤回的招聘智能问答助手项目。",
        re.compile(r"聚能媒体.{0,20}招聘.{0,20}(智能问答|助手)", re.S),
    ),
)


ROLE_RULES: tuple[tuple[re.Pattern[str], str, str | None], ...] = (
    (re.compile(r"AI\s*产品|产品\s*Builder", re.I), "ai_product_manager", None),
    (re.compile(r"卡牌.*策划|系统.*策划", re.I), "game_designer", "system"),
    (re.compile(r"游戏文案|游戏编剧", re.I), "game_designer", "writing"),
    (re.compile(r"项目管理|产品\s*PM", re.I), "game_production_pm", None),
    (re.compile(r"游戏策划|应聘策划岗", re.I), "game_designer", "general"),
    (re.compile(r"社区运营", re.I), "community_operations", "community"),
    (re.compile(r"内容运营", re.I), "community_operations", "content"),
    (re.compile(r"增长|产品运营|用户运营", re.I), "community_operations", "growth"),
    (re.compile(r"HR|招聘", re.I), "human_resources", None),
    (re.compile(r"编辑|童书", re.I), "editorial", None),
)


EXPERIENCE_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("EXP-WORK-001", ("《收获》编辑部", "收获编辑部")),
    ("EXP-WORK-002", ("梧州市中级人民法院",)),
    ("EXP-WORK-004", ("聚微传媒", "校园招聘大使")),
    ("EXP-WORK-005", ("智联招聘", "高校江南行")),
    ("EXP-PROJECT-001", ("MaiBot", "亲密关系对话机器人")),
    ("EXP-PROJECT-006", ("Codex 求职助手", "中国网申自动投递 Harness")),
    ("EXP-PROJECT-007", ("Mewgenics", "收音机音乐模式")),
    ("EXP-PROJECT-008", ("杀戮尖塔2", "杀戮尖塔 2")),
    ("EXP-PROJECT-009", ("独立游戏翻译组", "独立游戏翻译")),
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(payload)


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:  # pragma: no cover - environment contract
        raise RuntimeError("pypdf is required to audit PDF baselines") from error
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _path_is_skipped(path: Path, source_root: Path) -> bool:
    try:
        relative = path.relative_to(source_root)
    except ValueError:
        return True
    return any(part in SKIP_DIRECTORY_NAMES for part in relative.parts)


def discover_resume_pdfs(source_root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in source_root.rglob("*.pdf")
            if path.suffix.lower() in SUPPORTED_EXTENSIONS
            and not _path_is_skipped(path, source_root)
        ),
        key=lambda item: str(item).lower(),
    )


def audit_text(text: str, *, expected_phone: str, expected_email: str) -> list[dict[str, str]]:
    compact = canonical_text(text)
    findings = [
        {"code": issue.code, "severity": issue.severity, "message": issue.message}
        for issue in KNOWN_TEXT_ISSUES
        if issue.pattern.search(compact)
    ]
    if expected_email.lower() not in compact.lower():
        findings.append(
            {
                "code": "current_email_missing",
                "severity": "repair_required",
                "message": f"文本层未找到当前邮箱 {expected_email}。",
            }
        )
    digits = re.sub(r"\D", "", compact)
    if expected_phone not in digits:
        findings.append(
            {
                "code": "current_phone_missing",
                "severity": "repair_required",
                "message": f"文本层未找到当前手机号 {expected_phone}。",
            }
        )
    if len(compact) < 500:
        findings.append(
            {
                "code": "insufficient_text_layer",
                "severity": "blocked",
                "message": "PDF 文本层不足 500 字，不能作为可自动微调的内容快照。",
            }
        )
    return findings


def infer_role(path: Path, text: str) -> tuple[str, str | None]:
    # The file name is the author-controlled role label.  Inspect it before the
    # body so an incidental "项目管理" phrase cannot override "游戏文案".
    for pattern, family, track in ROLE_RULES:
        if pattern.search(path.stem):
            return family, track
    haystack = canonical_text(text)[:1200]
    for pattern, family, track in ROLE_RULES:
        if pattern.search(haystack):
            return family, track
    return "general", None


def infer_experience_ids(text: str) -> list[str]:
    return [
        experience_id
        for experience_id, markers in EXPERIENCE_MARKERS
        if any(marker.lower() in text.lower() for marker in markers)
    ]


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _resume_hash_from_manifest(value: dict[str, Any]) -> str | None:
    resume = value.get("resume")
    if isinstance(resume, dict) and isinstance(resume.get("sha256"), str):
        return resume["sha256"].lower()
    return None


def build_application_index(applications_root: Path) -> dict[str, list[Path]]:
    result: dict[str, set[Path]] = {}
    if not applications_root.exists():
        return {}
    for application_dir in applications_root.iterdir():
        if not application_dir.is_dir():
            continue
        hashes: set[str] = set()
        for manifest_name in ("manifest-draft.json", "manifest.json"):
            payload = _read_json(application_dir / manifest_name)
            if payload:
                digest = _resume_hash_from_manifest(payload)
                if digest:
                    hashes.add(digest)
        for pdf in application_dir.rglob("*.pdf"):
            try:
                hashes.add(sha256_file(pdf))
            except OSError:
                continue
        for digest in hashes:
            result.setdefault(digest, set()).add(application_dir)
    return {digest: sorted(paths) for digest, paths in result.items()}


def _normalised_artifact_label(value: str) -> str:
    label = value.lower()
    for pattern in (
        r"测试候选人",
        r"20\d{2}届?校招",
        r"\d{2}届秋招",
        r"校招简历",
        r"应届简历",
        r"可编辑",
        r"最终(?:版|校验)?",
        r"一页版",
        r"resume[-_ ]?output",
        r"v\d+",
        r"简历",
    ):
        label = re.sub(pattern, "", label, flags=re.I)
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", label)


def matching_application_dirs(primary_path: Path, applications_root: Path) -> list[Path]:
    """Return one high-confidence name match when exact hashes are unavailable.

    A unique winner and a margin over the runner-up are required.  This avoids
    silently attaching a generic resume such as "游戏策划" to a company JD.
    """

    source_label = _normalised_artifact_label(primary_path.stem)
    if len(source_label) < 5 or not applications_root.exists():
        return []
    scored: list[tuple[float, Path]] = []
    for directory in applications_root.iterdir():
        if not directory.is_dir():
            continue
        target_label = _normalised_artifact_label(directory.name)
        if len(target_label) < 5:
            continue
        score = difflib.SequenceMatcher(None, source_label, target_label).ratio()
        if source_label in target_label or target_label in source_label:
            score = max(score, min(len(source_label), len(target_label)) / max(len(source_label), len(target_label)))
        scored.append((score, directory))
    scored.sort(key=lambda pair: (pair[0], str(pair[1]).lower()), reverse=True)
    if not scored or scored[0][0] < 0.72:
        return []
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    if scored[0][0] - runner_up < 0.08:
        return []
    return [scored[0][1]]


def _hr_dimension_scores(payload: dict[str, Any]) -> list[float]:
    names = (
        "role_fit",
        "narrative_completeness",
        "evidence_specificity",
        "decision_readiness",
        "credibility",
        "content_fullness",
    )
    dimensions = payload.get("dimensions")
    scores: list[float] = []
    for name in names:
        value: Any = dimensions.get(name) if isinstance(dimensions, dict) else payload.get(name)
        if isinstance(value, dict):
            value = value.get("score")
        if isinstance(value, (int, float)):
            scores.append(float(value))
    return scores


def _baseline_hr_dimensions_pass(payload: dict[str, Any]) -> tuple[bool, int]:
    """Accept the historical five-dimension reviewer only for baseline ranking.

    Every new light-tune review is validated elsewhere against all six current
    dimensions.  The compatibility here only recovers provenance for finished
    resumes created before content_fullness became mandatory.
    """

    scores = _hr_dimension_scores(payload)
    return len(scores) >= 5 and min(scores) >= 8.0, len(scores)


def _current_hr_dimensions_pass(payload: dict[str, Any]) -> bool:
    scores = _hr_dimension_scores(payload)
    return len(scores) == 6 and min(scores) >= 8.0


def best_hr_review(application_dirs: Sequence[Path]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for directory in application_dirs:
        for path in directory.glob("resume-content/runs/*/hr-review.json"):
            payload = _read_json(path)
            if not payload:
                continue
            overall = payload.get("overall_score", payload.get("overall"))
            dimensions_passed, dimension_count = _baseline_hr_dimensions_pass(payload)
            passed = (
                payload.get("passed") is True
                and payload.get("recommendation") == "strong_push"
                and isinstance(overall, (int, float))
                and float(overall) >= 9.0
                and dimensions_passed
            )
            candidates.append(
                {
                    "path": str(path.resolve()),
                    "passed": passed,
                    "recommendation": payload.get("recommendation"),
                    "overall_score": overall,
                    "dimension_count": dimension_count,
                    "legacy_five_dimension_record": dimension_count == 5,
                }
            )
    if not candidates:
        return {"status": "not_verified", "passed": False}
    return max(
        candidates,
        key=lambda item: (bool(item["passed"]), float(item["overall_score"] or 0)),
    )


def approved_content_sources(application_dirs: Sequence[Path]) -> list[str]:
    sources: list[str] = []
    for directory in application_dirs:
        current_path = directory / "resume-content" / "current.json"
        current = _read_json(current_path)
        if not current or current.get("status") != "approved":
            continue
        run_id = current.get("approved_run_id")
        if not isinstance(run_id, str):
            continue
        content_path = directory / "resume-content" / "runs" / run_id / "content-master.md"
        if content_path.is_file():
            sources.append(str(content_path.resolve()))
    return sorted(set(sources))


def editable_sources_for(
    primary_path: Path, application_dirs: Sequence[Path], source_root: Path
) -> list[str]:
    candidates: set[Path] = set()
    for suffix in (".html", ".md", ".docx"):
        sibling = primary_path.with_suffix(suffix)
        if sibling.is_file():
            candidates.add(sibling.resolve())
    for path in source_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".html", ".md", ".docx"}:
            if path.stem == primary_path.stem:
                candidates.add(path.resolve())
    for directory in application_dirs:
        for pattern in ("*.html", "resume/*.html", "resume-content/runs/*/content-master.md"):
            candidates.update(path.resolve() for path in directory.glob(pattern) if path.is_file())
    return sorted(str(path) for path in candidates)


def manifest_visual_status(application_dirs: Sequence[Path], source_hashes: set[str]) -> str:
    for directory in application_dirs:
        payload = _read_json(directory / "manifest-draft.json")
        if not payload or _resume_hash_from_manifest(payload) not in source_hashes:
            continue
        checks = payload.get("review_checks")
        if isinstance(checks, dict) and checks.get("pdf_visual") == "passed":
            return "passed"
    return "not_verified"


def stored_visual_review(output_root: Path, source_hashes: set[str]) -> dict[str, Any] | None:
    payload = _read_json(output_root / "visual-reviews.json")
    reviews = payload.get("reviews") if payload else None
    if not isinstance(reviews, list):
        return None
    for review in reviews:
        if not isinstance(review, dict):
            continue
        if review.get("source_sha256") in source_hashes and review.get("status") == "passed":
            return review
    return None


def classify_status(
    findings: Sequence[dict[str, str]],
    *,
    hr_passed: bool,
    editable_sources: Sequence[str],
    artifact_type: str,
) -> str:
    if artifact_type != "resume":
        return "reference_only"
    severities = {item["severity"] for item in findings}
    if "blocked" in severities:
        return "blocked"
    if "repair_required" in severities:
        return "repair_required"
    if hr_passed and editable_sources:
        return "reusable"
    return "reference_only"


def _artifact_type(path: Path) -> str:
    return "supporting_attachment" if re.search(r"作品集", path.stem) else "resume"


def audit_baselines(
    *,
    source_root: Path,
    applications_root: Path,
    profile_path: Path,
    output_root: Path,
    expected_phone: str,
    expected_email: str,
    text_extractor: Callable[[Path], str] = extract_pdf_text,
) -> dict[str, Any]:
    profile_digest = sha256_file(profile_path)
    application_index = build_application_index(applications_root)
    grouped: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []
    for path in discover_resume_pdfs(source_root):
        try:
            payload = path.read_bytes()
            text = text_extractor(path)
        except Exception as error:  # keep the audit complete and explicit
            errors.append({"path": str(path.resolve()), "error": str(error)})
            continue
        file_digest = sha256_bytes(payload)
        text_digest = sha256_bytes(canonical_text(text).encode("utf-8"))
        grouped.setdefault(text_digest, []).append(
            {
                "path": path.resolve(),
                "sha256": file_digest,
                "size": len(payload),
                "modified_at": datetime.fromtimestamp(
                    path.stat().st_mtime, timezone.utc
                ).isoformat(),
                "text": text,
            }
        )

    items: list[dict[str, Any]] = []
    output_items = output_root / "items"
    output_items.mkdir(parents=True, exist_ok=True)
    for text_digest, sources in sorted(grouped.items()):
        sources.sort(
            key=lambda item: (
                "resume-output" in str(item["path"]).lower(),
                -item["path"].stat().st_mtime,
                str(item["path"]).lower(),
            )
        )
        primary = sources[0]
        source_hashes = {item["sha256"] for item in sources}
        application_dirs = sorted(
            {
                directory
                for digest in source_hashes
                for directory in application_index.get(digest, [])
            }
        )
        if not application_dirs:
            application_dirs = matching_application_dirs(
                primary["path"], applications_root
            )
        text = primary["text"]
        role_family, role_track = infer_role(primary["path"], text)
        findings = audit_text(
            text, expected_phone=expected_phone, expected_email=expected_email
        )
        hr = best_hr_review(application_dirs)
        editable = editable_sources_for(primary["path"], application_dirs, source_root)
        editable.extend(approved_content_sources(application_dirs))
        editable = sorted(set(editable))
        artifact_type = _artifact_type(primary["path"])
        status = classify_status(
            findings,
            hr_passed=bool(hr.get("passed")),
            editable_sources=editable,
            artifact_type=artifact_type,
        )
        baseline_id = f"baseline-{text_digest[:12]}"
        item_dir = output_items / baseline_id
        item_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = item_dir / "content.txt"
        snapshot_path.write_text(text, encoding="utf-8")
        stored_visual = stored_visual_review(output_root, source_hashes)
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "baseline_id": baseline_id,
            "title": primary["path"].stem,
            "artifact_type": artifact_type,
            "status": status,
            "role_family": role_family,
            "role_track": role_track,
            "experience_ids": infer_experience_ids(text),
            "profile_sha256": profile_digest,
            "content_text_sha256": text_digest,
            "content_snapshot_path": str(snapshot_path.resolve()),
            "source_files": [
                {
                    "path": str(item["path"]),
                    "sha256": item["sha256"],
                    "size": item["size"],
                    "modified_at": item["modified_at"],
                }
                for item in sources
            ],
            "duplicate_count": len(sources) - 1,
            "application_dirs": [str(path.resolve()) for path in application_dirs],
            "editable_sources": editable,
            "hr_review": hr,
            "visual_review": stored_visual
            or {"status": manifest_visual_status(application_dirs, source_hashes)},
            "findings": findings,
            "allowed_uses": [
                "同角色族和方向 JD 的轻微调候选",
                "在当前事实库哈希未变化时复用已审计内容快照",
                "比较岗位关键词覆盖、经历顺序和局部表达",
            ],
            "forbidden_uses": [
                "作为候选人事实源",
                "跨角色族直接套用",
                "保留已被当前事实库撤回或修正的旧表述",
                "绕过轻调后的确定性事实检查和独立 HR Reviewer",
            ],
        }
        metadata_path = item_dir / "metadata.json"
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        items.append(metadata)

    generated_at = datetime.now(timezone.utc).isoformat()
    index = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source_root": str(source_root.resolve()),
        "applications_root": str(applications_root.resolve()),
        "profile_path": str(profile_path.resolve()),
        "profile_sha256": profile_digest,
        "items": items,
        "errors": errors,
        "summary": {
            status: sum(1 for item in items if item["status"] == status)
            for status in ("reusable", "repair_required", "reference_only", "blocked")
        },
    }
    index["index_sha256"] = canonical_json_sha256(index)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return index


def load_index(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if not value or value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"invalid baseline index: {path}")
    return value


def _keyword_overlap(keywords: Sequence[str], item: dict[str, Any]) -> int:
    content = Path(item["content_snapshot_path"]).read_text(encoding="utf-8")
    return sum(1 for keyword in keywords if keyword and keyword.lower() in content.lower())


def _baseline_sources_current(item: dict[str, Any]) -> bool:
    sources = item.get("source_files")
    if not isinstance(sources, list) or not sources:
        return False
    for source in sources:
        if not isinstance(source, dict):
            return False
        path_value = source.get("path")
        expected = source.get("sha256")
        if not isinstance(path_value, str) or not isinstance(expected, str):
            return False
        path = Path(path_value)
        try:
            if sha256_file(path) != expected:
                return False
        except OSError:
            return False
    return True


def route_resume(
    *,
    index: dict[str, Any],
    current_profile_sha256: str,
    role_family: str,
    role_track: str | None,
    keywords: Sequence[str],
    required_experience_ids: Sequence[str] = (),
    material_change_reasons: Sequence[str] = (),
) -> dict[str, Any]:
    stale_index = index.get("profile_sha256") != current_profile_sha256
    stale_source = False
    candidates: list[tuple[tuple[int, int, int, str], dict[str, Any]]] = []
    for item in index.get("items", []):
        if item.get("status") not in REUSABLE_STATUSES:
            continue
        if item.get("profile_sha256") != current_profile_sha256:
            continue
        if not _baseline_sources_current(item):
            stale_source = True
            continue
        if item.get("role_family") != role_family:
            continue
        if item.get("role_track") != role_track:
            continue
        item_experiences = set(item.get("experience_ids", []))
        if required_experience_ids and not set(required_experience_ids).issubset(
            item_experiences
        ):
            continue
        hr_passed = bool(item.get("hr_review", {}).get("passed"))
        editable = bool(item.get("editable_sources"))
        overlap = _keyword_overlap(keywords, item)
        newest = max(
            (str(source.get("modified_at", "")) for source in item.get("source_files", [])),
            default="",
        )
        score = (
            int(hr_passed),
            int(editable),
            overlap,
            newest,
        )
        candidates.append((score, item))
    candidates.sort(key=lambda value: value[0], reverse=True)

    if material_change_reasons:
        reason = "；".join(material_change_reasons)
    elif stale_index:
        reason = "事实库哈希已变化，基线必须重新审计。"
    elif stale_source:
        reason = "成品源文件哈希已变化或文件缺失，基线必须重新审计。"
    elif not candidates:
        reason = "没有事实有效、角色族与方向一致且具有可编辑源的合格基线。"
    else:
        selected = candidates[0][1]
        return {
            "schema_version": SCHEMA_VERSION,
            "decision": "light_tune",
            "baseline_id": selected["baseline_id"],
            "baseline_content_path": selected["content_snapshot_path"],
            "editable_sources": selected.get("editable_sources", []),
            "requires_rewrite_batch_approval": False,
            "required_gates": [
                "deterministic_fact_check",
                "fresh_hr_reviewer",
                "pdf_visual",
                "pdf_text_layer",
                "ats",
            ],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "decision": "full_rewrite",
        "reason": reason,
        "requires_rewrite_batch_approval": True,
        "must_not_start_dual_writers": True,
        "content_pipeline_after_approval": "custom-resume",
    }


def evaluate_light_hr(payload: dict[str, Any], *, generation_round: int) -> dict[str, Any]:
    defect = payload.get("defect_category")
    if defect in {"selection", "story", "fact_conflict"} or payload.get(
        "requires_experience_change"
    ) is True:
        return {
            "decision": "rewrite_required",
            "requires_rewrite_batch_approval": True,
            "reason": "HR 指出选材、故事或事实层缺陷，超出轻微调边界。",
        }
    overall = payload.get("overall_score")
    recommendation = payload.get("recommendation")
    passed = (
        recommendation == "strong_push"
        and isinstance(overall, (int, float))
        and float(overall) >= 9.0
        and _current_hr_dimensions_pass(payload)
    )
    if passed:
        return {
            "decision": "passed",
            "can_generate_resume": True,
            "requires_user_content_approval": False,
        }
    if generation_round < 3:
        return {
            "decision": "local_repair",
            "next_generation_round": generation_round + 1,
            "can_generate_resume": False,
        }
    return {
        "decision": "rewrite_required",
        "requires_rewrite_batch_approval": True,
        "reason": "轻微调初稿及两次局部修订后仍未达到 HR 强推门槛。",
    }


def _json_output(value: Any) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit", help="Build the private baseline index")
    audit.add_argument("--source-root", type=Path, required=True)
    audit.add_argument("--applications-root", type=Path, required=True)
    audit.add_argument("--profile", type=Path, required=True)
    audit.add_argument("--output-root", type=Path, required=True)
    audit.add_argument("--phone", required=True)
    audit.add_argument("--email", required=True)

    route = subparsers.add_parser("route", help="Route one normalized JD")
    route.add_argument("--index", type=Path, required=True)
    route.add_argument("--profile", type=Path, required=True)
    route.add_argument("--role-family", required=True)
    route.add_argument("--role-track")
    route.add_argument("--keyword", action="append", default=[])
    route.add_argument("--required-experience-id", action="append", default=[])
    route.add_argument("--material-change", action="append", default=[])

    hr = subparsers.add_parser("evaluate-hr", help="Validate a light-tune HR result")
    hr.add_argument("--input", type=Path, required=True)
    hr.add_argument("--generation-round", type=int, choices=(1, 2, 3), required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "audit":
        _json_output(
            audit_baselines(
                source_root=args.source_root,
                applications_root=args.applications_root,
                profile_path=args.profile,
                output_root=args.output_root,
                expected_phone=args.phone,
                expected_email=args.email,
            )["summary"]
        )
        return 0
    if args.command == "route":
        _json_output(
            route_resume(
                index=load_index(args.index),
                current_profile_sha256=sha256_file(args.profile),
                role_family=args.role_family,
                role_track=args.role_track,
                keywords=args.keyword,
                required_experience_ids=args.required_experience_id,
                material_change_reasons=args.material_change,
            )
        )
        return 0
    payload = _read_json(args.input)
    if payload is None:
        raise ValueError(f"invalid HR review JSON: {args.input}")
    _json_output(evaluate_light_hr(payload, generation_round=args.generation_round))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
