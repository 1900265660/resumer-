from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel

from fact_library import ExperienceRecord, FactRecord, apply_fact_diff
from models import (
    AgentFailureArtifact,
    AgentRole,
    AuditArtifact,
    AuditDisposition,
    CandidateSuggestion,
    ConfirmationStatus,
    ContentState,
    DeterministicValidationArtifact,
    DraftAgent,
    DraftArtifact,
    EvidenceMapArtifact,
    ExecutionMode,
    FactDiffArtifact,
    FusionArtifact,
    JDAnalysisArtifact,
    NormalizedInputPacket,
    ReferenceResearchArtifact,
    ReferenceResearchMode,
    RoleFamily,
    RunCheckpointArtifact,
    RunManifestArtifact,
    SourceDigests,
    SourceType,
    assert_state_transition,
)
from storage import (
    RunStage,
    approve_run,
    begin_run,
    create_run_id,
    load_checkpoint,
    remove_checkpoint,
    save_checkpoint,
)
from validators import validate_fusion_content, validate_run_artifact_completeness


class OrchestrationError(RuntimeError):
    pass


class HumanGateError(OrchestrationError):
    pass


class AgentHandoffError(OrchestrationError):
    pass


class DeterministicGateError(OrchestrationError):
    def __init__(self, report: DeterministicValidationArtifact):
        super().__init__("deterministic content validation failed")
        self.report = report


WINDOWS_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
REFERENCE_CARDS = {
    RoleFamily.AI_PRODUCT_MANAGER: "ai-pm-method-cards.md",
    RoleFamily.GAME_PRODUCTION_PM: "game-production-pm-method-cards.md",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized_jd_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise OrchestrationError("JD text is empty")
    return normalized + "\n"


def safe_job_component(value: str, field_name: str) -> str:
    cleaned = WINDOWS_INVALID.sub("_", value).strip().rstrip(".")
    if not cleaned:
        raise OrchestrationError(f"{field_name} is missing or unsafe")
    return cleaned


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )
    temporary.replace(path)


