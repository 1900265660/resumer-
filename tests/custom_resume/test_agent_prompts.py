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
    "jd-analysis-community.md",
    "jd-analysis-game-designer.md",
    "writer.md",
    "writer-game-production.md",
    "writer-game-designer.md",
    "asu-writer.md",
    "asu-writer-game-production.md",
    "asu-writer-game-designer.md",
    "fusion.md",
    "auditor.md",
    "experience-selection.md",
    "selection-audit.md",
    "capability-transfer.md",
    "hr-reviewer.md",
    "story-planner.md",
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
    designer_writer = (PROMPT_DIR / "writer-game-designer.md").read_text(encoding="utf-8")
    designer_asu = (PROMPT_DIR / "asu-writer-game-designer.md").read_text(encoding="utf-8")
    assert "blind to all other drafts" in designer_writer
    assert "blind to all other drafts" in designer_asu


def test_v15_prompts_enforce_transfer_story_and_fixed_baseline_boundaries() -> None:
    mapper = (PROMPT_DIR / "capability-transfer.md").read_text(encoding="utf-8")
    selection = (PROMPT_DIR / "experience-selection.md").read_text(encoding="utf-8")
    auditor = (PROMPT_DIR / "auditor.md").read_text(encoding="utf-8")
    writer = (PROMPT_DIR / "writer.md").read_text(encoding="utf-8")
    assert "planning_delivery" in mapper
    assert "Schema 1.5 envelope" in mapper
    assert "candidate" in mapper and "multiplier `0`" in mapper
    assert "writable_scope" in mapper
    assert "portfolio_value_score" in selection
    assert "Schema 1.5" in selection
    assert "Never add the 0–20 portfolio score" in selection
    assert "transfer recall and precision" in (PROMPT_DIR / "selection-audit.md").read_text(encoding="utf-8")
    assert "approved non-candidate" in auditor
    assert "fixed_ability_headings" in writer
    story = (PROMPT_DIR / "story-planner.md").read_text(encoding="utf-8")
    assert "story_thesis" in story and "bullet_intents" in story
    assert "ownership_guard" in story and "never render" in story
    assert "audited proposed experience selection" in story
    assert "unapproved selection" not in story


def test_v15_hr_reviewer_is_strict_and_independent() -> None:
    reviewer = (PROMPT_DIR / "hr-reviewer.md").read_text(encoding="utf-8")
    assert "recommendation=strong_push" in reviewer
    assert "overall_score>=9.0" in reviewer
    assert "every dimension score `>=8.0`" in reviewer
    assert "evidence_bullet_ids" in reviewer
    assert "content_fullness" in reviewer
    assert "omitted_fact_ids" in reviewer
    assert "needs_input" in reviewer and "reselect" in reviewer
    assert "mutually exclusive" in reviewer
    assert "EXP-SKILL-001" not in reviewer


def test_t28_completion_gate_exposes_all_selected_facts_and_distinguishes_labels() -> None:
    selection_audit = (PROMPT_DIR / "selection-audit.md").read_text(
        encoding="utf-8"
    )
    writer = (PROMPT_DIR / "writer.md").read_text(encoding="utf-8")
    asu = (PROMPT_DIR / "asu-writer.md").read_text(encoding="utf-8")
    fusion = (PROMPT_DIR / "fusion.md").read_text(encoding="utf-8")
    auditor = (PROMPT_DIR / "auditor.md").read_text(encoding="utf-8")
    reviewer = (PROMPT_DIR / "hr-reviewer.md").read_text(encoding="utf-8")
    rubric = (
        REPO_ROOT
        / ".agents"
        / "skills"
        / "custom-resume"
        / "references"
        / "quality-rubric.md"
    ).read_text(encoding="utf-8")

    assert "complete confirmed fact set" in selection_audit
    assert "Capability-forward labels" in writer
    assert "Capability-forward labels" in asu
    assert "every confirmed fact exposed" in fusion
    assert "full confirmed fact set" in auditor
    assert "selected_fact_ids_by_experience" in reviewer
    assert "uncited_selected_fact_ids_by_experience" in reviewer
    assert "uncited_fact_assessments" in reviewer
    assert "irrelevant" in reviewer and "redundant" in reviewer
    assert "should_include" in reviewer
    assert "Character thresholds are hard HR admission gates" in rubric
    assert "Bullet totals are never minimum or maximum quality quotas" in rubric
    assert "content_fullness_gate" in reviewer
    assert "Bullet count is not a pass/fail criterion" in reviewer


