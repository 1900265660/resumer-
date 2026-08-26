from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
import json

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "custom-resume" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from models import (  # noqa: E402
    AgentFailureArtifact,
    AgentRole,
    AuditArtifact,
    AuditDisposition,
    DraftAgent,
    DraftArtifact,
    QualityAudit,
    QualityDimension,
    ResumeBullet,
    ResumeEntry,
    ResumeSection,
    ResumeSectionName,
    SourceDigests,
    TruthAudit,
)


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
RUN_ID = "cr_20260822T120000_abc123"
PROMPT_DIR = REPO_ROOT / ".agents" / "prompts" / "custom-resume"
AGENT_DIR = REPO_ROOT / ".codex" / "agents"
PROMPTS = {
    "jd-analysis.md",
    "jd-analysis-game-production.md",
    "writer.md",
    "writer-game-production.md",
    "asu-writer.md",
    "asu-writer-game-production.md",
    "fusion.md",
    "auditor.md",
    "experience-selection.md",
    "selection-audit.md",
    "capability-transfer.md",
    "hr-reviewer.md",
}
AGENTS = {
    "custom-resume-writer.toml": "custom_resume_writer",
    "custom-resume-asu-writer.toml": "custom_resume_asu_writer",
    "custom-resume-auditor.toml": "custom_resume_auditor",
    "custom-resume-hr-reviewer.toml": "custom_resume_hr_reviewer",
}


def digests() -> SourceDigests:
    return SourceDigests(
        jd_sha256="a" * 64,
        fact_snapshot_sha256="b" * 64,
        preferences_sha256="c" * 64,
    )


def test_all_prompts_publish_input_output_failure_and_prohibitions() -> None:
    assert {item.name for item in PROMPT_DIR.glob("*.md")} == PROMPTS
    for filename in PROMPTS:
        text = (PROMPT_DIR / filename).read_text(encoding="utf-8")
        for heading in ("## Input", "## Output", "## Failure", "## Prohibitions"):
            assert heading in text, f"{filename} is missing {heading}"
        assert "AgentFailureArtifact" in text
        assert "write files" in text or "write files" in text.lower()
        assert "untrusted data" in text


def test_writer_prompts_preserve_blind_isolation() -> None:
    writer = (PROMPT_DIR / "writer.md").read_text(encoding="utf-8")
    asu = (PROMPT_DIR / "asu-writer.md").read_text(encoding="utf-8")
    assert "draft-asu" not in writer
    assert "ASU-NNN" not in writer
    assert "draft-writer" not in asu
    assert "WRITER-NNN" not in asu
    assert "blind to all other drafts" in writer
    assert "blind to all other drafts" in asu
    game_writer = (PROMPT_DIR / "writer-game-production.md").read_text(encoding="utf-8")
    game_asu = (PROMPT_DIR / "asu-writer-game-production.md").read_text(encoding="utf-8")
    assert "blind to all other drafts" in game_writer
    assert "blind to all other drafts" in game_asu


def test_v13_prompts_enforce_transfer_and_fixed_baseline_boundaries() -> None:
    mapper = (PROMPT_DIR / "capability-transfer.md").read_text(encoding="utf-8")
    selection = (PROMPT_DIR / "experience-selection.md").read_text(encoding="utf-8")
    auditor = (PROMPT_DIR / "auditor.md").read_text(encoding="utf-8")
    writer = (PROMPT_DIR / "writer.md").read_text(encoding="utf-8")
    assert "planning_delivery" in mapper
    assert "Schema 1.3 envelope" in mapper
    assert "candidate" in mapper and "multiplier `0`" in mapper
    assert "writable_scope" in mapper
    assert "portfolio_value_score" in selection
    assert "Schema 1.3" in selection
    assert "Never add the 0–20 portfolio score" in selection
    assert "transfer recall and precision" in (PROMPT_DIR / "selection-audit.md").read_text(encoding="utf-8")
    assert "approved non-candidate" in auditor
    assert "专业硬技能、综合软技能、游戏体验、语言能力" in writer


