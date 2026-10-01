from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from fact_library import parse_fact_records
from models import (
    ARTIFACT_MODELS,
    AgentInvocationReceipt,
    AgentReceiptBundleArtifact,
    AgentRole,
    AgentStage,
    AuditArtifact,
    AuditDisposition,
    ContentState,
    DraftArtifact,
    DraftQualityAuditArtifact,
    ExperienceSelectionArtifact,
    FusionArtifact,
    HrReviewArtifact,
    JDAnalysisArtifact,
    NormalizedInputPacket,
    ReferenceResearchArtifact,
    RoleFamily,
    RoleTrack,
    RunManifestArtifact,
    RunStatus,
    RunStatusRecord,
    SelectionApprovalArtifact,
    SelectionAuditArtifact,
    SourceType,
    StoryPlanArtifact,
    UserApprovalRecord,
)
from orchestrator import normalize_run_input
from rendering import render_resume_markdown
from storage import (
    StorageError,
    append_run_status,
    approve_run,
    begin_run,
    canonical_json_sha256,
    latest_run_status,
    load_run,
    read_run_statuses,
    revoke_run,
    sha256_bytes,
    validate_v15_approval_evidence,
    validate_pointer_consistency,
)
from validators import (
    selection_decision_sha256,
    validate_draft_content,
    validate_fusion_content,
    validate_run_artifact_completeness,
)


class CliError(RuntimeError):
    pass


RECORD_MODELS: dict[str, type[BaseModel]] = {
    "reference-research.json": ReferenceResearchArtifact,
    "jd-analysis.json": JDAnalysisArtifact,
    "evidence-map.json": ARTIFACT_MODELS["evidence-map"],
    "fact-diff.json": ARTIFACT_MODELS["fact-diff"],
    "capability-transfer-map.json": ARTIFACT_MODELS["capability-transfer-map"],
    "experience-selection.json": ExperienceSelectionArtifact,
    "selection-audit-pre.json": SelectionAuditArtifact,
    "selection-user-approval.json": SelectionApprovalArtifact,
    "story-plan.json": StoryPlanArtifact,
    "draft-writer.json": DraftArtifact,
    "draft-asu.json": DraftArtifact,
    "draft-quality-audit.json": DraftQualityAuditArtifact,
    "fusion.json": FusionArtifact,
    "audit.json": AuditArtifact,
    "hr-review.json": HrReviewArtifact,
}

RECEIPT_STAGE_BY_ARTIFACT = {
    "jd-analysis.json": AgentStage.JD_ANALYSIS,
    "capability-transfer-map.json": AgentStage.CAPABILITY_TRANSFER,
    "experience-selection.json": AgentStage.EXPERIENCE_SELECTION,
    "selection-audit-pre.json": AgentStage.SELECTION_AUDIT,
    "story-plan.json": AgentStage.STORY_PLAN,
    "draft-writer.json": AgentStage.WRITER,
    "draft-asu.json": AgentStage.ASU_WRITER,
    "draft-quality-audit.json": AgentStage.DRAFT_AUDIT,
    "fusion.json": AgentStage.FUSION,
    "audit.json": AgentStage.POST_FUSION_AUDIT,
    "hr-review.json": AgentStage.HR_REVIEW,
}

RECEIPT_ROLE_BY_STAGE = {
    AgentStage.JD_ANALYSIS: AgentRole.COORDINATOR,
    AgentStage.CAPABILITY_TRANSFER: AgentRole.COORDINATOR,
    AgentStage.EXPERIENCE_SELECTION: AgentRole.COORDINATOR,
    AgentStage.SELECTION_AUDIT: AgentRole.AUDITOR,
    AgentStage.STORY_PLAN: AgentRole.WRITER,
    AgentStage.WRITER: AgentRole.WRITER,
    AgentStage.ASU_WRITER: AgentRole.ASU_WRITER,
    AgentStage.DRAFT_AUDIT: AgentRole.AUDITOR,
    AgentStage.FUSION: AgentRole.COORDINATOR,
    AgentStage.POST_FUSION_AUDIT: AgentRole.AUDITOR,
    AgentStage.HR_REVIEW: AgentRole.HR_REVIEWER,
}

