# AI Product Manager Method Cards

Use these cards only to interpret a JD and judge evidence quality. They are not candidate facts and must never be copied into resume claims.

## Card 1 — Requirement-to-evidence decomposition

- Break a JD into business goal, user/problem context, AI-specific product work, delivery collaboration, and outcome/evaluation requirements.
- Treat keywords as retrieval aids, not proof of experience.
- Prefer direct evidence with action, method, artifact, result, and personal boundary; mark composite and unsupported evidence explicitly.
- Source: Resume Matcher diff-based improvement design, <https://github.com/srbhr/Resume-Matcher/blob/main/docs/superpowers/specs/2026-03-23-diff-based-improvement-design.md>.
- Recorded: 2026-08-22.

## Card 2 — AI product evidence depth

- Strong AI PM evidence usually shows a real user/problem definition, data or knowledge preparation, model/prompt/retrieval choice, evaluation design, iteration, launch/delivery boundary, and outcome.
- Separate “understands an AI concept” from “made a product decision using it”.
- Evaluation evidence should state test set or feedback source, metric/criteria, iteration count when confirmed, and the candidate's contribution.
- This is a sanitized method synthesis; it contains no reference-resume claims.
- Recorded: 2026-08-22.

## Card 3 — Deterministic gates before subjective audit

- Validate schema, references, immutable fields, numeric provenance, and artifact integrity deterministically.
- Use independent quality review only after hard gates pass.
- Compare old/new flows on the same frozen facts and JD.
- Source: Resume Matcher Eval Harness, <https://github.com/srbhr/Resume-Matcher/blob/main/apps/backend/tests/evals/README.md>.
- Recorded: 2026-08-22.

## Card 4 — Truth-first independent audit

- The auditor is read-only and cannot repair the draft it judges.
- Truth failures are exhaustive hard failures; quality scores cannot offset them.
- Source: ResumeHQ read-only auditor configuration, <https://github.com/jananthan30/Resume-Builder/blob/master/.codex/agents/resume-auditor.toml>.
- Recorded: 2026-08-22.
