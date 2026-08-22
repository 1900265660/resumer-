from __future__ import annotations

import argparse
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION = "1.0"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
RUN_ID_PATTERN = r"^cr_[0-9]{8}T[0-9]{6}_[a-z0-9]{6}$"
FACT_ID_PATTERN = r"^FACT-[A-Z]+-[0-9]{3}-[0-9]{2}$"
EXPERIENCE_ID_PATTERN = r"^EXP-[A-Z]+-[0-9]{3}$"
REQUIREMENT_ID_PATTERN = r"^REQ-[0-9]{3}$"
BULLET_ID_PATTERN = r"^(WRITER|ASU|FUSION)-[0-9]{3}$"

Sha256 = Annotated[str, Field(pattern=SHA256_PATTERN)]
RunId = Annotated[str, Field(pattern=RUN_ID_PATTERN)]
FactId = Annotated[str, Field(pattern=FACT_ID_PATTERN)]
ExperienceId = Annotated[str, Field(pattern=EXPERIENCE_ID_PATTERN)]
RequirementId = Annotated[str, Field(pattern=REQUIREMENT_ID_PATTERN)]
BulletId = Annotated[str, Field(pattern=BULLET_ID_PATTERN)]


class StringEnum(str, Enum):
    pass


class SourceType(StringEnum):
    DIRECTORY = "directory"
    TEXT = "text"
    URL = "url"


class RoleFamily(StringEnum):
    AI_PRODUCT_MANAGER = "ai_product_manager"
    GAME_PRODUCTION_PM = "game_production_pm"


class ContentState(StringEnum):
    NOT_STARTED = "not_started"
    ANALYZING = "analyzing"
    NEEDS_INPUT = "needs_input"
    AWAITING_SELECTION_APPROVAL = "awaiting_selection_approval"
    DRAFTING = "drafting"
    AUDITING = "auditing"
    NEEDS_CONTENT_REVIEW = "needs_content_review"
    APPROVED = "approved"
    FAILED = "failed"
    STALE = "stale"


class RequirementPriority(StringEnum):
    MUST = "must"
    SHOULD = "should"
    NICE_TO_HAVE = "nice_to_have"


class CoverageLevel(StringEnum):
    DIRECT = "direct"
    COMPOSITE = "composite"
    ACCEPTED_ESTIMATE = "accepted_estimate"
    CANDIDATE = "candidate"
    UNSUPPORTED = "unsupported"


class FactProvenance(StringEnum):
    OBSERVED = "observed"
    ACCEPTED_ESTIMATE = "accepted_estimate"


class DiffAction(StringEnum):
    ADD = "add"
    REPLACE = "replace"


class ConfirmationStatus(StringEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class QuestionStatus(StringEnum):
    UNANSWERED = "unanswered"
    ANSWERED = "answered"
    SKIPPED = "skipped"


class DraftAgent(StringEnum):
    WRITER = "writer"
    ASU_WRITER = "asu_writer"


class AgentRole(StringEnum):
    COORDINATOR = "coordinator"
    WRITER = "writer"
    ASU_WRITER = "asu_writer"
    AUDITOR = "auditor"


class ExecutionMode(StringEnum):
    BLIND_DUAL = "blind_dual"
    SINGLE_AGENT_DEGRADED = "single_agent_degraded"


class ReferenceResearchMode(StringEnum):
    LOCAL = "local"
    SUPPLEMENTED = "supplemented"
    DEGRADED = "degraded"


class ResumeSectionName(StringEnum):
    EDUCATION = "教育经历"
    WORK = "实习/工作经历"
    PRACTICE = "实践经历"
    ABILITIES = "自我能力"


class FusionAction(StringEnum):
    SELECT_WRITER = "select_writer"
    SELECT_ASU = "select_asu"
    REWRITE_FROM_BOTH = "rewrite_from_both"
    DROP = "drop"


class Severity(StringEnum):
    HARD = "hard"
    WARNING = "warning"


class AuditDisposition(StringEnum):
    PASSED = "passed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False,
    )


def _ensure_unique(values: list[str], field_name: str) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return values


class SourceDigests(StrictModel):
    jd_sha256: Sha256
    fact_snapshot_sha256: Sha256
    preferences_sha256: Sha256
    reference_cards_sha256: Sha256 | None = None


