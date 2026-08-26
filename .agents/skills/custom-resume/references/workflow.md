# Custom Resume Workflow Contract

This reference is the runtime summary of the confirmed V1.4 workflow. `docs/custom-resume-agent/PRD.md` and `ARCHITECTURE.md` remain authoritative.

## Scope

- One Chinese AI product manager or game-production PM JD per run.
- Content analysis, drafting, fusion, audit, and content approval only.
- No HTML, PDF, visual QA, ATS page checks, application filling, or submission.

## Required sequence

1. Normalize an application directory, pasted JD, or JD URL.
2. Confirm `ai_product_manager` or `game_production_pm`; freeze JD, fact-library, preference, and selected reference-card digests.
3. Qualify reference research with a real resume/content sample, official role source, and sanitized selection rules; otherwise obtain explicit degraded approval.
4. Analyze the JD and build an ideal evidence blueprint.
5. Map requirements to confirmed facts and evidence levels.
6. Ask at most five high-value, option-style fact questions when needed.
7. Present one consolidated fact diff; write it only after explicit user confirmation.
   After an approved add/replace write, freeze the result hash and rerun analysis against the updated fact snapshot before selection approval.
8. Scan eight capability categories for every eligible experience. Persist fact-backed direct/adjacent/analogical transfer chains and zero-credit candidate questions in `capability-transfer-map.json`.
9. Score the complete pool on separate job-match and portfolio-value axes; recompute transfer credits, tiers, caps, work/variety constraints, any section-balance override, and bullet budgets. Run an independent exact-row pre-draft opportunity-cost audit.
10. Obtain user approval for experience selection, approved transfer IDs, bullet allocation, any override, and known gaps.
   Persist `needs_input`, `awaiting_selection_approval`, and approved `drafting` gates as a recoverable checkpoint before yielding for user input.
11. Run Writer and ASu Writer in isolated read-only contexts using only approved experiences, facts, and non-candidate transfer chains.
12. Fuse at bullet level without restoring excluded experiences or transfer chains.
13. Run deterministic validation, then a fresh post-fusion opportunity-cost, truth, and base-quality audit.
14. After the base audit passes, run a fresh strict HR decision review. Require `strong_push` and >=8.5 overall and in all five decision dimensions.
15. Route a failed HR review to existing-fact revision, missing-fact questions, or reselection. Every revision reruns deterministic validation, the base Auditor, and a fresh HR Reviewer; at most twice.
16. Present fusion content, decision differences, base audit, and HR review for human content approval. HR failure blocks approval.

## Hard gates

- The confirmed Markdown fact library is the only source for clean claims.
- Every clean bullet cites valid fact IDs.
- Education and skill facts are passed as fixed baseline content; only WORK/PROJECT experiences compete in selection scoring and bullet quotas.
- Every eligible work/project experience is scored; affinity-only evidence is capped below selection, auxiliary bullets are at most 25%, and omitted core experience has a user-confirmed reason.
- Every eligible experience has eight explicit capability scans; candidate chains score zero and never reach Writers.
- Job-match and portfolio scores stay separate; same-group personal projects are limited to two, at least two WORK entries are selected when available, and one low-score WORK exception requires an approved auditable override.
- Education exactly copies the confirmed baseline; self-ability entries are exactly 专业硬技能、综合软技能、游戏体验、语言能力.
- 14 experience bullets and 1,500 Chinese characters are maxima, not minimum targets.
- Unconfirmed candidates never enter clean content.
- A passing base audit cannot bypass HR review; `push|hesitate|reject` fail the high-standard decision gate.
- Content approval never changes the application status or triggers downstream files.
- If subagents are unavailable, pause and ask whether to retry or explicitly degrade.

## Current availability

T02–T11 implement the standalone content-only workflow and fixed AI PM evaluation. T13 adds the authorized game-production role family. T20's independent HR decision gate is implemented for review but remains unavailable until T20 is completed; T12 alone controls legacy-default cutover.
