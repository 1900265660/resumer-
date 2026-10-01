#!/usr/bin/env python3
"""Pick the first 20 AI-product-track priority-rewrite jobs for the next batch."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(r"E:\zhuomian\简历\项目\Codex-求职助手")
rows = json.loads(
    (ROOT / "outputs" / "fast-lane-pilot" / "priority-ai-pm-scored.json").read_text(encoding="utf-8")
)["rows"]

PRODUCT_TRACKS = {
    "ai_product_manager",
    "agent_product_manager",
    "general_ai_product",
    "consumer_ai_product",
    "llm_ai_product_manager",
    "technical_ai_product",
    "hr_ai_product",
    "ecommerce_ai_product",
    "ai_product",
    "ai_product_operations",
}

picked = [r for r in rows if (r.get("role_track") in PRODUCT_TRACKS)]
if len(picked) > 20:
    picked = picked[:20]

(ROOT / "outputs" / "fast-lane-pilot" / "batch20.json").write_text(
    json.dumps({"count": len(picked), "rows": picked}, ensure_ascii=False, indent=2), encoding="utf-8"
)
for i, r in enumerate(picked):
    print(f"{i+1}. [{r['category']}] {r['company']}｜{r['job']} | score={r['match_score']} | track={r['role_track']} | src={r['source_row']} | {r['app_dir']}")
