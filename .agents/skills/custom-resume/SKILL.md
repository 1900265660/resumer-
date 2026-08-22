---
name: custom-resume
description: Tailor evidence-grounded Chinese resume content for one AI product manager JD, including fact-gap questions, independent drafts, fusion, and content review. Use for 定制简历内容、按 JD 改简历 or 调用最新的简历 skill; do not use for HTML, PDF, templates, visual QA, export, or job submission.
---

# Custom Resume

Produce reviewable Chinese resume content for one AI product manager JD while keeping the confirmed candidate fact library as the only source for clean resume claims.

## Implementation status

T02–T09 provide the complete standalone content workflow: contracts, fact IDs, immutable storage, structured prompts, read-only agents, coordinator gates, deterministic validators, fusion, audit, and content approval. Main-harness routing and fixed evaluation evidence are still pending; do not claim V1 has replaced the legacy default until T10–T12 gates are satisfied.

## Boundaries

- Handle one JD at a time.
- Read candidate claims only from `profile/01-candidate-profile.md`.
- Keep unconfirmed material out of clean resume content.
- Do not generate HTML/PDF, choose templates, perform visual QA, fill applications, or submit jobs.
- Route file-making requests to the existing `resume` skill after content is separately approved.

## Required references

- Read [references/workflow.md](references/workflow.md) before orchestrating a run.
- Read [references/schemas.md](references/schemas.md) before creating or validating structured artifacts.
- The authoritative product and engineering decisions live in `docs/custom-resume-agent/`.

Do not claim a stage is available until its corresponding task in `docs/custom-resume-agent/TASKS.md` is completed and verified.
