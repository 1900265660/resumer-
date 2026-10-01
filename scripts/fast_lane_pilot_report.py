#!/usr/bin/env python3
"""Emit a clean UTF-8 markdown report for the fast-lane pilot, plus a
representative end-to-end content + writer packet for 腾讯 AI产品经理."""

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

OUT = ROOT / "outputs" / "fast-lane-pilot"


def main() -> None:
    report = fast_resume.read_json(OUT / "pilot-report.json")
    lines: list[str] = []
    lines.append("# 快速通道十岗检验报告\n")
    lines.append("## 结论\n")
    lines.append("- 10 个原“完整重写”岗位：9 个降级为“快速生成”，1 个判为“待补事实”。")
    lines.append("- 9 个快速生成岗均成功复用批准表达装配出完整正文（教育/实习/实践/自我能力四板块）。")
    lines.append("- 全部 9 岗都产生 `supported_coverage_gaps`：JD 能力有事实证据，但“自我能力”栏尚无直接命中表达，需单次 `fast_writer` 补缺。\n")

    lines.append("## 路由与装配明细\n")
    lines.append("| 岗位 | 路由 | 必须要求 | 无证据必须项 | 装配 | 事实缺口 | 需补写能力数 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for job in report["jobs"]:
        asm = job["assemble"] or {}
        gap_count = len(asm.get("fact_gaps", [])) if asm else 0
        supp_count = len(asm.get("supported_coverage_gaps", [])) if asm else 0
        unsup = "；".join(job["unsupported_required"]) or "—"
        asm_state = "成功" if asm and "error" not in asm else (asm.get("error") if asm else "未装配")
        lines.append(
            f"| {job['company']}｜{job['target_role']} | {job['strategy']} | {job['required_count']} | {unsup} | {asm_state} | {gap_count} | {supp_count} |"
        )

    lines.append("\n## 事实缺口（诚实暴露，未做关键词伪装）\n")
    for job in report["jobs"]:
        asm = job["assemble"] or {}
        for gap in asm.get("fact_gaps", []):
            lines.append(f"- {job['company']}｜{job['target_role']}：{gap['text']}")
    unsup_lines = []
    for job in report["jobs"]:
        for u in job["unsupported_required"]:
            unsup_lines.append(f"- {job['company']}｜{job['target_role']}：{u}")
    if unsup_lines:
        lines.append("\n无证据必须项（路由为待补事实）：")
        lines.extend(unsup_lines)

    lines.append("\n## 需补写能力（有事实但自我能力栏未覆盖）\n")
    for job in report["jobs"]:
        asm = job["assemble"] or {}
        for gap in asm.get("supported_coverage_gaps", []):
            facts = ",".join(gap["fact_ids"])
            lines.append(f"- {job['company']}｜{job['target_role']}：{gap['text']}（事实 {facts}）")

    report_path = OUT / "pilot-report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {report_path}")

    # Representative end-to-end artifact for 腾讯 AI产品经理.
    tencent = next(j for j in report["jobs"] if j["file"].startswith("腾讯"))
    job_path = OUT / tencent["file"]
    job = fast_resume.read_json(job_path)
    content = fast_resume.assemble_fast_content(
        job,
        {"selected_experience_ids": job["selected_experience_ids"]},
        CLAIMS,
        PROFILE,
        CONTACT,
    )
    fast_resume.write_json(OUT / "腾讯_AI产品经理.content.json", content)
    packet = fast_resume.build_fast_writer_packet(content, PROFILE)
    fast_resume.write_json(OUT / "腾讯_AI产品经理.writer-packet.json", packet)
    print("wrote 腾讯 content + writer-packet")


if __name__ == "__main__":
    main()