COMMIT_ARTIFACTS = (
    "input-packet.json",
    "fact-snapshot.md",
    "reference-research.json",
    "jd-analysis.json",
    "evidence-map.json",
    "fact-diff.json",
    "capability-transfer-map.json",
    "experience-selection.json",
    "selection-audit-pre.json",
    "selection-user-approval.json",
    "story-plan.json",
    "draft-writer.json",
    "draft-asu.json",
    "draft-quality-audit.json",
    "fusion.json",
    "validation.json",
    "quality-gate.json",
    "audit.json",
    "hr-review.json",
    "agent-receipts.json",
)

FACT_CONFLICT_CODES = frozenset(
    {
        "UNKNOWN_EXPERIENCE_ID",
        "UNKNOWN_FACT_ID",
        "CROSS_EXPERIENCE_FACT",
        "UNCONFIRMED_FACT_PROVENANCE",
        "UNSUPPORTED_NUMERIC_CLAIM",
    }
)


def _quality_failure_target(hard_failures: list[str]) -> str:
    return (
        "needs_input"
        if FACT_CONFLICT_CODES.intersection(hard_failures)
        else "fusion"
    )


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CliError(f"cannot read JSON object: {path}") from error
    if not isinstance(value, dict):
        raise CliError(f"JSON must be an object: {path}")
    return value


def _write_json_once(path: Path, value: BaseModel | dict[str, Any]) -> None:
    if path.exists():
        raise CliError(f"official artifact already exists: {path.name}")
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )


def _write_bytes_once(path: Path, value: bytes) -> None:
    if path.exists():
        raise CliError(f"official artifact already exists: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def _replace_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="",
    )
    temporary.replace(path)


def _official_dir(application_dir: Path, run_id: str) -> Path:
    return application_dir.resolve() / "resume-content" / ".official" / run_id


def _control(official_dir: Path) -> dict[str, Any]:
    return _read_object(official_dir / "control.json")


def _same_envelope(packet: NormalizedInputPacket, artifact: BaseModel) -> None:
    if getattr(artifact, "schema_version", None) != "1.5":
        raise CliError("official CLI accepts only schema 1.5 artifacts")
    if getattr(artifact, "run_id", None) != packet.run_id:
        raise CliError("artifact run_id does not match the official run")
    if getattr(artifact, "source_digests", None) != packet.source_digests:
        raise CliError("artifact source digests do not match the official run")


def _load_packet(official_dir: Path) -> NormalizedInputPacket:
    return NormalizedInputPacket.model_validate(
        _read_object(official_dir / "input-packet.json")
    )


def _load_frozen_fact_records(
    official_dir: Path, packet: NormalizedInputPacket
) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot_path = official_dir / "fact-snapshot.md"
    try:
        snapshot_bytes = snapshot_path.read_bytes()
    except OSError as error:
        raise CliError("official run is missing its frozen fact snapshot") from error
    if sha256_bytes(snapshot_bytes) != packet.source_digests.fact_snapshot_sha256:
        raise CliError("frozen fact snapshot hash does not match the official run")
    try:
        snapshot_text = snapshot_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CliError("frozen fact snapshot is not valid UTF-8") from error
    return parse_fact_records(snapshot_text)


def _load_receipts(official_dir: Path) -> list[AgentInvocationReceipt]:
    path = official_dir / "receipts.json"
    if not path.exists():
        return []
    payload = _read_object(path)
    return [AgentInvocationReceipt.model_validate(item) for item in payload["receipts"]]


def _save_receipts(
    official_dir: Path, receipts: list[AgentInvocationReceipt]
) -> None:
    _replace_json(
        official_dir / "receipts.json",
        {"receipts": [item.model_dump(mode="json") for item in receipts]},
    )


