# Custom Resume Workflow Contract

This reference is the runtime summary of the confirmed V1 workflow. `docs/custom-resume-agent/PRD.md` and `ARCHITECTURE.md` remain authoritative.

## Scope

- One Chinese AI product manager JD per run.
- Content analysis, drafting, fusion, audit, and content approval only.
- No HTML, PDF, visual QA, ATS page checks, application filling, or submission.

## Required sequence

1. Normalize an application directory, pasted JD, or JD URL.
2. Freeze JD, fact-library, preference, and reference-card digests.
3. Analyze the JD and build an ideal evidence blueprint.
4. Map requirements to confirmed facts and evidence levels.
5. Ask at most five high-value, option-style fact questions when needed.
6. Present one consolidated fact diff; write it only after explicit user confirmation.
7. Obtain user approval for evidence mapping, experience selection, and known gaps.
8. Run Writer and ASu Writer in isolated read-only contexts using equivalent input packets.
9. Fuse at bullet level and record every selection or rewrite decision.
10. Run deterministic validation, then independent truth and HR-quality audit.
11. Revise only identified issues, for at most two rounds.
12. Present fusion content and decision differences for human content approval.

## Hard gates

- The confirmed Markdown fact library is the only source for clean claims.
- Every clean bullet cites valid fact IDs.
- Unconfirmed candidates never enter clean content.
- Content approval never changes the application status or triggers downstream files.
- If subagents are unavailable, pause and ask whether to retry or explicitly degrade.

## Current availability

T02–T04 and T06 provide discovery metadata, strict domain contracts, state transitions, a read-only fact-library ID migration preview, and immutable run/current-pointer storage. Applying the preview and runtime orchestration remain disabled until the corresponding later tasks are completed and approved.
