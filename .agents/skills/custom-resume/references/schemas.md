# Custom Resume Artifact Contract

This reference summarizes the public artifact boundaries implemented by the strict Pydantic 2 models in `scripts/models.py`. The code models remain authoritative.

## Shared envelope

Every JSON artifact includes:

- `schema_version`
- `run_id`
- `created_at`
- source input digests
- normalized `role_family` on the input packet and JD analysis (`ai_product_manager|game_production_pm`)

Unknown fields are rejected unless a later documented schema revision explicitly allows them.

## Artifacts

| File | Purpose |
|---|---|
| `run.json` | State, input digests, artifact inventory, errors, and revision count |
| `jd-analysis.json` | Job goals, prioritized requirements, risks, keywords, and ideal evidence blueprint |
| `evidence-map.json` | Requirement-to-fact mapping, coverage level, and gaps; schema 1.1 does not select experiences here |
| `capability-transfer-map.json` | Eight-category scan for every eligible experience; traceable supported/candidate capability-transfer chains and writable boundaries |
| `experience-selection.json` | Complete experience scorecard, deterministic transfer credits/tier, separate portfolio value, selection, similarity group, override, reasons, and bullet budgets |
| `selection-audit-pre.json` | Independent exact-row pre-draft opportunity-cost audit |
| `fact-diff.json` | Proposed fact additions/replacements, provenance, confirmation state, source hash, and applied result hash |
| `draft-writer.json` | Writer sections, bullets, fact IDs, requirement IDs, and candidate suggestions |
| `draft-asu.json` | ASu Writer output using the same draft contract |
| `fusion.json` | Fused bullets, source decisions, rewrite reasons, and fact IDs |
| `audit.json` | Truth, positive JD evidence, selection quality, gap disclosure, revisions/reselection, and overrides |
| `hr-review.json` | Strict interview-advance decision, per-experience defects, omitted facts, and revision/input/reselection route |
| `current.json` | Approved/stale run pointer and referenced-fact value digests |
| `validation.json` | Stable hard/warning findings and content-budget metrics |
| `reference-research.json` | Local/supplemented/degraded method-card routing evidence |
| `resume-content/.pending/<run_id>.json` | Recoverable human-gate checkpoint; removed after immutable run commit |

`fact-diff.json` may contain at most five structured option-style questions. The number of confirmed add/replace operations is not coupled to the question count.

## Content states

`not_started → analyzing → needs_input → awaiting_reference_approval → awaiting_selection_approval → drafting → auditing → hr_reviewing → needs_content_review → approved`

`auditing → awaiting_selection_approval` is allowed only for recorded reselection, at most twice.

`hr_reviewing → auditing` is used for an existing-fact revision; HR may also return to selection or stop with missing-fact questions. HR failure blocks approval.

`failed` is an execution failure state. `stale` applies when a fact referenced by an approved run changes.

Schema 1.3 is the V1.4 target and becomes the default for new runs only after T20 is completed. Schema 1.0–1.2 runs remain readable and are never migrated or rewritten in place.

## Implementation

The models, strict enumerations, cross-field validators, transition guard, and JSON Schema exporter are implemented in `scripts/models.py`. Immutable storage lives in `scripts/storage.py`, fact parsing/migration in `scripts/fact_library.py`, deterministic hard gates in `scripts/validators.py`, the run-directory CLI verifier in `scripts/validate_run.py`, and the content-only state machine orchestration in `scripts/orchestrator.py`.
