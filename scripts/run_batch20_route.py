#!/usr/bin/env python3
"""Route + assemble the 20 batch jobs and emit a UTF-8 summary."""

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

JOB_DIR = ROOT / "outputs" / "fast-lane-pilot" / "batch20-jobs"


def main() -> None:
    report = {"jobs": []}
    for path in sorted(JOB_DIR.glob("*.job.json")):
        jd = fast_resume.read_json(path)
        route = fast_resume.route_job(jd, CLAIMS)
        entry = {
            "key": path.name[:-9],
            "company": jd["company"],
            "target_role": jd["target_role"],
            "strategy": route.get("resume_strategy"),
            "reason": route.get("reason"),
            "unsupported_required": [
                r["text"] for r in jd["requirements"] if r.get("required", True) and not r.get("fact_ids")
            ],
            "assemble": None,
        }
        if route.get("resume_strategy") == "快速生成":
            content = fast_resume.assemble_fast_content(
                jd,
                {"selected_experience_ids": jd["selected_experience_ids"]},
                CLAIMS,
                PROFILE,
                CONTACT,
            )
            entry["assemble"] = {
                "covered": len(content["covered_requirement_ids"]),
                "required": sum(1 for r in jd["requirements"] if r.get("required", True)),
                "fact_gaps": content["fact_gaps"],
                "supported_gaps": content["supported_coverage_gaps"],
            }
            fast_resume.write_json(JOB_DIR / f"{entry['key']}.content.json", content)
        report["jobs"].append(entry)

    summary = {}
    for e in report["jobs"]:
        summary[e["strategy"]] = summary.get(e["strategy"], 0) + 1
    report["summary"] = summary
    out = JOB_DIR / "route-report.json"
    fast_resume.write_json(out, report)

    lines = ["# 20岗路由与装配摘要\n", f"## 汇总\n{json.dumps(summary, ensure_ascii=False)}\n", "## 明细\n"]
    for e in report["jobs"]:
        a = e["assemble"] or {}
        lines.append(
            f"- {e['company']}｜{e['target_role']} → {e['strategy']}"
            + (f" | 覆盖{a.get('covered')}/{a.get('required')} | 事实缺口{len(a.get('fact_gaps', []))} | 需补写{len(a.get('supported_gaps', []))}" if a else "")
        )
        if e["unsupported_required"]:
            lines.append(f"  - 无证据必须项：{'; '.join(e['unsupported_required'])}")
    (JOB_DIR / "route-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
