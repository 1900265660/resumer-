from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "china-job-search"
    / "scripts"
    / "resume_baseline.py"
)
SPEC = importlib.util.spec_from_file_location("resume_baseline", MODULE_PATH)
assert SPEC and SPEC.loader
resume_baseline = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = resume_baseline
SPEC.loader.exec_module(resume_baseline)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_baseline_audit_groups_duplicate_text_and_blocks_stale_claims(tmp_path: Path) -> None:
    source = tmp_path / "latest"
    source.mkdir()
    first = source / "运营简历.pdf"
    second = source / "resume-output" / "运营简历-copy.pdf"
    second.parent.mkdir()
    first.write_bytes(b"pdf-one")
    second.write_bytes(b"pdf-two")
    profile = tmp_path / "profile.md"
    profile.write_text("confirmed facts", encoding="utf-8")
    text = (
        "测试候选人 13800138000 test@example.com "
        "产品运营 环比增长 300% "
        + "完整正文" * 200
    )
    index = resume_baseline.audit_baselines(
        source_root=source,
        applications_root=tmp_path / "applications",
        profile_path=profile,
        output_root=tmp_path / "baselines",
        expected_phone="13800138000",
        expected_email="test@example.com",
        text_extractor=lambda _: text,
    )
    assert len(index["items"]) == 1
    item = index["items"][0]
    assert item["duplicate_count"] == 1
    assert item["status"] == "blocked"
    assert {finding["code"] for finding in item["findings"]} >= {
        "removed_growth_claim"
    }


def test_baseline_route_requires_exact_role_track_and_current_profile(tmp_path: Path) -> None:
    snapshot = tmp_path / "content.txt"
    snapshot.write_text("系统策划 版本规划 需求拆解", encoding="utf-8")
    source = tmp_path / "resume.pdf"
    source.write_bytes(b"current resume")
    current = "a" * 64
    index = {
        "schema_version": "1.0",
        "profile_sha256": current,
        "items": [
            {
                "baseline_id": "baseline-test",
                "title": "游戏系统策划",
                "status": "reusable",
                "role_family": "game_designer",
                "role_track": "system",
                "profile_sha256": current,
                "content_snapshot_path": str(snapshot),
                "source_files": [
                    {
                        "path": str(source),
                        "sha256": _digest(source),
                        "modified_at": "2026-09-14T00:00:00+00:00",
                    }
                ],
                "experience_ids": ["EXP-WORK-005"],
                "editable_sources": [str(tmp_path / "resume.html")],
                "hr_review": {"passed": True},
                "visual_review": {"status": "passed"},
            }
        ],
    }
    light = resume_baseline.route_resume(
        index=index,
        current_profile_sha256=current,
        role_family="game_designer",
        role_track="system",
        keywords=["版本规划"],
        required_experience_ids=["EXP-WORK-005"],
    )
    assert light["decision"] == "light_tune"
    assert light["requires_rewrite_batch_approval"] is False

    rewrite = resume_baseline.route_resume(
        index=index,
        current_profile_sha256=current,
        role_family="game_designer",
        role_track="writing",
        keywords=[],
    )
    assert rewrite["decision"] == "full_rewrite"
    assert rewrite["must_not_start_dual_writers"] is True

    stale = resume_baseline.route_resume(
        index=index,
        current_profile_sha256="b" * 64,
        role_family="game_designer",
        role_track="system",
        keywords=[],
    )
    assert stale["decision"] == "full_rewrite"
    assert "重新审计" in stale["reason"]

    source.write_bytes(b"changed resume")
    changed = resume_baseline.route_resume(
        index=index,
        current_profile_sha256=current,
        role_family="game_designer",
        role_track="system",
        keywords=[],
    )
    assert changed["decision"] == "full_rewrite"
    assert "源文件哈希" in changed["reason"]


def test_name_fallback_requires_a_unique_high_confidence_application(tmp_path: Path) -> None:
    applications = tmp_path / "applications"
    applications.mkdir()
    expected = applications / "完美世界_卡牌游戏策划（系统玩法方向）"
    expected.mkdir()
    (applications / "巨人网络_项目管理工程师-27届秋招").mkdir()
    matched = resume_baseline.matching_application_dirs(
        Path("测试候选人_完美世界_卡牌游戏策划.pdf"), applications
    )
    assert matched == [expected]
    assert resume_baseline.matching_application_dirs(
        Path("测试候选人_游戏策划.pdf"), applications
    ) == []


def _passing_hr() -> dict[str, object]:
    return {
        "recommendation": "strong_push",
        "overall_score": 9.1,
        "dimensions": {
            "role_fit": 9.0,
            "narrative_completeness": 8.5,
            "evidence_specificity": 9.0,
            "decision_readiness": 8.8,
            "credibility": 9.2,
            "content_fullness": 8.6,
        },
        "defect_category": "none",
        "requires_experience_change": False,
    }


def test_light_tune_hr_passes_without_content_approval_and_escalates_story_defect() -> None:
    passed = resume_baseline.evaluate_light_hr(_passing_hr(), generation_round=1)
    assert passed == {
        "decision": "passed",
        "can_generate_resume": True,
        "requires_user_content_approval": False,
    }
    story = _passing_hr()
    story["defect_category"] = "story"
    story["requires_experience_change"] = True
    escalated = resume_baseline.evaluate_light_hr(story, generation_round=1)
    assert escalated["decision"] == "rewrite_required"
    assert escalated["requires_rewrite_batch_approval"] is True


def test_legacy_five_dimension_hr_only_counts_for_baseline_provenance() -> None:
    historical = _passing_hr()
    historical["passed"] = True
    dimensions = historical["dimensions"]
    assert isinstance(dimensions, dict)
    dimensions.pop("content_fullness")
    baseline_passed, count = resume_baseline._baseline_hr_dimensions_pass(historical)
    assert baseline_passed is True
    assert count == 5
    assert resume_baseline.evaluate_light_hr(historical, generation_round=1)[
        "decision"
    ] == "local_repair"


def test_light_tune_allows_two_local_repairs_then_requires_rewrite() -> None:
    failed = _passing_hr()
    failed["recommendation"] = "push"
    failed["overall_score"] = 8.8
    assert resume_baseline.evaluate_light_hr(failed, generation_round=1)[
        "decision"
    ] == "local_repair"
    assert resume_baseline.evaluate_light_hr(failed, generation_round=2)[
        "decision"
    ] == "local_repair"
    assert resume_baseline.evaluate_light_hr(failed, generation_round=3)[
        "decision"
    ] == "rewrite_required"


def test_workbook_updater_expands_three_company_jobs() -> None:
    node = Path(
        r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
    )
    result = subprocess.run(
        [str(node), str(REPO_ROOT / "scripts" / "update_job_resume_workbook.mjs"), "--self-test"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["rows"] == 3
