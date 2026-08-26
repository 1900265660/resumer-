from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from models import (
    AgentFailureArtifact,
    AuditArtifact,
    AuditDisposition,
    CapabilityTransferMapArtifact,
    ContentState,
    DeterministicValidationArtifact,
    DraftArtifact,
    EvidenceMapArtifact,
    ExperienceSelectionArtifact,
    FactDiffArtifact,
    FusionArtifact,
    HrReviewArtifact,
    JDAnalysisArtifact,
    NormalizedInputPacket,
    ReferenceResearchArtifact,
    SelectionAuditArtifact,
)
from storage import RunIntegrityError, load_run
from validators import validate_run_artifact_completeness


ARTIFACT_TYPES: dict[str, type] = {
    "input-packet.json": NormalizedInputPacket,
    "jd-analysis.json": JDAnalysisArtifact,
    "evidence-map.json": EvidenceMapArtifact,
    "fact-diff.json": FactDiffArtifact,
    "reference-research.json": ReferenceResearchArtifact,
    "capability-transfer-map.json": CapabilityTransferMapArtifact,
    "experience-selection.json": ExperienceSelectionArtifact,
    "selection-audit-pre.json": SelectionAuditArtifact,
    "draft-writer.json": DraftArtifact,
    "fusion.json": FusionArtifact,
    "validation.json": DeterministicValidationArtifact,
    "audit.json": AuditArtifact,
    "hr-review.json": HrReviewArtifact,
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path.name}")
    return payload


def validate_run_directory(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    findings: list[str] = []
    if run_dir.parent.name != "runs" or run_dir.parent.parent.name != "resume-content":
        return {
            "passed": False,
            "review_ready": False,
            "state": None,
            "findings": ["run directory must be resume-content/runs/<run_id>"],
        }
    application_dir = run_dir.parents[2]
    try:
        manifest = load_run(application_dir, run_dir.name)
    except (RunIntegrityError, OSError, ValidationError, ValueError) as error:
        return {
            "passed": False,
            "review_ready": False,
            "state": None,
            "findings": [str(error)],
        }
    findings.extend(
        item.message for item in validate_run_artifact_completeness(run_dir)
    )
    parsed: dict[str, Any] = {}
    for filename, model in ARTIFACT_TYPES.items():
        path = run_dir / filename
        if not path.is_file():
            continue
        try:
            parsed[filename] = model.model_validate(_load_json(path))
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as error:
            findings.append(f"invalid {filename}: {error}")
    asu_path = run_dir / "draft-asu.json"
    if asu_path.is_file():
        try:
            asu_payload = _load_json(asu_path)
            try:
                parsed["draft-asu.json"] = DraftArtifact.model_validate(asu_payload)
            except ValidationError:
                parsed["draft-asu.json"] = AgentFailureArtifact.model_validate(
                    asu_payload
                )
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as error:
            findings.append(f"invalid draft-asu.json: {error}")
    for filename, artifact in parsed.items():
        if artifact.run_id != manifest.run_id:
            findings.append(f"{filename} run_id does not match run.json")
        if artifact.source_digests != manifest.source_digests:
            findings.append(f"{filename} source digests do not match run.json")
    packet = parsed.get("input-packet.json")
    if packet is not None and packet != manifest.input_packet:
        findings.append("input-packet.json does not match run.json input_packet")
    validation = parsed.get("validation.json")
    audit = parsed.get("audit.json")
    hr_review = parsed.get("hr-review.json")
    hr_ready = manifest.schema_version != "1.3" or bool(
        hr_review is not None and hr_review.passed
    )
    review_ready = bool(
        not findings
        and manifest.state is ContentState.NEEDS_CONTENT_REVIEW
        and validation is not None
        and validation.passed
        and audit is not None
        and audit.disposition is AuditDisposition.PASSED
        and audit.truth.passed
        and hr_ready
    )
    return {
        "passed": not findings,
        "review_ready": review_ready,
        "state": manifest.state.value,
        "run_id": manifest.run_id,
        "artifact_count": len(manifest.artifacts),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate an immutable custom-resume run directory"
    )
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    result = validate_run_directory(args.run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
