#!/usr/bin/env python3
"""Generate fast-lane job inputs for the 20 AI-PM batch jobs.

Each JD requirement maps only to confirmed fact IDs in the candidate profile.
Unsupported/priority-only requirements keep an empty fact_ids list so routing
can flag them honestly (待补事实) rather than fake a keyword match.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(r"E:\zhuomian\简历\项目\Codex-求职助手")
SELECTION = ["EXP-WORK-005", "EXP-PROJECT-006", "EXP-PROJECT-015"]

F = {
    "ai": "FACT-SKILL-001-04",
    "tech": "FACT-SKILL-001-03",
    "tools": "FACT-SKILL-001-02",
    "content": "FACT-SKILL-001-01",
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
    "p016_py": "FACT-PROJECT-016-01",
    "p017_edu": "FACT-PROJECT-017-03",
    "social_data": "FACT-WORK-004-02",
    "edu1": "FACT-EDU-001-01",
    "edu2": "FACT-EDU-002-01",
}


def req(rid: str, text: str, facts: list[str] | None, required: bool = True) -> dict:
    return {"requirement_id": rid, "text": text, "fact_ids": facts or [], "required": required}


def job(company: str, role: str, track: str, reqs: list[dict]) -> dict:
    return {
        "company": company,
        "target_role": role,
        "role_family": "ai_product_manager",
        "role_track": track,
        "context": "non_game",
        "jd_complete": True,
        "requirements": reqs,
        "selected_experience_ids": SELECTION,
    }


# Common capability requirement templates (fact-bound).
def ai_tech(rid, text="理解 LLM/Agent/RAG/Prompt 等 AI 技术边界"):
    return req(rid, text, [F["ai"], F["p015_agent"]])


def product_design(rid, text="产品需求分析、方案设计与从 0 到 1 推进"):
    return req(rid, text, [F["p006_problem"], F["p006_flow"], F["p015_agent"]])


def user_research(rid, text="用户调研、需求洞察与数据分析"):
    return req(rid, text, [F["p006_problem"], F["tools"], F["social_data"]])


def collab(rid, text="跨团队协作与项目落地推进"):
    return req(rid, text, [F["work_coord"], F["work_scope"]])


def logic(rid, text="逻辑思维与结构化表达"):
    return req(rid, text, [F["writing"], F["p006_problem"]])


def ownership(rid, text="自驱、结果导向与主动推进"):
    return req(rid, text, [F["owner"]])


def metrics(rid, text="建立评估指标体系，数据驱动优化"):
    return req(rid, text, [F["p006_test"], F["tools"], F["social_data"]])


JOBS: dict[str, dict] = {}

JOBS["三七互娱_AI产品经理_HR方向"] = job(
    "三七互娱", "AI产品经理 （HR方向）", "hr_ai_product",
    [
        req("REQ-01", "深入 HR 业务场景，通过访谈、流程梳理与数据分析识别痛点，提炼 AI 产品机会", [F["p006_problem"], F["tools"], F["social_data"]]),
        product_design("REQ-02", "从需求定义、方案设计到原型/MVP 验证与上线迭代"),
        collab("REQ-03", "协同 HR 专家、研发、数据及外部方推进交付并闭环"),
        ai_tech("REQ-04", "跟踪大模型/Agent 趋势，动手完成场景测试与原型实践"),
        logic("REQ-05", "学习与抽象能力、用户洞察、需求分析与逻辑表达"),
        ownership("REQ-06", "自驱、好奇、结果导向与跨团队沟通"),
    ],
)

JOBS["京东_技术产品经理_9085"] = job(
    "京东", "技术产品经理", "technical_ai_product",
    [
        req("REQ-01", "负责 B 端/C 端产品策划，设计技术产品架构与功能需求", [F["p006_problem"], F["p006_flow"]]),
        req("REQ-02", "参与 AI 产品全流程设计：需求调研、场景挖掘、原型与 MVP 验证", [F["p006_problem"], F["p006_flow"], F["p015_agent"]]),
        metrics("REQ-03", "构建 AI 产品效果评估体系与优化策略"),
        user_research("REQ-04", "基于 A/B、用户行为与反馈数据推动产品迭代"),
        ai_tech("REQ-05", "对 AI 技术与生成式应用有基础认知，主动运用 AI 工具提效"),
        logic("REQ-06", "逻辑思维、理解沟通协调与文字表达"),
        req("REQ-07", "熟练使用 AI 原型设计工具（优先）", [F["tools"], F["p015_agent"]], required=False),
    ],
)

JOBS["作业帮_AI产品经理（AI业务）-27秋招"] = job(
    "作业帮", "AI产品经理（AI业务）-27秋招", "consumer_ai_product",
    [
        req("REQ-01", "负责 AI 对话与内容生成产品设计，自主推进 0 到 1 全流程", [F["p006_problem"], F["p006_flow"], F["p015_agent"]]),
        metrics("REQ-02", "基于数据表现持续迭代产品，提升体验与用户规模"),
        ai_tech("REQ-03", "跟进 AI 行业动态，将新技术落地应用"),
        collab("REQ-04", "沟通能力与热爱产品经理岗位"),
        logic("REQ-05", "逻辑思维与市场敏感度"),
        req("REQ-06", "互联网大厂产品实习经验（优先）", [F["work_scope"]], required=False),
    ],
)

JOBS["字节跳动_AI产品经理-Aime-A137569B"] = job(
    "字节跳动", "AI产品经理 - Aime", "ai_product_manager",
    [
        req("REQ-01", "企业级 AI Agent 平台产品设计：通用 Agent 架构、任务链路、交互与工作流", [F["p015_agent"], F["p006_flow"], F["ai"]]),
        ai_tech("REQ-02", "任务规划、工具调用、RAG、Memory、Workflow 等能力产品化"),
        req("REQ-03", "面向研发/产品/运营场景完成需求分析、策略与功能设计并推动落地", [F["p006_problem"], F["work_scope"]]),
        metrics("REQ-04", "建立任务过程、结果质量与业务价值评估指标体系"),
        req("REQ-05", "用户洞察与产品设计，把关键痛点转为需求与方案", [F["p006_problem"], F["p015_agent"]]),
        logic("REQ-06", "学习能力、逻辑思维与跨团队协作"),
        req("REQ-07", "AI Agent/Copilot/复杂 B 端产品实习或项目经验（优先）", [F["p015_agent"], F["p006_flow"]], required=False),
    ],
)

JOBS["字节跳动_AI产品经理-TRAE-A179614"] = job(
    "字节跳动", "AI产品经理 - TRAE", "ai_product_manager",
    [
        req("REQ-01", "建设 AI 产品 TRAE：用户调研、行业分析、产品与用户体验设计", [F["p006_problem"], F["p006_flow"], F["content"]]),
        collab("REQ-02", "与运营/市场/开发者/用户社区协作，传递产品价值并落实需求"),
        req("REQ-03", "与研发/算法/测试协作提升端到端 AI 效果，推动上线", [F["ai"], F["work_scope"]]),
        req("REQ-04", "了解 NLP/机器学习/LLM 基础原理", [F["ai"]]),
        req("REQ-05", "英语读写能力，能阅读产品/技术文档与论文", [F["lang"]]),
        logic("REQ-06", "主人翁精神、逻辑思维、创新与分析能力"),
        ownership("REQ-07", "责任感与跨团队协作，以用户价值为先"),
    ],
)

JOBS["字节跳动_AI产品经理（AI-通用场景方向）-集团信息系统-A178122"] = job(
    "字节跳动", "AI产品经理（AI-通用场景方向） - 集团信息系统", "ai_product_manager",
    [
        req("REQ-01", "AI Agent 产品规划与设计：智能体构建、知识问答 RAG", [F["p015_agent"], F["ai"]]),
        req("REQ-02", "抽象企业用户核心需求，通过访谈、数据分析和用户行为洞察", [F["p006_problem"], F["tools"], F["social_data"]]),
        metrics("REQ-03", "测评集构建与优化，跟踪产品效果与模型表现"),
        ai_tech("REQ-04", "关注 AIGC 应用创新，探索办公自动化、知识管理、内容生成实践"),
        req("REQ-05", "熟悉 Claude Code/Cursor/扣子等 Agent 工具，有搭建 Agent 或 AI 应用经验（优先）", [F["ai"], F["tools"], F["p015_agent"]], required=False),
        req("REQ-06", "编程基础，理解 API 调用、Prompt Engineering（优先）", [F["tech"], F["p006_prompt"]], required=False),
    ],
)

JOBS["字节跳动_AI产品经理（感知Agent平台方向）-TikTok-A259199"] = job(
    "字节跳动", "AI产品经理（感知Agent平台方向） - TikTok", "agent_product_manager",
    [
        req("REQ-01", "内容安全风险发现与处置平台搭建，主导产品路线规划与需求管理", [F["p006_problem"], F["p006_flow"], F["work_scope"]]),
        collab("REQ-02", "与业务团队协作，深入视频/直播场景挖掘痛点并拆解为方案"),
        ai_tech("REQ-03", "运用 LLM 提升风险处置效率，含内容排查、检测模型与策略优化"),
        metrics("REQ-04", "上线后数据分析与模型效果评估，推动产品迭代"),
        logic("REQ-05", "逻辑分析与策略推演，对数据与文档严谨细致"),
        req("REQ-06", "熟悉大模型原理，具备 Prompt Engineering 调优经验（优先）", [F["ai"], F["p006_prompt"]], required=False),
        req("REQ-07", "英语听写与沟通能力", [F["lang"]]),
    ],
)

JOBS["字节跳动_AI产品经理（营销Agent方向）-抖音电商-A251896"] = job(
    "字节跳动", "AI产品经理（营销Agent方向） - 抖音电商", "agent_product_manager",
    [
        req("REQ-01", "商家营销 Agent 产品规划与设计，拆解业务问题并设计可落地方案", [F["p006_problem"], F["p015_agent"], F["p006_flow"]]),
        ai_tech("REQ-02", "结合 AI/算法/策略推动营销诊断、策略建议、任务执行与效果复盘"),
        collab("REQ-03", "协同研发、算法、设计、运营、数据推动项目落地与验收"),
        metrics("REQ-04", "基于数据表现与用户反馈持续优化产品"),
        logic("REQ-05", "逻辑思维与问题拆解，从复杂场景抓关键问题"),
        ownership("REQ-06", "自驱、认真、负责，能在不确定环境中持续学习推进"),
        req("REQ-07", "产品/数据分析/AI 应用/电商运营实习或项目经验（优先）", [F["work_scope"], F["social_data"]], required=False),
    ],
)

JOBS["字节跳动_Agent产品经理-AI算力基础设施-A72879"] = job(
    "字节跳动", "Agent产品经理 - AI算力基础设施", "agent_product_manager",
    [
        req("REQ-01", "参与 Agent 产品建设与迭代", [F["p015_agent"], F["ai"]]),
        user_research("REQ-02", "通过用户/产品调研与数据分析挖掘需求，产出需求文档并推进落地"),
        metrics("REQ-03", "跟踪上线效果与用户反馈，为功能优化提供建议"),
        req("REQ-04", "通过培训、教学文档支持用户高效使用 AI 平台", [F["p017_edu"], F["content"]]),
        logic("REQ-05", "逻辑清晰，问题分析与解决能力"),
        collab("REQ-06", "沟通与团队合作，与多团队紧密协作"),
        req("REQ-07", "产品实习经历（优先）", [F["work_scope"]], required=False),
    ],
)

JOBS["转转_产品经理_710ea802-8427-4a8f-bd30-983f9dc3a657"] = job(
    "转转", "产品经理", "ecommerce_ai_product",
    [
        req("REQ-01", "参与 B 端/C 端/搜索/大数据产品规划与设计，覆盖核心业务场景", [F["p006_problem"], F["p006_flow"]]),
        user_research("REQ-02", "通过数据分析、用户调研、竞品研究挖掘产品机会并转方案"),
        metrics("REQ-03", "指标拆解、产品机制设计、A/B 实验设计与效果复盘"),
        ai_tech("REQ-04", "结合 AI/大模型/数据智能探索搜索语义、智能问答、流程自动化落地"),
        collab("REQ-05", "协同研发、算法、设计、数据、运营等推进全流程高质量交付"),
        logic("REQ-06", "逻辑思维与数据意识"),
    ],
)

JOBS["淘宝闪购_AI产品经理"] = job(
    "阿里巴巴-淘宝闪购", "AI产品经理", "general_ai_product",
    [
        user_research("REQ-01", "深入业务场景，通过用户调研与行业分析挖掘 AI 落地机会"),
        req("REQ-02", "AI 应用/平台方案设计：功能定义、Workflow 编排与 Prompt 设计", [F["p015_agent"], F["ai"], F["p006_prompt"]]),
        ai_tech("REQ-03", "与算法/后端协作，把 LLM/多模态/Agent/RAG 转成产品功能"),
        metrics("REQ-04", "建立产品评估体系，用数据工具监控指标并优化体验"),
        req("REQ-05", "了解 AIGC（文本/图像/视频生成、提示词工程）", [F["ai"]]),
        logic("REQ-06", "抽象思维与问题拆解"),
        req("REQ-07", "SQL/Python 数据处理（优先）", [F["tech"], F["p016_py"]], required=False),
    ],
)

JOBS["小红书_RPT点点产品"] = job(
    "小红书", "小红书产品经理培训生（RPT）—点点产品", "consumer_ai_product",
    [
        req("REQ-01", "参与 AI 搜索、对话策略、记忆系统建设，定义好答案标准", [F["p015_agent"], F["ai"], F["p006_problem"]]),
        req("REQ-02", "社区特色 Agent 场景挖掘与任务规划，形成陪伴用户决策的 Agent", [F["p015_agent"], F["p006_problem"]]),
        req("REQ-03", "面向截图/笔记/语音/实拍等输入方式进行产品设计与创新", [F["p006_problem"], F["p006_flow"]]),
        req("REQ-04", "从大规模数据中发现问题，以 AI Native 视角重新定义解法", [F["tools"], F["social_data"], F["ai"]]),
        ownership("REQ-05", "持续思考进化，面对不确定性有韧性，自驱"),
    ],
)

JOBS["快手_AIAgent产品经理"] = job(
    "快手", "AI Agent 产品经理", "ai_product",
    [
        req("REQ-01", "AI Agent 产品全生命周期：需求调研、产品规划、方案设计、版本迭代", [F["p006_problem"], F["p015_agent"], F["p006_flow"]]),
        ai_tech("REQ-02", "利用提示词工程、知识库构建等方式提升产品交互体验"),
        req("REQ-03", "理解机器学习/深度学习/LLM 原理，把业务需求转为算法可实现方案", [F["ai"], F["p015_agent"]]),
        metrics("REQ-04", "建立产品评估指标体系，通过用户反馈与数据分析优化体验"),
        req("REQ-05", "熟练使用 Python 进行数据分析和基础开发（优先）", [F["tech"], F["p016_py"]], required=False),
        logic("REQ-06", "产品敏感度、理解用户与需求、思维独立与执行力"),
    ],
)

JOBS["淘宝闪购_AI产品运营"] = job(
    "阿里巴巴-淘宝闪购", "AI产品运营", "ai_product_operations",
    [
        user_research("REQ-01", "深入业务场景，通过用户研究与竞品分析定义 AI 赋能产品方案"),
        ai_tech("REQ-02", "Prompt 优化、标签体系梳理、特征质量管理，与算法/研发协作部署"),
        metrics("REQ-03", "AI 模型指标跟踪、灰度发布与效果监控，评估稳定性与一致性"),
        req("REQ-04", "监控核心指标，用 SQL/Python 数据挖掘与实验评估", [F["tools"], F["p006_test"], F["social_data"]]),
        req("REQ-05", "AIGC 产品内容包装与创意传播，提升活跃度与忠诚度", [F["content"], F["social_data"]]),
        logic("REQ-06", "逻辑思维与结构化拆解，把复杂业务抽象为算法可解决问题"),
        req("REQ-07", "熟练掌握 SQL，熟悉 Python/Pandas 或机器学习指标（优先）", [F["tech"]], required=False),
    ],
)

JOBS["字节跳动_AIMV音乐产品经理（抖音AI产品人才校招）-抖音音乐-A251855"] = job(
    "字节跳动", "AIMV音乐产品经理（抖音AI产品人才校招） - 抖音音乐", "ai_product_manager",
    [
        req("REQ-01", "AI 音乐可视化创作工具产品规划、定位、功能方案与迭代路线", [F["p006_problem"], F["p006_flow"], F["content"]]),
        metrics("REQ-02", "建立生成效果评估方法与标注规范，数据驱动产品与模型优化"),
        collab("REQ-03", "联动研发、算法、设计、运营推进版本开发与上线，把控进度与风险"),
        req("REQ-04", "跟踪核心数据，结合用户反馈与市场动态迭代产品", [F["social_data"], F["p006_test"]]),
        ai_tech("REQ-05", "理解大模型技术边界，探索新一代 AI 创作人机交互范式"),
        logic("REQ-06", "逻辑清晰、结构化思维，独立产出需求文档与产品方案"),
        req("REQ-07", "AI 创作工具/音视频/内容平台实习经验（优先）", [F["content"], F["work_scope"]], required=False),
    ],
)

JOBS["字节跳动_AI产品经理-TikTokShop-A94415"] = job(
    "字节跳动", "AI产品经理 - TikTok Shop", "ai_product_manager",
    [
        req("REQ-01", "国际电商 AIGC、AI 导购产品，与算法/工程协作支持高效迭代", [F["p015_agent"], F["ai"], F["p006_flow"]]),
        ai_tech("REQ-02", "建设面向商家/达人/运营的 AI 内容生成平台，结合模型评测与用户调研迭代"),
        metrics("REQ-03", "迭代算法策略，提升内容供给效率与转化效果"),
        req("REQ-04", "理解大模型能力边界，把前沿 AI 技术转化为用户价值", [F["ai"], F["p015_agent"]]),
        req("REQ-05", "业务理解与商业感，敏锐捕捉用户需求", [F["p006_problem"], F["social_data"]]),
        collab("REQ-06", "学习能力、沟通协作与项目管理，确保按时按质完成"),
    ],
)

JOBS["字节跳动_AI产品经理-TikTok直播-A164910"] = job(
    "字节跳动", "AI产品经理 - TikTok直播", "ai_product_manager",
    [
        req("REQ-01", "面向主播/公会运营场景探索 AI 招募、服务、调优工具", [F["p015_agent"], F["p006_problem"]]),
        req("REQ-02", "AI 对话式问答入口与知识库建设，保证多轮澄清、引用溯源、反馈闭环体验", [F["p006_prompt"], F["ai"], F["p006_flow"]]),
        req("REQ-03", "把运营 SOP/FAQ/规则沉淀为可配置工具包，支持快速复制", [F["p006_prompt"], F["content"]]),
        metrics("REQ-04", "搭建指标体系，通过灰度与实验持续优化"),
        ai_tech("REQ-05", "了解基础大模型训练原理，熟悉国内外直播产品"),
        req("REQ-06", "英语听写与沟通能力", [F["lang"]]),
        ownership("REQ-07", "需求洞察、自驱、责任感"),
    ],
)

JOBS["字节跳动_AI产品经理-TikTok直播-A26432A"] = job(
    "字节跳动", "AI产品经理 - TikTok直播", "ai_product_manager",
    [
        req("REQ-01", "深度参与 AI 在直播场景落地，与产品/数据/设计/研发协作", [F["p015_agent"], F["work_coord"]]),
        req("REQ-02", "AI 礼物、AI 互动玩法等营收玩法设计，结合大模型评测生成效果", [F["p006_problem"], F["ai"], F["p006_test"]]),
        metrics("REQ-03", "通过数据分析洞察各国付费动机，持续迭代"),
        collab("REQ-04", "产出需求并推动方案落地，协调资源促进业务协同"),
        ai_tech("REQ-05", "了解基础大模型训练原理，熟悉国内外直播产品"),
        req("REQ-06", "英语听写与沟通能力", [F["lang"]]),
        ownership("REQ-07", "需求洞察、自驱、责任感"),
    ],
)

JOBS["字节跳动_AI产品经理-剪映CapCut-A48539"] = job(
    "字节跳动", "AI产品经理 - 剪映CapCut", "ai_product_manager",
    [
        req("REQ-01", "即梦 Dreamina AI 创作产品规划与设计，覆盖文生图/文生视频/创作 Agent 模块", [F["p006_problem"], F["p015_agent"], F["p006_flow"]]),
        ai_tech("REQ-02", "把前沿 AI 技术转化为用户价值，与算法/工程/设计协作定义路线图"),
        user_research("REQ-03", "洞察创作者需求与痛点，通过访谈、数据分析挖掘产品机会"),
        metrics("REQ-04", "建立 AIGC 核心指标体系，用数据驱动与 A/B 实验验证假设"),
        req("REQ-05", "熟悉 LLM、AI Agent、多模态、扩散模型、视频生成基本原理（优先）", [F["ai"], F["p015_agent"]], required=False),
        collab("REQ-06", "沟通协作与项目推进，胜任跨职能协作"),
        req("REQ-07", "数据分析与指标体系建设经验（优先）", [F["tools"], F["social_data"]], required=False),
    ],
)

JOBS["字节跳动_AI产品经理-广告业务-A88260"] = job(
    "字节跳动", "AI产品经理 - 广告业务", "ai_product_manager",
    [
        req("REQ-01", "商业场景 AI 能力效果优化，建设模型评估策略，挖掘优化点", [F["ai"], F["p006_test"], F["p015_agent"]]),
        user_research("REQ-02", "通过数据分析、客户调研、行业研究挖掘商业广告需求场景"),
        collab("REQ-03", "与业务团队协作，保障需求高质量执行落地"),
        logic("REQ-04", "学习能力、逻辑思维与业务场景理解"),
        ai_tech("REQ-05", "对大模型与 AI 应用有热情，跟踪大模型特性与动态"),
        req("REQ-06", "AI 产品实习经验（优先）", [F["work_scope"]], required=False),
    ],
)


def main() -> None:
    rows = json.loads((ROOT / "outputs" / "fast-lane-pilot" / "batch20.json").read_text(encoding="utf-8"))["rows"]
    out_root = ROOT / "outputs" / "fast-lane-pilot" / "batch20-jobs"
    out_root.mkdir(parents=True, exist_ok=True)
    for r in rows:
        key = Path(r["app_dir"]).name
        if key not in JOBS:
            raise KeyError(f"no job mapping for {key}")
        j = JOBS[key]
        path = out_root / f"{key}.job.json"
        path.write_text(json.dumps(j, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} job files")


if __name__ == "__main__":
    main()
