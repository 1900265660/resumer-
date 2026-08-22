# Custom Resume Artifact Contract

This reference summarizes the public artifact boundaries implemented by the strict Pydantic 2 models in `scripts/models.py`. The code models remain authoritative.

## Shared envelope

Every JSON artifact includes:

- `schema_version`
- `run_id`
- `created_at`
- source input digests

Unknown fields are rejected unless a later documented schema revision explicitly allows them.

## Artifacts

| File | Purpose |
|---|---|
| `run.json` | State, input digests, artifact inventory, errors, and revision count |
| `jd-analysis.json` | Job goals, prioritized requirements, risks, keywords, and ideal evidence blueprint |
| `evidence-map.json` | Requirement-to-fact mapping, coverage level, selections, and gaps |
| `fact-diff.json` | Proposed fact additions/replacements, provenance, and confirmation state |
| `draft-writer.json` | Writer sections, bullets, fact IDs, requirement IDs, and candidate suggestions |
| `draft-asu.json` | ASu Writer output using the same draft contract |
| `fusion.json` | Fused bullets, source decisions, rewrite reasons, and fact IDs |
| `audit.json` | Deterministic gates, truth audit, quality scores, revisions, and overrides |
| `current.json` | Approved/stale run pointer and referenced-fact value digests |

`fact-diff.json` may contain at most five structured option-style questions. The number of confirmed add/replace operations is not coupled to the question count.

## Content states

`not_started → analyzing → needs_input → awaiting_selection_approval → drafting → auditing → needs_content_review → approved`

`failed` is an execution failure state. `stale` applies when a fact referenced by an approved run changes.

## Implementation

The models, strict enumerations, cross-field validators, transition guard, and JSON Schema exporter are implemented in `scripts/models.py`. Immutable run commits, transactional approval pointers, and referenced-fact staleness checks are implemented in `scripts/storage.py`. Later tasks add orchestration and full content validation; callers must not treat these components as proof that a complete run is operational.
