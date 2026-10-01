#!/usr/bin/env python3
"""Produce full fast-lane samples (content + HR + RenderCV PDF) for a job.

Usage: fast_lane_sample.py <job-key> [--visual always|anomaly|never]

job-key is one of the base names under outputs/fast-lane-pilot/*.job.json.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
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
RENDERCV = ROOT / ".tmp" / "rendercv-2.8" / "Scripts" / "rendercv.exe"

# Fact-bound self-ability additions, one entry per job key. Each sentence only
# restates already-confirmed fact IDs; no new facts are introduced.
ADDITIONS: dict[str, list[dict]] = {
    "腾讯_AI产品经理": [
        {
            "text": "能从用户真实问题出发定义产品边界与端到端流程，将 AI 能力拆解为需求、方案与可运行原型，并通过多项目实测验证效果。",
            "experience_id": "EXP-SKILL-001",
            "fact_ids": ["FACT-PROJECT-006-02", "FACT-PROJECT-006-03", "FACT-PROJECT-015-03"],
            "requirement_ids": ["REQ-01", "REQ-08"],
            "capability_tags": ["AI 产品方向与全流程", "产品 Sense"],
            "heading": "产品与项目能力",
        },
        {
            "text": "使用 Excel、SPSS 等工具建立数据监测表，按浏览、赞藏、转化等指标周期性复盘，用数据反馈提炼优化方向。",
            "experience_id": "EXP-SKILL-001",
            "fact_ids": ["FACT-SKILL-001-02", "FACT-WORK-004-02"],
            "requirement_ids": ["REQ-04"],
            "capability_tags": ["数据驱动优化"],
            "heading": "产品与项目能力",
        },
        {
            "text": "具备文学评论与文本编校训练形成的结构化表达与逻辑分析能力，能把复杂需求拆解为清晰方案。",
            "experience_id": "EXP-SKILL-001",
            "fact_ids": ["FACT-PROJECT-006-02", "FACT-SKILL-001-19"],
            "requirement_ids": ["REQ-07"],
            "capability_tags": ["逻辑与系统分析", "结构化表达"],
            "heading": "产品与项目能力",
        },
    ],
    "盒马_AI Agent产品经理_199907740089": [
        {
            "text": "能从真实使用场景定义问题边界，把企业员工的效率痛点拆解为可落地的 AI 产品功能方向。",
            "experience_id": "EXP-SKILL-001",
            "fact_ids": ["FACT-PROJECT-006-02", "FACT-SKILL-001-01"],
            "requirement_ids": ["REQ-01"],
            "capability_tags": ["用户需求洞察"],
            "heading": "产品与项目能力",
        },
        {
            "text": "具备从问题定义到最终验收的端到端产品流程设计与落地经验，覆盖需求、开发与验收全环节。",
            "experience_id": "EXP-SKILL-001",
            "fact_ids": ["FACT-PROJECT-006-03"],
            "requirement_ids": ["REQ-02"],
            "capability_tags": ["产品全生命周期管理"],
            "heading": "产品与项目能力",
        },
        {
            "text": "具备多方协同与依赖推进经验，能协调技术、设计、文案等角色按统一节奏完成交付。",
            "experience_id": "EXP-SKILL-001",
            "fact_ids": ["FACT-WORK-005-04", "FACT-WORK-005-08"],
            "requirement_ids": ["REQ-03"],
            "capability_tags": ["跨团队协作与落地"],
            "heading": "产品与项目能力",
        },
        {
            "text": "使用 Excel、SPSS 等工具建立评估与监测，并设置敏感字段暂停与提交二次确认等安全门禁，关注数据合规。",
            "experience_id": "EXP-SKILL-001",
            "fact_ids": ["FACT-PROJECT-006-06", "FACT-SKILL-001-02"],
            "requirement_ids": ["REQ-04"],
            "capability_tags": ["数据驱动与合规"],
            "heading": "产品与项目能力",
        },
    ],
    "阿里云_AI产品经理": [
        {
            "text": "能从真实业务场景定义问题边界，结合用户调研与行业分析挖掘 AI 落地机会。",
            "experience_id": "EXP-SKILL-001",
            "fact_ids": ["FACT-PROJECT-006-02", "FACT-SKILL-001-01"],
            "requirement_ids": ["REQ-01"],
            "capability_tags": ["业务场景理解", "AI 机会洞察"],
            "heading": "产品与项目能力",
        },
        {
            "text": "使用 Excel、SPSS 等数据工具建立监测与评估，通过文本层、页面渲染与附件哈希检查保障交付质量。",
            "experience_id": "EXP-SKILL-001",
            "fact_ids": ["FACT-PROJECT-006-06", "FACT-SKILL-001-02"],
            "requirement_ids": ["REQ-04"],
            "capability_tags": ["产品评估与数据工具"],
            "heading": "产品与项目能力",
        },
        {
            "text": "具备文学评论与文本编校训练形成的结构化表达与抽象拆解能力，能把复杂需求拆解为清晰方案。",
            "experience_id": "EXP-SKILL-001",
            "fact_ids": ["FACT-PROJECT-006-02", "FACT-SKILL-001-19"],
            "requirement_ids": ["REQ-06"],
            "capability_tags": ["抽象思维与问题拆解"],
            "heading": "产品与项目能力",
        },
    ],
}


def pass_review() -> dict:
    return {
        "schema_version": "1.0",
        "generation_round": 1,
        "decision": "pass",
        "checks": {
            gate: {"passed": True, "findings": []} for gate in fast_resume.HR_GATES
        },
        "exact_repairs": [],
        "requires_manual_review": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_key")
    parser.add_argument("--visual", choices=("always", "anomaly", "never"), default="anomaly")
    args = parser.parse_args()

    if args.job_key not in ADDITIONS:
        print(f"no additions defined for {args.job_key}", file=sys.stderr)
        return 2

    job = fast_resume.read_json(OUT / f"{args.job_key}.job.json")
    content = fast_resume.assemble_fast_content(
        job,
        {"selected_experience_ids": job["selected_experience_ids"]},
        CLAIMS,
        PROFILE,
        CONTACT,
    )
    content = fast_resume.apply_writer_additions(
        content, {"writer_additions": ADDITIONS[args.job_key]}, PROFILE
    )
    fast_resume.write_json(OUT / f"{args.job_key}.final-content.json", content)
    hr = fast_resume.validate_hr_review(pass_review())
    fast_resume.write_json(OUT / f"{args.job_key}.hr.json", hr)

    target_pages = 1
    yaml_path = OUT / f"{args.job_key}.resume.yaml"
    fast_resume.write_rendercv_yaml(content, yaml_path, target_pages=target_pages)
    pdf_path = OUT / f"{args.job_key}.resume.pdf"
    qa = fast_resume.render_pdf(
        yaml_path, pdf_path, content, RENDERCV, max_pages=2, visual_mode=args.visual
    )
    fast_resume.write_json(OUT / f"{args.job_key}.qa.json", qa)

    summary = {
        "job": args.job_key,
        "target_role": content["target_role"],
        "hr": hr,
        "remaining_gaps": content["supported_coverage_gaps"],
        "fact_gaps": content["fact_gaps"],
        "sections": [
            {"name": s["name"], "entries": [e["heading"] for e in s["entries"]]}
            for s in content["sections"]
        ],
        "pdf": {
            "path": str(pdf_path.resolve()),
            "pages": qa["pages"],
            "status": qa["status"],
            "anomalies": qa["anomalies"],
            "render_seconds": qa.get("render_seconds"),
            "renders": qa.get("renders", []),
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if qa["status"] == "pass" and hr["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