def command_start(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = args.repo_root.resolve()
    normalized = normalize_run_input(
        repo_root,
        source_type=SourceType.DIRECTORY,
        source_locator=str(args.application_dir),
        application_dir=args.application_dir,
        role_family=RoleFamily(args.role_family),
        role_track=RoleTrack(args.role_track) if args.role_track else None,
        schema_version="1.5",
    )
    official_dir = _official_dir(normalized.application_dir, normalized.packet.run_id)
    if official_dir.exists():
        raise CliError(f"official run already exists: {normalized.packet.run_id}")
    fact_snapshot = (
        repo_root / "profile" / "01-candidate-profile.md"
    ).read_bytes()
    if (
        sha256_bytes(fact_snapshot)
        != normalized.packet.source_digests.fact_snapshot_sha256
    ):
        raise CliError("fact library changed while the run was being initialized")
    _write_json_once(official_dir / "input-packet.json", normalized.packet)
    _write_bytes_once(official_dir / "fact-snapshot.md", fact_snapshot)
    _write_json_once(
        official_dir / "control.json",
        {
            "schema_version": "1.5",
            "run_id": normalized.packet.run_id,
            "state": ContentState.ANALYZING.value,
            "generation_round": 0,
            "rewrite_target": None,
            "issue_codes": [],
            "application_dir": str(normalized.application_dir),
            "created_at": normalized.packet.created_at.isoformat(),
        },
    )
    return {
        "run_id": normalized.packet.run_id,
        "state": ContentState.ANALYZING.value,
        "official_dir": str(official_dir),
    }


def command_record(args: argparse.Namespace) -> dict[str, Any]:
    application_dir = args.application_dir.resolve()
    official_dir = _official_dir(application_dir, args.run_id)
    packet = _load_packet(official_dir)
    model = RECORD_MODELS.get(args.artifact_name)
    if model is None:
        raise CliError(f"unsupported official artifact: {args.artifact_name}")
    artifact_payload = _read_object(args.artifact)
    artifact = model.model_validate(artifact_payload)
    _same_envelope(packet, artifact)
    if isinstance(artifact, SelectionApprovalArtifact):
        selection_path = official_dir / "experience-selection.json"
        audit_path = official_dir / "selection-audit-pre.json"
        story_path = official_dir / "story-plan.json"
        if not all(path.is_file() for path in (selection_path, audit_path, story_path)):
            raise CliError(
                "selection approval requires selection, passing pre-audit, and story plan"
            )
        selection = ExperienceSelectionArtifact.model_validate(
            _read_object(selection_path)
        )
        selection_audit = SelectionAuditArtifact.model_validate(
            _read_object(audit_path)
        )
        story_plan = StoryPlanArtifact.model_validate(_read_object(story_path))
        if not selection.selection_approved or not selection_audit.passed:
            raise CliError("selection approval requires approved selection and passing audit")
        if artifact.experience_selection_sha256 != selection_decision_sha256(
            selection
        ):
            raise CliError("selection approval does not match the current selection")
        if story_plan.experience_selection_sha256 != artifact.experience_selection_sha256:
            raise CliError("story plan does not match the user-approved selection")
        if artifact.story_plan_sha256 != canonical_json_sha256(
            story_plan.model_dump(mode="json")
        ):
            raise CliError("selection approval does not match the current story plan")
    expected_stage = RECEIPT_STAGE_BY_ARTIFACT.get(args.artifact_name)
    if expected_stage is not None:
        if not args.receipt or not args.prompt_file or not args.input_file:
            raise CliError(
                "agent artifacts require --receipt, --prompt-file, and --input-file"
            )
        receipt = AgentInvocationReceipt.model_validate(_read_object(args.receipt))
        if receipt.stage is not expected_stage:
            raise CliError("receipt stage does not match artifact")
        if receipt.role is not RECEIPT_ROLE_BY_STAGE[expected_stage]:
            raise CliError("receipt role does not match artifact stage")
        if receipt.prompt_sha256 != sha256_bytes(args.prompt_file.read_bytes()):
            raise CliError("receipt prompt hash does not match")
        input_payload = _read_object(args.input_file)
        if receipt.input_sha256 != canonical_json_sha256(input_payload):
            raise CliError("receipt input hash does not match")
        if receipt.output_sha256 != canonical_json_sha256(artifact_payload):
            raise CliError("receipt output hash does not match")
        receipts = _load_receipts(official_dir)
        if any(item.invocation_id == receipt.invocation_id for item in receipts):
            raise CliError("duplicate invocation receipt")
        receipts.append(receipt)
        _save_receipts(official_dir, receipts)
    # Preserve the exact validated agent output. Expanding Pydantic defaults here
    # changes the canonical JSON hash after the receipt has already bound the
    # output, which also breaks hashes referenced by downstream artifacts.
    _write_json_once(official_dir / args.artifact_name, artifact_payload)
    return {"recorded": args.artifact_name, "run_id": args.run_id}


def _require(official_dir: Path, names: tuple[str, ...]) -> bool:
    return all((official_dir / name).is_file() for name in names)


def _set_state(official_dir: Path, state: ContentState) -> None:
    control = _control(official_dir)
    control["state"] = state.value
    _replace_json(official_dir / "control.json", control)


def _set_state_with_route(
    official_dir: Path,
    state: ContentState,
    *,
    rewrite_target: str,
    issue_codes: list[str],
) -> None:
    control = _control(official_dir)
    control.update(
        {
            "state": state.value,
            "rewrite_target": rewrite_target,
            "issue_codes": issue_codes,
        }
    )
    _replace_json(official_dir / "control.json", control)


def _archive_for_retry(
    official_dir: Path, names: tuple[str, ...], round_index: int
) -> None:
    history_dir = official_dir / "history" / f"round-{round_index + 1:02d}"
    for name in names:
        source = official_dir / name
        if not source.is_file():
            continue
        history_dir.mkdir(parents=True, exist_ok=True)
        target = history_dir / name
        if target.exists():
            raise CliError(f"retry history already contains {name}")
        source.replace(target)


def _route_retry(
    official_dir: Path,
    *,
    target: str,
    state: ContentState,
    issue_codes: list[str],
    archive: tuple[str, ...],
) -> dict[str, Any]:
    control = _control(official_dir)
    current_round = int(control.get("generation_round", 0))
    if current_round + 1 >= 3:
        control.update(
            {
                "state": ContentState.QUALITY_FAILED.value,
                "rewrite_target": target,
                "issue_codes": issue_codes,
            }
        )
        _replace_json(official_dir / "control.json", control)
        return {
            "run_id": control["run_id"],
            "state": ContentState.QUALITY_FAILED.value,
            "generation_round": current_round,
            "rewrite_target": target,
            "issue_codes": issue_codes,
        }
    _archive_for_retry(official_dir, archive, current_round)
    control.update(
        {
            "state": state.value,
            "generation_round": current_round + 1,
            "rewrite_target": target,
            "issue_codes": issue_codes,
        }
    )
    _replace_json(official_dir / "control.json", control)
    return {
        "run_id": control["run_id"],
        "state": state.value,
        "generation_round": current_round + 1,
        "rewrite_target": target,
        "issue_codes": issue_codes,
    }


def _commit_review_run(
    application_dir: Path,
    official_dir: Path,
    packet: NormalizedInputPacket,
) -> Path:
    receipts = AgentReceiptBundleArtifact(
        schema_version="1.5",
        run_id=packet.run_id,
        created_at=packet.created_at,
        source_digests=packet.source_digests,
        receipts=_load_receipts(official_dir),
    )
    _replace_json(
        official_dir / "agent-receipts.json", receipts.model_dump(mode="json")
    )
    fusion = FusionArtifact.model_validate(_read_object(official_dir / "fusion.json"))
    content = render_resume_markdown(fusion)
    stage = begin_run(application_dir, packet.run_id)
    for name in COMMIT_ARTIFACTS:
        stage.write_text(name, (official_dir / name).read_text(encoding="utf-8"))
    history_root = official_dir / "history"
    if history_root.is_dir():
        for history_path in sorted(history_root.rglob("*.json")):
            relative = history_path.relative_to(official_dir).as_posix()
            stage.write_text(relative, history_path.read_text(encoding="utf-8"))
    stage.write_text("content-master.md", content)
    stage.write_text("one-page-density.md", content)
    stage.write_text(
        "content-review.md",
        "# 内容审核\n\nSchema 1.5 确定性质量门、独立审计与 HR 门均已通过；等待用户确认。\n",
    )
    manifest = RunManifestArtifact(
        schema_version="1.5",
        run_id=packet.run_id,
        created_at=packet.created_at,
        source_digests=packet.source_digests,
        state=ContentState.READY_FOR_USER_REVIEW,
        input_packet=packet,
        artifacts=stage.artifact_records(),
        producer="official_coordinator",
    )
    path = stage.commit(manifest)
    missing = validate_run_artifact_completeness(path)
    if missing:
        raise CliError(
            f"committed run is incomplete: {[item.field_path for item in missing]}"
        )
    return path


def command_advance(args: argparse.Namespace) -> dict[str, Any]:
    application_dir = args.application_dir.resolve()
    official_dir = _official_dir(application_dir, args.run_id)
    packet = _load_packet(official_dir)
    state = ContentState(_control(official_dir)["state"])
    if state is ContentState.HR_REVIEWING and (
        official_dir / "hr-review.json"
    ).is_file():
        # Re-enter the audited branch after the independently recorded HR result.
        state = ContentState.AUDITING
    analysis = (
        "reference-research.json",
        "jd-analysis.json",
        "evidence-map.json",
        "fact-diff.json",
        "capability-transfer-map.json",
        "experience-selection.json",
        "selection-audit-pre.json",
        "story-plan.json",
        "selection-user-approval.json",
    )
    draft_files = ("draft-writer.json", "draft-asu.json")
    drafts = (*draft_files, "draft-quality-audit.json")
    if state is ContentState.ANALYZING and _require(official_dir, analysis):
        selection = ExperienceSelectionArtifact.model_validate(
            _read_object(official_dir / "experience-selection.json")
        )
        selection_audit = SelectionAuditArtifact.model_validate(
            _read_object(official_dir / "selection-audit-pre.json")
        )
        selection_approval = SelectionApprovalArtifact.model_validate(
            _read_object(official_dir / "selection-user-approval.json")
        )
        story_plan = StoryPlanArtifact.model_validate(
            _read_object(official_dir / "story-plan.json")
        )
        if not selection.selection_approved or not selection_audit.passed:
            raise CliError("selection and pre-draft audit must pass before drafting")
        selection_sha256 = selection_decision_sha256(selection)
        transfer_sha256 = canonical_json_sha256(
            _read_object(official_dir / "capability-transfer-map.json")
        )
        if (
            selection_approval.experience_selection_sha256 != selection_sha256
            or story_plan.experience_selection_sha256 != selection_sha256
            or selection_approval.story_plan_sha256
            != canonical_json_sha256(story_plan.model_dump(mode="json"))
        ):
            raise CliError("selection approval and story plan must bind the selection")
        if selection.capability_transfer_map_sha256 != transfer_sha256:
            raise CliError("experience selection does not bind the capability map")
        selected_ids = {
            item.experience_id for item in selection.candidates if item.selected
        }
        if {item.experience_id for item in story_plan.experiences} != selected_ids:
            raise CliError("story plan must cover every selected experience exactly once")
        _set_state(official_dir, ContentState.DRAFTING)
        state = ContentState.DRAFTING
    if state is ContentState.DRAFTING and _require(official_dir, draft_files):
        experiences, facts = _load_frozen_fact_records(official_dir, packet)
        jd_analysis = JDAnalysisArtifact.model_validate(
            _read_object(official_dir / "jd-analysis.json")
        )
        selection = ExperienceSelectionArtifact.model_validate(
            _read_object(official_dir / "experience-selection.json")
        )
        story_plan = StoryPlanArtifact.model_validate(
            _read_object(official_dir / "story-plan.json")
        )
        draft_reports = {
            filename: validate_draft_content(
                DraftArtifact.model_validate(_read_object(official_dir / filename)),
                jd_analysis,
                experiences,
                facts,
                experience_selection=selection,
                story_plan=story_plan,
            )
            for filename in draft_files
        }
        failed_drafts = [
            filename for filename, report in draft_reports.items() if not report.passed
        ]
        if failed_drafts:
            lane_by_file = {
                "draft-writer.json": "writer",
                "draft-asu.json": "asu_writer",
            }
            lanes = [lane_by_file[filename] for filename in failed_drafts]
            issue_codes = list(
                dict.fromkeys(
                    code
                    for filename in failed_drafts
                    for code in draft_reports[filename].hard_failures
                )
            )
            return _route_retry(
                official_dir,
                target=(lanes[0] if len(lanes) == 1 else "writers"),
                state=ContentState.DRAFTING,
                issue_codes=issue_codes,
                archive=(*failed_drafts, "draft-quality-audit.json"),
            )
    if state is ContentState.DRAFTING and _require(official_dir, drafts):
        draft_audit = DraftQualityAuditArtifact.model_validate(
            _read_object(official_dir / "draft-quality-audit.json")
        )
        if not draft_audit.passed:
            failed_agents = [
                lane.agent.value for lane in draft_audit.lane_reviews if not lane.passed
            ]
            archive = ["draft-quality-audit.json"]
            if "writer" in failed_agents:
                archive.append("draft-writer.json")
            if "asu_writer" in failed_agents:
                archive.append("draft-asu.json")
            return _route_retry(
                official_dir,
                target=(failed_agents[0] if len(failed_agents) == 1 else "writers"),
                state=ContentState.DRAFTING,
                issue_codes=["DRAFT_QUALITY_GATE_FAILED", *failed_agents],
                archive=tuple(archive),
            )
        _set_state(official_dir, ContentState.AUDITING)
        state = ContentState.AUDITING
    if state is ContentState.AUDITING and (official_dir / "fusion.json").is_file():
        experiences, facts = _load_frozen_fact_records(official_dir, packet)
        report = validate_fusion_content(
            FusionArtifact.model_validate(_read_object(official_dir / "fusion.json")),
            JDAnalysisArtifact.model_validate(_read_object(official_dir / "jd-analysis.json")),
            experiences,
            facts,
            experience_selection=ExperienceSelectionArtifact.model_validate(
                _read_object(official_dir / "experience-selection.json")
            ),
            story_plan=StoryPlanArtifact.model_validate(
                _read_object(official_dir / "story-plan.json")
            ),
        )
        _replace_json(official_dir / "validation.json", report.model_dump(mode="json"))
        _replace_json(official_dir / "quality-gate.json", report.model_dump(mode="json"))
        if not report.passed:
            if _quality_failure_target(report.hard_failures) == "needs_input":
                _set_state(official_dir, ContentState.NEEDS_INPUT)
                control = _control(official_dir)
                control["rewrite_target"] = "needs_input"
                control["issue_codes"] = report.hard_failures
                _replace_json(official_dir / "control.json", control)
                return {
                    "run_id": args.run_id,
                    "state": ContentState.NEEDS_INPUT.value,
                    "issue_codes": report.hard_failures,
                }
            return _route_retry(
                official_dir,
                target="fusion",
                state=ContentState.AUDITING,
                issue_codes=report.hard_failures,
                archive=(
                    "fusion.json",
                    "validation.json",
                    "quality-gate.json",
                    "audit.json",
                    "hr-review.json",
                ),
            )
    if state is ContentState.AUDITING and _require(
        official_dir, ("audit.json", "quality-gate.json")
    ):
        audit = AuditArtifact.model_validate(_read_object(official_dir / "audit.json"))
        if audit.disposition is not AuditDisposition.PASSED:
            if audit.reselect_required:
                return _route_retry(
                    official_dir,
                    target="story_plan",
                    state=ContentState.ANALYZING,
                    issue_codes=audit.selection_issue_codes,
                    archive=(
                        "experience-selection.json",
                        "selection-audit-pre.json",
                        "story-plan.json",
                        "selection-user-approval.json",
                        "draft-writer.json",
                        "draft-asu.json",
                        "draft-quality-audit.json",
                        "fusion.json",
                        "validation.json",
                        "quality-gate.json",
                        "audit.json",
                        "hr-review.json",
                    ),
                )
            if not audit.truth.passed:
                truth_issue_codes = [
                    item.error_code for item in audit.truth.findings
                ]
                _set_state_with_route(
                    official_dir,
                    ContentState.NEEDS_INPUT,
                    rewrite_target="needs_input",
                    issue_codes=truth_issue_codes,
                )
                return {
                    "run_id": args.run_id,
                    "state": ContentState.NEEDS_INPUT.value,
                    "issue_codes": truth_issue_codes,
                }
            return _route_retry(
                official_dir,
                target="fusion",
                state=ContentState.AUDITING,
                issue_codes=["AUDITOR_BLOCKING_DEFECT"],
                archive=("fusion.json", "validation.json", "quality-gate.json", "audit.json", "hr-review.json"),
            )
        if not (official_dir / "hr-review.json").is_file():
            _set_state(official_dir, ContentState.HR_REVIEWING)
            return {
                "run_id": args.run_id,
                "state": ContentState.HR_REVIEWING.value,
            }
        hr = HrReviewArtifact.model_validate(
            _read_object(official_dir / "hr-review.json")
        )
        if not hr.passed:
            if hr.fact_questions_required:
                _set_state_with_route(
                    official_dir,
                    ContentState.NEEDS_INPUT,
                    rewrite_target="needs_input",
                    issue_codes=hr.issue_codes,
                )
                return {
                    "run_id": args.run_id,
                    "state": ContentState.NEEDS_INPUT.value,
                    "issue_codes": hr.issue_codes,
                }
            if hr.reselect_required:
                return _route_retry(
                    official_dir,
                    target="story_plan",
                    state=ContentState.ANALYZING,
                    issue_codes=hr.issue_codes,
                    archive=(
                        "experience-selection.json",
                        "selection-audit-pre.json",
                        "story-plan.json",
                        "selection-user-approval.json",
                        "draft-writer.json",
                        "draft-asu.json",
                        "draft-quality-audit.json",
                        "fusion.json",
                        "validation.json",
                        "quality-gate.json",
                        "audit.json",
                        "hr-review.json",
                    ),
                )
            return _route_retry(
                official_dir,
                target="fusion",
                state=ContentState.AUDITING,
                issue_codes=hr.issue_codes or ["HR_GATE_FAILED"],
                archive=("fusion.json", "validation.json", "quality-gate.json", "audit.json", "hr-review.json"),
            )
        _set_state(official_dir, ContentState.READY_FOR_USER_REVIEW)
        path = _commit_review_run(application_dir, official_dir, packet)
        state = ContentState.READY_FOR_USER_REVIEW
        return {"run_id": args.run_id, "state": state.value, "run_dir": str(path)}
    return {"run_id": args.run_id, "state": state.value}


def command_approve(args: argparse.Namespace) -> dict[str, Any]:
    application_dir = args.application_dir.resolve()
    current_path = application_dir / "resume-content" / "current.json"
    previous_pointer = (
        validate_pointer_consistency(application_dir)
        if current_path.is_file()
        else None
    )
    manifest = load_run(application_dir, args.run_id)
    run_dir = application_dir / "resume-content" / "runs" / args.run_id
    approval = UserApprovalRecord(
        user_approval_id=args.user_approval_id,
        run_id=args.run_id,
        content_sha256=sha256_bytes((run_dir / "content-master.md").read_bytes()),
        approved_at=datetime.fromisoformat(args.approved_at),
    )
    fact_values = _read_object(args.fact_values)
    pointer = approve_run(
        application_dir,
        manifest.run_id,
        {str(key): str(value) for key, value in fact_values.items()},
        user_approval=approval,
    )
    if (
        previous_pointer is not None
        and previous_pointer.approved_run_id is not None
        and previous_pointer.approved_run_id != args.run_id
    ):
        append_run_status(
            application_dir,
            RunStatusRecord(
                run_id=previous_pointer.approved_run_id,
                content_sha256=previous_pointer.content_sha256,
                status=RunStatus.SUPERSEDED,
                reason_code="REPLACED_BY_NEW_APPROVAL",
                recorded_at=approval.approved_at,
            ),
        )
    return pointer.model_dump(mode="json")


def command_revoke(args: argparse.Namespace) -> dict[str, Any]:
    application_dir = args.application_dir.resolve()
    run_dir = application_dir / "resume-content" / "runs" / args.run_id
    content_path = run_dir / "content-master.md"
    record = RunStatusRecord(
        run_id=args.run_id,
        content_sha256=(sha256_bytes(content_path.read_bytes()) if content_path.is_file() else None),
        status=RunStatus(args.status),
        reason_code=args.reason_code,
        recorded_at=datetime.now(timezone.utc),
    )
    cleared = revoke_run(application_dir, record)
    return {"run_id": args.run_id, "status": args.status, "current_cleared": cleared}


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    application_dir = args.application_dir.resolve()
    if getattr(args, "require_approved_current", False):
        pointer = validate_pointer_consistency(application_dir)
        if (
            pointer.schema_version != "1.5"
            or pointer.status is not ContentState.APPROVED
            or pointer.approved_run_id is None
            or pointer.user_approval_id is None
        ):
            raise CliError("no valid approved Schema 1.5 current content")
        approval = UserApprovalRecord.model_validate(
            _read_object(
                application_dir
                / "resume-content"
                / "approvals"
                / f"{pointer.user_approval_id}.json"
            )
        )
        manifest = load_run(application_dir, pointer.approved_run_id)
        validate_v15_approval_evidence(application_dir, manifest, approval)
        status = latest_run_status(application_dir, pointer.approved_run_id)
        if status is None or status.status is not RunStatus.APPROVED:
            raise CliError("approved current is missing its final approved status record")
        return {
            "current_valid": True,
            "current": pointer.model_dump(mode="json"),
        }
    if args.run_id:
        official_dir = _official_dir(application_dir, args.run_id)
        return {
            "run_id": args.run_id,
            "official": _control(official_dir) if official_dir.exists() else None,
            "committed": (
                application_dir / "resume-content" / "runs" / args.run_id / "run.json"
            ).is_file(),
            "latest_status": (
                latest_run_status(application_dir, args.run_id).model_dump(mode="json")
                if latest_run_status(application_dir, args.run_id)
                else None
            ),
        }
    return {
        "run_statuses": [
            item.model_dump(mode="json") for item in read_run_statuses(application_dir)
        ]
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Official custom-resume Schema 1.5 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    start = subparsers.add_parser("start")
    start.add_argument("--repo-root", type=Path, required=True)
    start.add_argument("--application-dir", type=Path, required=True)
    start.add_argument("--role-family", choices=[item.value for item in RoleFamily], required=True)
    start.add_argument("--role-track", choices=[item.value for item in RoleTrack])
    start.set_defaults(handler=command_start)
    record = subparsers.add_parser("record")
    record.add_argument("--application-dir", type=Path, required=True)
    record.add_argument("--run-id", required=True)
    record.add_argument("--artifact-name", choices=sorted(RECORD_MODELS), required=True)
    record.add_argument("--artifact", type=Path, required=True)
    record.add_argument("--receipt", type=Path)
    record.add_argument("--prompt-file", type=Path)
    record.add_argument("--input-file", type=Path)
    record.set_defaults(handler=command_record)
    advance = subparsers.add_parser("advance")
    advance.add_argument("--application-dir", type=Path, required=True)
    advance.add_argument("--run-id", required=True)
    advance.set_defaults(handler=command_advance)
    approve = subparsers.add_parser("approve")
    approve.add_argument("--application-dir", type=Path, required=True)
    approve.add_argument("--run-id", required=True)
    approve.add_argument("--user-approval-id", required=True)
    approve.add_argument("--approved-at", required=True)
    approve.add_argument("--fact-values", type=Path, required=True)
    approve.set_defaults(handler=command_approve)
    revoke = subparsers.add_parser("revoke")
    revoke.add_argument("--application-dir", type=Path, required=True)
    revoke.add_argument("--run-id", required=True)
    revoke.add_argument(
        "--status",
        choices=[RunStatus.USER_REJECTED.value, RunStatus.SCHEMA_INVALID.value, RunStatus.REVOKED.value],
        required=True,
    )
    revoke.add_argument("--reason-code", required=True)
    revoke.set_defaults(handler=command_revoke)
    status = subparsers.add_parser("status")
    status.add_argument("--application-dir", type=Path, required=True)
    status.add_argument("--run-id")
    status.add_argument("--require-approved-current", action="store_true")
    status.set_defaults(handler=command_status)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = args.handler(args)
    except (CliError, StorageError, ValidationError, ValueError, OSError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"passed": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