class ArtifactBase(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    run_id: RunId
    created_at: datetime
    source_digests: SourceDigests

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return value


class NormalizedInputPacket(ArtifactBase):
    application_dir: str = Field(pattern=r"^applications[\\/][^\r\n]+$")
    source_type: SourceType
    source_locator: str
    role_family: RoleFamily = RoleFamily.AI_PRODUCT_MANAGER
    approved_requirement_ids: list[RequirementId] = Field(default_factory=list)
    approved_fact_ids: list[FactId] = Field(default_factory=list)

    @field_validator("approved_requirement_ids", "approved_fact_ids")
    @classmethod
    def identifiers_must_be_unique(cls, value: list[str], info: Any) -> list[str]:
        return _ensure_unique(value, info.field_name)


class JobRequirement(StrictModel):
    requirement_id: RequirementId
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1)
    priority: RequirementPriority
    rationale: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)

    @field_validator("keywords")
    @classmethod
    def keywords_must_be_unique(cls, value: list[str]) -> list[str]:
        return _ensure_unique(value, "keywords")


class IdealEvidenceItem(StrictModel):
    requirement_id: RequirementId
    evidence_description: str = Field(min_length=1)
    candidate_specific: Literal[False] = False


class JDAnalysisArtifact(ArtifactBase):
    role_family: RoleFamily = RoleFamily.AI_PRODUCT_MANAGER
    job_goal: str = Field(min_length=1)
    business_problems: list[str] = Field(min_length=1)
    requirements: list[JobRequirement] = Field(min_length=1)
    ideal_evidence_blueprint: list[IdealEvidenceItem] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def requirement_identifiers_must_be_consistent(self) -> "JDAnalysisArtifact":
        requirement_ids = [item.requirement_id for item in self.requirements]
        _ensure_unique(requirement_ids, "requirements.requirement_id")
        known = set(requirement_ids)
        unknown = {
            item.requirement_id
            for item in self.ideal_evidence_blueprint
            if item.requirement_id not in known
        }
        if unknown:
            raise ValueError(f"ideal evidence references unknown requirements: {sorted(unknown)}")
        return self


class EvidenceMapping(StrictModel):
    requirement_id: RequirementId
    coverage: CoverageLevel
    fact_ids: list[FactId] = Field(default_factory=list)
    selected: bool = False
    rationale: str = Field(min_length=1)
    gap_summary: str | None = None

    @field_validator("fact_ids")
    @classmethod
    def fact_ids_must_be_unique(cls, value: list[str]) -> list[str]:
        return _ensure_unique(value, "fact_ids")

    @model_validator(mode="after")
    def coverage_must_match_fact_references(self) -> "EvidenceMapping":
        supported = {
            CoverageLevel.DIRECT,
            CoverageLevel.COMPOSITE,
            CoverageLevel.ACCEPTED_ESTIMATE,
        }
        unsupported = {CoverageLevel.CANDIDATE, CoverageLevel.UNSUPPORTED}
        if self.coverage in supported and not self.fact_ids:
            raise ValueError(f"{self.coverage.value} coverage requires fact_ids")
        if self.coverage in unsupported and self.fact_ids:
            raise ValueError(f"{self.coverage.value} coverage cannot cite confirmed fact_ids")
        if self.coverage in unsupported and not self.gap_summary:
            raise ValueError(f"{self.coverage.value} coverage requires gap_summary")
        return self


class EvidenceMapArtifact(ArtifactBase):
    mappings: list[EvidenceMapping] = Field(min_length=1)
    selection_approved: bool = False
    approved_at: datetime | None = None

    @model_validator(mode="after")
    def mappings_and_approval_must_be_consistent(self) -> "EvidenceMapArtifact":
        ids = [item.requirement_id for item in self.mappings]
        _ensure_unique(ids, "mappings.requirement_id")
        if self.selection_approved != (self.approved_at is not None):
            raise ValueError("selection_approved and approved_at must be set together")
        if self.approved_at and (
            self.approved_at.tzinfo is None or self.approved_at.utcoffset() is None
        ):
            raise ValueError("approved_at must include a timezone")
        return self


