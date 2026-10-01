from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROUTE_SCRIPTS = (
    REPO_ROOT / ".agents" / "skills" / "china-job-search" / "scripts"
)
sys.path.insert(0, str(CONTENT_ROUTE_SCRIPTS))

from content_route import ContentRouteError, route_content  # noqa: E402


def test_main_harness_documents_v15_release_candidate_gate() -> None:
    harness = (
        REPO_ROOT / ".agents" / "skills" / "china-job-search" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert ".agents/skills/custom-resume/SKILL.md" in harness
    assert "$custom-resume" in harness
    assert "当前已发布的两个角色族" in harness
    assert "awaiting_v15_release_approval" in harness
    for role_family in (
        "ai_product_manager",
        "game_production_pm",
        "community_operations",
        "community_product_manager",
        "game_designer",
    ):
        assert role_family in harness
    assert "scripts/content_route.py" in harness
    assert "方向不明、缺失或非法时停在用户确认" in harness
    assert "只有用户明确批准内容后" in harness
    assert "Deprecated 旧版定制回退（仅限用户显式要求）" in harness
    assert ".agents/agents/resume-optimizer-agent.md" in harness
    assert ".agents/prompts/campus-resume-optimizer.md" in harness
    assert "不得静默回退" in harness
    assert "validate_approved_manifest.ps1" in harness


def test_t28_main_harness_keeps_new_roles_behind_release_approval() -> None:
    published_routes = [
        ("ai_product_manager", None),
        ("game_production_pm", None),
    ]
    for role_family, role_track in published_routes:
        result = route_content(role_family, role_track)
        assert result["status"] == "routed"
        assert result["content_pipeline"] == "custom-resume"

    release_candidate_routes = [
        ("community_operations", "community"),
        ("community_operations", "content"),
        ("community_operations", "growth"),
        ("community_operations", "integrated"),
        ("community_product_manager", None),
        ("game_designer", "system"),
        ("game_designer", "combat"),
        ("game_designer", "writing"),
        ("game_designer", "narrative"),
        ("game_designer", "general"),
    ]
    for role_family, role_track in release_candidate_routes:
        result = route_content(role_family, role_track)
        assert result["status"] == "awaiting_v15_release_approval"
        assert result["content_pipeline"] is None
        assert result["candidate_content_pipeline"] == "custom-resume"
        assert result["requires_user_release_approval"] is True
        assert result["role_family"] == role_family
        assert result["role_track"] == role_track


def test_t28_unknown_or_invalid_direction_never_silently_uses_legacy() -> None:
    with pytest.raises(ContentRouteError, match="requires user confirmation"):
        route_content("community_operations")
    with pytest.raises(ContentRouteError, match="requires user confirmation"):
        route_content("game_designer", "level")
    with pytest.raises(ContentRouteError, match="requires user confirmation"):
        route_content("ai_product_manager", "growth")

    unsupported = route_content("brand_marketing")
    assert unsupported == {
        "status": "out_of_scope",
        "content_pipeline": None,
        "role_family": "brand_marketing",
        "role_track": None,
        "requires_explicit_legacy_approval": True,
    }


def test_t28_legacy_fallback_requires_explicit_approval_and_reason() -> None:
    with pytest.raises(ContentRouteError, match="recorded reason"):
        route_content("brand_marketing", legacy_approved=True)
    fallback = route_content(
        "brand_marketing",
        legacy_approved=True,
        fallback_reason="该岗位族不在 Schema 1.4 支持范围，用户明确批准旧版回退。",
    )
    assert fallback["content_pipeline"] == "legacy-explicit-fallback"

    unavailable = route_content("ai_product_manager", runtime_failure=True)
    assert unavailable["status"] == "custom_resume_unavailable"
    with pytest.raises(ContentRouteError, match="preference override"):
        route_content(
            "game_designer",
            "system",
            legacy_approved=True,
            fallback_reason="用户更喜欢旧版。",
        )


def test_custom_resume_runtime_has_no_pdf_or_submission_dependencies() -> None:
    scripts_dir = REPO_ROOT / ".agents" / "skills" / "custom-resume" / "scripts"
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in scripts_dir.glob("*.py")
    ).lower()
    forbidden = {
        "render_resume_pdf",
        "create_approved_manifest",
        "browser-application",
        "playwright",
        "selenium",
        ".pdf",
        ".html",
    }
    assert not forbidden.intersection(combined)


