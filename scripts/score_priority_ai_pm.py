#!/usr/bin/env python3
"""Annotate eligible AI-PM candidates with match_score and sort by priority."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(r"E:\zhuomian\简历\项目\Codex-求职助手")
rows = json.loads(
    (ROOT / "outputs" / "fast-lane-pilot" / "priority-ai-pm-eligible.json").read_text(encoding="utf-8")
)["rows"]

out = []
for r in rows:
    mf = json.loads((ROOT / r["app_dir"] / "manifest.json").read_text(encoding="utf-8-sig"))
    out.append({**r, "match_score": mf.get("match_score"), "role_track": mf.get("role_track")})

out.sort(key=lambda x: (0 if x["category"].startswith("1-") else 1, -(x["match_score"] or 0), x["company"], x["job"]))
(ROOT / "outputs" / "fast-lane-pilot" / "priority-ai-pm-scored.json").write_text(
    json.dumps({"count": len(out), "rows": out}, ensure_ascii=False, indent=2), encoding="utf-8"
)
for i, x in enumerate(out[:30]):
    print(f"{i+1}. [{x['category']}] {x['company']}｜{x['job']} | score={x['match_score']} | track={x['role_track']} | src={x['source_row']}")