class FactDiffOperation(StrictModel):
    operation_id: str = Field(pattern=r"^FD-[0-9]{3}$")
    action: DiffAction
    experience_id: ExperienceId
    target_fact_id: FactId | None = None
    proposed_fact_id: FactId | None = None
    old_value: str | None = None
    new_value: str = Field(min_length=1)
    provenance: FactProvenance
    estimate_basis: str | None = None
    confirmation_status: ConfirmationStatus = ConfirmationStatus.PENDING
    confirmed_at: datetime | None = None

    @model_validator(mode="after")
    def operation_shape_must_be_valid(self) -> "FactDiffOperation":
        if self.action is DiffAction.ADD:
            if not self.proposed_fact_id or self.target_fact_id or self.old_value is not None:
                raise ValueError(
                    "add requires proposed_fact_id and forbids target_fact_id/old_value"
                )
        if self.action is DiffAction.REPLACE:
            if not self.target_fact_id or not self.old_value or self.proposed_fact_id:
                raise ValueError(
                    "replace requires target_fact_id/old_value and forbids proposed_fact_id"
                )
        if self.provenance is FactProvenance.ACCEPTED_ESTIMATE and not self.estimate_basis:
            raise ValueError("accepted_estimate requires estimate_basis")
        if self.provenance is FactProvenance.OBSERVED and self.estimate_basis:
            raise ValueError("observed facts cannot include estimate_basis")
        approved = self.confirmation_status is ConfirmationStatus.APPROVED
        if approved != (self.confirmed_at is not None):
            raise ValueError("approved operations require confirmed_at, and only approved operations may set it")
        if self.confirmed_at and (
            self.confirmed_at.tzinfo is None or self.confirmed_at.utcoffset() is None
        ):
            raise ValueError("confirmed_at must include a timezone")
        return self


class FactQuestionOption(StrictModel):
    option_id: str = Field(pattern=r"^[A-Z]$")
    label: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1)


class FactGapQuestion(StrictModel):
    question_id: str = Field(pattern=r"^Q-[0-9]{3}$")
    requirement_ids: list[RequirementId] = Field(min_length=1)
    prompt: str = Field(min_length=1)
    options: list[FactQuestionOption] = Field(min_length=2, max_length=4)
    status: QuestionStatus = QuestionStatus.UNANSWERED
    selected_option_id: str | None = Field(default=None, pattern=r"^[A-Z]$")
    answer_text: str | None = None

    @model_validator(mode="after")
    def answer_must_match_status_and_options(self) -> "FactGapQuestion":
        _ensure_unique(self.requirement_ids, "requirement_ids")
        option_ids = [item.option_id for item in self.options]
        _ensure_unique(option_ids, "options.option_id")
        if self.selected_option_id and self.selected_option_id not in option_ids:
            raise ValueError("selected_option_id must reference an option")
        if self.status is QuestionStatus.UNANSWERED and (
            self.selected_option_id or self.answer_text
        ):
            raise ValueError("unanswered questions cannot contain an answer")
        if self.status is QuestionStatus.ANSWERED and not (
            self.selected_option_id or self.answer_text
        ):
            raise ValueError("answered questions require an option or answer_text")
        if self.status is QuestionStatus.SKIPPED and (
            self.selected_option_id or self.answer_text
        ):
            raise ValueError("skipped questions cannot contain an answer")
        return self


class FactDiffArtifact(ArtifactBase):
    source_fact_sha256: Sha256
    confirmation_status: ConfirmationStatus = ConfirmationStatus.PENDING
    questions: list[FactGapQuestion] = Field(default_factory=list, max_length=5)
    operations: list[FactDiffOperation] = Field(default_factory=list)

    @model_validator(mode="after")
    def root_status_must_match_operations(self) -> "FactDiffArtifact":
        ids = [item.operation_id for item in self.operations]
        _ensure_unique(ids, "operations.operation_id")
        question_ids = [item.question_id for item in self.questions]
        _ensure_unique(question_ids, "questions.question_id")
        statuses = {item.confirmation_status for item in self.operations}
        if not self.operations:
            question_statuses = {item.status for item in self.questions}
            if not self.questions and self.confirmation_status is not ConfirmationStatus.PENDING:
                raise ValueError("an empty fact diff without questions must remain pending")
            if self.confirmation_status is ConfirmationStatus.PENDING and question_statuses.difference(
                {QuestionStatus.UNANSWERED}
            ):
                raise ValueError("pending fact questions must remain unanswered")
            if self.confirmation_status is ConfirmationStatus.REJECTED and (
                not self.questions or question_statuses != {QuestionStatus.SKIPPED}
            ):
                raise ValueError("rejected question-only diff requires every question to be skipped")
            if self.confirmation_status is ConfirmationStatus.APPROVED and (
                not self.questions or QuestionStatus.UNANSWERED in question_statuses
            ):
                raise ValueError("approved question-only diff requires every question to be resolved")
            return self
        if self.confirmation_status is ConfirmationStatus.APPROVED and statuses != {
            ConfirmationStatus.APPROVED
        }:
            raise ValueError("approved fact diff requires every operation to be approved")
        if self.confirmation_status is ConfirmationStatus.REJECTED and statuses != {
            ConfirmationStatus.REJECTED
        }:
            raise ValueError("rejected fact diff requires every operation to be rejected")
        if self.confirmation_status is ConfirmationStatus.PENDING and statuses != {
            ConfirmationStatus.PENDING
        }:
            raise ValueError("pending fact diff cannot contain decided operations")
        return self


