# Custom Resume Schema 1.5 Workflow

This file describes the workflow implemented by `scripts/custom_resume_cli.py`. Schema 1.0–1.4 runs are read-only and cannot receive a new approval.

## Scope

- Tailor resume content for one supported Chinese JD.
- Produce and review structured content artifacts only.
- Do not create HTML/PDF, perform visual QA, fill applications, or submit jobs.

## Official entrypoint

Only `custom_resume_cli.py start|record|advance|approve|revoke|status` may advance a Schema 1.5 run. The coordinator validates every imported artifact and its `AgentInvocationReceipt`; agent-authored pass fields do not write state.

## Execution sequence

1. `start` freezes the JD, fact library, preferences, and selected reference hashes.
2. JD analysis, evidence mapping, capability transfer, experience selection, selection audit, and `story-plan.json` are recorded.
3. Selection covers 1–4 WORK/PROJECT experiences in total. Any proposed bullet count is an advisory layout estimate derived from semantic units, never a gate. There is no minimum WORK count, section-balance padding, or low-score WORK exception.
4. The user approves the exact selection and story-plan hashes in `selection-user-approval.json`.
5. Writer and ASu Writer independently write against the same story plan. Each bullet binds `experience_id`, `intent_id`, and `fact_ids`.
6. Each draft passes deterministic validation and a fresh independent draft Auditor before it may enter Fusion.
7. Fusion uses only passing draft content, then passes deterministic validation, an independent post-fusion Auditor, and HR review.
8. Passing HR means `ready_for_user_review`. It does not approve content.
9. `approve` records the user's approval of the final content hash, verifies the full artifact/receipt/hash chain, commits the immutable run, and updates `current.json`.

## Story contract

Each selected experience has one `story_thesis`, capability IDs, context/action/method/challenge/result evidence buckets, one or more different bullet intents, and an internal ownership guard. Intent count follows the evidence story rather than a fixed bullet quota. The rendered resume must not contain the ownership guard or negative responsibility disclaimers.

Across an experience's bullets, the content must cover context/problem, action/method, and result/impact. A selected experience without at least one action fact and one result/impact fact is removed, merged only with the same real subject, or routed to `needs_input`.

## Retry loop

`MAX_GENERATION_ROUNDS = 3`: the initial candidate plus at most two repaired candidates.

- Selection or story defects return to Story Plan.
- A defect isolated to one Writer rewrites only that lane.
- Fusion, language, duplication, and HR defects rewrite Fusion.
- Fact conflicts stop in `needs_input`.
- A third failed candidate ends as `quality_failed`; it cannot be force-approved.

Every retry archives the superseded artifacts and keeps their receipt-bound hashes in the committed history.

## Hard gates

- Every WORK/PROJECT experience contains non-empty content, covers each approved intent once, and avoids duplicate split bullets; bullet count itself is not graded.
- HR admission requires at least 1,200 Chinese characters overall, at least 180 in each core experience, and at least 120 in each auxiliary experience.
- Resume text cannot contain negative-boundary or internal-workflow phrases configured in `validators.py`.
- A bullet identical to one source fact fails. Similarity >=0.90 with only one fact and no cross-element synthesis fails; 0.80–0.90 warns.
- New facts, numbers, or unsupported ownership still fail deterministic fact validation.
- HR must return `strong_push`, overall >=9.0, every decision dimension >=8.0, and cite concrete experience and bullet IDs.
- Quality gate, both Auditors, HR, receipts, content rendering, and all hashes must agree.
- `approved` requires a separate user approval bound to the final content hash.
- `user_rejected`, `schema_invalid`, `revoked`, and `superseded` statuses block current content and downstream use.

## Release state

Schema 1.5 code is implemented but remains pending product acceptance with a new real target JD. It must not automatically approve a real job before that acceptance.