def test_root_rules_keep_content_and_application_state_separate() -> None:
    root_rules = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "manifest.resume_content" in root_rules
    assert "不得推进岗位申请主状态" in root_rules
    assert "不得生成 PDF 或触发投递" in root_rules


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _run_pwsh(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(script), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _build_approval_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "workspace"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (root / "AGENTS.md").write_text("test workspace", encoding="utf-8")
    for name in (
        "approval_manifest_common.ps1",
        "create_approved_manifest.ps1",
        "validate_approved_manifest.ps1",
    ):
        shutil.copy2(REPO_ROOT / "scripts" / name, scripts / name)

    application = root / "applications" / "示例公司_游戏制作PM"
    application.mkdir(parents=True)
    artifact_paths = {
        "jd": application / "jd.md",
        "resume": application / "resume.pdf",
        "answers": application / "answers.json",
        "review": application / "review.md",
    }
    for name, path in artifact_paths.items():
        path.write_text(f"verified {name}", encoding="utf-8")

    run_id = "cr_20260830T120000_abc123"
    run_dir = application / "resume-content" / "runs" / run_id
    run_dir.mkdir(parents=True)
    content_master = run_dir / "content-master.md"
    content_master.write_text("approved resume content", encoding="utf-8")
    story_plan = {"schema_version": "1.5", "experiences": []}
    fusion = {
        "schema_version": "1.5",
        "sections": [],
        "decisions": [],
        "test_bullet_id": "FUSION-001",
    }
    required_run_artifacts: dict[str, object] = {
        "jd-analysis.json": {"schema_version": "1.5", "requirements": []},
        "capability-transfer-map.json": {"schema_version": "1.5", "scans": []},
        "experience-selection.json": {"schema_version": "1.5", "candidates": []},
        "selection-audit-pre.json": {"schema_version": "1.5", "passed": True},
        "story-plan.json": story_plan,
        "selection-user-approval.json": {
            "schema_version": "1.5",
            "selection_approval_id": "selection_approval_" + "d" * 32,
            "experience_selection_sha256": "e" * 64,
            "story_plan_sha256": _canonical_json_sha256(story_plan),
        },
        "draft-writer.json": {"schema_version": "1.5", "agent": "writer"},
        "draft-asu.json": {"schema_version": "1.5", "agent": "asu_writer"},
        "draft-quality-audit.json": {"schema_version": "1.5", "passed": True},
        "fusion.json": fusion,
        "quality-gate.json": {
            "schema_version": "1.5",
            "passed": True,
            "hard_failures": [],
            "candidate_sha256": _canonical_json_sha256(fusion),
            "story_plan_sha256": _canonical_json_sha256(story_plan),
        },
        "audit.json": {"schema_version": "1.5", "disposition": "passed"},
        "hr-review.json": {
            "schema_version": "1.5",
            "passed": True,
            "recommendation": "strong_push",
            "overall_score": 9.2,
            **{
                name: {"score": 9.0, "evidence_bullet_ids": ["FUSION-001"]}
                for name in (
                    "role_fit",
                    "narrative_completeness",
                    "evidence_specificity",
                    "decision_readiness",
                    "credibility",
                    "content_fullness",
                )
            },
            "experience_reviews": [
                {"experience_id": "EXP-PROJECT-001", "evidence_bullet_ids": ["FUSION-001"]}
            ],
        },
    }
    stage_roles = {
        "jd-analysis.json": ("jd_analysis", "coordinator"),
        "capability-transfer-map.json": ("capability_transfer", "coordinator"),
        "experience-selection.json": ("experience_selection", "coordinator"),
        "selection-audit-pre.json": ("selection_audit", "auditor"),
        "story-plan.json": ("story_plan", "writer"),
        "draft-writer.json": ("writer", "writer"),
        "draft-asu.json": ("asu_writer", "asu_writer"),
        "draft-quality-audit.json": ("draft_audit", "auditor"),
        "fusion.json": ("fusion", "coordinator"),
        "audit.json": ("post_fusion_audit", "auditor"),
        "hr-review.json": ("hr_review", "hr_reviewer"),
    }
    required_run_artifacts["agent-receipts.json"] = {
        "schema_version": "1.5",
        "receipts": [
            {
                "stage": stage,
                "role": role,
                "invocation_id": f"test-{stage}",
                "model": "codex-test",
                "reasoning_effort": "high",
                "prompt_sha256": "1" * 64,
                "input_sha256": "2" * 64,
                "output_sha256": _canonical_json_sha256(
                    required_run_artifacts[filename]
                ),
                "created_at": "2026-08-30T12:00:00+08:00",
            }
            for filename, (stage, role) in stage_roles.items()
        ],
    }
    for filename, payload in required_run_artifacts.items():
        _write_json(run_dir / filename, payload)
    run_artifact_records = [
        {
            "relative_path": "content-master.md",
            "sha256": _sha256(content_master),
        },
        *[
            {
                "relative_path": filename,
                "sha256": _sha256(run_dir / filename),
            }
            for filename in required_run_artifacts
        ],
    ]
    _write_json(
        run_dir / "run.json",
        {
            "schema_version": "1.5",
            "run_id": run_id,
            "producer": "official_coordinator",
            "state": "ready_for_user_review",
            "artifacts": run_artifact_records,
        },
    )
    timestamp = "2026-08-30T12:00:00+08:00"
    transaction_id = "approval_" + "a" * 32
    user_approval_id = "user_approval_" + "c" * 32
    _write_json(
        application / "resume-content" / "approvals" / f"{user_approval_id}.json",
        {
            "schema_version": "1.5",
            "user_approval_id": user_approval_id,
            "run_id": run_id,
            "content_sha256": _sha256(content_master),
            "approved_at": timestamp,
            "source": "explicit_user_message",
        },
    )
    resume_content = {
        "status": "approved",
        "current_pointer": "resume-content/current.json",
        "approved_run_id": run_id,
        "updated_at": timestamp,
        "transaction_id": transaction_id,
    }
    _write_json(
        application / "resume-content" / "current.json",
        {
            "schema_version": "1.5",
            "status": "approved",
            "approved_run_id": run_id,
            "run_relative_path": f"resume-content/runs/{run_id}",
            "approved_at": timestamp,
            "updated_at": timestamp,
            "transaction_id": transaction_id,
            "user_approval_id": user_approval_id,
            "content_sha256": _sha256(content_master),
            "referenced_facts": [
                {"fact_id": "FACT-TEST-001-01", "value_sha256": "b" * 64}
            ],
        },
    )
    _write_json(application / "manifest.json", {"resume_content": resume_content})
    (application / "resume-content" / "run-status.jsonl").write_text(
        json.dumps(
            {
                "schema_version": "1.5",
                "run_id": run_id,
                "content_sha256": _sha256(content_master),
                "status": "approved",
                "reason_code": "USER_APPROVED",
                "recorded_at": timestamp,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    draft = {
        "status": "ready_for_user_approval",
        "company": "示例公司",
        "job_title": "游戏制作PM",
        "normalized_url": "https://example.com/jobs/1",
        "application_url": "https://example.com/apply/1",
        "mode": "定制",
        "content_pipeline": "custom-resume",
        "resume_content": resume_content,
        "review_checks": {
            "pdf_visual": "passed",
            "pdf_text_layer": "passed",
            "ats": "passed",
        },
    }
    for name, path in artifact_paths.items():
        draft[name] = {"path": path.name, "sha256": _sha256(path)}
    draft_path = application / "manifest-draft.json"
    _write_json(draft_path, draft)
    return root, draft_path, content_master


def test_approved_manifest_freezes_and_revalidates_custom_resume_provenance(
    tmp_path: Path,
) -> None:
    root, draft_path, content_master = _build_approval_fixture(tmp_path)
    create = root / "scripts" / "create_approved_manifest.ps1"
    result = _run_pwsh(
        create,
        "-DraftPath",
        str(draft_path),
        "-ApprovalStatement",
        "批准示例公司游戏制作PM及当前附件",
        "-Commit",
    )
    assert result.returncode == 0, result.stderr
    approved_path = Path(json.loads(result.stdout)["path"])
    approved = json.loads(approved_path.read_text(encoding="utf-8-sig"))
    assert approved["schema_version"] == 2
    assert approved["content_provenance"]["content_pipeline"] == "custom-resume"
    assert approved["content_provenance"]["content_master_sha256"] == _sha256(
        content_master
    )

    validate = root / "scripts" / "validate_approved_manifest.ps1"
    validation = _run_pwsh(validate, "-ApprovedPath", str(approved_path))
    assert validation.returncode == 0, validation.stderr
    assert json.loads(validation.stdout)["status"] == "validation_pass"

    content_master.write_text("tampered content", encoding="utf-8")
    rejected = _run_pwsh(validate, "-ApprovedPath", str(approved_path))
    assert rejected.returncode != 0
    assert "content-master.md" in rejected.stderr


def test_approved_manifest_freezes_fast_assemble_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    (root / "AGENTS.md").write_text("test workspace", encoding="utf-8")
    for name in (
        "approval_manifest_common.ps1",
        "create_approved_manifest.ps1",
        "validate_approved_manifest.ps1",
    ):
        shutil.copy2(REPO_ROOT / "scripts" / name, scripts / name)

    application = root / "applications" / "示例公司_AI产品经理"
    application.mkdir(parents=True)
    facts = root / "profile" / "01-candidate-profile.md"
    claims = root / "profile" / "resume-claims.json"
    selection = application / "experience-selection.json"
    content = application / "fast-content.json"
    hr_review = application / "fast-hr-review.json"
    yaml = application / "resume.yaml"
    artifacts = {
        "facts": facts,
        "claims": claims,
        "jd": application / "jd.md",
        "selection": selection,
        "content": content,
        "hr_review": hr_review,
        "resume_yaml": yaml,
        "pdf": application / "resume.pdf",
    }
    facts.parent.mkdir(parents=True)
    facts.write_text("confirmed fact", encoding="utf-8")
    _write_json(claims, {"schema_version": "1.0", "claims": []})
    artifacts["jd"].write_text("AI product JD", encoding="utf-8")
    _write_json(selection, {"selected_experience_ids": ["EXP-PROJECT-001"]})
    _write_json(
        content,
        {
            "schema_version": "1.0",
            "content_pipeline": "fast-assemble",
            "company": "示例公司",
            "target_role": "AI产品经理",
        },
    )
    _write_json(
        hr_review,
        {
            "schema_version": "1.0",
            "generation_round": 1,
            "decision": "pass",
            "checks": {
                gate: {"passed": True, "findings": []}
                for gate in (
                    "position_context",
                    "relevance",
                    "truth_and_contact",
                    "supported_capability_coverage",
                )
            },
            "exact_repairs": [],
            "requires_manual_review": False,
        },
    )
    yaml.write_text("cv: test", encoding="utf-8")
    artifacts["pdf"].write_bytes(b"test pdf artifact")
    answers = application / "answers.json"
    answers.write_text("{}", encoding="utf-8")

    def record(path: Path) -> dict[str, str]:
        return {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256(path),
        }

    draft = {
        "status": "ready_for_user_approval",
        "company": "示例公司",
        "job_title": "AI产品经理",
        "normalized_url": "https://example.com/jobs/fast-1",
        "application_url": "https://example.com/apply/fast-1",
        "mode": "定制",
        "content_pipeline": "fast-assemble",
        "review_checks": {
            "pdf_visual": "passed",
            "pdf_text_layer": "passed",
            "ats": "passed",
        },
        "fast_assemble": {name: record(path) for name, path in artifacts.items()},
        "jd": {"path": "jd.md", "sha256": _sha256(artifacts["jd"])},
        "resume": {"path": "resume.pdf", "sha256": _sha256(artifacts["pdf"])},
        "answers": {"path": "answers.json", "sha256": _sha256(answers)},
        "review": {
            "path": "fast-hr-review.json",
            "sha256": _sha256(hr_review),
        },
    }
    draft_path = application / "manifest-draft.json"
    _write_json(draft_path, draft)
    result = _run_pwsh(
        scripts / "create_approved_manifest.ps1",
        "-DraftPath",
        str(draft_path),
        "-ApprovalStatement",
        "批准示例公司AI产品经理及当前附件",
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["status"] == "dry_run_pass"
    assert output["content_pipeline"] == "fast-assemble"

    content.write_text("tampered", encoding="utf-8")
    rejected = _run_pwsh(
        scripts / "create_approved_manifest.ps1",
        "-DraftPath",
        str(draft_path),
        "-ApprovalStatement",
        "批准示例公司AI产品经理及当前附件",
    )
    assert rejected.returncode != 0
    assert "content" in rejected.stderr


@pytest.mark.parametrize(
    "blocking_status",
    ["superseded", "user_rejected", "schema_invalid", "revoked"],
)
def test_blocked_run_cannot_generate_approved_manifest(
    tmp_path: Path, blocking_status: str
) -> None:
    root, draft_path, content_master = _build_approval_fixture(tmp_path)
    application = draft_path.parent
    run_id = "cr_20260830T120000_abc123"
    status_path = application / "resume-content" / "run-status.jsonl"
    status_path.write_text(
        json.dumps(
            {
                "schema_version": "1.5",
                "run_id": run_id,
                "content_sha256": _sha256(content_master),
                "status": blocking_status,
                "reason_code": "TEST_BLOCKED_RUN",
                "recorded_at": "2026-09-03T00:00:00+08:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = _run_pwsh(
        root / "scripts" / "create_approved_manifest.ps1",
        "-DraftPath",
        str(draft_path),
        "-ApprovalStatement",
        "批准示例公司游戏制作PM及当前附件",
    )
    assert result.returncode != 0
    assert blocking_status in result.stderr


def test_missing_hr_receipt_blocks_approved_manifest_even_with_strong_push(
    tmp_path: Path,
) -> None:
    root, draft_path, _ = _build_approval_fixture(tmp_path)
    application = draft_path.parent
    run_dir = (
        application
        / "resume-content"
        / "runs"
        / "cr_20260830T120000_abc123"
    )
    receipts_path = run_dir / "agent-receipts.json"
    receipts = json.loads(receipts_path.read_text(encoding="utf-8"))
    receipts["receipts"] = [
        item for item in receipts["receipts"] if item["stage"] != "hr_review"
    ]
    _write_json(receipts_path, receipts)
    run_manifest_path = run_dir / "run.json"
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    next(
        item
        for item in run_manifest["artifacts"]
        if item["relative_path"] == "agent-receipts.json"
    )["sha256"] = _sha256(receipts_path)
    _write_json(run_manifest_path, run_manifest)

    result = _run_pwsh(
        root / "scripts" / "create_approved_manifest.ps1",
        "-DraftPath",
        str(draft_path),
        "-ApprovalStatement",
        "批准示例公司游戏制作PM及当前附件",
    )
    assert result.returncode != 0
    assert "hr_review" in result.stderr


def test_tailored_draft_cannot_silently_skip_content_pipeline(tmp_path: Path) -> None:
    root, draft_path, _ = _build_approval_fixture(tmp_path)
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    draft.pop("content_pipeline")
    _write_json(draft_path, draft)
    result = _run_pwsh(
        root / "scripts" / "create_approved_manifest.ps1",
        "-DraftPath",
        str(draft_path),
        "-ApprovalStatement",
        "批准示例公司游戏制作PM及当前附件",
    )
    assert result.returncode != 0
    assert "content_pipeline" in result.stderr


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        ("content_not_approved", "内容状态不是 approved"),
        ("pdf_visual_failed", "review_checks.pdf_visual 未通过"),
    ],
)
def test_t28_content_or_pdf_gate_cannot_create_application_approval(
    tmp_path: Path, mutation: str, expected_error: str
) -> None:
    root, draft_path, _ = _build_approval_fixture(tmp_path)
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    if mutation == "content_not_approved":
        draft["resume_content"]["status"] = "needs_content_review"
    else:
        draft["review_checks"]["pdf_visual"] = "failed"
    _write_json(draft_path, draft)
    result = _run_pwsh(
        root / "scripts" / "create_approved_manifest.ps1",
        "-DraftPath",
        str(draft_path),
        "-ApprovalStatement",
        "批准示例公司游戏制作PM及当前附件",
    )
    assert result.returncode != 0
    assert expected_error in result.stderr


def test_t28_attachment_and_approved_manifest_tampering_are_rejected(
    tmp_path: Path,
) -> None:
    root, draft_path, _ = _build_approval_fixture(tmp_path)
    create = _run_pwsh(
        root / "scripts" / "create_approved_manifest.ps1",
        "-DraftPath",
        str(draft_path),
        "-ApprovalStatement",
        "批准示例公司游戏制作PM及当前附件",
        "-Commit",
    )
    assert create.returncode == 0, create.stderr
    approved_path = Path(json.loads(create.stdout)["path"])
    validate = root / "scripts" / "validate_approved_manifest.ps1"

    resume_path = draft_path.parent / "resume.pdf"
    resume_path.write_text("tampered resume", encoding="utf-8")
    attachment_rejected = _run_pwsh(
        validate, "-ApprovedPath", str(approved_path)
    )
    assert attachment_rejected.returncode != 0
    assert "resume 哈希不一致" in attachment_rejected.stderr

    resume_path.write_text("verified resume", encoding="utf-8")
    approved = json.loads(approved_path.read_text(encoding="utf-8-sig"))
    approved["manifest"]["job_title"] = "被篡改岗位"
    _write_json(approved_path, approved)
    manifest_rejected = _run_pwsh(validate, "-ApprovedPath", str(approved_path))
    assert manifest_rejected.returncode != 0
    assert "内嵌 manifest 与源草案不一致" in manifest_rejected.stderr


def test_t28_browser_submission_still_requires_manifest_and_final_confirmation() -> None:
    browser_skill = (
        REPO_ROOT / ".agents" / "skills" / "browser-application" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "validate_approved_manifest.ps1" in browser_skill
    assert "只有输出 `validation_pass` 才能继续" in browser_skill
    assert "等待用户明确确认本次提交" in browser_skill
    assert "用户确认后才点击一次" in browser_skill
    assert "未成功确认不能写 `submitted`" in browser_skill