class CandidateSuggestion(StrictModel):
    suggestion_id: str = Field(pattern=r"^CAND-[0-9]{3}$")
    category: Literal["process", "tool", "result", "estimate"]
    question: str = Field(min_length=1)
    suggested_text: str = Field(min_length=1)
    estimate_range: str | None = None

    @model_validator(mode="after")
    def estimate_category_must_match_range(self) -> "CandidateSuggestion":
        if self.category == "estimate" and not self.estimate_range:
            raise ValueError("estimate suggestions require estimate_range")
        if self.category != "estimate" and self.estimate_range:
            raise ValueError("only estimate suggestions may include estimate_range")
        return self


class ResumeBullet(StrictModel):
    bullet_id: BulletId
    text: str = Field(min_length=1)
    fact_ids: list[FactId] = Field(min_length=1)
    requirement_ids: list[RequirementId] = Field(default_factory=list)
    primary_value: str = Field(min_length=1)

    @field_validator("fact_ids", "requirement_ids")
    @classmethod
    def bullet_ids_must_be_unique(cls, value: list[str], info: Any) -> list[str]:
        return _ensure_unique(value, info.field_name)


class ResumeEntry(StrictModel):
    experience_id: ExperienceId
    heading: str = Field(min_length=1)
    bullets: list[ResumeBullet] = Field(min_length=1)

    @model_validator(mode="after")
    def bullet_identifiers_must_be_unique(self) -> "ResumeEntry":
        _ensure_unique([item.bullet_id for item in self.bullets], "bullets.bullet_id")
        return self


class ResumeSection(StrictModel):
    name: ResumeSectionName
    entries: list[ResumeEntry] = Field(default_factory=list)


EXPECTED_SECTION_ORDER = [
    ResumeSectionName.EDUCATION,
    ResumeSectionName.WORK,
    ResumeSectionName.PRACTICE,
    ResumeSectionName.ABILITIES,
]


def _validate_sections(sections: list[ResumeSection]) -> None:
    names = [section.name for section in sections]
    if names != EXPECTED_SECTION_ORDER:
        raise ValueError(
            "sections must appear exactly as 教育经历、实习/工作经历、实践经历、自我能力"
        )
    bullet_ids = [
        bullet.bullet_id
        for section in sections
        for entry in section.entries
        for bullet in entry.bullets
    ]
    _ensure_unique(bullet_ids, "sections.bullets.bullet_id")


class DraftArtifact(ArtifactBase):
    agent: DraftAgent
    sections: list[ResumeSection] = Field(min_length=4, max_length=4)
    candidate_suggestions: list[CandidateSuggestion] = Field(default_factory=list)

    @model_validator(mode="after")
    def draft_sections_must_be_complete(self) -> "DraftArtifact":
        _validate_sections(self.sections)
        if self.agent is DraftAgent.WRITER:
            invalid = [
                bullet.bullet_id
                for section in self.sections
                for entry in section.entries
                for bullet in entry.bullets
                if not bullet.bullet_id.startswith("WRITER-")
            ]
        else:
            invalid = [
                bullet.bullet_id
                for section in self.sections
                for entry in section.entries
                for bullet in entry.bullets
                if not bullet.bullet_id.startswith("ASU-")
            ]
        if invalid:
            raise ValueError(f"bullet IDs do not match draft agent: {invalid}")
        return self


