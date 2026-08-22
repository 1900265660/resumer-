from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_main_harness_exposes_explicit_content_only_route_and_keeps_legacy() -> None:
    harness = (
        REPO_ROOT / ".agents" / "skills" / "china-job-search" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert ".agents/skills/custom-resume/SKILL.md" in harness
    assert "$custom-resume" in harness
    assert "调用最新的简历 Skill" in harness
    assert "既有定制模式（T12 前仍可用）" in harness
    assert ".agents/agents/resume-optimizer-agent.md" in harness
    assert ".agents/prompts/campus-resume-optimizer.md" in harness
    assert "不得把既有入口标记 deprecated" in harness


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
