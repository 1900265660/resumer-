# Schema 1.5 Content Quality Gates

Quality is enforced in three independent layers. A later layer cannot override an earlier failure.

## Deterministic gate

The candidate fails when any of these is true:

- a selected WORK/PROJECT experience has no non-empty resume content;
- an experience is missing story-plan, intent, or fact bindings;
- its bullets do not jointly cover context/problem, action/method, and result/impact;
- multiple bullets repeat the same intent instead of serving complementary purposes;
- resume-visible text contains negative responsibility disclaimers or internal audit/workflow wording;
- a bullet is identical to a source fact;
- a bullet is at least 0.90 similar to one fact, cites only that fact, and does not synthesize multiple story elements;
- a claim, number, or ownership assertion is unsupported by confirmed facts.

Similarity from 0.80 through 0.90 is an audit warning. The internal ownership guard is checked by the gate but is never rendered.

## Independent Auditor

The Auditor checks each experience for:

- a clear target-role selling point;
- complete background/problem → action/method → result/impact narrative;
- abstraction and synthesis instead of fact-library transcription;
- complementary bullets with high information density;
- inclusion of the highest-value supported evidence;
- natural, concise Chinese resume language.

A blocking defect or `pass=false` triggers the routed retry. Truth conflicts route to `needs_input` rather than a rewrite.

## HR admission gate

HR runs only after deterministic validation and the post-fusion Auditor pass. Passing requires all of:

- verdict `strong_push`;
- overall score >=9.0;
- every decision dimension >=8.0;
- concrete citations to existing experience IDs and bullet IDs.
- the content-fullness gate: at least 1,200 Chinese characters overall, 180 in each core experience, and 120 in each auxiliary experience.

HR evaluates interview value, role fit, narrative completeness, evidence specificity, decision readiness, credibility, and content fullness. Visible boundary disclaimers do not earn credit. HR pass changes state only to `ready_for_user_review`; explicit user approval of the final content hash is still required.

## Content fullness

Character thresholds are hard HR admission gates. Bullet totals are never minimum or maximum quality quotas: split only where distinct semantic units or scan readability require it. If confirmed facts cannot support the character thresholds, route to `needs_input` or reselection; never invent, duplicate, or paraphrase filler merely to reach a number.