class FusionDecision(StrictModel):
    decision_id: str = Field(pattern=r"^DEC-[0-9]{3}$")
    action: FusionAction
    source_bullet_ids: list[BulletId] = Field(min_length=1)
    output_bullet_id: BulletId | None = None
    output_text: str | None = None
    fact_ids: list[FactId] = Field(default_factory=list)
    requirement_ids: list[RequirementId] = Field(default_factory=list)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def decision_shape_must_match_action(self) -> "FusionDecision":
        _ensure_unique(self.source_bullet_ids, "source_bullet_ids")
        _ensure_unique(self.fact_ids, "fact_ids")
        _ensure_unique(self.requirement_ids, "requirement_ids")
        if self.action is FusionAction.DROP:
            if self.output_bullet_id or self.output_text or self.fact_ids:
                raise ValueError("drop decisions cannot include output or fact_ids")
        else:
            if not self.output_bullet_id or not self.output_text or not self.fact_ids:
                raise ValueError("non-drop decisions require output_bullet_id, output_text, and fact_ids")
            if not self.output_bullet_id.startswith("FUSION-"):
                raise ValueError("fusion output bullet IDs must use the FUSION prefix")
        return self


class FusionArtifact(ArtifactBase):
    sections: list[ResumeSection] = Field(min_length=4, max_length=4)
    decisions: list[FusionDecision] = Field(min_length=1)

    @model_validator(mode="after")
    def fusion_must_be_consistent(self) -> "FusionArtifact":
        _validate_sections(self.sections)
        decision_ids = [item.decision_id for item in self.decisions]
        _ensure_unique(decision_ids, "decisions.decision_id")
        output_bullets = {
            bullet.bullet_id
            for section in self.sections
            for entry in section.entries
            for bullet in entry.bullets
        }
        if any(not item.startswith("FUSION-") for item in output_bullets):
            raise ValueError("fusion sections may contain only FUSION bullet IDs")
        decided_outputs = {
            item.output_bullet_id
            for item in self.decisions
            if item.output_bullet_id is not None
        }
        if output_bullets != decided_outputs:
            raise ValueError("fusion bullets and non-drop decision outputs must match exactly")
        return self


class AuditFinding(StrictModel):
    error_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    severity: Severity
    artifact: str = Field(min_length=1)
    field_path: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ContentMetrics(StrictModel):
    chinese_character_count: Annotated[int, Field(ge=0)]
    experience_bullet_count: Annotated[int, Field(ge=0)]
    total_bullet_count: Annotated[int, Field(ge=0)]


class DeterministicValidationArtifact(ArtifactBase):
    passed: bool
    findings: list[AuditFinding] = Field(default_factory=list)
    metrics: ContentMetrics

    @model_validator(mode="after")
    def passed_must_match_hard_findings(self) -> "DeterministicValidationArtifact":
        hard_failures = any(item.severity is Severity.HARD for item in self.findings)
        if self.passed == hard_failures:
            raise ValueError("validation passed flag must be the inverse of hard findings")
        return self


