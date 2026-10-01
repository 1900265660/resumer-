from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SCHEMA_VERSION = "1.5"
SUPPORTED_SCHEMA_VERSIONS = ("1.0", "1.1", "1.2", "1.3", "1.4", "1.5")
MAX_GENERATION_ROUNDS = 3
SHA256_PATTERN = r"^[0-9a-f]{64}$"
RUN_ID_PATTERN = r"^cr_[0-9]{8}T[0-9]{6}_[a-z0-9]{6}$"
FACT_ID_PATTERN = r"^FACT-[A-Z]+-[0-9]{3}-[0-9]{2}$"
EXPERIENCE_ID_PATTERN = r"^EXP-[A-Z]+-[0-9]{3}$"
REQUIREMENT_ID_PATTERN = r"^REQ-[0-9]{3}$"
BULLET_ID_PATTERN = r"^(WRITER|ASU|FUSION)-[0-9]{3}$"
TRANSFER_ID_PATTERN = r"^TR-[0-9]{3}$"
INTENT_ID_PATTERN = r"^INT-[0-9]{3}$"

Sha256 = Annotated[str, Field(pattern=SHA256_PATTERN)]
RunId = Annotated[str, Field(pattern=RUN_ID_PATTERN)]
FactId = Annotated[str, Field(pattern=FACT_ID_PATTERN)]
ExperienceId = Annotated[str, Field(pattern=EXPERIENCE_ID_PATTERN)]
RequirementId = Annotated[str, Field(pattern=REQUIREMENT_ID_PATTERN)]
BulletId = Annotated[str, Field(pattern=BULLET_ID_PATTERN)]
TransferId = Annotated[str, Field(pattern=TRANSFER_ID_PATTERN)]
IntentId = Annotated[str, Field(pattern=INTENT_ID_PATTERN)]


class StringEnum(str, Enum):
    pass


class SourceType(StringEnum):
    DIRECTORY = "directory"
    TEXT = "text"
    URL = "url"


class RoleFamily(StringEnum):
    AI_PRODUCT_MANAGER = "ai_product_manager"
    GAME_PRODUCTION_PM = "game_production_pm"
    COMMUNITY_OPERATIONS = "community_operations"
    COMMUNITY_PRODUCT_MANAGER = "community_product_manager"
    GAME_DESIGNER = "game_designer"


class RoleTrack(StringEnum):
    COMMUNITY = "community"
    CONTENT = "content"
    GROWTH = "growth"
    INTEGRATED = "integrated"
    SYSTEM = "system"
    COMBAT = "combat"
    WRITING = "writing"
    NARRATIVE = "narrative"
    GENERAL = "general"


LEGACY_ROLE_FAMILIES = frozenset(
    {RoleFamily.AI_PRODUCT_MANAGER, RoleFamily.GAME_PRODUCTION_PM}
)
ROLE_TRACKS_BY_FAMILY: dict[RoleFamily, frozenset[RoleTrack]] = {
    RoleFamily.COMMUNITY_OPERATIONS: frozenset(
        {
            RoleTrack.COMMUNITY,
            RoleTrack.CONTENT,
            RoleTrack.GROWTH,
            RoleTrack.INTEGRATED,
        }
    ),
    RoleFamily.GAME_DESIGNER: frozenset(
        {
            RoleTrack.SYSTEM,
            RoleTrack.COMBAT,
            RoleTrack.WRITING,
            RoleTrack.NARRATIVE,
            RoleTrack.GENERAL,
        }
    ),
}


def validate_role_route(
    schema_version: str,
    role_family: RoleFamily,
    role_track: RoleTrack | None,
) -> None:
    if schema_version not in {"1.4", "1.5"}:
        if role_family not in LEGACY_ROLE_FAMILIES:
            raise ValueError("new role families require schema 1.4+")
        if role_track is not None:
            raise ValueError("role_track is available only in schema 1.4+")
        return
    allowed_tracks = ROLE_TRACKS_BY_FAMILY.get(role_family)
    if allowed_tracks is None:
        if role_track is not None:
            raise ValueError(f"{role_family.value} must not define role_track")
        return
    if role_track is None:
        raise ValueError(f"{role_family.value} requires role_track")
    if role_track not in allowed_tracks:
        allowed = ", ".join(sorted(item.value for item in allowed_tracks))
        raise ValueError(
            f"invalid role_track {role_track.value} for {role_family.value}; allowed: {allowed}"
        )


def self_ability_headings_for_role(
    role_family: RoleFamily, schema_version: str = SCHEMA_VERSION
) -> tuple[str, ...]:
    if schema_version == "1.5" and role_family is RoleFamily.AI_PRODUCT_MANAGER:
        return ("专业硬技能", "综合软技能", "个人优势")
    third_heading = (
        "行业/平台经历"
        if role_family
        in {RoleFamily.COMMUNITY_OPERATIONS, RoleFamily.COMMUNITY_PRODUCT_MANAGER}
        else "游戏经历"
    )
    return ("专业硬技能", "综合软技能", third_heading, "语言能力")


class ContentState(StringEnum):
    NOT_STARTED = "not_started"
    ANALYZING = "analyzing"
    NEEDS_INPUT = "needs_input"
    AWAITING_REFERENCE_APPROVAL = "awaiting_reference_approval"
    AWAITING_SELECTION_APPROVAL = "awaiting_selection_approval"
    DRAFTING = "drafting"
    AUDITING = "auditing"
    HR_REVIEWING = "hr_reviewing"
    NEEDS_CONTENT_REVIEW = "needs_content_review"
    READY_FOR_USER_REVIEW = "ready_for_user_review"
    APPROVED = "approved"
    FAILED = "failed"
    QUALITY_FAILED = "quality_failed"
    STALE = "stale"
    NO_APPROVED_CONTENT = "no_approved_content"


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


class DraftResultStatus(StringEnum):
    QUANTIFIED = "quantified"
    QUALITATIVE = "qualitative"
    NO_CONFIRMED_RESULT = "no_confirmed_result"
    MISSING_SUPPORTED_RESULT = "missing_supported_result"


class AgentRole(StringEnum):
    COORDINATOR = "coordinator"
    WRITER = "writer"
    ASU_WRITER = "asu_writer"
    AUDITOR = "auditor"
    HR_REVIEWER = "hr_reviewer"


class AgentStage(StringEnum):
    REFERENCE_RESEARCH = "reference_research"
    JD_ANALYSIS = "jd_analysis"
    CAPABILITY_TRANSFER = "capability_transfer"
    EXPERIENCE_SELECTION = "experience_selection"
    SELECTION_AUDIT = "selection_audit"
    STORY_PLAN = "story_plan"
    WRITER = "writer"
    ASU_WRITER = "asu_writer"
    DRAFT_AUDIT = "draft_audit"
    FUSION = "fusion"
    POST_FUSION_AUDIT = "post_fusion_audit"
    HR_REVIEW = "hr_review"


class RunStatus(StringEnum):
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    USER_REJECTED = "user_rejected"
    SCHEMA_INVALID = "schema_invalid"
    REVOKED = "revoked"


class ExecutionMode(StringEnum):
    BLIND_DUAL = "blind_dual"
    SINGLE_AGENT_DEGRADED = "single_agent_degraded"


class ReferenceResearchMode(StringEnum):
    LOCAL = "local"
    SUPPLEMENTED = "supplemented"
    DEGRADED = "degraded"


class ReferenceSourceType(StringEnum):
    RESUME_SAMPLE = "resume_sample"
    OFFICIAL_ROLE = "official_role"
    HIRING_GUIDE = "hiring_guide"
    OPEN_SOURCE_METHOD = "open_source_method"


class JobTaskEvidenceLevel(StringEnum):
    DIRECT = "direct"
    TRANSFERABLE = "transferable"
    AFFINITY_ONLY = "affinity_only"
    NONE = "none"


class CapabilityCategory(StringEnum):
    PLANNING_DELIVERY = "planning_delivery"
    STAKEHOLDER_COLLABORATION = "stakeholder_collaboration"
    QUALITY_RISK = "quality_risk"
    USER_RESEARCH = "user_research"
    DATA_ANALYSIS = "data_analysis"
    CONTENT_COMMUNICATION = "content_communication"
    PRODUCT_TECHNOLOGY = "product_technology"
    OPERATIONS_BUSINESS_DOMAIN = "operations_business_domain"


class CapabilityStatus(StringEnum):
    SUPPORTED = "supported"
    CANDIDATE = "candidate"
    NONE = "none"


class TransferDistance(StringEnum):
    DIRECT = "direct"
    ADJACENT = "adjacent"
    ANALOGICAL = "analogical"
    CANDIDATE = "candidate"