def test_t21_prompts_enforce_evidence_story_and_keyword_details() -> None:
    writer_prompts = [
        (PROMPT_DIR / "writer.md").read_text(encoding="utf-8"),
        (PROMPT_DIR / "asu-writer.md").read_text(encoding="utf-8"),
        (PROMPT_DIR / "writer-game-production.md").read_text(encoding="utf-8"),
        (PROMPT_DIR / "asu-writer-game-production.md").read_text(encoding="utf-8"),
    ]
    for prompt in writer_prompts:
        assert "evidence story" in prompt
        assert "first three high-signal work/project headings or bullets" in prompt
        assert "background/problem" in prompt
        assert "JD keyword" in prompt and "work/project detail" in prompt

    selection = (PROMPT_DIR / "experience-selection.md").read_text(encoding="utf-8")
    selection_audit = (PROMPT_DIR / "selection-audit.md").read_text(encoding="utf-8")
    fusion = (PROMPT_DIR / "fusion.md").read_text(encoding="utf-8")
    auditor = (PROMPT_DIR / "auditor.md").read_text(encoding="utf-8")
    reviewer = (PROMPT_DIR / "hr-reviewer.md").read_text(encoding="utf-8")
    assert "several weak, redundant, or non-expandable entries" in selection
    assert "one-line/non-expandable experience" in selection_audit
    assert "weak padding" in selection_audit
    assert "first three high-signal work/project headings or bullets" in fusion
    assert "JD keywords" in auditor and "work/project detail" in auditor
    assert "global positioning consistency" not in reviewer
    assert "mutually distracting role identities" not in reviewer
    assert "skill list, label, or self-evaluation alone" not in reviewer


def test_t30_uses_character_fullness_without_bullet_quotas() -> None:
    prompts = [
        (PROMPT_DIR / name).read_text(encoding="utf-8")
        for name in (
            "writer.md",
            "asu-writer.md",
            "fusion.md",
            "auditor.md",
            "hr-reviewer.md",
        )
    ]
    joined = "\n".join(prompts)
    assert "1,200" in joined and "180" in joined and "120" in joined
    assert "Bullet count is not" in joined or "bullet count is not" in joined
    assert "exactly 2–4" not in joined


def test_t22_game_prompts_enforce_fresh_fact_reselection_and_self_ability_judgment() -> None:
    reference = (
        REPO_ROOT
        / ".agents"
        / "skills"
        / "custom-resume"
        / "references"
        / "game-production-content-judgment.md"
    ).read_text(encoding="utf-8")
    writer = (PROMPT_DIR / "writer-game-production.md").read_text(encoding="utf-8")
    asu = (PROMPT_DIR / "asu-writer-game-production.md").read_text(encoding="utf-8")
    fusion = (PROMPT_DIR / "fusion.md").read_text(encoding="utf-8")
    auditor = (PROMPT_DIR / "auditor.md").read_text(encoding="utf-8")
    reviewer = (PROMPT_DIR / "hr-reviewer.md").read_text(encoding="utf-8")

    assert "prior resume, prior run" in reference
    assert "Do not rank by hours alone" in reference
    assert "generic player labels are insufficient" in writer
    assert "prior resume/run" in writer and "prior resume/run" in asu
    assert "role_content_guidance" in writer and "role_content_guidance" in asu
    assert "current fact snapshot" in fusion
    assert "complete current SKILL fact snapshot" in auditor
    assert "stale prior-run game list" in reviewer
    for prompt in (writer, asu, fusion, auditor, reviewer):
        assert "product/commercialization" in prompt or "commercialization" in prompt


def test_t23_exemplar_prompts_preserve_non_fact_and_fresh_selection_boundaries() -> None:
    selection = (PROMPT_DIR / "experience-selection.md").read_text(encoding="utf-8")
    selection_audit = (PROMPT_DIR / "selection-audit.md").read_text(
        encoding="utf-8"
    )
    writer = (PROMPT_DIR / "writer.md").read_text(encoding="utf-8")
    asu_writer = (PROMPT_DIR / "asu-writer.md").read_text(encoding="utf-8")
    game_writer = (PROMPT_DIR / "writer-game-production.md").read_text(
        encoding="utf-8"
    )
    game_asu = (PROMPT_DIR / "asu-writer-game-production.md").read_text(
        encoding="utf-8"
    )
    auditor = (PROMPT_DIR / "auditor.md").read_text(encoding="utf-8")
    reviewer = (PROMPT_DIR / "hr-reviewer.md").read_text(encoding="utf-8")

    for prompt in (selection, selection_audit, writer, asu_writer, game_writer, game_asu):
        assert "exemplar" in prompt.lower()
    assert "never a fact source" in selection
    assert "Exemplar similarity never approves the selection" in selection_audit
    assert "fact_source=false" in game_writer
    assert "company-specific wording" in game_asu
    assert "stale exemplar game list" in auditor
    assert "The exemplar never raises a score by itself" in reviewer


