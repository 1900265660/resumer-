from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "custom-resume" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from fact_library import (  # noqa: E402
    FactLibraryError,
    SourceChangedError,
    apply_fact_diff,
    apply_preview,
    assert_source_unchanged,
    migrate_text,
    parse_fact_records,
    sha256_bytes,
    strip_metadata,
    write_preview,
)
from models import (  # noqa: E402
    ConfirmationStatus,
    DiffAction,
    FactDiffArtifact,
    FactDiffOperation,
    FactProvenance,
    SourceDigests,
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

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
RUN_ID = "cr_20260822T120000_abc123"


def approved_diff(
    source_hash: str, operation: FactDiffOperation
) -> FactDiffArtifact:
    return FactDiffArtifact(
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=SourceDigests(
            jd_sha256="a" * 64,
            fact_snapshot_sha256=source_hash,
            preferences_sha256="b" * 64,
        ),
        source_fact_sha256=source_hash,
        confirmation_status=ConfirmationStatus.APPROVED,
        operations=[operation],
    )


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


def test_approved_fact_diff_adds_accepted_estimate_atomically(
    tmp_path: Path,
) -> None:
    migrated, _ = migrate_text(SAMPLE)
    source = tmp_path / "profile.md"
    source.write_text(migrated, encoding="utf-8")
    source_hash = sha256_bytes(source.read_bytes())
    operation = FactDiffOperation(
        operation_id="FD-001",
        action=DiffAction.ADD,
        experience_id="EXP-WORK-001",
        proposed_fact_id="FACT-WORK-001-03",
        new_value="访谈范围估计为 12–15 位用户。",
        provenance=FactProvenance.ACCEPTED_ESTIMATE,
        estimate_basis="用户确认模型建议区间",
        confirmation_status=ConfirmationStatus.APPROVED,
        confirmed_at=NOW,
    )
    result = apply_fact_diff(
        source,
        approved_diff(source_hash, operation),
        approval_granted=True,
    )
    _, facts = parse_fact_records(source.read_text(encoding="utf-8"))
    written = facts["FACT-WORK-001-03"]
    assert written.value == operation.new_value
    assert written.provenance == "accepted_estimate"
    assert written.metadata["source_run"] == RUN_ID
    assert written.metadata["estimate_basis"] == "用户确认模型建议区间"
    assert result["original_sha256"] == source_hash
    assert result["applied_sha256"] == sha256_bytes(source.read_bytes())


def test_approved_fact_diff_replaces_exact_old_value_and_guards_source(
    tmp_path: Path,
) -> None:
    migrated, _ = migrate_text(SAMPLE)
    source = tmp_path / "profile.md"
    source.write_text(migrated, encoding="utf-8")
    source_hash = sha256_bytes(source.read_bytes())
    operation = FactDiffOperation(
        operation_id="FD-001",
        action=DiffAction.REPLACE,
        experience_id="EXP-WORK-001",
        target_fact_id="FACT-WORK-001-02",
        old_value="完成原型与验收。",
        new_value="完成原型、测试与验收。",
        provenance=FactProvenance.OBSERVED,
        confirmation_status=ConfirmationStatus.APPROVED,
        confirmed_at=NOW,
    )
    diff = approved_diff(source_hash, operation)
    with pytest.raises(FactLibraryError, match="explicit approval"):
        apply_fact_diff(source, diff, approval_granted=False)
    source.write_text(migrated + "\n", encoding="utf-8")
    with pytest.raises(SourceChangedError, match="changed after diff generation"):
        apply_fact_diff(source, diff, approval_granted=True)
    source.write_text(migrated, encoding="utf-8")
    apply_fact_diff(source, diff, approval_granted=True)
    _, facts = parse_fact_records(source.read_text(encoding="utf-8"))
    assert facts["FACT-WORK-001-02"].value == "完成原型、测试与验收。"
    assert facts["FACT-WORK-001-02"].provenance == "observed"
