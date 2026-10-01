#!/usr/bin/env python3
"""Generate fast-lane route/assemble inputs for the 10 pilot AI-PM jobs.

This only maps each JD requirement to already-confirmed fact IDs from
profile/01-candidate-profile.md. It never invents facts. Requirements with no
confirmed evidence are left with an empty fact_ids list so route_job can flag
them as 待补事实 instead of silently keyword-matching.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(r"E:\zhuomian\简历\项目\Codex-求职助手")
SELECTION = ["EXP-WORK-005", "EXP-PROJECT-006", "EXP-PROJECT-015"]

# Fact IDs verified present in profile/01-candidate-profile.md.
F = {
    "content": "FACT-SKILL-001-01",
    "tools": "FACT-SKILL-001-02",
    "tech": "FACT-SKILL-001-03",
    "ai": "FACT-SKILL-001-04",
    "lang": "FACT-SKILL-001-05",
    "writing": "FACT-SKILL-001-19",
    "owner": "FACT-SKILL-001-22",
    "work_plan": "FACT-WORK-005-02",
    "work_coord": "FACT-WORK-005-04",
    "work_risk": "FACT-WORK-005-05",
    "work_scope": "FACT-WORK-005-08",
    "p006_problem": "FACT-PROJECT-006-02",
    "p006_flow": "FACT-PROJECT-006-03",
    "p006_prompt": "FACT-PROJECT-006-04",
    "p006_test": "FACT-PROJECT-006-06",
    "p015_agent": "FACT-PROJECT-015-02",
    "p015_effect": "FACT-PROJECT-015-03",
    "p016_agent": "FACT-PROJECT-016-02",
    "p017_edu": "FACT-PROJECT-017-03",
    "edu1": "FACT-EDU-001-01",
    "edu2": "FACT-EDU-002-01",
    "social_data": "FACT-WORK-004-02",
}


def req(rid: str, text: str, facts: list[str] | None, required: bool = True) -> dict:
    return {
        "requirement_id": rid,
        "text": text,
        "fact_ids": facts or [],
        "required": required,
    }


def make_job(company: str, role: str, role_track: str, requirements: list[dict]) -> dict:
    return {
        "company": company,
        "target_role": role,
        "role_family": "ai_product_manager",
        "role_track": role_track,
        "context": "non_game",
        "jd_complete": True,
        "requirements": requirements,
        "selected_experience_ids": SELECTION,
    }


JOBS: dict[str, dict] = {}


# 1. 字节跳动 评测产品经理 AI Platform
JOBS["字节跳动_评测产品经理-AIPlatform-A69940"] = make_job(
    "字节跳动",
    "评测产品经理 - AI Platform",
    "llm_ai_product_manager",
    [
        req("REQ-01", "LLM/AgentOps 平台评测产品规划与需求调研", [F["p006_problem"], F["ai"]]),
        req("REQ-02", "与应用开发者、社区沟通并设计 AI 产品方案", [F["work_coord"], F["p006_problem"]]),
        req("REQ-03", "与研发协作推动产品发布与项目落地", [F["work_scope"], F["p006_flow"]]),
        req("REQ-04", "技术理解能力与大模型技术兴趣", [F["ai"], F["p015_agent"]]),
        req("REQ-05", "逻辑思维、自主学习与跨部门沟通协调", [F["writing"], F["owner"], F["work_coord"]]),
        req("REQ-06", "AI 评测产品经验（优先）", None, required=False),
    ],
)

# 2. 字节跳动 Agent产品经理 AI算力基础设施
JOBS["字节跳动_Agent产品经理-AI算力基础设施-A72879"] = make_job(
    "字节跳动",
    "Agent产品经理 - AI算力基础设施",
    "agent_product_manager",
    [
        req("REQ-01", "参与 Agent 产品建设与迭代", [F["p015_agent"], F["ai"]]),
        req("REQ-02", "用户/产品调研与数据分析，产出需求文档并推进落地", [F["p006_problem"], F["tools"], F["social_data"]]),
        req("REQ-03", "跟踪上线效果与用户反馈，优化产品功能", [F["p015_effect"], F["p006_test"]]),
        req("REQ-04", "通过培训与文档支持用户高效使用 AI 平台", [F["p017_edu"], F["content"]]),
        req("REQ-05", "逻辑清晰、问题分析与解决能力", [F["writing"], F["p006_problem"]]),
        req("REQ-06", "沟通与团队合作能力", [F["work_coord"]]),
        req("REQ-07", "产品实习经历（优先）", [F["work_scope"]], required=False),
    ],
)

# 3. 字节跳动 AI产品经理(研发平台方向) 开发者服务
JOBS["字节跳动_AI产品经理（研发平台方向）-开发者服务-A259118"] = make_job(
    "字节跳动",
    "AI产品经理（研发平台方向） - 开发者服务",
    "ai_product_manager",
    [
        req("REQ-01", "研究大模型在研发场景的应用，制定产品策略与规划", [F["p006_problem"], F["p006_flow"], F["ai"]]),
        req("REQ-02", "了解大模型技术并对接技术团队", [F["ai"], F["tech"]]),
        req("REQ-03", "整合产品资源，协调研发、设计、运营推进上市", [F["work_scope"], F["work_coord"]]),
        req("REQ-04", "根据用户需求持续优化产品体验与竞争力", [F["p015_effect"]]),
        req("REQ-05", "掌握行业动态，为产品创新提供思路", [F["ai"]]),
        req("REQ-06", "技术理解能力与大模型兴趣", [F["ai"]]),
        req("REQ-07", "创新产品见解，把内部研发场景机会转为产品需求", [F["p006_problem"]]),
        req("REQ-08", "AI Coding / 通用 Agent 产品经验（优先）", [F["p015_agent"], F["ai"]], required=False),
    ],
)

# 4. 字节跳动 大模型产品经理 数据平台
JOBS["字节跳动_大模型产品经理-数据平台-A258309"] = make_job(
    "字节跳动",
    "大模型产品经理 - 数据平台",
    "llm_ai_product_manager",
    [
        req("REQ-01", "打造多模态数据湖 / 大模型数据基础设施产品", [F["ai"], F["p006_problem"]]),
        req("REQ-02", "面向 LLM/多模态/Agent 提供数据处理与管理能力", [F["ai"], F["p015_agent"]]),
        req("REQ-03", "市场调研与 B 端客户需求梳理，商业化产品方案", [F["p006_problem"], F["content"]]),
        req("REQ-04", "产品功能设计并推动研发交付与商业闭环", [F["p006_flow"], F["work_scope"]]),
        req("REQ-05", "掌握至少一门编程语言（Python/Java/C 等）", [F["tech"]]),
        req("REQ-06", "自驱、持续学习、结果导向、开放包容", [F["owner"]]),
        req("REQ-07", "逻辑分析，对业务逻辑抽象与拆分", [F["writing"], F["p006_problem"]]),
    ],
)

# 5. 阿里云 AI产品经理
JOBS["阿里云_AI产品经理"] = make_job(
    "阿里云",
    "AI产品经理",
    "general_ai_product",
    [
        req("REQ-01", "业务场景理解，用户调研与行业分析挖掘 AI 落地机会", [F["p006_problem"], F["content"]]),
        req("REQ-02", "AI 应用/平台方案设计：功能定义、Workflow 编排、Prompt 设计", [F["p015_agent"], F["ai"]]),
        req("REQ-03", "与算法/后端协作，把 LLM/多模态/Agent/RAG 转成产品功能", [F["ai"], F["work_coord"]]),
        req("REQ-04", "建立产品评估体系，用数据工具监控指标并优化体验", [F["tools"], F["p006_test"]]),
        req("REQ-05", "了解 AIGC（文本/图像/视频生成、提示词工程）", [F["ai"]]),
        req("REQ-06", "抽象思维与问题拆解能力", [F["writing"], F["p006_problem"]]),
        req("REQ-07", "SQL/Python 数据处理（优先）", [F["tech"]], required=False),
    ],
)

# 6. 腾讯 AI产品经理
JOBS["腾讯_AI产品经理"] = make_job(
    "腾讯",
    "AI产品经理",
    "general_ai_product",
    [
        req("REQ-01", "定义 AI 产品方向，需求定义、方案设计与效果验证闭环", [F["p006_problem"], F["p006_flow"], F["p015_effect"]]),
        req("REQ-02", "理解 LLM/MLLM/Agent/RAG/多模态能力与局限", [F["ai"], F["p015_agent"]]),
        req("REQ-03", "设计 AI 交互体验，建立 AI 产品体验指标", [F["p015_agent"], F["ai"]]),
        req("REQ-04", "数据实验（A/B、行为分析、漏斗）优化产品策略", [F["tools"], F["social_data"]]),
        req("REQ-05", "追踪 AI 前沿并转化为产品机会", [F["ai"]]),
        req("REQ-06", "洞察思维与把想法变为现实", [F["owner"], F["p015_effect"]]),
        req("REQ-07", "逻辑思维、系统分析、技术/商业敏感度", [F["writing"], F["p006_problem"]]),
        req("REQ-08", "产品 Sense、用户同理心与全流程思考", [F["p006_problem"]]),
        req("REQ-09", "计算机背景 / 产品实习 / AI 原型经验（加分）", [F["work_scope"], F["ai"]], required=False),
    ],
)

# 7. 盒马 AI Agent产品经理
JOBS["盒马_AI Agent产品经理_199907740089"] = make_job(
    "盒马",
    "AI Agent产品经理",
    "agent_product_manager",
    [
        req("REQ-01", "用户需求洞察，调研企业员工场景并转化为 AI 产品功能", [F["p006_problem"], F["content"]]),
        req("REQ-02", "企业级 AI 效率产品全生命周期管理", [F["p006_flow"]]),
        req("REQ-03", "联动技术、算法、设计团队推动功能落地", [F["work_coord"], F["work_scope"]]),
        req("REQ-04", "数据驱动优化，建立产品效果评估体系，关注 AI 伦理与数据安全", [F["p006_test"], F["tools"]]),
        req("REQ-05", "行业前瞻调研，探索 AI 企业效率创新应用", [F["ai"]]),
        req("REQ-06", "熟悉 AI 基础技术框架并与技术团队沟通", [F["ai"]]),
        req("REQ-07", "从员工视角拆解复杂任务，设计轻量化 AI 方案", [F["p006_problem"], F["owner"]]),
        req("REQ-08", "熟悉企业服务/RPA/低代码，Prompt 工程或 AIGC 实践", [F["ai"], F["tools"]]),
        req("REQ-09", "SQL/Python 数据分析（优先）", [F["tech"]], required=False),
        req("REQ-10", "逻辑清晰，把抽象需求转为方案，自驱", [F["writing"], F["owner"]]),
    ],
)

# 8. 蚂蚁集团 AI产品经理
JOBS["蚂蚁集团_AI产品经理_260721011010330"] = make_job(
    "蚂蚁集团",
    "AI产品经理",
    "agent_product_manager",
    [
        req("REQ-01", "定义 Agent 的 Planning/Reflection/Memory 策略", [F["p015_agent"], F["ai"]]),
        req("REQ-02", "探索意图驱动的流式 UI 与动态组件生成", []),
        req("REQ-03", "编排客服/数据/ERP 场景工作流与 Human-in-the-loop", [F["p006_flow"]]),
        req("REQ-04", "结构化 Prompt，配合 RAG/Function Calling/向量库控制幻觉", [F["ai"], F["p006_prompt"]]),
        req("REQ-05", "建立交互/任务成功率指标，Bad Case 复盘与 A/B 迭代", [F["p006_test"], F["tools"]]),
        req("REQ-06", "LLM/Agent 落地案例（优先）", [F["p015_agent"], F["p016_agent"]], required=False),
        req("REQ-07", "掌握 Transformer/Token/RAG，理解 ReAct/CoT/Multi-Agent", [F["ai"]], required=False),
        req("REQ-08", "深度使用 LangChain/Dify/Coze/LangGraph 等框架", [F["tools"]], required=False),
        req("REQ-09", "Prompt 逻辑拆解，控制模型输出稳定与质量", [F["ai"], F["writing"]]),
        req("REQ-10", "跟踪新技术（HuggingFace/GitHub/X）", [F["ai"]], required=False),
    ],
)

# 9. 阿里巴巴-千问办公 AI产品经理-智能体
JOBS["阿里巴巴-千问办公_AI产品经理-智能体"] = make_job(
    "阿里巴巴-千问办公",
    "AI产品经理-智能体",
    "agent_product",
    [
        req("REQ-01", "主导 Agent 与人协作产品设计与迭代", [F["p015_agent"]]),
        req("REQ-02", "研究用户场景痛点，建立反馈闭环驱动体验优化", [F["p006_problem"]]),
        req("REQ-03", "与工程/设计/运营及 Agent 协作，推动 0 到 1 及规模化增长", [F["work_coord"], F["p006_flow"]]),
        req("REQ-04", "定义并跟踪核心产品指标（DAU/留存/NPS），数据驱动决策", [F["social_data"], F["tools"]]),
        req("REQ-05", "行业动态与竞品分析，保持产品竞争力", [F["ai"]]),
        req("REQ-06", "熟悉 AI 基础技术框架并与技术团队沟通", [F["ai"]]),
        req("REQ-07", "从员工视角拆解复杂任务，设计低学习成本 AI 方案", [F["p006_problem"], F["owner"]]),
        req("REQ-08", "熟悉企业服务/RPA/低代码，Prompt 工程或 AIGC 实践", [F["ai"], F["tools"]]),
        req("REQ-09", "SQL/Python 分析用户行为（优先）", [F["tech"]], required=False),
        req("REQ-10", "逻辑清晰，抽象需求转方案，自驱", [F["writing"], F["owner"]]),
    ],
)

# 10. 小米 AI Agent产品经理
JOBS["小米_AIAgent产品经理_7670928765471852843"] = make_job(
    "小米",
    "AI Agent产品经理",
    "agent_product_manager",
    [
        req("REQ-01", "AI Agent 平台核心产品规划：智能体全生命周期、任务编排、Skill 体系", [F["p015_agent"], F["ai"]]),
        req("REQ-02", "识别业务场景（办公协同/流程自动化/知识管理）机会，产出需求文档与交互方案", [F["p006_problem"]]),
        req("REQ-03", "与工程/算法协作，把大模型/Agent 框架/MCP 转成平台功能", [F["ai"], F["work_coord"]]),
        req("REQ-04", "建立产品效果评估体系（成功率/采纳率/成本），数据驱动优化", [F["p006_test"], F["tools"]]),
        req("REQ-05", "跨域协同推动交付，跟踪 Agent 竞品并输出分析", [F["work_scope"], F["ai"]]),
        req("REQ-06", "大模型/LLM/NLP/Agent 技术认知，理解边界与产品化路径", [F["ai"], F["p015_agent"]]),
        req("REQ-07", "需求分析、用户研究、交互设计、数据分析等产品基本功", [F["p006_problem"], F["tools"], F["social_data"]]),
        req("REQ-08", "逻辑与结构化表达，产品文档与方案汇报", [F["writing"], F["p006_prompt"]]),
    ],
)


def main() -> None:
    out_root = ROOT / "outputs" / "fast-lane-pilot"
    out_root.mkdir(parents=True, exist_ok=True)
    for name, job in JOBS.items():
        path = out_root / f"{name}.job.json"
        path.write_text(
            json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"wrote {len(JOBS)} job files to {out_root}")


if __name__ == "__main__":
    main()
