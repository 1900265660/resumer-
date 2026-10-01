#!/usr/bin/env python3
"""Dump the duties/requirements body of the 20 batch jobs' jd.md for mapping."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(r"E:\zhuomian\简历\项目\Codex-求职助手")
rows = json.loads((ROOT / "outputs" / "fast-lane-pilot" / "batch20.json").read_text(encoding="utf-8"))["rows"]


def body(text: str) -> str:
    # Drop the front-matter metadata lines; keep the descriptive body.
    lines = text.splitlines()
    start = 0
    for i, line in enumerate(lines):
        if re.match(r"^#+\s", line) and ("职位描述" in line or "岗位描述" in line or "职责" in line or "工作职责" in line or "岗位职责" in line or "职位要求" in line or "任职要求" in line):
            start = i
            break
    return "\n".join(lines[start:]).strip()


out_lines: list[str] = []
for r in rows:
    jd = (ROOT / r["app_dir"] / "jd.md").read_text(encoding="utf-8-sig")
    out_lines.append(f"\n===== {r['company']}｜{r['job']} (src {r['source_row']}) =====")
    out_lines.append(body(jd)[:2200])

out = ROOT / "outputs" / "fast-lane-pilot" / "batch20-jd.md"
out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
print(f"wrote {out}")
