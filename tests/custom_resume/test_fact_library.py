from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "custom-resume" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from fact_library import (  # noqa: E402
    FactLibraryError,
    SourceChangedError,
    apply_preview,
    assert_source_unchanged,
    migrate_text,
    strip_metadata,
    write_preview,
)


SAMPLE = """# 候选人事实库（已确认）

## 基本信息

- 姓名：测试用户；所在地：上海

## 教育

1. 测试大学，测试专业，本科，2022/09–2026/06。

## 工作经历

### 测试公司｜产品实习生｜2025/01–2025/03

- 访谈 10 位用户并输出需求清单。
- 完成原型与验收。

## 项目经历

### 测试 Agent｜产品负责人｜2025/04–2025/06

- 构建知识库问答原型。

## 技能与兴趣

- 工具：Excel、Python。
"""


def test_migration_only_adds_metadata_and_is_idempotent() -> None:
    migrated, report = migrate_text(SAMPLE)
    assert report.body_preserved is True
    assert report.experience_count == 5
    assert report.fact_count == 6
    assert strip_metadata(migrated) == SAMPLE
    assert "EXP-WORK-001" in migrated
    assert "FACT-PROJECT-001-01" in migrated

    second, second_report = migrate_text(migrated)
    assert second == migrated
    assert second_report.inserted_experience_ids == 0
    assert second_report.inserted_fact_ids == 0


def test_duplicate_id_is_rejected() -> None:
    damaged = SAMPLE.replace(
        "- 完成原型与验收。",
        "- 完成原型与验收。 <!-- fact_id: FACT-WORK-001-01; provenance: observed -->",
    ).replace(
        "- 访谈 10 位用户并输出需求清单。",
        "- 访谈 10 位用户并输出需求清单。 <!-- fact_id: FACT-WORK-001-01; provenance: observed -->",
    )
    with pytest.raises(FactLibraryError, match="duplicate fact_id"):
        migrate_text(damaged)


def test_damaged_or_incomplete_metadata_is_rejected() -> None:
    with pytest.raises(FactLibraryError, match="damaged inline metadata"):
        migrate_text(SAMPLE.replace("- 完成原型与验收。", "- 完成原型 <!-- fact_id: X"))

    incomplete = SAMPLE.replace(
        "- 完成原型与验收。",
        "- 完成原型与验收。 <!-- fact_id: FACT-WORK-001-02 -->",
    )
    with pytest.raises(FactLibraryError, match="requires a valid provenance"):
        migrate_text(incomplete)


def test_fact_id_must_reference_its_current_experience() -> None:
    mismatched = SAMPLE.replace(
        "### 测试公司｜产品实习生｜2025/01–2025/03",
        "### 测试公司｜产品实习生｜2025/01–2025/03 <!-- experience_id: EXP-WORK-002 -->",
    ).replace(
        "- 完成原型与验收。",
        "- 完成原型与验收。 <!-- fact_id: FACT-WORK-001-01; provenance: observed -->",
    )
    with pytest.raises(FactLibraryError, match="does not belong"):
        migrate_text(mismatched)


def test_source_hash_guard_detects_concurrent_change(tmp_path: Path) -> None:
    source = tmp_path / "profile.md"
    source.write_text(SAMPLE, encoding="utf-8")
    report = write_preview(source, tmp_path / "preview")
    assert_source_unchanged(source, report.source_sha256)

    source.write_text(SAMPLE + "\n", encoding="utf-8")
    with pytest.raises(SourceChangedError, match="source hash changed"):
        assert_source_unchanged(source, report.source_sha256)


def test_preview_writes_reviewable_diff_without_touching_source(tmp_path: Path) -> None:
    source = tmp_path / "profile.md"
    source.write_text(SAMPLE, encoding="utf-8")
    original = source.read_bytes()
    output_dir = tmp_path / "preview"

    report = write_preview(source, output_dir)

    assert source.read_bytes() == original
    assert report.changed is True
    assert (output_dir / "candidate-profile.with-ids.md").exists()
    assert "experience_id" in (output_dir / "migration.diff").read_text(
        encoding="utf-8"
    )
    assert (output_dir / "migration-report.json").exists()


def test_real_fact_library_supports_read_only_preview(tmp_path: Path) -> None:
    source = REPO_ROOT / "profile" / "01-candidate-profile.md"
    if not source.exists():
        pytest.skip("private fact library is intentionally absent")
    original = source.read_bytes()

    report = write_preview(source, tmp_path / "real-preview")

    assert source.read_bytes() == original
    assert report.body_preserved is True
    assert report.experience_count > 0
    assert report.fact_count > 0


def test_apply_requires_approval_and_preserves_body(tmp_path: Path) -> None:
    source = tmp_path / "profile.md"
    source.write_text(SAMPLE, encoding="utf-8")
    output_dir = tmp_path / "preview"
    write_preview(source, output_dir)
    original_body = source.read_text(encoding="utf-8")

    with pytest.raises(FactLibraryError, match="explicit approval"):
        apply_preview(
            source,
            output_dir / "candidate-profile.with-ids.md",
            output_dir / "migration-report.json",
            output_dir / "apply-report.json",
            approval_granted=False,
        )
    assert source.read_text(encoding="utf-8") == original_body

    result = apply_preview(
        source,
        output_dir / "candidate-profile.with-ids.md",
        output_dir / "migration-report.json",
        output_dir / "apply-report.json",
        approval_granted=True,
    )
    assert result["body_preserved"] is True
    assert strip_metadata(source.read_text(encoding="utf-8")) == original_body
    assert (output_dir / "apply-report.json").exists()


def test_apply_rejects_source_or_preview_tampering(tmp_path: Path) -> None:
    source = tmp_path / "profile.md"
    source.write_text(SAMPLE, encoding="utf-8")
    output_dir = tmp_path / "preview"
    write_preview(source, output_dir)
    source.write_text(SAMPLE + "\n", encoding="utf-8")
    with pytest.raises(SourceChangedError, match="source hash changed"):
        apply_preview(
            source,
            output_dir / "candidate-profile.with-ids.md",
            output_dir / "migration-report.json",
            output_dir / "apply-report.json",
            approval_granted=True,
        )

    source.write_text(SAMPLE, encoding="utf-8")
    preview = output_dir / "candidate-profile.with-ids.md"
    preview.write_text(
        preview.read_text(encoding="utf-8").replace("测试公司", "被篡改公司"),
        encoding="utf-8",
    )
    with pytest.raises(FactLibraryError, match="preview hash"):
        apply_preview(
            source,
            preview,
            output_dir / "migration-report.json",
            output_dir / "apply-report.json",
            approval_granted=True,
        )