class TransferConfidence(StringEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScoreComponent(StringEnum):
    RESPONSIBILITY = "responsibility"
    PROCESS_DELIVERY = "process_delivery"
    RESULT = "result"
    DOMAIN = "domain"
    INCREMENTAL_COVERAGE = "incremental_coverage"
    EVIDENCE_STRENGTH = "evidence_strength"


class ExperienceTier(StringEnum):
    CORE = "core"
    AUXILIARY = "auxiliary"
    EXCLUDED = "excluded"


class SelectionAuditPhase(StringEnum):
    PRE_DRAFT = "pre_draft"
    POST_FUSION = "post_fusion"


class SelectionAuditVerdict(StringEnum):
    KEEP = "keep"
    AUXILIARY = "auxiliary"
    DROP = "drop"
    RECONSIDER = "reconsider"


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


class HrRecommendation(StringEnum):
    STRONG_PUSH = "strong_push"
    PUSH = "push"
    HESITATE = "hesitate"
    REJECT = "reject"


class HrReviewDisposition(StringEnum):
    PASSED = "passed"
    REVISE = "revise"
    NEEDS_INPUT = "needs_input"
    RESELECT = "reselect"
    NEEDS_REVIEW = "needs_review"


class InterviewImpact(StringEnum):
    NONE = "none"
    MINOR = "minor"
    MATERIAL = "material"
    BLOCKING = "blocking"


class UncitedFactDisposition(StringEnum):
    IRRELEVANT = "irrelevant"
    REDUNDANT = "redundant"
    SHOULD_INCLUDE = "should_include"


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
    schema_version: Literal["1.0", "1.1", "1.2", "1.3", "1.4", "1.5"] = SCHEMA_VERSION
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
    role_track: RoleTrack | None = None
    approved_requirement_ids: list[RequirementId] = Field(default_factory=list)
    approved_fact_ids: list[FactId] = Field(default_factory=list)
    approved_experience_ids: list[ExperienceId] = Field(default_factory=list)
    approved_transfer_ids: list[TransferId] = Field(default_factory=list)

    @field_validator(
        "approved_requirement_ids",
        "approved_fact_ids",
        "approved_experience_ids",
        "approved_transfer_ids",
    )
    @classmethod
    def identifiers_must_be_unique(cls, value: list[str], info: Any) -> list[str]:
        return _ensure_unique(value, info.field_name)

    @model_validator(mode="before")
    @classmethod
    def schema_v14_requires_explicit_role_family(cls, value: Any) -> Any:
        if (
            isinstance(value, dict)
            and value.get("schema_version", SCHEMA_VERSION) in {"1.4", "1.5"}
            and "role_family" not in value
        ):
            raise ValueError("schema 1.4+ requires explicit role_family")
        return value

    @model_validator(mode="after")
    def role_route_must_match_schema(self) -> "NormalizedInputPacket":
        validate_role_route(self.schema_version, self.role_family, self.role_track)
        return self


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
    role_track: RoleTrack | None = None
    job_goal: str = Field(min_length=1)
    business_problems: list[str] = Field(min_length=1)
    requirements: list[JobRequirement] = Field(min_length=1)
    ideal_evidence_blueprint: list[IdealEvidenceItem] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def requirement_identifiers_must_be_consistent(self) -> "JDAnalysisArtifact":
        validate_role_route(self.schema_version, self.role_family, self.role_track)
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


TRANSFER_MULTIPLIERS: dict[TransferDistance, float] = {
    TransferDistance.DIRECT: 1.0,
    TransferDistance.ADJACENT: 0.8,
    TransferDistance.ANALOGICAL: 0.6,
    TransferDistance.CANDIDATE: 0.0,
}


class CapabilityTransfer(StrictModel):
    transfer_id: TransferId
    experience_id: ExperienceId
    category: CapabilityCategory
    fact_ids: list[FactId] = Field(default_factory=list)
    source_action: str = Field(min_length=1)
    target_capability: str = Field(min_length=1)
    requirement_ids: list[RequirementId] = Field(min_length=1)
    distance: TransferDistance
    confidence: TransferConfidence
    credit_multiplier: Annotated[float, Field(ge=0, le=1)]
    writable_scope: str | None = None
    candidate_question_id: str | None = Field(default=None, pattern=r"^Q-[0-9]{3}$")

    @field_validator("fact_ids", "requirement_ids")
    @classmethod
    def transfer_identifiers_must_be_unique(
        cls, value: list[str], info: Any
    ) -> list[str]:
        return _ensure_unique(value, info.field_name)

    @model_validator(mode="after")
    def transfer_boundary_must_match_distance(self) -> "CapabilityTransfer":
        expected_multiplier = TRANSFER_MULTIPLIERS[self.distance]
        if self.credit_multiplier != expected_multiplier:
            raise ValueError(
                f"credit_multiplier must be {expected_multiplier} for {self.distance.value}"
            )
        if self.distance is TransferDistance.CANDIDATE:
            if self.fact_ids or self.writable_scope or not self.candidate_question_id:
                raise ValueError(
                    "candidate transfer forbids fact_ids/writable_scope and requires candidate_question_id"
                )
        else:
            if not self.fact_ids or not self.writable_scope or self.candidate_question_id:
                raise ValueError(
                    "writable transfer requires fact_ids/writable_scope and forbids candidate_question_id"
                )
        return self


class CapabilityCategoryScan(StrictModel):
    experience_id: ExperienceId
    category: CapabilityCategory
    status: CapabilityStatus
    transfer_ids: list[TransferId] = Field(default_factory=list)
    rationale: str = Field(min_length=1)

    @field_validator("transfer_ids")
    @classmethod
    def scan_transfer_ids_must_be_unique(cls, value: list[str]) -> list[str]:
        return _ensure_unique(value, "transfer_ids")

    @model_validator(mode="after")
    def scan_status_must_match_transfers(self) -> "CapabilityCategoryScan":
        if self.status is CapabilityStatus.NONE and self.transfer_ids:
            raise ValueError("none capability scan cannot reference transfers")
        if self.status is not CapabilityStatus.NONE and not self.transfer_ids:
            raise ValueError("supported/candidate capability scan requires transfers")
        return self


class CapabilityTransferMapArtifact(ArtifactBase):
    experience_ids: list[ExperienceId] = Field(min_length=1)
    transfers: list[CapabilityTransfer] = Field(default_factory=list)
    scans: list[CapabilityCategoryScan] = Field(min_length=1)

    @model_validator(mode="after")
    def map_must_cover_every_experience_and_category(
        self,
    ) -> "CapabilityTransferMapArtifact":
        _ensure_unique(self.experience_ids, "experience_ids")
        transfer_by_id = {item.transfer_id: item for item in self.transfers}
        if len(transfer_by_id) != len(self.transfers):
            raise ValueError("transfers.transfer_id must not contain duplicates")
        scan_pairs = [(item.experience_id, item.category) for item in self.scans]
        if len(scan_pairs) != len(set(scan_pairs)):
            raise ValueError("scans must contain one row per experience/category pair")
        expected_pairs = {
            (experience_id, category)
            for experience_id in self.experience_ids
            for category in CapabilityCategory
        }
        if set(scan_pairs) != expected_pairs:
            raise ValueError(
                "scans must cover all eight capability categories for every experience"
            )
        referenced_transfer_ids: list[str] = []
        for scan in self.scans:
            for transfer_id in scan.transfer_ids:
                transfer = transfer_by_id.get(transfer_id)
                if transfer is None:
                    raise ValueError(f"scan references unknown transfer_id {transfer_id}")
                if (
                    transfer.experience_id != scan.experience_id
                    or transfer.category is not scan.category
                ):
                    raise ValueError("scan transfer must match its experience and category")
                if scan.status is CapabilityStatus.SUPPORTED and transfer.distance is TransferDistance.CANDIDATE:
                    raise ValueError("supported scan cannot reference candidate transfer")
                if scan.status is CapabilityStatus.CANDIDATE and transfer.distance is not TransferDistance.CANDIDATE:
                    raise ValueError("candidate scan may reference only candidate transfers")
                referenced_transfer_ids.append(transfer_id)
        if len(referenced_transfer_ids) != len(set(referenced_transfer_ids)):
            raise ValueError("each transfer must be referenced by exactly one scan")
        if set(referenced_transfer_ids) != set(transfer_by_id):
            raise ValueError("every transfer must be referenced by a capability scan")
        return self


class TransferScoreCredit(StrictModel):
    transfer_id: TransferId
    component: ScoreComponent
    base_points: Annotated[int, Field(ge=0, le=30)]
    credited_points: Annotated[int, Field(ge=0, le=30)]


class PortfolioValue(StrictModel):
    section_balance: Annotated[int, Field(ge=0, le=5)]
    capability_diversity: Annotated[int, Field(ge=0, le=5)]
    narrative_uniqueness: Annotated[int, Field(ge=0, le=5)]
    non_redundancy: Annotated[int, Field(ge=0, le=5)]
    total: Annotated[int, Field(ge=0, le=20)]

    @model_validator(mode="after")
    def portfolio_total_must_be_recomputed(self) -> "PortfolioValue":
        expected = (
            self.section_balance
            + self.capability_diversity
            + self.narrative_uniqueness
            + self.non_redundancy
        )
        if self.total != expected:
            raise ValueError(f"portfolio total must equal deterministic component total {expected}")
        return self


class SectionBalanceOverride(StrictModel):
    experience_id: ExperienceId
    reason: str = Field(min_length=1)
    compared_alternative_ids: list[ExperienceId] = Field(min_length=1)
    approved_at: datetime
    max_bullets: Literal[2] = 2

    @model_validator(mode="after")
    def override_must_be_auditable(self) -> "SectionBalanceOverride":
        _ensure_unique(self.compared_alternative_ids, "compared_alternative_ids")
        if self.experience_id in self.compared_alternative_ids:
            raise ValueError("section balance override cannot compare itself")
        if self.approved_at.tzinfo is None or self.approved_at.utcoffset() is None:
            raise ValueError("approved_at must include a timezone")
        return self


class PageFillOverride(StrictModel):
    """Auditable last-resort selection of weak evidence to eliminate a sparse page."""

    experience_ids: list[ExperienceId] = Field(min_length=1, max_length=2)
    reason: str = Field(min_length=1)
    expanded_selected_evidence_exhausted: bool
    approved_at: datetime
    min_bullets_per_experience: Literal[2] = 2

    @model_validator(mode="after")
    def override_must_be_auditable(self) -> "PageFillOverride":
        _ensure_unique(self.experience_ids, "experience_ids")
        if not self.expanded_selected_evidence_exhausted:
            raise ValueError(
                "page fill override requires expanding selected evidence first"
            )
        if self.approved_at.tzinfo is None or self.approved_at.utcoffset() is None:
            raise ValueError("approved_at must include a timezone")
        return self


class ExperienceCandidateScore(StrictModel):
    experience_id: ExperienceId
    fact_ids: list[FactId] = Field(min_length=1)
    responsibility_score: Annotated[int, Field(ge=0, le=30)]
    process_delivery_score: Annotated[int, Field(ge=0, le=20)]
    result_score: Annotated[int, Field(ge=0, le=15)]
    domain_score: Annotated[int, Field(ge=0, le=10)]
    incremental_coverage_score: Annotated[int, Field(ge=0, le=15)]
    evidence_strength_score: Annotated[int, Field(ge=0, le=10)]
    job_task_evidence: JobTaskEvidenceLevel
    total_score: Annotated[int, Field(ge=0, le=100)]
    tier: ExperienceTier
    matched_requirement_ids: list[RequirementId] = Field(default_factory=list)
    incremental_requirement_ids: list[RequirementId] = Field(default_factory=list)
    selected: bool = False
    proposed_bullet_count: Annotated[int, Field(ge=0)] = 0
    rationale: str = Field(min_length=1)
    omission_reason: str | None = None
    user_override_reason: str | None = None
    capability_transfer_ids: list[TransferId] = Field(default_factory=list)
    transfer_score_credits: list[TransferScoreCredit] = Field(default_factory=list)
    portfolio_value_score: PortfolioValue | None = None
    similarity_group: str | None = Field(default=None, min_length=1, max_length=80)
    is_personal_development: bool = False

    @field_validator(
        "fact_ids",
        "matched_requirement_ids",
        "incremental_requirement_ids",
        "capability_transfer_ids",
    )
    @classmethod
    def score_identifiers_must_be_unique(cls, value: list[str], info: Any) -> list[str]:
        return _ensure_unique(value, info.field_name)

    @model_validator(mode="after")
    def score_and_tier_must_be_deterministic(self) -> "ExperienceCandidateScore":
        raw_total = (
            self.responsibility_score
            + self.process_delivery_score
            + self.result_score
            + self.domain_score
            + self.incremental_coverage_score
            + self.evidence_strength_score
        )
        expected_total = min(raw_total, 54) if self.job_task_evidence is JobTaskEvidenceLevel.AFFINITY_ONLY else raw_total
        if self.total_score != expected_total:
            raise ValueError(
                f"total_score must equal deterministic component total {expected_total}"
            )
        expected_tier = (
            ExperienceTier.CORE
            if expected_total >= 70
            else ExperienceTier.AUXILIARY
            if expected_total >= 55
            else ExperienceTier.EXCLUDED
        )
        if self.tier is not expected_tier:
            raise ValueError(f"tier must be {expected_tier.value} for score {expected_total}")
        if self.selected and self.proposed_bullet_count < 1:
            raise ValueError("selected experiences require a positive bullet budget")
        if not self.selected and self.proposed_bullet_count:
            raise ValueError("unselected experiences cannot reserve bullet budget")
        credit_pairs = [
            (item.transfer_id, item.component) for item in self.transfer_score_credits
        ]
        if len(credit_pairs) != len(set(credit_pairs)):
            raise ValueError("transfer score credits must be unique per transfer/component")
        unknown_credit_ids = {
            item.transfer_id for item in self.transfer_score_credits
        }.difference(self.capability_transfer_ids)
        if unknown_credit_ids:
            raise ValueError("transfer score credits must reference candidate transfer IDs")
        if self.is_personal_development and not self.similarity_group:
            raise ValueError("personal development experience requires similarity_group")
        return self


class ExperienceSelectionArtifact(ArtifactBase):
    candidates: list[ExperienceCandidateScore] = Field(min_length=1)
    capability_transfer_map_sha256: Sha256 | None = None
    section_balance_override: SectionBalanceOverride | None = None
    page_fill_override: PageFillOverride | None = None
    honest_weak_draft: bool = False
    selection_approved: bool = False
    approved_at: datetime | None = None

    @model_validator(mode="after")
    def selection_must_be_complete_and_budgeted(self) -> "ExperienceSelectionArtifact":
        _ensure_unique(
            [item.experience_id for item in self.candidates],
            "candidates.experience_id",
        )
        if self.selection_approved != (self.approved_at is not None):
            raise ValueError("selection_approved and approved_at must be set together")
        if self.approved_at and (
            self.approved_at.tzinfo is None or self.approved_at.utcoffset() is None
        ):
            raise ValueError("approved_at must include a timezone")
        if self.schema_version in {"1.0", "1.1"}:
            if (
                self.capability_transfer_map_sha256
                or self.section_balance_override
                or self.page_fill_override
            ):
                raise ValueError("schema 1.0/1.1 cannot contain V1.3 selection fields")
            legacy_fields = [
                item.experience_id
                for item in self.candidates
                if item.portfolio_value_score
                or item.capability_transfer_ids
                or item.transfer_score_credits
                or item.similarity_group
                or item.is_personal_development
            ]
            if legacy_fields:
                raise ValueError("schema 1.0/1.1 candidates cannot contain V1.3 fields")
            selected_excluded = [
                item.experience_id
                for item in self.candidates
                if item.selected and item.tier is ExperienceTier.EXCLUDED
            ]
            if selected_excluded:
                raise ValueError("experiences below 55 cannot be selected")
            invalid_auxiliary = [
                item.experience_id
                for item in self.candidates
                if item.selected
                and item.tier is ExperienceTier.AUXILIARY
                and not item.incremental_requirement_ids
            ]
            if invalid_auxiliary:
                raise ValueError(
                    "selected auxiliary experience must add uncovered JD requirements"
                )
        else:
            if not self.capability_transfer_map_sha256:
                raise ValueError("schema 1.2 selection requires capability transfer map hash")
            missing_portfolio = [
                item.experience_id
                for item in self.candidates
                if item.portfolio_value_score is None
            ]
            if missing_portfolio:
                raise ValueError(
                    f"schema 1.2 candidates require portfolio value: {sorted(missing_portfolio)}"
                )
        selected = [item for item in self.candidates if item.selected]
        if self.selection_approved and not selected:
            raise ValueError("approved selection requires at least one selected experience")
        if self.selection_approved and not self.honest_weak_draft:
            if not any(item.tier is ExperienceTier.CORE for item in selected):
                raise ValueError("normal selection requires at least one core experience")
        if self.selection_approved:
            omitted_core = [
                item.experience_id
                for item in self.candidates
                if item.tier is ExperienceTier.CORE
                and not item.selected
                and not item.omission_reason
            ]
            if omitted_core:
                raise ValueError(
                    f"omitted core experiences require reasons: {sorted(omitted_core)}"
                )
        selected_excluded = [
            item for item in selected if item.tier is ExperienceTier.EXCLUDED
        ]
        if self.schema_version in {"1.2", "1.3", "1.4"}:
            if self.page_fill_override:
                raise ValueError("page fill override is available only in schema 1.5")
            if selected_excluded:
                if len(selected_excluded) != 1 or not self.section_balance_override:
                    raise ValueError(
                        "below-55 selection requires exactly one section_balance_override"
                    )
                overridden = selected_excluded[0]
                override = self.section_balance_override
                if overridden.experience_id != override.experience_id:
                    raise ValueError("section balance override must target selected excluded experience")
                if not overridden.experience_id.startswith("EXP-WORK-"):
                    raise ValueError("section balance override may select only WORK experience")
                if overridden.proposed_bullet_count > override.max_bullets:
                    raise ValueError("section balance override may allocate at most 2 bullets")
                if overridden.user_override_reason != override.reason:
                    raise ValueError("candidate override reason must match section balance override")
            elif self.section_balance_override:
                raise ValueError("section balance override requires a selected below-55 experience")

            available_work = [
                item for item in self.candidates if item.experience_id.startswith("EXP-WORK-")
            ]
            selected_work = [
                item for item in selected if item.experience_id.startswith("EXP-WORK-")
            ]
            if self.selection_approved and len(available_work) >= 2 and len(selected_work) < 2:
                raise ValueError("approved schema 1.2 selection requires at least two WORK experiences")

            personal_groups: dict[str, int] = {}
            for item in selected:
                if item.is_personal_development:
                    assert item.similarity_group is not None
                    personal_groups[item.similarity_group] = (
                        personal_groups.get(item.similarity_group, 0) + 1
                    )
            overfull_groups = {
                group: count for group, count in personal_groups.items() if count > 2
            }
            if overfull_groups:
                raise ValueError(
                    f"personal development similarity groups may select at most two: {overfull_groups}"
                )
        if self.schema_version == "1.5":
            if self.section_balance_override:
                raise ValueError("schema 1.5 forbids section-balance padding overrides")
            if self.selection_approved and not 1 <= len(selected) <= 4:
                raise ValueError("schema 1.5 requires 1-4 selected WORK/PROJECT experiences")
            if selected_excluded:
                override = self.page_fill_override
                if not override:
                    raise ValueError(
                        "schema 1.5 below-55 selection requires a page fill override"
                    )
                selected_excluded_ids = {item.experience_id for item in selected_excluded}
                if selected_excluded_ids != set(override.experience_ids):
                    raise ValueError(
                        "page fill override must list exactly the selected below-55 experiences"
                    )
                invalid_bullet_allocation = [
                    item.experience_id
                    for item in selected_excluded
                    if item.proposed_bullet_count < override.min_bullets_per_experience
                ]
                if invalid_bullet_allocation:
                    raise ValueError(
                        "page fill override experiences require at least two complementary bullets: "
                        f"{sorted(invalid_bullet_allocation)}"
                    )
                invalid_reason = [
                    item.experience_id
                    for item in selected_excluded
                    if item.user_override_reason != override.reason
                ]
                if invalid_reason:
                    raise ValueError(
                        "candidate override reason must match page fill override"
                    )
            elif self.page_fill_override:
                raise ValueError(
                    "page fill override requires selected below-55 experiences"
                )
            personal_groups: dict[str, int] = {}
            for item in selected:
                if item.is_personal_development:
                    assert item.similarity_group is not None
                    personal_groups[item.similarity_group] = (
                        personal_groups.get(item.similarity_group, 0) + 1
                    )
            overfull_groups = {
                group: count for group, count in personal_groups.items() if count > 2
            }
            if overfull_groups:
                raise ValueError(
                    "personal development similarity groups may select at most two: "
                    f"{overfull_groups}"
                )
        else:
            total_bullets = sum(item.proposed_bullet_count for item in selected)
            auxiliary_bullets = sum(
                item.proposed_bullet_count
                for item in selected
                if item.tier is ExperienceTier.AUXILIARY
            )
            if total_bullets and auxiliary_bullets / total_bullets > 0.25:
                raise ValueError("auxiliary experience bullets cannot exceed 25%")
        return self


class StoryEvidence(StrictModel):
    context_fact_ids: list[FactId] = Field(min_length=1)
    action_fact_ids: list[FactId] = Field(min_length=1)
    method_fact_ids: list[FactId] = Field(default_factory=list)
    challenge_fact_ids: list[FactId] = Field(default_factory=list)
    result_fact_ids: list[FactId] = Field(min_length=1)

    @model_validator(mode="after")
    def evidence_ids_must_be_unique(self) -> "StoryEvidence":
        for field_name in (
            "context_fact_ids",
            "action_fact_ids",
            "method_fact_ids",
            "challenge_fact_ids",
            "result_fact_ids",
        ):
            _ensure_unique(getattr(self, field_name), field_name)
        return self

    def all_fact_ids(self) -> set[str]:
        return {
            *self.context_fact_ids,
            *self.action_fact_ids,
            *self.method_fact_ids,
            *self.challenge_fact_ids,
            *self.result_fact_ids,
        }


class BulletIntent(StrictModel):
    intent_id: IntentId
    purpose: str = Field(min_length=1)
    required_fact_ids: list[FactId] = Field(min_length=1)

    @field_validator("required_fact_ids")
    @classmethod
    def fact_ids_must_be_unique(cls, value: list[str]) -> list[str]:
        return _ensure_unique(value, "required_fact_ids")


class OwnershipGuard(StrictModel):
    allowed_claims: list[str] = Field(min_length=1)
    prohibited_claims: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def claims_must_be_unique(self) -> "OwnershipGuard":
        _ensure_unique(self.allowed_claims, "allowed_claims")
        _ensure_unique(self.prohibited_claims, "prohibited_claims")
        return self


class StoryExperience(StrictModel):
    experience_id: ExperienceId
    story_thesis: str = Field(min_length=1)
    capability_ids: list[str] = Field(min_length=1)
    evidence: StoryEvidence
    bullet_intents: list[BulletIntent] = Field(min_length=1)
    ownership_guard: OwnershipGuard

    @model_validator(mode="after")
    def story_must_be_traceable_and_complementary(self) -> "StoryExperience":
        _ensure_unique(self.capability_ids, "capability_ids")
        _ensure_unique(
            [item.intent_id for item in self.bullet_intents],
            "bullet_intents.intent_id",
        )
        purposes = [re.sub(r"\s+", "", item.purpose).casefold() for item in self.bullet_intents]
        _ensure_unique(purposes, "bullet_intents.purpose")
        story_facts = self.evidence.all_fact_ids()
        unknown = {
            fact_id
            for item in self.bullet_intents
            for fact_id in item.required_fact_ids
            if fact_id not in story_facts
        }
        if unknown:
            raise ValueError(
                f"bullet intents cite facts outside story evidence: {sorted(unknown)}"
            )
        return self


class StoryPlanArtifact(ArtifactBase):
    experience_selection_sha256: Sha256
    experiences: list[StoryExperience] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def experiences_must_be_unique(self) -> "StoryPlanArtifact":
        _ensure_unique(
            [item.experience_id for item in self.experiences],
            "experiences.experience_id",
        )
        intent_ids = [
            intent.intent_id
            for experience in self.experiences
            for intent in experience.bullet_intents
        ]
        _ensure_unique(intent_ids, "experiences.bullet_intents.intent_id")
        return self


class SelectionApprovalArtifact(ArtifactBase):
    selection_approval_id: str = Field(
        pattern=r"^selection_approval_[a-f0-9]{32}$"
    )
    experience_selection_sha256: Sha256
    story_plan_sha256: Sha256
    approved_at: datetime
    source: Literal["explicit_user_message"] = "explicit_user_message"

    @field_validator("approved_at")
    @classmethod
    def approval_time_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approved_at must include a timezone")
        return value


class SelectionAuditRow(StrictModel):
    experience_id: ExperienceId
    verdict: SelectionAuditVerdict
    rationale: str = Field(min_length=1)


class SelectionAuditArtifact(ArtifactBase):
    phase: SelectionAuditPhase
    rows: list[SelectionAuditRow] = Field(min_length=1)
    passed: bool
    reselect_required: bool = False
    issue_codes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def rows_and_disposition_must_match(self) -> "SelectionAuditArtifact":
        _ensure_unique([item.experience_id for item in self.rows], "rows.experience_id")
        _ensure_unique(self.issue_codes, "issue_codes")
        reconsider = any(
            item.verdict is SelectionAuditVerdict.RECONSIDER for item in self.rows
        )
        if self.passed == reconsider:
            raise ValueError("selection audit passes only when no row requires reconsideration")
        if self.reselect_required and self.phase is not SelectionAuditPhase.POST_FUSION:
            raise ValueError("only post-fusion audit can require reselection")
        if self.reselect_required and self.passed:
            raise ValueError("reselection cannot be required by a passing audit")
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
    result_fact_sha256: Sha256 | None = None
    confirmation_status: ConfirmationStatus = ConfirmationStatus.PENDING
    questions: list[FactGapQuestion] = Field(default_factory=list, max_length=5)
    operations: list[FactDiffOperation] = Field(default_factory=list)

    @model_validator(mode="after")
    def root_status_must_match_operations(self) -> "FactDiffArtifact":
        if (
            self.confirmation_status is not ConfirmationStatus.APPROVED
            and self.result_fact_sha256 is not None
        ):
            raise ValueError("only an approved fact diff may record a result hash")
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
    intent_id: IntentId | None = None
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
EXPECTED_ABILITY_HEADINGS = ["专业硬技能", "综合软技能", "游戏经历", "语言能力"]
INDUSTRY_ABILITY_HEADINGS = ["专业硬技能", "综合软技能", "行业/平台经历", "语言能力"]
AI_PRODUCT_ABILITY_HEADINGS = ["专业硬技能", "综合软技能", "个人优势"]
LEGACY_ABILITY_HEADINGS = ["专业硬技能", "综合软技能", "游戏体验", "语言能力"]


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


def _validate_ability_entries(sections: list[ResumeSection], schema_version: str) -> None:
    abilities = next(
        section for section in sections if section.name is ResumeSectionName.ABILITIES
    )
    headings = [entry.heading for entry in abilities.entries]
    allowed = {tuple(EXPECTED_ABILITY_HEADINGS)}
    if schema_version in {"1.4", "1.5"}:
        allowed.add(tuple(INDUSTRY_ABILITY_HEADINGS))
    if schema_version == "1.5":
        allowed.add(tuple(AI_PRODUCT_ABILITY_HEADINGS))
    else:
        allowed.add(tuple(LEGACY_ABILITY_HEADINGS))
    if tuple(headings) not in allowed:
        raise ValueError(
            "self-ability entries do not match a heading set allowed by the artifact schema"
        )


class DraftArtifact(ArtifactBase):
    role_family: RoleFamily = RoleFamily.AI_PRODUCT_MANAGER
    role_track: RoleTrack | None = None
    agent: DraftAgent
    sections: list[ResumeSection] = Field(min_length=4, max_length=4)
    candidate_suggestions: list[CandidateSuggestion] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def schema_v14_requires_explicit_role_family(cls, value: Any) -> Any:
        if (
            isinstance(value, dict)
            and value.get("schema_version", SCHEMA_VERSION) in {"1.4", "1.5"}
            and "role_family" not in value
        ):
            raise ValueError("schema 1.4+ requires explicit role_family")
        return value

    @model_validator(mode="after")
    def draft_sections_must_be_complete(self) -> "DraftArtifact":
        validate_role_route(self.schema_version, self.role_family, self.role_track)
        _validate_sections(self.sections)
        if self.schema_version in {"1.2", "1.3", "1.4", "1.5"}:
            _validate_ability_entries(self.sections, self.schema_version)
        if self.schema_version == "1.5":
            for section in self.sections:
                for entry in section.entries:
                    if entry.experience_id.startswith(("EXP-WORK-", "EXP-PROJECT-")):
                        if any(bullet.intent_id is None for bullet in entry.bullets):
                            raise ValueError(
                                "schema 1.5 WORK/PROJECT bullets require intent_id"
                            )
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


class DraftQualityDimension(StrictModel):
    score: Annotated[float, Field(ge=0, le=10)]
    evidence: list[str] = Field(min_length=1)
    recommendations: list[str] = Field(default_factory=list)


class DraftExperienceQualityReview(StrictModel):
    experience_id: ExperienceId
    bullet_count: Annotated[int, Field(ge=1, le=14)]
    score: Annotated[float, Field(ge=0, le=10)]
    developed_elements: list[
        Literal[
            "context_or_object",
            "personal_action",
            "method_or_decision",
            "deliverable_or_complexity",
            "credible_result",
            "personal_boundary",
        ]
    ] = Field(min_length=1)
    result_status: DraftResultStatus
    result_rationale: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    defects: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
    passed: bool

    @model_validator(mode="after")
    def pass_must_match_basic_resume_quality(self) -> "DraftExperienceQualityReview":
        _ensure_unique(self.developed_elements, "developed_elements")
        _ensure_unique(self.evidence, "evidence")
        _ensure_unique(self.defects, "defects")
        _ensure_unique(self.revision_instructions, "revision_instructions")
        required_core = "personal_action" in self.developed_elements and any(
            item in self.developed_elements
            for item in ("method_or_decision", "deliverable_or_complexity")
        )
        supported_result_missing = (
            self.result_status is DraftResultStatus.MISSING_SUPPORTED_RESULT
        )
        meets_gate = self.score >= 8 and required_core and not supported_result_missing
        if self.passed:
            if not meets_gate:
                raise ValueError(
                    "passing experience review requires score >=8, personal action, "
                    "method/deliverable depth, and no omitted supported result"
                )
            if self.defects or self.revision_instructions:
                raise ValueError("passing experience review cannot request revision")
        elif meets_gate and not self.defects and not self.revision_instructions:
            raise ValueError("failed experience review requires a defect or revision")
        return self


class DraftLaneQualityReview(StrictModel):
    agent: DraftAgent
    draft_sha256: Sha256
    experience_development: DraftQualityDimension
    result_backing: DraftQualityDimension
    information_density: DraftQualityDimension
    scan_naturalness: DraftQualityDimension
    experience_reviews: list[DraftExperienceQualityReview] = Field(min_length=1)
    passed: bool

    @model_validator(mode="after")
    def pass_must_match_lane_quality(self) -> "DraftLaneQualityReview":
        _ensure_unique(
            [item.experience_id for item in self.experience_reviews],
            "experience_reviews.experience_id",
        )
        scores = (
            self.experience_development.score,
            self.result_backing.score,
            self.information_density.score,
            self.scan_naturalness.score,
        )
        meets_gate = all(score >= 8 for score in scores) and all(
            item.passed for item in self.experience_reviews
        )
        if self.passed != meets_gate:
            raise ValueError(
                "draft lane passes only when all dimensions and experiences reach 8"
            )
        return self


class DraftQualityAuditArtifact(ArtifactBase):
    revision_round: Annotated[int, Field(ge=0, le=2)]
    execution_mode: ExecutionMode
    lane_reviews: list[DraftLaneQualityReview] = Field(min_length=1, max_length=2)
    passed: bool

    @model_validator(mode="after")
    def lanes_and_disposition_must_match(self) -> "DraftQualityAuditArtifact":
        agents = [item.agent for item in self.lane_reviews]
        _ensure_unique(agents, "lane_reviews.agent")
        expected = (
            {DraftAgent.WRITER, DraftAgent.ASU_WRITER}
            if self.execution_mode is ExecutionMode.BLIND_DUAL
            else {DraftAgent.WRITER}
        )
        if set(agents) != expected:
            raise ValueError("draft quality audit lanes do not match execution mode")
        if self.passed != all(item.passed for item in self.lane_reviews):
            raise ValueError("draft quality audit passes only when every lane passes")
        return self


class FusionDecision(StrictModel):
    decision_id: str = Field(pattern=r"^DEC-[0-9]{3}$")
    action: FusionAction
    source_bullet_ids: list[BulletId] = Field(min_length=1)
    output_bullet_id: BulletId | None = None
    output_text: str | None = None
    fact_ids: list[FactId] = Field(default_factory=list)
    requirement_ids: list[RequirementId] = Field(default_factory=list)
    intent_id: IntentId | None = None
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def decision_shape_must_match_action(self) -> "FusionDecision":
        _ensure_unique(self.source_bullet_ids, "source_bullet_ids")
        _ensure_unique(self.fact_ids, "fact_ids")
        _ensure_unique(self.requirement_ids, "requirement_ids")
        if self.action is FusionAction.DROP:
            if self.output_bullet_id or self.output_text or self.fact_ids or self.intent_id:
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
        if self.schema_version in {"1.2", "1.3", "1.4", "1.5"}:
            _validate_ability_entries(self.sections, self.schema_version)
        if self.schema_version == "1.5":
            for section in self.sections:
                for entry in section.entries:
                    if entry.experience_id.startswith(("EXP-WORK-", "EXP-PROJECT-")):
                        if any(bullet.intent_id is None for bullet in entry.bullets):
                            raise ValueError(
                                "schema 1.5 WORK/PROJECT bullets require intent_id"
                            )
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
        if self.schema_version == "1.5":
            decision_intents = {
                item.output_bullet_id: item.intent_id
                for item in self.decisions
                if item.output_bullet_id is not None
            }
            mismatched = [
                bullet.bullet_id
                for section in self.sections
                for entry in section.entries
                for bullet in entry.bullets
                if decision_intents.get(bullet.bullet_id) != bullet.intent_id
            ]
            if mismatched:
                raise ValueError(
                    f"fusion decision intent IDs must match output bullets: {mismatched}"
                )
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


class ExperienceQualityGateResult(StrictModel):
    experience_id: ExperienceId
    bullet_count: Annotated[int, Field(ge=0)]
    intent_ids: list[IntentId] = Field(default_factory=list)
    covered_elements: list[
        Literal["context", "action", "method", "challenge", "result"]
    ] = Field(default_factory=list)
    max_source_similarity: Annotated[float, Field(ge=0, le=1)] = 0
    failure_codes: list[str] = Field(default_factory=list)
    passed: bool

    @model_validator(mode="after")
    def result_must_be_internally_consistent(self) -> "ExperienceQualityGateResult":
        _ensure_unique(self.intent_ids, "intent_ids")
        _ensure_unique(self.covered_elements, "covered_elements")
        _ensure_unique(self.failure_codes, "failure_codes")
        if self.passed == bool(self.failure_codes):
            raise ValueError("experience gate passes only when failure_codes is empty")
        return self


class DeterministicValidationArtifact(ArtifactBase):
    candidate_sha256: Sha256 | None = None
    story_plan_sha256: Sha256 | None = None
    passed: bool
    findings: list[AuditFinding] = Field(default_factory=list)
    hard_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    per_experience_results: list[ExperienceQualityGateResult] = Field(
        default_factory=list
    )
    metrics: ContentMetrics

    @model_validator(mode="after")
    def passed_must_match_hard_findings(self) -> "DeterministicValidationArtifact":
        hard_failures = any(item.severity is Severity.HARD for item in self.findings)
        if self.passed == hard_failures:
            raise ValueError("validation passed flag must be the inverse of hard findings")
        if self.schema_version == "1.5":
            if not self.candidate_sha256 or not self.story_plan_sha256:
                raise ValueError(
                    "schema 1.5 quality gate requires candidate and story-plan hashes"
                )
            expected_hard = [
                item.error_code
                for item in self.findings
                if item.severity is Severity.HARD
            ]
            expected_warnings = [
                item.error_code
                for item in self.findings
                if item.severity is Severity.WARNING
            ]
            if self.hard_failures != expected_hard:
                raise ValueError("hard_failures must match hard findings in order")
            if self.warnings != expected_warnings:
                raise ValueError("warnings must match warning findings in order")
            _ensure_unique(
                [item.experience_id for item in self.per_experience_results],
                "per_experience_results.experience_id",
            )
            if self.passed and not all(
                item.passed for item in self.per_experience_results
            ):
                raise ValueError(
                    "schema 1.5 quality gate requires every experience to pass"
                )
        return self


QualityGateArtifact = DeterministicValidationArtifact


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
    selection_quality: QualityDimension | None = None
    evidence_depth: QualityDimension
    hr_scan: QualityDimension
    language_naturalness: QualityDimension
    gap_disclosure_passed: bool = True
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
        if self.selection_quality is not None:
            scores.append(self.selection_quality.score)
        meets_threshold = all(score >= 8 for score in scores)
        if self.passed and not self.gap_disclosure_passed:
            raise ValueError("undisclosed material gaps cannot pass quality")
        if self.passed and not meets_threshold and not self.override_reason:
            raise ValueError("quality below 8 requires override_reason")
        if not self.passed and meets_threshold and self.gap_disclosure_passed:
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
    reselect_required: bool = False
    selection_issue_codes: list[str] = Field(default_factory=list)
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
        if self.schema_version in {"1.1", "1.2", "1.3", "1.4", "1.5"} and self.quality.selection_quality is None:
            raise ValueError("schema 1.1+ audit requires selection_quality")
        _ensure_unique(self.selection_issue_codes, "selection_issue_codes")
        if self.reselect_required and not self.selection_issue_codes:
            raise ValueError("reselection requires selection issue codes")
        fully_passed = (
            self.deterministic_passed
            and self.truth.passed
            and self.quality.passed
            and not self.reselect_required
        )
        if fully_passed and self.disposition is not AuditDisposition.PASSED:
            raise ValueError("all audit layers passed, so disposition must be passed")
        if not fully_passed and self.disposition is AuditDisposition.PASSED:
            raise ValueError("failed audit layers cannot produce a passed disposition")
        return self


class HrDecisionDimension(StrictModel):
    score: Annotated[float, Field(ge=0, le=10)]
    evidence: list[str] = Field(min_length=1)
    evidence_bullet_ids: list[BulletId] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    @field_validator("evidence_bullet_ids")
    @classmethod
    def evidence_bullet_ids_must_be_unique(cls, value: list[str]) -> list[str]:
        return _ensure_unique(value, "evidence_bullet_ids")


class HrUncitedFactAssessment(StrictModel):
    fact_id: FactId
    disposition: UncitedFactDisposition
    rationale: str = Field(min_length=1)


class HrExperienceReview(StrictModel):
    experience_id: ExperienceId
    ten_second_impression: str = Field(min_length=1)
    effective_requirement_ids: list[RequirementId] = Field(default_factory=list)
    evidence_bullet_ids: list[BulletId] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    defects: list[str] = Field(default_factory=list)
    omitted_fact_ids: list[FactId] = Field(default_factory=list)
    uncited_fact_assessments: list[HrUncitedFactAssessment] = Field(
        default_factory=list
    )
    severity_score: Annotated[float, Field(ge=0, le=10)]
    interview_impact: InterviewImpact
    recommended_bullet_count: Annotated[int, Field(ge=1)]
    revision_instructions: list[str] = Field(default_factory=list)
    missing_fact_questions: list[str] = Field(default_factory=list)

    @field_validator(
        "effective_requirement_ids",
        "evidence_bullet_ids",
        "strengths",
        "defects",
        "omitted_fact_ids",
        "revision_instructions",
        "missing_fact_questions",
    )
    @classmethod
    def review_lists_must_be_unique(
        cls, value: list[str], info: Any
    ) -> list[str]:
        return _ensure_unique(value, info.field_name)

    @model_validator(mode="after")
    def uncited_assessments_must_match_high_value_omissions(
        self,
    ) -> "HrExperienceReview":
        assessed_ids = [item.fact_id for item in self.uncited_fact_assessments]
        _ensure_unique(assessed_ids, "uncited_fact_assessments.fact_id")
        should_include = {
            item.fact_id
            for item in self.uncited_fact_assessments
            if item.disposition is UncitedFactDisposition.SHOULD_INCLUDE
        }
        if set(self.omitted_fact_ids) != should_include:
            raise ValueError(
                "omitted_fact_ids must exactly match uncited facts judged should_include"
            )
        return self


class HrReviewArtifact(ArtifactBase):
    revision_round: Annotated[int, Field(ge=0, le=2)]
    recommendation: HrRecommendation
    overall_score: Annotated[float, Field(ge=0, le=10)]
    role_fit: HrDecisionDimension
    narrative_completeness: HrDecisionDimension
    evidence_specificity: HrDecisionDimension
    decision_readiness: HrDecisionDimension
    credibility: HrDecisionDimension
    content_fullness: HrDecisionDimension | None = None
    experience_reviews: list[HrExperienceReview] = Field(min_length=1)
    issue_codes: list[str] = Field(default_factory=list)
    existing_fact_revision_sufficient: bool
    fact_questions_required: bool
    reselect_required: bool
    passed: bool
    disposition: HrReviewDisposition

    @model_validator(mode="after")
    def high_standard_gate_must_be_consistent(self) -> "HrReviewArtifact":
        _ensure_unique(self.issue_codes, "issue_codes")
        review_ids = [item.experience_id for item in self.experience_reviews]
        _ensure_unique(review_ids, "experience_reviews.experience_id")
        scores = [
            self.role_fit.score,
            self.narrative_completeness.score,
            self.evidence_specificity.score,
            self.decision_readiness.score,
            self.credibility.score,
        ]
        if self.schema_version == "1.5":
            if self.content_fullness is None:
                raise ValueError("schema 1.5 HR review requires content_fullness")
            scores.append(self.content_fullness.score)
            meets_high_standard = (
                self.recommendation is HrRecommendation.STRONG_PUSH
                and self.overall_score >= 9.0
                and all(score >= 8.0 for score in scores)
                and all(
                    dimension.evidence_bullet_ids
                    for dimension in (
                        self.role_fit,
                        self.narrative_completeness,
                        self.evidence_specificity,
                        self.decision_readiness,
                        self.credibility,
                        self.content_fullness,
                    )
                )
                and all(
                    item.evidence_bullet_ids
                    for item in self.experience_reviews
                )
            )
        else:
            if self.content_fullness is not None:
                raise ValueError("content_fullness is available only in schema 1.5")
            meets_high_standard = (
                self.recommendation is HrRecommendation.STRONG_PUSH
                and self.overall_score >= 8.5
                and all(score >= 8.5 for score in scores)
            )
        if self.passed != meets_high_standard:
            raise ValueError(
                "HR pass requires strong_push and the schema-version score/evidence gate"
            )
        has_questions = any(
            item.missing_fact_questions for item in self.experience_reviews
        )
        if self.fact_questions_required != has_questions:
            raise ValueError(
                "fact_questions_required must match per-experience missing questions"
            )
        remediation_routes = (
            self.existing_fact_revision_sufficient,
            self.fact_questions_required,
            self.reselect_required,
        )
        if sum(bool(item) for item in remediation_routes) > 1:
            raise ValueError("HR remediation routes must be mutually exclusive")
        if self.passed:
            if self.disposition is not HrReviewDisposition.PASSED:
                raise ValueError("passing HR review requires passed disposition")
            if any(
                (
                    self.issue_codes,
                    self.existing_fact_revision_sufficient,
                    self.fact_questions_required,
                    self.reselect_required,
                )
            ):
                raise ValueError("passing HR review cannot request remediation")
            if any(
                item.defects
                or item.omitted_fact_ids
                or item.revision_instructions
                or item.missing_fact_questions
                or item.severity_score != 0
                or item.interview_impact is not InterviewImpact.NONE
                for item in self.experience_reviews
            ):
                raise ValueError(
                    "passing HR review cannot contain per-experience remediation"
                )
            return self
        if not self.issue_codes:
            raise ValueError("failed HR review requires issue_codes")
        if not any(
            item.defects
            or item.omitted_fact_ids
            or item.revision_instructions
            or item.missing_fact_questions
            or item.interview_impact is not InterviewImpact.NONE
            for item in self.experience_reviews
        ):
            raise ValueError("failed HR review requires a per-experience issue")
        if self.existing_fact_revision_sufficient and not any(
            item.revision_instructions for item in self.experience_reviews
        ):
            raise ValueError(
                "existing-fact revision route requires revision instructions"
            )
        if self.reselect_required:
            expected = HrReviewDisposition.RESELECT
        elif self.fact_questions_required:
            expected = HrReviewDisposition.NEEDS_INPUT
        elif self.existing_fact_revision_sufficient and self.revision_round < 2:
            expected = HrReviewDisposition.REVISE
        else:
            expected = HrReviewDisposition.NEEDS_REVIEW
        if self.disposition is not expected:
            raise ValueError(
                f"failed HR review requires {expected.value} disposition"
            )
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


class AgentInvocationReceipt(StrictModel):
    stage: AgentStage
    role: AgentRole
    invocation_id: str = Field(min_length=1, max_length=200)
    model: str = Field(min_length=1, max_length=100)
    reasoning_effort: str = Field(min_length=1, max_length=40)
    prompt_sha256: Sha256
    input_sha256: Sha256
    output_sha256: Sha256
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def receipt_time_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return value


class AgentReceiptBundleArtifact(ArtifactBase):
    receipts: list[AgentInvocationReceipt] = Field(min_length=1)

    @model_validator(mode="after")
    def invocation_ids_must_be_unique(self) -> "AgentReceiptBundleArtifact":
        _ensure_unique(
            [item.invocation_id for item in self.receipts],
            "receipts.invocation_id",
        )
        return self


class ReferenceSource(StrictModel):
    title: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://[^\s]+$")
    retrieved_at: datetime
    source_type: ReferenceSourceType = ReferenceSourceType.OPEN_SOURCE_METHOD
    qualified: bool = False

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
    selection_rules: list[str] = Field(default_factory=list)
    qualified: bool = False
    degradation_approved_at: datetime | None = None
    degradation_approval_reason: str | None = None
    error: str | None = None

    @model_validator(mode="after")
    def research_mode_must_match_evidence(self) -> "ReferenceResearchArtifact":
        _ensure_unique(self.missing_topics, "missing_topics")
        _ensure_unique([item.url for item in self.sources], "sources.url")
        _ensure_unique(self.selection_rules, "selection_rules")
        if self.schema_version == "1.0":
            if self.mode is ReferenceResearchMode.LOCAL:
                if self.sources or self.sanitized_method_cards or self.error:
                    raise ValueError("local reference mode cannot contain network results")
            elif self.mode is ReferenceResearchMode.SUPPLEMENTED:
                if not self.sources or not self.sanitized_method_cards or self.error:
                    raise ValueError("supplemented mode requires sources and sanitized cards")
            elif not self.error:
                raise ValueError("degraded reference mode requires an error")
            return self
        source_types = {item.source_type for item in self.sources if item.qualified}
        has_required_sources = {
            ReferenceSourceType.RESUME_SAMPLE,
            ReferenceSourceType.OFFICIAL_ROLE,
        }.issubset(source_types)
        if self.qualified != (has_required_sources and bool(self.selection_rules)):
            raise ValueError(
                "qualified research requires a qualified resume sample, official role source, and selection rules"
            )
        if self.mode is ReferenceResearchMode.SUPPLEMENTED and not self.qualified:
            raise ValueError("supplemented research must be qualified")
        if self.mode is ReferenceResearchMode.DEGRADED and (self.qualified or not self.error):
            raise ValueError("degraded research requires an error and cannot be qualified")
        if self.mode is ReferenceResearchMode.LOCAL and self.qualified:
            raise ValueError("local method cards alone cannot qualify reference research")
        if (self.degradation_approved_at is None) != (
            self.degradation_approval_reason is None
        ):
            raise ValueError("degradation approval time and reason must be set together")
        if self.degradation_approved_at:
            if self.mode is not ReferenceResearchMode.DEGRADED:
                raise ValueError("only degraded research can receive user approval")
            if (
                self.degradation_approved_at.tzinfo is None
                or self.degradation_approved_at.utcoffset() is None
            ):
                raise ValueError("degradation_approved_at must include a timezone")
        return self


class SelectionRevisionRecord(StrictModel):
    round: Annotated[int, Field(ge=1, le=2)]
    prior_selected_experience_ids: list[ExperienceId] = Field(min_length=1)
    issue_codes: list[str] = Field(min_length=1)
    requested_at: datetime

    @model_validator(mode="after")
    def revision_record_must_be_valid(self) -> "SelectionRevisionRecord":
        _ensure_unique(
            self.prior_selected_experience_ids,
            "prior_selected_experience_ids",
        )
        _ensure_unique(self.issue_codes, "issue_codes")
        if self.requested_at.tzinfo is None or self.requested_at.utcoffset() is None:
            raise ValueError("requested_at must include a timezone")
        return self


class RunCheckpointArtifact(ArtifactBase):
    state: ContentState
    execution_mode: ExecutionMode = ExecutionMode.BLIND_DUAL
    input_packet: NormalizedInputPacket
    reference_research: ReferenceResearchArtifact
    jd_analysis: JDAnalysisArtifact
    evidence_map: EvidenceMapArtifact
    fact_diff: FactDiffArtifact
    capability_transfer_map: CapabilityTransferMapArtifact | None = None
    experience_selection: ExperienceSelectionArtifact | None = None
    selection_audit: SelectionAuditArtifact | None = None
    story_plan: StoryPlanArtifact | None = None
    selection_revisions: list[SelectionRevisionRecord] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def checkpoint_must_be_consistent(self) -> "RunCheckpointArtifact":
        allowed = {
            ContentState.ANALYZING,
            ContentState.NEEDS_INPUT,
            ContentState.AWAITING_REFERENCE_APPROVAL,
            ContentState.AWAITING_SELECTION_APPROVAL,
            ContentState.DRAFTING,
        }
        if self.state not in allowed:
            raise ValueError(f"unsupported checkpoint state: {self.state.value}")
        artifacts = [
            self.input_packet,
            self.reference_research,
            self.jd_analysis,
            self.evidence_map,
            self.fact_diff,
        ]
        artifacts.extend(
            item
            for item in (
                self.capability_transfer_map,
                self.experience_selection,
                self.selection_audit,
                self.story_plan,
            )
            if item is not None
        )
        if any(item.run_id != self.run_id for item in artifacts):
            raise ValueError("checkpoint artifacts must share run_id")
        if any(item.source_digests != self.source_digests for item in artifacts):
            raise ValueError("checkpoint artifacts must share source_digests")
        if self.jd_analysis.role_family is not self.input_packet.role_family:
            raise ValueError("checkpoint role families must match")
        rounds = [item.round for item in self.selection_revisions]
        if rounds != list(range(1, len(rounds) + 1)):
            raise ValueError("selection revision rounds must be sequential")
        approved = self.state is ContentState.DRAFTING
        if self.schema_version == "1.0":
            if self.evidence_map.selection_approved is not approved:
                raise ValueError(
                    "drafting checkpoint requires approved selection; gate checkpoints forbid it"
                )
            if approved != bool(self.input_packet.approved_requirement_ids):
                raise ValueError(
                    "drafting checkpoint requires approved requirement IDs only after selection"
                )
            if not approved and self.input_packet.approved_fact_ids:
                raise ValueError("gate checkpoints cannot contain approved fact IDs")
            return self
        if self.evidence_map.selection_approved:
            raise ValueError("schema 1.1/1.2 selects experiences outside evidence-map.json")
        if self.schema_version in {"1.2", "1.3", "1.4", "1.5"} and approved and not self.capability_transfer_map:
            raise ValueError("schema 1.2+ drafting requires capability transfer map")
        if approved:
            if not self.experience_selection or not self.experience_selection.selection_approved:
                raise ValueError("drafting requires approved experience selection")
            if not self.selection_audit or not self.selection_audit.passed:
                raise ValueError("drafting requires a passing pre-draft selection audit")
            if not self.input_packet.approved_experience_ids:
                raise ValueError("drafting requires approved experience IDs")
            if self.schema_version == "1.5" and not self.story_plan:
                raise ValueError("schema 1.5 drafting requires an approved story plan")
        elif any(
            (
                self.input_packet.approved_requirement_ids,
                self.input_packet.approved_fact_ids,
                self.input_packet.approved_experience_ids,
                self.input_packet.approved_transfer_ids,
            )
        ):
            raise ValueError("gate checkpoints cannot contain approved identifiers")
        return self


class RunManifestArtifact(ArtifactBase):
    state: ContentState
    execution_mode: ExecutionMode = ExecutionMode.BLIND_DUAL
    input_packet: NormalizedInputPacket
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    revision_count: Annotated[int, Field(ge=0, le=2)] = 0
    selection_revision_count: Annotated[int, Field(ge=0, le=2)] = 0
    selection_revisions: list[SelectionRevisionRecord] = Field(default_factory=list, max_length=2)
    producer: Literal["official_coordinator"] | None = None
    error: RunError | None = None

    @model_validator(mode="before")
    @classmethod
    def inherit_legacy_schema_from_input_packet(cls, value: Any) -> Any:
        """Keep old callers read-compatible when run.json omitted schema_version."""
        if not isinstance(value, dict) or "schema_version" in value:
            return value
        packet = value.get("input_packet")
        packet_schema = (
            packet.schema_version
            if isinstance(packet, NormalizedInputPacket)
            else packet.get("schema_version")
            if isinstance(packet, dict)
            else None
        )
        if packet_schema:
            return {**value, "schema_version": packet_schema}
        return value

    @model_validator(mode="after")
    def manifest_must_be_consistent(self) -> "RunManifestArtifact":
        if self.input_packet.run_id != self.run_id:
            raise ValueError("input_packet.run_id must match run_id")
        if self.input_packet.source_digests != self.source_digests:
            raise ValueError("input_packet.source_digests must match source_digests")
        _ensure_unique([item.name for item in self.artifacts], "artifacts.name")
        _ensure_unique([item.relative_path for item in self.artifacts], "artifacts.relative_path")
        if self.selection_revision_count != len(self.selection_revisions):
            raise ValueError("selection revision count must match records")
        if (self.state is ContentState.FAILED) != (self.error is not None):
            raise ValueError("failed state and error must be set together")
        if self.schema_version == "1.5" and self.producer != "official_coordinator":
            raise ValueError("schema 1.5 runs require the official coordinator producer")
        return self


class ReferencedFactDigest(StrictModel):
    fact_id: FactId
    value_sha256: Sha256


class UserApprovalRecord(StrictModel):
    schema_version: Literal["1.5"] = "1.5"
    user_approval_id: str = Field(pattern=r"^user_approval_[a-f0-9]{32}$")
    run_id: RunId
    content_sha256: Sha256
    approved_at: datetime
    source: Literal["explicit_user_message"] = "explicit_user_message"

    @field_validator("approved_at")
    @classmethod
    def approval_time_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approved_at must include a timezone")
        return value


class RunStatusRecord(StrictModel):
    schema_version: Literal["1.5"] = "1.5"
    run_id: RunId
    content_sha256: Sha256 | None = None
    status: RunStatus
    reason_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def status_time_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recorded_at must include a timezone")
        return value


class CurrentPointer(StrictModel):
    schema_version: Literal["1.0", "1.1", "1.2", "1.3", "1.4", "1.5"] = SCHEMA_VERSION
    status: ContentState
    approved_run_id: RunId | None = None
    run_relative_path: str | None = Field(
        default=None,
        pattern=r"^resume-content[\\/]runs[\\/]cr_[0-9]{8}T[0-9]{6}_[a-z0-9]{6}$",
    )
    approved_at: datetime | None = None
    updated_at: datetime
    transaction_id: str = Field(pattern=r"^approval_[a-f0-9]{32}$")
    referenced_facts: list[ReferencedFactDigest] = Field(default_factory=list)
    user_approval_id: str | None = Field(
        default=None, pattern=r"^user_approval_[a-f0-9]{32}$"
    )
    content_sha256: Sha256 | None = None

    @model_validator(mode="before")
    @classmethod
    def missing_schema_version_is_legacy(cls, value: Any) -> Any:
        if isinstance(value, dict) and "schema_version" not in value:
            value = {**value, "schema_version": "1.4"}
        return value

    @model_validator(mode="after")
    def pointer_must_be_consistent(self) -> "CurrentPointer":
        if self.status is ContentState.NO_APPROVED_CONTENT:
            if any(
                (
                    self.approved_run_id,
                    self.run_relative_path,
                    self.approved_at,
                    self.referenced_facts,
                    self.user_approval_id,
                    self.content_sha256,
                )
            ):
                raise ValueError("no_approved_content pointer cannot reference a run")
        else:
            if self.status not in {ContentState.APPROVED, ContentState.STALE}:
                raise ValueError(
                    "current pointer status must be approved, stale, or no_approved_content"
                )
            if not all(
                (
                    self.approved_run_id,
                    self.run_relative_path,
                    self.approved_at,
                    self.referenced_facts,
                )
            ):
                raise ValueError("approved/stale pointer requires run and fact references")
            if self.schema_version == "1.5" and not all(
                (self.user_approval_id, self.content_sha256)
            ):
                raise ValueError(
                    "schema 1.5 pointer requires user_approval_id and content_sha256"
                )
            expected_suffix = f"runs/{self.approved_run_id}"
            normalized_path = self.run_relative_path.replace("\\", "/")
            if not normalized_path.endswith(expected_suffix):
                raise ValueError("run_relative_path must reference approved_run_id")
        for field_name in ("approved_at", "updated_at"):
            value = getattr(self, field_name)
            if value is not None and (
                value.tzinfo is None or value.utcoffset() is None
            ):
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
    approved_run_id: RunId | None = None
    updated_at: datetime
    transaction_id: str = Field(pattern=r"^approval_[a-f0-9]{32}$")

    @model_validator(mode="after")
    def summary_must_reference_approved_content(self) -> "ResumeContentSummary":
        if self.status not in {
            ContentState.APPROVED,
            ContentState.STALE,
            ContentState.NO_APPROVED_CONTENT,
        }:
            raise ValueError(
                "resume content summary status must be approved, stale, or no_approved_content"
            )
        if self.status is ContentState.NO_APPROVED_CONTENT and self.approved_run_id:
            raise ValueError("no_approved_content summary cannot reference a run")
        if self.status is not ContentState.NO_APPROVED_CONTENT and not self.approved_run_id:
            raise ValueError("approved/stale summary requires approved_run_id")
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise ValueError("updated_at must include a timezone")
        return self


ALLOWED_TRANSITIONS: dict[ContentState, frozenset[ContentState]] = {
    ContentState.NOT_STARTED: frozenset({ContentState.ANALYZING, ContentState.FAILED}),
    ContentState.ANALYZING: frozenset(
        {
            ContentState.NEEDS_INPUT,
            ContentState.AWAITING_REFERENCE_APPROVAL,
            ContentState.AWAITING_SELECTION_APPROVAL,
            ContentState.FAILED,
        }
    ),
    ContentState.NEEDS_INPUT: frozenset(
        {
            ContentState.ANALYZING,
            ContentState.AWAITING_REFERENCE_APPROVAL,
            ContentState.AWAITING_SELECTION_APPROVAL,
            ContentState.FAILED,
        }
    ),
    ContentState.AWAITING_REFERENCE_APPROVAL: frozenset(
        {
            ContentState.ANALYZING,
            ContentState.AWAITING_SELECTION_APPROVAL,
            ContentState.FAILED,
        }
    ),
    ContentState.AWAITING_SELECTION_APPROVAL: frozenset(
        {ContentState.DRAFTING, ContentState.FAILED}
    ),
    ContentState.DRAFTING: frozenset(
        {ContentState.AUDITING, ContentState.FAILED, ContentState.QUALITY_FAILED}
    ),
    ContentState.AUDITING: frozenset(
        {
            ContentState.AWAITING_SELECTION_APPROVAL,
            ContentState.HR_REVIEWING,
            ContentState.NEEDS_CONTENT_REVIEW,
            ContentState.APPROVED,
            ContentState.FAILED,
            ContentState.QUALITY_FAILED,
        }
    ),
    ContentState.HR_REVIEWING: frozenset(
        {
            ContentState.AUDITING,
            ContentState.NEEDS_INPUT,
            ContentState.AWAITING_SELECTION_APPROVAL,
            ContentState.NEEDS_CONTENT_REVIEW,
            ContentState.READY_FOR_USER_REVIEW,
            ContentState.FAILED,
            ContentState.QUALITY_FAILED,
        }
    ),
    ContentState.NEEDS_CONTENT_REVIEW: frozenset(
        {
            ContentState.AUDITING,
            ContentState.APPROVED,
            ContentState.FAILED,
            ContentState.QUALITY_FAILED,
        }
    ),
    ContentState.READY_FOR_USER_REVIEW: frozenset(
        {
            ContentState.APPROVED,
            ContentState.FAILED,
        }
    ),
    ContentState.APPROVED: frozenset({ContentState.STALE}),
    ContentState.FAILED: frozenset(),
    ContentState.QUALITY_FAILED: frozenset(),
    ContentState.STALE: frozenset(),
    ContentState.NO_APPROVED_CONTENT: frozenset(),
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
    "capability-transfer-map": CapabilityTransferMapArtifact,
    "experience-selection": ExperienceSelectionArtifact,
    "story-plan": StoryPlanArtifact,
    "selection-approval": SelectionApprovalArtifact,
    "selection-audit": SelectionAuditArtifact,
    "fact-diff": FactDiffArtifact,
    "draft": DraftArtifact,
    "draft-quality-audit": DraftQualityAuditArtifact,
    "fusion": FusionArtifact,
    "audit": AuditArtifact,
    "hr-review": HrReviewArtifact,
    "current": CurrentPointer,
    "agent-failure": AgentFailureArtifact,
    "agent-receipts": AgentReceiptBundleArtifact,
    "validation": DeterministicValidationArtifact,
    "quality-gate": QualityGateArtifact,
    "reference-research": ReferenceResearchArtifact,
    "run-checkpoint": RunCheckpointArtifact,
    "user-approval": UserApprovalRecord,
    "run-status": RunStatusRecord,
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