def test_t26_community_prompts_preserve_track_and_product_ownership_boundaries() -> None:
    jd = (PROMPT_DIR / "jd-analysis-community.md").read_text(encoding="utf-8")
    mapper = (PROMPT_DIR / "capability-transfer.md").read_text(encoding="utf-8")
    selection = (PROMPT_DIR / "experience-selection.md").read_text(encoding="utf-8")
    selection_audit = (PROMPT_DIR / "selection-audit.md").read_text(encoding="utf-8")
    writer = (PROMPT_DIR / "writer.md").read_text(encoding="utf-8")
    asu = (PROMPT_DIR / "asu-writer.md").read_text(encoding="utf-8")
    fusion = (PROMPT_DIR / "fusion.md").read_text(encoding="utf-8")
    auditor = (PROMPT_DIR / "auditor.md").read_text(encoding="utf-8")
    reviewer = (PROMPT_DIR / "hr-reviewer.md").read_text(encoding="utf-8")

    assert "exact confirmed `role_family`" in jd
    assert "funnel stage" in jd and "requirement or solution definition" in jd
    assert "Publishing or editing" in mapper and "adjacent growth evidence" in mapper
    assert "shared users, platforms, or metrics do not remove transfer distance" in selection
    assert "direct growth credit based only on publishing/reach" in selection_audit
    for prompt in (writer, asu, fusion, auditor, reviewer):
        assert "community_operations" in prompt
        assert "community_product_manager" in prompt
    assert "fixed_ability_headings" in writer and "fixed_ability_headings" in asu
    assert "content-to-growth" in fusion
    assert "Unsupported cross-track action" in auditor
    assert "cannot justify product ownership" in reviewer


def test_t27_game_designer_prompts_preserve_direction_and_ownership_boundaries() -> None:
    jd = (PROMPT_DIR / "jd-analysis-game-designer.md").read_text(encoding="utf-8")
    mapper = (PROMPT_DIR / "capability-transfer.md").read_text(encoding="utf-8")
    selection = (PROMPT_DIR / "experience-selection.md").read_text(encoding="utf-8")
    selection_audit = (PROMPT_DIR / "selection-audit.md").read_text(encoding="utf-8")
    writer = (PROMPT_DIR / "writer-game-designer.md").read_text(encoding="utf-8")
    asu = (PROMPT_DIR / "asu-writer-game-designer.md").read_text(encoding="utf-8")
    fusion = (PROMPT_DIR / "fusion.md").read_text(encoding="utf-8")
    auditor = (PROMPT_DIR / "auditor.md").read_text(encoding="utf-8")
    reviewer = (PROMPT_DIR / "hr-reviewer.md").read_text(encoding="utf-8")

    for track in ("system", "combat", "writing", "narrative", "general"):
        assert f"`{track}`" in jd
    assert "Play and reviews" in mapper
    assert "system and combat interchangeable" in selection
    assert "MOD/QA as combat design" in selection_audit
    for prompt in (writer, asu, fusion, auditor, reviewer):
        assert "game_designer" in prompt
    assert "player/content/localization/QA evidence" in writer
    assert "localization, ordinary writing, MOD work, and QA" in asu
    assert "MOD/QA into combat design" in fusion
    assert "Any invented design action" in auditor
    assert "cannot justify `strong_push`" in reviewer


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


def test_t28_echotech_user_rejection_is_a_non_regressible_completion_gate() -> None:
    fixture = json.loads(
        (
            REPO_ROOT
            / "tests"
            / "custom_resume"
            / "fixtures"
            / "hr-v1.4"
            / "echotech-user-rejected-overcompressed.json"
        ).read_text(encoding="utf-8")
    )
    assert fixture["user_accepted"] is False
    assert fixture["old_hr_review"]["passed"] is True
    assert fixture["old_hr_review"]["invalidated_by_user_acceptance"] is True
    assert fixture["completion_benchmark"]["fact_source"] is False
    assert fixture["completion_benchmark"]["selection_approval"] is False
    assert fixture["rejected_content_metrics"]["below_both_reference_targets"] is True

    old_work_facts = set(
        fixture["selected_fact_ids_before_fix"]["EXP-WORK-001"]
    )
    complete_work_facts = set(
        fixture["complete_selected_fact_ids_after_fix"]["EXP-WORK-001"]
    )
    assert complete_work_facts.difference(old_work_facts) == set(
        fixture["expected_pre_hidden_fact_ids"]
    )
    cited = set(fixture["cited_fact_ids_in_rejected_content"])
    complete_selected = set().union(
        *(
            set(fact_ids)
            for fact_ids in fixture["complete_selected_fact_ids_after_fix"].values()
        )
    )
    assert complete_selected.difference(cited) == set(
        fixture["expected_uncited_fact_ids_after_complete_exposure"]
    )
    assert fixture["expected_gate"]["selection_with_pre_hidden_facts_passed"] is False
    assert fixture["expected_gate"]["hr_passed"] is False
    assert fixture["expected_gate"]["recommendation_must_not_be"] == "strong_push"
    assert fixture["expected_gate"]["required_disposition_for_uncited_facts"] == "should_include"


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