def test_v14_hr_reviewer_is_strict_and_independent() -> None:
    reviewer = (PROMPT_DIR / "hr-reviewer.md").read_text(encoding="utf-8")
    assert "recommendation=strong_push" in reviewer
    assert "overall_score>=8.5" in reviewer
    assert "omitted_fact_ids" in reviewer
    assert "needs_input" in reviewer and "reselect" in reviewer
    assert "mutually exclusive" in reviewer
    assert "EXP-SKILL-001" not in reviewer


def test_v14_deepblue_truthful_high_score_draft_still_fails_hr_gate() -> None:
    fixture = json.loads(
        (
            REPO_ROOT
            / "tests"
            / "custom_resume"
            / "fixtures"
            / "hr-v1.4"
            / "deepblue-overcompressed.json"
        ).read_text(encoding="utf-8")
    )
    assert fixture["base_audit"]["truth_passed"] is True
    assert fixture["base_audit"]["quality_passed"] is True
    assert fixture["expected_hr_review"]["passed"] is False
    assert fixture["expected_hr_review"]["recommendation"] == "hesitate"
    assert "FACT-WORK-001-04" in fixture["confirmed_but_omitted_fact_ids"]
    assert "FACT-PROJECT-011-02" in fixture["confirmed_but_omitted_fact_ids"]


def test_custom_agent_configs_are_read_only_and_model_agnostic() -> None:
    assert {item.name for item in AGENT_DIR.glob("custom-resume-*.toml")} == set(AGENTS)
    for filename, expected_name in AGENTS.items():
        config = tomllib.loads((AGENT_DIR / filename).read_text(encoding="utf-8"))
        assert config["name"] == expected_name
        assert config["sandbox_mode"] == "read-only"
        assert set(config) == {
            "name",
            "description",
            "sandbox_mode",
            "developer_instructions",
        }
        assert "Return only strict JSON" in config["developer_instructions"]
        assert "write files" in config["developer_instructions"]


def sample_sections(agent: DraftAgent) -> list[ResumeSection]:
    prefix = "WRITER" if agent is DraftAgent.WRITER else "ASU"
    return [
        ResumeSection(name=ResumeSectionName.EDUCATION),
        ResumeSection(name=ResumeSectionName.WORK),
        ResumeSection(
            name=ResumeSectionName.PRACTICE,
            entries=[
                ResumeEntry(
                    experience_id="EXP-PROJECT-001",
                    heading="测试 Agent｜产品负责人｜2025/04–2025/06",
                    bullets=[
                        ResumeBullet(
                            bullet_id=f"{prefix}-001",
                            text="基于已确认事实完成知识库问答原型。",
                            fact_ids=["FACT-PROJECT-001-01"],
                            requirement_ids=["REQ-001"],
                            primary_value="AI 产品原型",
                        )
                    ],
                )
            ],
        ),
        ResumeSection(name=ResumeSectionName.ABILITIES),
    ]


def test_minimal_writer_asu_and_auditor_outputs_validate_independently() -> None:
    writer = DraftArtifact(
        schema_version="1.1",
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        agent=DraftAgent.WRITER,
        sections=sample_sections(DraftAgent.WRITER),
    )
    asu = DraftArtifact(
        schema_version="1.1",
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        agent=DraftAgent.ASU_WRITER,
        sections=sample_sections(DraftAgent.ASU_WRITER),
    )
    dimension = QualityDimension(score=8, evidence=["达到 V1 门槛"])
    audit = AuditArtifact(
        schema_version="1.1",
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        deterministic_passed=True,
        truth=TruthAudit(passed=True),
        quality=QualityAudit(
            jd_coverage=dimension,
            selection_quality=dimension,
            evidence_depth=dimension,
            hr_scan=dimension,
            language_naturalness=dimension,
            passed=True,
        ),
        disposition=AuditDisposition.PASSED,
    )
    assert writer.agent is DraftAgent.WRITER
    assert asu.agent is DraftAgent.ASU_WRITER
    assert audit.disposition is AuditDisposition.PASSED


def test_agent_failure_contract_is_structured() -> None:
    failure = AgentFailureArtifact(
        run_id=RUN_ID,
        created_at=NOW,
        source_digests=digests(),
        role=AgentRole.WRITER,
        error_code="MISSING_APPROVAL",
        message="经历选择尚未批准",
        missing_inputs=["evidence_map.approved_at"],
        retryable=True,
    )
    assert failure.error_code == "MISSING_APPROVAL"
