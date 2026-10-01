from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "custom-resume" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from exemplar_library import (  # noqa: E402
    ExemplarLibraryError,
    exemplar_bundle_sha256,
    load_matching_resume_exemplars,
)


def _write_exemplar(
    root: Path,
    *,
    exemplar_id: str = "game-production-test-v1",
    schema_version: str = "1.0",
    role_family: str = "game_production_pm",
    role_track: str | None = None,
) -> tuple[Path, bytes]:
    entry = root / "profile" / "resume-exemplars" / exemplar_id
    entry.mkdir(parents=True)
    content = b"## Work\n\n- approved structure reference\n"
    content_path = entry / "content-master.md"
    content_path.write_bytes(content)
    metadata = {
        "schema_version": schema_version,
        "exemplar_id": exemplar_id,
        "title": "Game production exemplar",
        "status": "approved_reference",
        "approved_at": "2026-08-30T12:00:00+08:00",
        "role_family": role_family,
        "source": {
            "run_id": "cr_20260829T112758_games2",
            "fact_snapshot_sha256": "a" * 64,
            "content_sha256": hashlib.sha256(content).hexdigest(),
        },
        "match": {
            "minimum_keyword_matches": 2,
            "keywords": ["版本规划", "跨职能", "游戏产品体验"],
        },
        "quality": {
            "truth_passed": True,
            "audit_disposition": "passed",
            "hr_recommendation": "strong_push",
            "hr_overall_score": 9.4,
        },
        "allowed_uses": ["structure", "evidence allocation"],
        "forbidden_uses": ["fact source", "selection inheritance"],
    }
    if schema_version == "1.1":
        metadata["role_track"] = role_track
    (entry / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
    )
    return content_path, content


def test_matching_exemplar_requires_role_and_keyword_similarity(tmp_path: Path) -> None:
    _, content = _write_exemplar(tmp_path)
    matches = load_matching_resume_exemplars(
        tmp_path,
        role_family="game_production_pm",
        jd_text="负责版本规划、跨职能协作与交付。",
    )
    assert len(matches) == 1
    packet = matches[0].packet()
    assert packet["matched_keywords"] == ["版本规划", "跨职能"]
    assert packet["content_snapshot"] == content.decode("utf-8")
    assert packet["fact_source"] is False
    assert packet["selection_approval"] is False

    assert not load_matching_resume_exemplars(
        tmp_path,
        role_family="ai_product_manager",
        jd_text="负责版本规划、跨职能协作。",
    )
    assert not load_matching_resume_exemplars(
        tmp_path,
        role_family="game_production_pm",
        jd_text="负责社区内容运营。",
    )


def test_exemplar_bundle_digest_freezes_selected_snapshot(tmp_path: Path) -> None:
    _, _ = _write_exemplar(tmp_path)
    matches = load_matching_resume_exemplars(
        tmp_path,
        role_family="game_production_pm",
        jd_text="负责版本规划、跨职能协作。",
    )
    method_card = b"method card"
    assert exemplar_bundle_sha256(method_card, ()) == hashlib.sha256(
        method_card
    ).hexdigest()
    assert exemplar_bundle_sha256(method_card, matches) != hashlib.sha256(
        method_card
    ).hexdigest()


def test_schema_v11_exemplar_requires_exact_role_track(tmp_path: Path) -> None:
    _write_exemplar(
        tmp_path,
        exemplar_id="community-content-test-v1",
        schema_version="1.1",
        role_family="community_operations",
        role_track="content",
    )
    matches = load_matching_resume_exemplars(
        tmp_path,
        role_family="community_operations",
        role_track="content",
        jd_text="负责版本规划、跨职能协作与内容运营。",
    )
    assert len(matches) == 1
    assert matches[0].role_track == "content"
    assert matches[0].packet()["role_track"] == "content"
    assert not load_matching_resume_exemplars(
        tmp_path,
        role_family="community_operations",
        role_track="growth",
        jd_text="负责版本规划、跨职能协作与内容运营。",
    )
    assert not load_matching_resume_exemplars(
        tmp_path,
        role_family="community_operations",
        jd_text="负责版本规划、跨职能协作与内容运营。",
    )


def test_tampered_exemplar_is_rejected(tmp_path: Path) -> None:
    content_path, _ = _write_exemplar(tmp_path)
    content_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(ExemplarLibraryError, match="content hash mismatch"):
        load_matching_resume_exemplars(
            tmp_path,
            role_family="game_production_pm",
            jd_text="负责版本规划、跨职能协作。",
        )


def test_exemplar_below_hr_gate_is_rejected(tmp_path: Path) -> None:
    content_path, _ = _write_exemplar(tmp_path)
    metadata_path = content_path.with_name("metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["quality"]["hr_recommendation"] = "push"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ExemplarLibraryError, match="quality gates"):
        load_matching_resume_exemplars(
            tmp_path,
            role_family="game_production_pm",
            jd_text="负责版本规划、跨职能协作。",
        )
