# Custom Resume Schema 1.5 Artifacts

The strict Pydantic definitions in `scripts/models.py` and the exported JSON Schemas in `schemas/` are authoritative. Unknown fields are rejected.

## Required artifacts

| File | Current purpose |
|---|---|
| `run.json` | Immutable run manifest, input hashes, artifacts, state, and generation round |
| `jd-analysis.json` | Normalized role, requirements, risks, keywords, and evidence blueprint |
| `evidence-map.json` | Requirement-to-confirmed-fact coverage and gaps |
| `capability-transfer-map.json` | Fact-backed transfer chains and candidate questions |
| `experience-selection.json` | Complete scoring pool and the selected 1–4 WORK/PROJECT experiences |
| `selection-audit-pre.json` | Independent pre-draft selection audit |
| `story-plan.json` | Story thesis, evidence buckets, one or more evidence-driven intents, capability IDs, and internal ownership guard for each selected experience |
| `selection-user-approval.json` | User approval bound to the selection and story-plan hashes |
| `draft-writer.json` | Standard Writer candidate with experience/intent/fact bindings |
| `draft-asu.json` | Independent ASu Writer candidate using the same contract |
| `draft-quality-audit.json` | Independent draft-lane audit bound to candidate hashes |
| `fusion.json` | Fused candidate and bullet-level provenance |
| `quality-gate.json` | Deterministic hard failures, warnings, per-experience results, and metrics bound to the fusion hash |
| `audit.json` | Independent post-fusion audit |
| `hr-review.json` | Strict interview-advance review with concrete experience/bullet evidence |
| `agent-receipts.json` | Invocation receipts binding stage, role, model, prompt, input, and output hashes |
| `validation.json` | Deterministic validation findings retained with the run |
| `current.json` | `approved|stale|no_approved_content` pointer bound to run, content hash, and user approval ID |
| `run-status.jsonl` | Append-only `approved|superseded|user_rejected|schema_invalid|revoked` status ledger |

## Public structures

```text
StoryPlanArtifact
  schema_version = "1.5"
  experiences[]
    experience_id
    story_thesis
    capability_ids[]
    evidence.context_fact_ids[]
    evidence.action_fact_ids[]
    evidence.method_fact_ids[]
    evidence.challenge_fact_ids[]
    evidence.result_fact_ids[]
    bullet_intents[{ intent_id, purpose, required_fact_ids[] }]
    ownership_guard{ allowed_claims[], prohibited_claims[] }

AgentInvocationReceipt
  stage
  role
  invocation_id
  model
  reasoning_effort
  prompt_sha256
  input_sha256
  output_sha256
  created_at

QualityGateArtifact
  candidate_sha256
  story_plan_sha256
  passed
  hard_failures[]
  warnings[]
  per_experience_results[]
  metrics

CurrentPointer
  status = approved | stale | no_approved_content
  approved_run_id?
  content_sha256?
  user_approval_id?

RunStatusRecord
  run_id
  content_sha256
  status
  reason_code
  recorded_at
```

## State and compatibility

The active path is `not_started → analyzing → needs_input/awaiting_selection_approval → drafting → auditing → hr_reviewing → ready_for_user_review → approved`, with `quality_failed` after the third failed generation candidate.

Schema 1.0–1.4 artifacts remain readable and immutable. Official entrypoints reject new approvals for them. A blocking run-status record overrides an older `run.json` approval field.

## Implementation locations

- Models and schema export: `scripts/models.py`
- Official coordinator CLI: `scripts/custom_resume_cli.py`
- State-machine helpers: `scripts/orchestrator.py`
- Deterministic gates: `scripts/validators.py`
- Rendering: `scripts/rendering.py`
- Immutable storage, receipt/hash approval validation, and status ledger: `scripts/storage.py`
- Run-directory verifier: `scripts/validate_run.py`
