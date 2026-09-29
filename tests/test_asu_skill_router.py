from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / ".agents" / "skills" / "china-job-search" / "scripts" / "asu_skill_router.py"
SPEC = importlib.util.spec_from_file_location("asu_skill_router", MODULE_PATH)
assert SPEC and SPEC.loader
router = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = router
SPEC.loader.exec_module(router)


def _installed_skills(root: Path) -> None:
    for name in router.GLOBAL_SKILLS:
        skill_file = root / name / "SKILL.md"
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_text("---\nname: test\n---\n", encoding="utf-8")


def test_discovery_reports_new_suite_and_never_requires_legacy_asu(tmp_path: Path) -> None:
    _installed_skills(tmp_path)
    discovered = router.discover_skills(tmp_path)
    assert all(discovered[name].installed for name in router.GLOBAL_SKILLS)
    assert discovered["asu"].installed is False
    assert "历史全局名称" in discovered["asu"].purpose


def test_fast_assemble_never_routes_to_make_resume(tmp_path: Path) -> None:
    _installed_skills(tmp_path)
    decision = router.route_intent(
        "make-resume", router.discover_skills(tmp_path), content_pipeline="fast-assemble"
    )
    assert decision.status == "ready"
    assert decision.executor == "resume/RenderCV"
    assert decision.capability_skill is None
    assert "do not call make-resume" in decision.prohibitions


def test_job_apply_keeps_browser_application_as_only_executor(tmp_path: Path) -> None:
    _installed_skills(tmp_path)
    decision = router.route_intent("job-apply", router.discover_skills(tmp_path))
    assert decision.status == "ready"
    assert decision.executor == "browser-application"
    assert "validated approved manifest" in decision.requires
    assert "Kimi WebBridge" in " ".join(decision.prohibitions)


@pytest.mark.parametrize("intent", ["job-match", "great-resume", "interview", "offer"])
def test_non_execution_skills_preserve_project_boundaries(tmp_path: Path, intent: str) -> None:
    _installed_skills(tmp_path)
    decision = router.route_intent(intent, router.discover_skills(tmp_path))
    assert decision.status == "ready"
    assert decision.capability_skill is not None
    assert any("do not" in item for item in decision.prohibitions)


def test_missing_required_skill_fails_closed(tmp_path: Path) -> None:
    _installed_skills(tmp_path)
    (tmp_path / "interview" / "SKILL.md").unlink()
    decision = router.route_intent("interview", router.discover_skills(tmp_path))
    assert decision.status == "degraded"
    assert decision.capability_skill is None
    assert "unavailable" in decision.detail


def test_project_local_asu_writer_remains_the_second_writer(tmp_path: Path) -> None:
    files = (
        ".codex/agents/custom-resume-writer.toml",
        ".codex/agents/custom-resume-asu-writer.toml",
        ".agents/prompts/custom-resume/writer.md",
        ".agents/prompts/custom-resume/asu-writer.md",
    )
    for relative in files:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("present", encoding="utf-8")
    assert router.dual_writer_ready(tmp_path) is True
    (tmp_path / files[-1]).unlink()
    assert router.dual_writer_ready(tmp_path) is False


def test_cli_emits_utf8_json(tmp_path: Path) -> None:
    _installed_skills(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "route",
            "--skills-root",
            str(tmp_path),
            "--workspace-root",
            str(tmp_path),
            "--intent",
            "job-match",
        ],
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout.decode("utf-8"))
    assert payload["route"]["capability_skill"] == "job-match"
