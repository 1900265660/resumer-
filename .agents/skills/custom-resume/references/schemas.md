# Custom Resume Artifact Contract

This reference lists the public artifact boundaries that T03 will implement with strict Pydantic 2 models. It is not a substitute for the models.

## Shared envelope

Every JSON artifact will include:

- `schema_version`
- `run_id`
- `created_at`
- source input digests

Unknown fields will be rejected unless a later documented schema revision explicitly allows them.

## Planned artifacts

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

## Planned content states

`not_started → analyzing → needs_input → awaiting_selection_approval → drafting → auditing → needs_content_review → approved`

`failed` is an execution failure state. `stale` applies when a fact referenced by an approved run changes.

## Current availability

The Pydantic models and validators do not exist in T02. Callers must not create ad hoc JSON that claims compliance with this contract.