def _write_jd_once(path: Path, content: str) -> None:
    if path.exists():
        existing = normalized_jd_text(path.read_text(encoding="utf-8"))
        if existing != content:
            raise OrchestrationError(f"existing JD differs and will not be overwritten: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="")


@dataclass(frozen=True)
class NormalizedRunInput:
    packet: NormalizedInputPacket
    application_dir: Path
    jd_text: str
    fact_text: str
    preferences_text: str
    reference_cards_text: str


def normalize_run_input(
    repo_root: Path,
    *,
    source_type: SourceType,
    source_locator: str,
    company: str | None = None,
    role: str | None = None,
    jd_text: str | None = None,
    application_dir: Path | None = None,
    now: datetime | None = None,
    run_id: str | None = None,
    role_family: RoleFamily = RoleFamily.AI_PRODUCT_MANAGER,
) -> NormalizedRunInput:
    repo_root = repo_root.resolve()
    timestamp = now or datetime.now(timezone.utc)
    if source_type is SourceType.DIRECTORY:
        if application_dir is None:
            raise OrchestrationError("directory input requires application_dir")
        resolved_application = application_dir.resolve()
        try:
            relative_application = resolved_application.relative_to(repo_root)
        except ValueError as error:
            raise OrchestrationError("application_dir must be inside the repository") from error
        if not relative_application.as_posix().startswith("applications/"):
            raise OrchestrationError("application_dir must be under applications/")
        jd_path = resolved_application / "jd.md"
        if not jd_path.is_file():
            raise OrchestrationError(f"application JD is missing: {jd_path}")
        content = normalized_jd_text(jd_path.read_text(encoding="utf-8"))
    else:
        if not company or not role:
            raise HumanGateError("text and URL inputs require confirmed company and role")
        company_name = safe_job_component(company, "company")
        role_name = safe_job_component(role, "role")
        resolved_application = repo_root / "applications" / f"{company_name}_{role_name}"
        relative_application = resolved_application.relative_to(repo_root)
        if jd_text is None:
            raise OrchestrationError("normalized JD text is required")
        content = normalized_jd_text(jd_text)
        _write_jd_once(resolved_application / "jd.md", content)
        manifest_path = resolved_application / "manifest.json"
        if not manifest_path.exists():
            _atomic_json(
                manifest_path,
                {
                    "status": "imported",
                    "company": company,
                    "role": role,
                    "jd_source": source_locator,
                },
            )

    fact_path = repo_root / "profile" / "01-candidate-profile.md"
    preferences_path = repo_root / "profile" / "preferences.md"
    reference_path = (
        repo_root
        / ".agents"
        / "skills"
        / "custom-resume"
        / "references"
        / REFERENCE_CARDS[role_family]
    )
    for required in (fact_path, preferences_path, reference_path):
        if not required.is_file():
            raise OrchestrationError(f"required input is missing: {required}")
    fact_bytes = fact_path.read_bytes()
    preferences_bytes = preferences_path.read_bytes()
    reference_bytes = reference_path.read_bytes()
    actual_run_id = run_id or create_run_id(timestamp)
    digests = SourceDigests(
        jd_sha256=sha256_bytes(content.encode("utf-8")),
        fact_snapshot_sha256=sha256_bytes(fact_bytes),
        preferences_sha256=sha256_bytes(preferences_bytes),
        reference_cards_sha256=sha256_bytes(reference_bytes),
    )
    packet = NormalizedInputPacket(
        run_id=actual_run_id,
        created_at=timestamp,
        source_digests=digests,
        application_dir=relative_application.as_posix(),
        source_type=source_type,
        source_locator=source_locator,
        role_family=role_family,
    )
    return NormalizedRunInput(
        packet=packet,
        application_dir=resolved_application,
        jd_text=content,
        fact_text=fact_bytes.decode("utf-8-sig"),
        preferences_text=preferences_bytes.decode("utf-8-sig"),
        reference_cards_text=reference_bytes.decode("utf-8-sig"),
    )


def _same_envelope(expected: NormalizedInputPacket, artifact: BaseModel) -> None:
    if getattr(artifact, "run_id", None) != expected.run_id:
        raise AgentHandoffError("artifact run_id does not match the approved packet")
    if getattr(artifact, "source_digests", None) != expected.source_digests:
        raise AgentHandoffError("artifact source digests do not match the approved packet")


def _artifact_payload(value: BaseModel) -> dict[str, Any]:
    return value.model_dump(mode="json")


def render_resume_markdown(fusion: FusionArtifact) -> str:
    lines: list[str] = []
    for section in fusion.sections:
        lines.extend([f"## {section.name.value}", ""])
        for entry in section.entries:
            lines.extend([f"### {entry.heading}", ""])
            lines.extend(f"- {bullet.text}" for bullet in entry.bullets)
            if entry.bullets:
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_content_review(
    fusion: FusionArtifact,
    validation: DeterministicValidationArtifact,
    audit: AuditArtifact,
    suggestions: Sequence[CandidateSuggestion],
) -> str:
    lines = [
        "# 定制简历内容验收",
        "",
        f"- Run ID：`{fusion.run_id}`",
        f"- 确定性硬校验：{'通过' if validation.passed else '失败'}",
        f"- 真实性审计：{'通过' if audit.truth.passed else '失败'}",
        f"- JD 覆盖：{audit.quality.jd_coverage.score}/10",
        f"- 证据深度：{audit.quality.evidence_depth.score}/10",
        f"- HR 扫读：{audit.quality.hr_scan.score}/10",
        f"- 语言自然度：{audit.quality.language_naturalness.score}/10",
        "",
        "## 融合决策",
        "",
    ]
    lines.extend(
        f"- `{item.decision_id}` `{item.action.value}`：{item.rationale}"
        for item in fusion.decisions
    )
    lines.extend(["", "## 内容预算", ""])
    lines.append(
        f"- 中文字符：{validation.metrics.chinese_character_count}；经历要点：{validation.metrics.experience_bullet_count}"
    )
    if validation.findings:
        lines.extend(["", "## 校验提示", ""])
        lines.extend(
            f"- `{item.error_code}`（{item.severity.value}）：{item.message}"
            for item in validation.findings
        )
    lines.extend(["", "## 未确认建议（不在干净稿）", ""])
    if suggestions:
        lines.extend(f"- `{item.suggestion_id}` {item.question}" for item in suggestions)
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 原稿",
            "",
            "- Writer：`draft-writer.json`",
            "- ASu Writer：`draft-asu.json`",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


@dataclass
class CoordinatorRun:
    normalized: NormalizedRunInput
    stage: RunStage | None = None
    state: ContentState = ContentState.NOT_STARTED
    jd_analysis: JDAnalysisArtifact | None = None
    evidence_map: EvidenceMapArtifact | None = None
    fact_diff: FactDiffArtifact | None = None
    writer_draft: DraftArtifact | None = None
    asu_draft: DraftArtifact | None = None
    asu_failure: AgentFailureArtifact | None = None
    execution_mode: ExecutionMode = ExecutionMode.BLIND_DUAL
    fusion_history: list[FusionArtifact] = field(default_factory=list)
    validation_history: list[DeterministicValidationArtifact] = field(
        default_factory=list
    )
    audit_history: list[AuditArtifact] = field(default_factory=list)
    reference_research: ReferenceResearchArtifact | None = None
    committed_path: Path | None = None

    @classmethod
    def create(cls, normalized: NormalizedRunInput) -> "CoordinatorRun":
        run = cls(normalized=normalized)
        run.reference_research = ReferenceResearchArtifact(
            run_id=normalized.packet.run_id,
            created_at=normalized.packet.created_at,
            source_digests=normalized.packet.source_digests,
            mode=ReferenceResearchMode.LOCAL,
            local_card_sha256=normalized.packet.source_digests.reference_cards_sha256,
        )
        run._transition(ContentState.ANALYZING)
        return run

    @classmethod
    def resume(cls, normalized: NormalizedRunInput) -> "CoordinatorRun":
        checkpoint = load_checkpoint(
            normalized.application_dir, normalized.packet.run_id
        )
        if checkpoint.source_digests != normalized.packet.source_digests:
            raise AgentHandoffError(
                "checkpoint inputs changed; start a new run with fresh analysis"
            )
        if checkpoint.input_packet.application_dir != normalized.packet.application_dir:
            raise AgentHandoffError("checkpoint application directory does not match")
        if checkpoint.input_packet.role_family is not normalized.packet.role_family:
            raise AgentHandoffError("checkpoint role family does not match")
        restored_input = NormalizedRunInput(
            packet=checkpoint.input_packet,
            application_dir=normalized.application_dir,
            jd_text=normalized.jd_text,
            fact_text=normalized.fact_text,
            preferences_text=normalized.preferences_text,
            reference_cards_text=normalized.reference_cards_text,
        )
        return cls(
            normalized=restored_input,
            state=checkpoint.state,
            jd_analysis=checkpoint.jd_analysis,
            evidence_map=checkpoint.evidence_map,
            fact_diff=checkpoint.fact_diff,
            execution_mode=checkpoint.execution_mode,
            reference_research=checkpoint.reference_research,
        )

    @property
    def packet(self) -> NormalizedInputPacket:
        return self.normalized.packet

    @property
    def current_fusion(self) -> FusionArtifact:
        if not self.fusion_history:
            raise OrchestrationError("fusion has not been recorded")
        return self.fusion_history[-1]

    @property
    def current_validation(self) -> DeterministicValidationArtifact:
        if not self.validation_history:
            raise OrchestrationError("validation has not been recorded")
        return self.validation_history[-1]

    @property
    def current_audit(self) -> AuditArtifact:
        if not self.audit_history:
            raise OrchestrationError("audit has not been recorded")
        return self.audit_history[-1]

    def _transition(self, target: ContentState) -> None:
        assert_state_transition(self.state, target)
        self.state = target

    def _save_gate_checkpoint(self) -> Path:
        if not all(
            [
                self.reference_research,
                self.jd_analysis,
                self.evidence_map,
                self.fact_diff,
            ]
        ):
            raise OrchestrationError("gate checkpoint artifacts are incomplete")
        checkpoint = RunCheckpointArtifact(
            run_id=self.packet.run_id,
            created_at=self.packet.created_at,
            source_digests=self.packet.source_digests,
            state=self.state,
            execution_mode=self.execution_mode,
            input_packet=self.packet,
            reference_research=self.reference_research,
            jd_analysis=self.jd_analysis,
            evidence_map=self.evidence_map,
            fact_diff=self.fact_diff,
        )
        return save_checkpoint(self.normalized.application_dir, checkpoint)

    def record_reference_research(self, artifact: ReferenceResearchArtifact) -> None:
        if self.state is not ContentState.ANALYZING:
            raise OrchestrationError("reference routing must finish before JD analysis")
        _same_envelope(self.packet, artifact)
        if artifact.local_card_sha256 != self.packet.source_digests.reference_cards_sha256:
            raise AgentHandoffError(
                "reference artifact does not match the local method cards"
            )
        self.reference_research = artifact

    def record_analysis(
        self,
        jd_analysis: JDAnalysisArtifact,
        evidence_map: EvidenceMapArtifact,
        fact_diff: FactDiffArtifact,
    ) -> None:
        if self.state is not ContentState.ANALYZING:
            raise OrchestrationError("analysis can only be recorded while analyzing")
        for artifact in (jd_analysis, evidence_map, fact_diff):
            _same_envelope(self.packet, artifact)
        if jd_analysis.role_family is not self.packet.role_family:
            raise AgentHandoffError("JD analysis role family does not match the approved packet")
        if evidence_map.selection_approved:
            raise HumanGateError("selection cannot be pre-approved by the coordinator")
        current_fact_hash = self.packet.source_digests.fact_snapshot_sha256
        if fact_diff.result_fact_sha256 is not None:
            if fact_diff.result_fact_sha256 != current_fact_hash:
                raise AgentHandoffError("applied fact diff result hash is stale")
        elif fact_diff.source_fact_sha256 != current_fact_hash:
            raise AgentHandoffError("fact diff source hash is stale")
        self.jd_analysis = jd_analysis
        self.evidence_map = evidence_map
        self.fact_diff = fact_diff
        unresolved = (
            fact_diff.confirmation_status is ConfirmationStatus.PENDING
            and bool(fact_diff.questions or fact_diff.operations)
        )
        if unresolved:
            self._transition(ContentState.NEEDS_INPUT)
        else:
            self._transition(ContentState.AWAITING_SELECTION_APPROVAL)
        self._save_gate_checkpoint()

    def resolve_fact_diff(self, fact_diff: FactDiffArtifact) -> None:
        if self.state is not ContentState.NEEDS_INPUT:
            raise HumanGateError("no fact-diff confirmation is currently pending")
        _same_envelope(self.packet, fact_diff)
        if fact_diff.confirmation_status is ConfirmationStatus.PENDING:
            raise HumanGateError("fact diff still requires explicit user confirmation")
        if (
            fact_diff.confirmation_status is ConfirmationStatus.APPROVED
            and fact_diff.operations
        ):
            raise HumanGateError(
                "approved fact operations must be atomically applied before selection"
            )
        self.fact_diff = fact_diff
        self._transition(ContentState.AWAITING_SELECTION_APPROVAL)
        self._save_gate_checkpoint()

    def apply_confirmed_fact_diff(
        self,
        fact_diff: FactDiffArtifact,
        *,
        approval_granted: bool,
    ) -> dict[str, object]:
        if self.state is not ContentState.NEEDS_INPUT:
            raise HumanGateError("no fact-diff write is currently pending")
        _same_envelope(self.packet, fact_diff)
        if not fact_diff.operations:
            raise HumanGateError("fact diff has no write operations")
        profile_path = (
            self.normalized.application_dir.parents[1]
            / "profile"
            / "01-candidate-profile.md"
        )
        result = apply_fact_diff(
            profile_path,
            fact_diff,
            approval_granted=approval_granted,
        )
        fact_bytes = profile_path.read_bytes()
        applied_hash = sha256_bytes(fact_bytes)
        if result["applied_sha256"] != applied_hash:
            raise OrchestrationError("fact diff result hash verification failed")
        updated_digests = self.packet.source_digests.model_copy(
            update={"fact_snapshot_sha256": applied_hash}
        )
        updated_packet = self.packet.model_copy(
            update={"source_digests": updated_digests}
        )
        updated_diff = fact_diff.model_copy(
            update={
                "source_digests": updated_digests,
                "result_fact_sha256": applied_hash,
            }
        )
        assert self.reference_research is not None
        assert self.jd_analysis is not None
        assert self.evidence_map is not None
        self.normalized = NormalizedRunInput(
            packet=NormalizedInputPacket.model_validate(updated_packet.model_dump()),
            application_dir=self.normalized.application_dir,
            jd_text=self.normalized.jd_text,
            fact_text=fact_bytes.decode("utf-8-sig"),
            preferences_text=self.normalized.preferences_text,
            reference_cards_text=self.normalized.reference_cards_text,
        )
        self.reference_research = self.reference_research.model_copy(
            update={"source_digests": updated_digests}
        )
        self.jd_analysis = self.jd_analysis.model_copy(
            update={"source_digests": updated_digests}
        )
        self.evidence_map = self.evidence_map.model_copy(
            update={"source_digests": updated_digests}
        )
        self.fact_diff = FactDiffArtifact.model_validate(updated_diff.model_dump())
        self._transition(ContentState.ANALYZING)
        self._save_gate_checkpoint()
        return result

    def approve_selection(self, evidence_map: EvidenceMapArtifact) -> None:
        if self.state is not ContentState.AWAITING_SELECTION_APPROVAL:
            raise HumanGateError("selection approval is not currently allowed")
        _same_envelope(self.packet, evidence_map)
        if not evidence_map.selection_approved:
            raise HumanGateError("selection_approved must be explicitly true")
        selected = [item for item in evidence_map.mappings if item.selected]
        if not selected:
            raise HumanGateError("at least one evidence mapping must be selected")
        approved_requirements = sorted({item.requirement_id for item in selected})
        approved_facts = sorted({fact_id for item in selected for fact_id in item.fact_ids})
        self.evidence_map = evidence_map
        updated_packet = self.packet.model_copy(
            update={
                "approved_requirement_ids": approved_requirements,
                "approved_fact_ids": approved_facts,
            }
        )
        self.normalized = NormalizedRunInput(
            packet=NormalizedInputPacket.model_validate(updated_packet.model_dump()),
            application_dir=self.normalized.application_dir,
            jd_text=self.normalized.jd_text,
            fact_text=self.normalized.fact_text,
            preferences_text=self.normalized.preferences_text,
            reference_cards_text=self.normalized.reference_cards_text,
        )
        self._transition(ContentState.DRAFTING)
        self._save_gate_checkpoint()

    def writer_packet(
        self,
        experiences: dict[str, ExperienceRecord],
        facts: dict[str, FactRecord],
    ) -> dict[str, Any]:
        if self.state is not ContentState.DRAFTING:
            raise HumanGateError("writer packets require approved selection")
        if not self.jd_analysis or not self.evidence_map:
            raise OrchestrationError("analysis artifacts are missing")
        selected_fact_ids = set(self.packet.approved_fact_ids)
        selected_facts = [
            {
                "fact_id": fact.fact_id,
                "experience_id": fact.experience_id,
                "value": fact.value,
                "provenance": fact.provenance,
            }
            for fact in facts.values()
            if fact.fact_id in selected_fact_ids
        ]
        selected_experience_ids = {item["experience_id"] for item in selected_facts}
        return {
            "schema_version": "1.0",
            "input_packet": _artifact_payload(self.packet),
            "jd_analysis": _artifact_payload(self.jd_analysis),
            "evidence_map": _artifact_payload(self.evidence_map),
            "selected_experiences": [
                {
                    "experience_id": item.experience_id,
                    "heading": item.heading,
                    "immutable_tokens": list(item.immutable_tokens),
                }
                for item in experiences.values()
                if item.experience_id in selected_experience_ids
            ],
            "confirmed_facts": selected_facts,
            "preferences": self.normalized.preferences_text,
            "content_budget": {
                "chinese_characters": [1200, 1500],
                "experience_bullets": [10, 14],
            },
        }

    def record_drafts(self, writer: DraftArtifact, asu: DraftArtifact) -> None:
        if self.state is not ContentState.DRAFTING:
            raise OrchestrationError("drafts are not currently expected")
        for artifact in (writer, asu):
            _same_envelope(self.packet, artifact)
        if writer.agent is not DraftAgent.WRITER:
            raise AgentHandoffError("writer lane returned the wrong agent type")
        if asu.agent is not DraftAgent.ASU_WRITER:
            raise AgentHandoffError("ASu lane returned the wrong agent type")
        self.writer_draft = writer
        self.asu_draft = asu

    def handle_subagent_unavailable(self, choice: str | None = None) -> str:
        if self.state is not ContentState.DRAFTING:
            raise OrchestrationError("subagent availability is relevant only while drafting")
        if choice is None:
            raise HumanGateError(
                "subagents are unavailable; user must choose retry or single_agent_degraded"
            )
        if choice == "retry":
            return choice
        if choice != ExecutionMode.SINGLE_AGENT_DEGRADED.value:
            raise HumanGateError("unsupported subagent fallback choice")
        self.execution_mode = ExecutionMode.SINGLE_AGENT_DEGRADED
        self._save_gate_checkpoint()
        return choice

    def record_single_degraded_draft(self, writer: DraftArtifact) -> None:
        if self.execution_mode is not ExecutionMode.SINGLE_AGENT_DEGRADED:
            raise HumanGateError("single draft requires explicit degraded-mode approval")
        if self.state is not ContentState.DRAFTING:
            raise OrchestrationError("draft is not currently expected")
        _same_envelope(self.packet, writer)
        if writer.agent is not DraftAgent.WRITER:
            raise AgentHandoffError("degraded lane must return a writer draft")
        self.writer_draft = writer
        self.asu_draft = None
        self.asu_failure = AgentFailureArtifact(
            run_id=self.packet.run_id,
            created_at=self.packet.created_at,
            source_digests=self.packet.source_digests,
            role=AgentRole.ASU_WRITER,
            error_code="SUBAGENT_UNAVAILABLE",
            message="ASu Writer was unavailable; user explicitly approved degraded mode",
            retryable=True,
        )

    def _candidate_suggestions(self) -> list[CandidateSuggestion]:
        suggestions = list(self.writer_draft.candidate_suggestions) if self.writer_draft else []
        if self.asu_draft:
            suggestions.extend(self.asu_draft.candidate_suggestions)
        return suggestions

    def record_fusion(
        self,
        fusion: FusionArtifact,
        experiences: dict[str, ExperienceRecord],
        facts: dict[str, FactRecord],
    ) -> DeterministicValidationArtifact:
        if self.state not in {ContentState.DRAFTING, ContentState.AUDITING}:
            raise OrchestrationError("fusion is not currently expected")
        if not self.writer_draft or not self.jd_analysis:
            raise AgentHandoffError("a writer draft is required before fusion")
        if (
            self.execution_mode is ExecutionMode.BLIND_DUAL
            and not self.asu_draft
        ):
            raise AgentHandoffError("both independent drafts are required before fusion")
        if len(self.fusion_history) >= 3:
            raise OrchestrationError("at most two directed revision rounds are allowed")
        if self.fusion_history and len(self.audit_history) != len(self.fusion_history):
            raise OrchestrationError("a new fusion requires an audit of the prior fusion")
        _same_envelope(self.packet, fusion)
        suggestions = self._candidate_suggestions()
        report = validate_fusion_content(
            fusion,
            self.jd_analysis,
            experiences,
            facts,
            suggestions,
        )
        if not report.passed:
            raise DeterministicGateError(report)
        self.fusion_history.append(fusion)
        self.validation_history.append(report)
        if self.state is ContentState.DRAFTING:
            self._transition(ContentState.AUDITING)
        return report

    def auditor_packet(self, fact_values: dict[str, str]) -> dict[str, Any]:
        if self.state is not ContentState.AUDITING or not self.current_validation.passed:
            raise HumanGateError("Auditor cannot run before deterministic hard gates pass")
        if not self.jd_analysis or not self.evidence_map:
            raise OrchestrationError("analysis artifacts are missing")
        if len(self.fusion_history) != len(self.audit_history) + 1:
            raise OrchestrationError("current fusion was already audited")
        cited_fact_ids = {
            fact_id
            for section in self.current_fusion.sections
            for entry in section.entries
            for bullet in entry.bullets
            for fact_id in bullet.fact_ids
        }
        missing = cited_fact_ids.difference(fact_values)
        if missing:
            raise AgentHandoffError(f"Auditor packet is missing facts: {sorted(missing)}")
        return {
            "schema_version": "1.0",
            "fusion": _artifact_payload(self.current_fusion),
            "jd_analysis": _artifact_payload(self.jd_analysis),
            "evidence_map": _artifact_payload(self.evidence_map),
            "validation": _artifact_payload(self.current_validation),
            "referenced_fact_values": {
                fact_id: fact_values[fact_id] for fact_id in sorted(cited_fact_ids)
            },
            "revision_count": max(0, len(self.fusion_history) - 1),
            "execution_mode": self.execution_mode.value,
        }

    def record_audit(self, audit: AuditArtifact) -> bool:
        if self.state is not ContentState.AUDITING:
            raise OrchestrationError("audit is not currently expected")
        if len(self.fusion_history) != len(self.audit_history) + 1:
            raise OrchestrationError("current fusion was already audited")
        _same_envelope(self.packet, audit)
        validation = self.current_validation
        if audit.deterministic_passed != validation.passed:
            raise AgentHandoffError("Auditor changed deterministic pass status")
        if audit.deterministic_findings != validation.findings:
            raise AgentHandoffError("Auditor changed deterministic findings")
        revision_count = len(self.fusion_history) - 1
        if len(audit.revisions) != revision_count:
            raise AgentHandoffError("audit revision records do not match coordinator history")
        self.audit_history.append(audit)
        if audit.disposition is AuditDisposition.PASSED:
            self._transition(ContentState.NEEDS_CONTENT_REVIEW)
            return True
        if revision_count >= 2:
            self._transition(ContentState.NEEDS_CONTENT_REVIEW)
        return False

    def commit_for_review(self) -> Path:
        if self.state is not ContentState.NEEDS_CONTENT_REVIEW:
            raise HumanGateError("content is not ready for review commit")
        if self.committed_path is not None:
            return self.committed_path
        if not all(
            [
                self.jd_analysis,
                self.evidence_map,
                self.fact_diff,
                self.writer_draft,
                self.reference_research,
            ]
        ):
            raise OrchestrationError("required run artifacts are incomplete")
        if self.execution_mode is ExecutionMode.BLIND_DUAL and not self.asu_draft:
            raise OrchestrationError("blind-dual run is missing ASu draft")
        if self.execution_mode is ExecutionMode.SINGLE_AGENT_DEGRADED and not self.asu_failure:
            raise OrchestrationError("degraded run is missing the unavailable-agent record")
        if self.stage is None:
            self.stage = begin_run(
                self.normalized.application_dir, self.packet.run_id
            )
        self.stage.write_model("input-packet.json", self.packet)
        self.stage.write_model("jd-analysis.json", self.jd_analysis)
        self.stage.write_model("evidence-map.json", self.evidence_map)
        self.stage.write_model("fact-diff.json", self.fact_diff)
        self.stage.write_model("reference-research.json", self.reference_research)
        self.stage.write_model("draft-writer.json", self.writer_draft)
        self.stage.write_model(
            "draft-asu.json", self.asu_draft or self.asu_failure
        )
        self.stage.write_model("fusion.json", self.current_fusion)
        self.stage.write_model("validation.json", self.current_validation)
        self.stage.write_model("audit.json", self.current_audit)
        for index in range(1, len(self.fusion_history)):
            self.stage.write_model(
                f"revisions/{index:02d}/fusion.json", self.fusion_history[index]
            )
            self.stage.write_model(
                f"revisions/{index:02d}/validation.json",
                self.validation_history[index],
            )
            self.stage.write_model(
                f"revisions/{index:02d}/audit.json", self.audit_history[index]
            )
        content = render_resume_markdown(self.current_fusion)
        suggestions = self._candidate_suggestions()
        self.stage.write_text("content-master.md", content)
        self.stage.write_text("one-page-density.md", content)
        self.stage.write_text(
            "content-review.md",
            render_content_review(
                self.current_fusion,
                self.current_validation,
                self.current_audit,
                suggestions,
            ),
        )
        manifest = RunManifestArtifact(
            run_id=self.packet.run_id,
            created_at=self.packet.created_at,
            source_digests=self.packet.source_digests,
            state=ContentState.NEEDS_CONTENT_REVIEW,
            execution_mode=self.execution_mode,
            input_packet=self.packet,
            artifacts=self.stage.artifact_records(),
            revision_count=len(self.fusion_history) - 1,
        )
        self.committed_path = self.stage.commit(manifest)
        remove_checkpoint(self.normalized.application_dir, self.packet.run_id)
        missing = validate_run_artifact_completeness(self.committed_path)
        if missing:
            raise OrchestrationError(
                f"committed run is missing artifacts: {[item.field_path for item in missing]}"
            )
        return self.committed_path

    def approve_content(
        self,
        *,
        approval_granted: bool,
        referenced_fact_values: dict[str, str],
        approved_at: datetime | None = None,
    ) -> Path:
        if not approval_granted:
            raise HumanGateError("explicit content approval is required")
        if self.state is not ContentState.NEEDS_CONTENT_REVIEW:
            raise HumanGateError("content is not ready for approval")
        if self.current_audit.disposition is not AuditDisposition.PASSED:
            raise HumanGateError("failed hard/truth audit cannot be approved")
        final_path = self.commit_for_review()
        cited = {
            fact_id
            for section in self.current_fusion.sections
            for entry in section.entries
            for bullet in entry.bullets
            for fact_id in bullet.fact_ids
        }
        missing_values = cited.difference(referenced_fact_values)
        if missing_values:
            raise OrchestrationError(
                f"approval is missing referenced fact values: {sorted(missing_values)}"
            )
        self._transition(ContentState.APPROVED)
        approve_run(
            self.normalized.application_dir,
            self.packet.run_id,
            {fact_id: referenced_fact_values[fact_id] for fact_id in cited},
            approved_at=approved_at,
        )
        return final_path

    def finalize_content(
        self,
        *,
        approval_granted: bool,
        referenced_fact_values: dict[str, str],
        approved_at: datetime | None = None,
    ) -> Path:
        return self.approve_content(
            approval_granted=approval_granted,
            referenced_fact_values=referenced_fact_values,
            approved_at=approved_at,
        )
