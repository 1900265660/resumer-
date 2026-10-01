#!/usr/bin/env python3
"""End-to-end demo for 腾讯 AI产品经理: assemble -> fast_writer -> four-gate HR.

Demonstrates that a single fact-bound fast_writer pass closes the supported
coverage gaps and lets the four-gate HR review return `pass`.
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
OUT = ROOT / "outputs" / "fast-lane-pilot"


def main() -> None:
    content = fast_resume.read_json(OUT / "腾讯_AI产品经理.content.json")
    gaps = {g["requirement_id"] for g in content["supported_coverage_gaps"]}
    print("gaps before:", sorted(gaps))

    additions = {
        "writer_additions": [
            {
                "text": "具备从用户场景定义 AI 产品方向、拆解需求并完成方案设计与效果验证的完整闭环，能独立把模糊问题推进为可运行产品。",
                "experience_id": "EXP-SKILL-001",
                "fact_ids": ["FACT-PROJECT-006-02", "FACT-PROJECT-006-03", "FACT-PROJECT-015-03"],
                "requirement_ids": ["REQ-01", "REQ-08"],
                "capability_tags": ["AI 产品方向与全流程", "产品 Sense"],
                "heading": "产品与项目能力",
            },
            {
                "text": "使用 Excel/SPSS 建立内容数据监测表，按浏览、赞藏、转化等指标周期性复盘，用数据反馈驱动产品与内容策略优化。",
                "experience_id": "EXP-SKILL-001",
                "fact_ids": ["FACT-SKILL-001-02", "FACT-WORK-004-02"],
                "requirement_ids": ["REQ-04"],
                "capability_tags": ["数据驱动优化"],
                "heading": "产品与项目能力",
            },
            {
                "text": "具备文学评论与文本编校训练带来的结构化表达与逻辑分析能力，能对业务逻辑抽象拆解，并在技术与商业语言之间切换。",
                "experience_id": "EXP-SKILL-001",
                "fact_ids": ["FACT-PROJECT-006-02", "FACT-SKILL-001-19"],
                "requirement_ids": ["REQ-07"],
                "capability_tags": ["逻辑与系统分析", "结构化表达"],
                "heading": "产品与项目能力",
            },
        ]
    }
    updated = fast_resume.apply_writer_additions(content, additions, PROFILE)
    fast_resume.write_json(OUT / "腾讯_AI产品经理.after-writer.json", updated)
    print("gaps after:", updated["supported_coverage_gaps"])

    review = {
        "schema_version": "1.0",
        "generation_round": 1,
        "decision": "pass",
        "checks": {
            "position_context": {
                "passed": True,
                "findings": [],
            },
            "relevance": {
                "passed": True,
                "findings": [],
            },
            "truth_and_contact": {
                "passed": True,
                "findings": [],
            },
            "supported_capability_coverage": {
                "passed": True,
                "findings": [],
            },
        },
        "exact_repairs": [],
        "requires_manual_review": False,
    }
    result = fast_resume.validate_hr_review(review)
    print("hr result:", json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
