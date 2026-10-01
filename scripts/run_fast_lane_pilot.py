#!/usr/bin/env python3
"""Run the 10-job fast-lane pilot: route + assemble, emit one JSON summary.

Read-only with respect to the profile and claim library. Produces a report the
main agent uses to (a) confirm which full-rewrite jobs demote to fast-assemble,
(b) list fact gaps / supported coverage gaps, and (c) drive the four-gate HR
review.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(r"E:\zhuomian\简历\项目\Codex-求职助手")
MODULE = ROOT / ".agents" / "skills" / "china-job-search" / "scripts" / "fast_resume.py"
SPEC = importlib.util.spec_from_file_location("fast_resume", MODULE)
assert SPEC and SPEC.loader
fast_resume = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fast_resume)

PROFILE = (ROOT / "profile" / "01-candidate-profile.md").read_text(encoding="utf-8-sig")
ANSWERS = (ROOT / "profile" / "application-answers.md").read_text(encoding="utf-8-sig")
CLAIMS = fast_resume.read_json(ROOT / "profile" / "resume-claims.json")
CONTACT = fast_resume.parse_answers(ANSWERS)

JOB_DIR = ROOT / "outputs" / "fast-lane-pilot"


def main() -> None:
    report = {"jobs": []}
    for path in sorted(JOB_DIR.glob("*.job.json")):
        job = fast_resume.read_json(path)
        route = fast_resume.route_job(job, CLAIMS)
        entry: dict = {
            "file": path.name,
            "company": job["company"],
            "target_role": job["target_role"],
            "strategy": route.get("resume_strategy"),
            "reason": route.get("reason"),
            "required_count": sum(
                1 for r in job["requirements"] if r.get("required", True)
            ),
            "unsupported_required": [
                r["text"]
                for r in job["requirements"]
                if r.get("required", True) and not r.get("fact_ids")
            ],
            "assemble": None,
        }
        if route.get("resume_strategy") == "快速生成":
            try:
                content = fast_resume.assemble_fast_content(
                    job,
                    {"selected_experience_ids": job["selected_experience_ids"]},
                    CLAIMS,
                    PROFILE,
                    CONTACT,
                )
                entry["assemble"] = {
                    "covered_requirement_ids": content["covered_requirement_ids"],
                    "fact_gaps": content["fact_gaps"],
                    "supported_coverage_gaps": content["supported_coverage_gaps"],
                    "sections": [
                        {
                            "name": s["name"],
                            "entries": [
                                {
                                    "experience_id": e["experience_id"],
                                    "heading": e["heading"],
                                    "bullet_count": len(e["bullets"]),
                                }
                                for e in s["entries"]
                            ],
                        }
                        for s in content["sections"]
                    ],
                }
            except fast_resume.FastResumeError as err:
                entry["assemble"] = {"error": str(err)}
        report["jobs"].append(entry)

    summary = {}
    for e in report["jobs"]:
        summary[e["strategy"]] = summary.get(e["strategy"], 0) + 1
    report["summary"] = summary

    out = JOB_DIR / "pilot-report.json"
    fast_resume.write_json(out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