class TruthAudit(StrictModel):
    passed: bool
    findings: list[AuditFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def passed_must_match_findings(self) -> "TruthAudit":
        hard_failures = any(item.severity is Severity.HARD for item in self.findings)
        if self.passed == hard_failures:
            raise ValueError("truth passed flag must be the inverse of hard findings")
        return self


class QualityDimension(StrictModel):
    score: Annotated[float, Field(ge=0, le=10)]
    evidence: list[str] = Field(min_length=1)
    recommendations: list[str] = Field(default_factory=list)


class QualityAudit(StrictModel):
    jd_coverage: QualityDimension
    evidence_depth: QualityDimension
    hr_scan: QualityDimension
    language_naturalness: QualityDimension
    passed: bool
    override_reason: str | None = None

    @model_validator(mode="after")
    def passed_must_match_scores_or_override(self) -> "QualityAudit":
        scores = [
            self.jd_coverage.score,
            self.evidence_depth.score,
            self.hr_scan.score,
            self.language_naturalness.score,
        ]
        meets_threshold = all(score >= 8 for score in scores)
        if self.passed and not meets_threshold and not self.override_reason:
            raise ValueError("quality below 8 requires override_reason")
        if not self.passed and meets_threshold:
            raise ValueError("quality meeting all thresholds must pass")
        if self.override_reason and not self.passed:
            raise ValueError("override_reason is valid only when quality is passed")
        return self


class RevisionRecord(StrictModel):
    round: Annotated[int, Field(ge=1, le=2)]
    issue_codes: list[str] = Field(min_length=1)
    changes: list[str] = Field(min_length=1)


class AuditArtifact(ArtifactBase):
    deterministic_passed: bool
    deterministic_findings: list[AuditFinding] = Field(default_factory=list)
    truth: TruthAudit
    quality: QualityAudit
    revisions: list[RevisionRecord] = Field(default_factory=list, max_length=2)
    disposition: AuditDisposition

    @model_validator(mode="after")
    def disposition_must_match_results(self) -> "AuditArtifact":
        hard_deterministic = any(
            item.severity is Severity.HARD for item in self.deterministic_findings
        )
        if self.deterministic_passed == hard_deterministic:
            raise ValueError("deterministic_passed must be the inverse of hard findings")
        rounds = [item.round for item in self.revisions]
        if rounds != list(range(1, len(rounds) + 1)):
            raise ValueError("revision rounds must be sequential starting at 1")
        fully_passed = self.deterministic_passed and self.truth.passed and self.quality.passed
        if fully_passed and self.disposition is not AuditDisposition.PASSED:
            raise ValueError("all audit layers passed, so disposition must be passed")
        if not fully_passed and self.disposition is AuditDisposition.PASSED:
            raise ValueError("failed audit layers cannot produce a passed disposition")
        return self


class ArtifactRecord(StrictModel):
    name: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    sha256: Sha256


class RunError(StrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    message: str = Field(min_length=1)
    recoverable: bool


class AgentFailureArtifact(ArtifactBase):
    role: AgentRole
    error_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    message: str = Field(min_length=1)
    missing_inputs: list[str] = Field(default_factory=list)
    retryable: bool

    @field_validator("missing_inputs")
    @classmethod
    def missing_inputs_must_be_unique(cls, value: list[str]) -> list[str]:
        return _ensure_unique(value, "missing_inputs")


class ReferenceSource(StrictModel):
    title: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://[^\s]+$")
    retrieved_at: datetime

    @field_validator("retrieved_at")
    @classmethod
    def retrieved_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must include a timezone")
        return value


class ReferenceResearchArtifact(ArtifactBase):
    mode: ReferenceResearchMode
    local_card_sha256: Sha256
    missing_topics: list[str] = Field(default_factory=list)
    sources: list[ReferenceSource] = Field(default_factory=list)
    sanitized_method_cards: list[str] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def research_mode_must_match_evidence(self) -> "ReferenceResearchArtifact":
        _ensure_unique(self.missing_topics, "missing_topics")
        _ensure_unique([item.url for item in self.sources], "sources.url")
        if self.mode is ReferenceResearchMode.LOCAL:
            if self.sources or self.sanitized_method_cards or self.error:
                raise ValueError("local reference mode cannot contain network results")
        elif self.mode is ReferenceResearchMode.SUPPLEMENTED:
            if not self.sources or not self.sanitized_method_cards or self.error:
                raise ValueError("supplemented mode requires sources and sanitized cards")
        elif not self.error:
            raise ValueError("degraded reference mode requires an error")
        return self


class RunManifestArtifact(ArtifactBase):
    state: ContentState
    execution_mode: ExecutionMode = ExecutionMode.BLIND_DUAL
    input_packet: NormalizedInputPacket
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    revision_count: Annotated[int, Field(ge=0, le=2)] = 0
    error: RunError | None = None

    @model_validator(mode="after")
    def manifest_must_be_consistent(self) -> "RunManifestArtifact":
        if self.input_packet.run_id != self.run_id:
            raise ValueError("input_packet.run_id must match run_id")
        if self.input_packet.source_digests != self.source_digests:
            raise ValueError("input_packet.source_digests must match source_digests")
        _ensure_unique([item.name for item in self.artifacts], "artifacts.name")
        _ensure_unique([item.relative_path for item in self.artifacts], "artifacts.relative_path")
        if (self.state is ContentState.FAILED) != (self.error is not None):
            raise ValueError("failed state and error must be set together")
        return self


class ReferencedFactDigest(StrictModel):
    fact_id: FactId
    value_sha256: Sha256


class CurrentPointer(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    status: ContentState
    approved_run_id: RunId
    run_relative_path: str = Field(
        pattern=r"^resume-content[\\/]runs[\\/]cr_[0-9]{8}T[0-9]{6}_[a-z0-9]{6}$"
    )
    approved_at: datetime
    updated_at: datetime
    transaction_id: str = Field(pattern=r"^approval_[a-f0-9]{32}$")
    referenced_facts: list[ReferencedFactDigest] = Field(min_length=1)

    @model_validator(mode="after")
    def pointer_must_be_consistent(self) -> "CurrentPointer":
        if self.status not in {ContentState.APPROVED, ContentState.STALE}:
            raise ValueError("current pointer status must be approved or stale")
        expected_suffix = f"runs/{self.approved_run_id}"
        normalized_path = self.run_relative_path.replace("\\", "/")
        if not normalized_path.endswith(expected_suffix):
            raise ValueError("run_relative_path must reference approved_run_id")
        for field_name in ("approved_at", "updated_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must include a timezone")
        _ensure_unique(
            [item.fact_id for item in self.referenced_facts],
            "referenced_facts.fact_id",
        )
        return self


class ResumeContentSummary(StrictModel):
    status: ContentState
    current_pointer: Literal["resume-content/current.json"] = (
        "resume-content/current.json"
    )
    approved_run_id: RunId
    updated_at: datetime
    transaction_id: str = Field(pattern=r"^approval_[a-f0-9]{32}$")

    @model_validator(mode="after")
    def summary_must_reference_approved_content(self) -> "ResumeContentSummary":
        if self.status not in {ContentState.APPROVED, ContentState.STALE}:
            raise ValueError("resume content summary status must be approved or stale")
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise ValueError("updated_at must include a timezone")
        return self


ALLOWED_TRANSITIONS: dict[ContentState, frozenset[ContentState]] = {
    ContentState.NOT_STARTED: frozenset({ContentState.ANALYZING, ContentState.FAILED}),
    ContentState.ANALYZING: frozenset(
        {
            ContentState.NEEDS_INPUT,
            ContentState.AWAITING_SELECTION_APPROVAL,
            ContentState.FAILED,
        }
    ),
    ContentState.NEEDS_INPUT: frozenset(
        {ContentState.AWAITING_SELECTION_APPROVAL, ContentState.FAILED}
    ),
    ContentState.AWAITING_SELECTION_APPROVAL: frozenset(
        {ContentState.DRAFTING, ContentState.FAILED}
    ),
    ContentState.DRAFTING: frozenset({ContentState.AUDITING, ContentState.FAILED}),
    ContentState.AUDITING: frozenset(
        {
            ContentState.NEEDS_CONTENT_REVIEW,
            ContentState.APPROVED,
            ContentState.FAILED,
        }
    ),
    ContentState.NEEDS_CONTENT_REVIEW: frozenset(
        {ContentState.AUDITING, ContentState.APPROVED, ContentState.FAILED}
    ),
    ContentState.APPROVED: frozenset({ContentState.STALE}),
    ContentState.FAILED: frozenset(),
    ContentState.STALE: frozenset(),
}


class InvalidStateTransition(ValueError):
    pass


def assert_state_transition(current: ContentState, target: ContentState) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidStateTransition(
            f"invalid resume content state transition: {current.value} -> {target.value}"
        )


ARTIFACT_MODELS: dict[str, type[BaseModel]] = {
    "input-packet": NormalizedInputPacket,
    "run": RunManifestArtifact,
    "jd-analysis": JDAnalysisArtifact,
    "evidence-map": EvidenceMapArtifact,
    "fact-diff": FactDiffArtifact,
    "draft": DraftArtifact,
    "fusion": FusionArtifact,
    "audit": AuditArtifact,
    "current": CurrentPointer,
    "agent-failure": AgentFailureArtifact,
    "validation": DeterministicValidationArtifact,
    "reference-research": ReferenceResearchArtifact,
}


def export_json_schemas(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in ARTIFACT_MODELS.items():
        path = output_dir / f"{name}.schema.json"
        path.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Export custom-resume V1 JSON schemas")
    parser.add_argument("--export-dir", required=True, type=Path)
    args = parser.parse_args()
    for path in export_json_schemas(args.export_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
