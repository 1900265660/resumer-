# 定制简历 Agent V1.5 架构

> 状态：Schema 1.5 实现完成，等待真实 JD 产品验收
> 版本：1.5
> 日期：2026-09-03

## 1. 架构目标

V1 是 Codex 内部可发现的内容工作流，不是常驻应用或外部 LLM 服务。架构需保证：

- 事实和候选补全严格分层；
- 能力发散有完整证据链，选材扩大化不等于事实扩大化；
- LLM 只承担语义分析、写作、融合和质量判断；
- Schema、状态、引用、数字和不可变字段由确定性代码校验；
- 并行子代理只读，协调器是唯一文件写入者；
- 岗位扩展通过角色族和方向路由实现，不复制事实、选材、写作审批或状态机；
- 所有中间结果可恢复、可审查、可回归。

## 2. 当前架构

当前实现使用 Schema 1.5。`custom_resume_cli.py` 是唯一受支持的状态协调入口，提供 `start`、`record`、`advance`、`approve`、`revoke`、`status`；Codex 仍是模型执行宿主，CLI 不接外部模型 API。Python 代码负责输入冻结、Schema、故事计划、回执和哈希校验、三轮候选循环、不可变提交、批准与撤销；Writer、ASu Writer、Auditor 和 HR Reviewer 只返回结构化产物，不能写状态。五个角色族都可由本 Skill 直接执行，但主 Harness 对新增角色的默认路由仍等待真实 JD 产品验收。

旧 `.agents/prompts/campus-resume-optimizer.md` 与 `.agents/agents/resume-optimizer-agent.md` 只保留显式 Legacy 回退。现有 PDF、浏览器和投递脚本位于下游，不属于本模块内容定制边界。

## 3. 执行架构与依赖方向

```text
JD directory / JD text / JD URL
               │
               ▼
    custom-resume Skill（应用编排）
      │        │           │
      │        │           └── Reference provider（本地优先 / Web 降级）
      │        └── Fact store adapter（Markdown + 稳定 ID）
      └── Domain schemas + deterministic rules
               │
      capability transfer map
               │
       full experience scorecard
               │
      portfolio composition pass
               │
       independent selection audit
               │
          story plan
               │
       user selection approval
               │
        approved input packet
          ┌────┴────┐
          ▼         ▼
       Writer    ASu Writer       （只读、互相隔离）
          └────┬────┘
               ▼
      draft quality Auditor       （全新只读调用，融合前门禁）
               ▼
         Coordinator fusion
               ▼
      deterministic quality gate
               ▼
            Auditor             （另一全新只读调用，融合后审计）
               ▼
          HR Reviewer           （只读、招聘决策门禁）
               ▼
       ready for user review
               │
       explicit user hash approval
               │
      immutable run / current pointer
```

依赖只能从应用编排指向领域规则和基础设施适配器。领域 Schema 不得依赖具体模型、浏览器、网页或文件路径。

## 4. 模块边界

### 4.1 领域层

位于 `.agents/skills/custom-resume/scripts/` 的 Python 模块，使用 Pydantic 2：

- 事实、JD 要求、证据映射、事实差异、草稿、融合决策、审计和运行清单模型；
- 能力迁移链、组合价值、相似项目分组、故事计划、调用回执和运行状态模型；
- 三轮候选循环和内容状态转换规则；
- 事实引用、数字来源、不可变字段、四板块和候选泄漏校验；
- 引用事实摘要与 `stale` 判定。

领域层不调用 LLM，不访问网页，不决定文案质量。

### 4.2 应用层

`.agents/skills/custom-resume/SKILL.md` 定义运行协议，`scripts/custom_resume_cli.py` 是状态写入入口，二者当前负责：

- 输入路由和人工检查点；
- 参考研究策略；
- 私有模范简历匹配、哈希校验和用途边界路由；
- 子代理启动、隔离、等待和失败处理；
- 故事计划、融合与三轮候选修订循环；
- 代理调用回执和产物哈希校验；
- 运行产物的提交顺序；
- 内容批准，不处理 PDF 或投递。

### 4.3 基础设施层

- Markdown 事实库适配器；
- 岗位目录和不可变运行目录适配器；
- 本地参考方法卡读取器；
- 私有模范简历库适配器；
- Codex Web/Browser 研究 Provider；
- Codex 项目级自定义子代理。

联网、子代理和文件系统异常必须转换为结构化错误，不得让 LLM 自行猜测成功。

## 5. 当前主要目录

```text
.agents/skills/custom-resume/
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── workflow.md
│   ├── schemas.md
│   ├── quality-rubric.md
│   ├── ai-pm-method-cards.md
│   ├── game-production-pm-method-cards.md
│   ├── game-production-content-judgment.md
│   ├── community-operations-method-cards.md
│   ├── community-product-method-cards.md
│   ├── game-designer-method-cards.md
│   ├── community-content-judgment.md
│   └── game-designer-content-judgment.md
└── scripts/
    ├── custom_resume_cli.py
    ├── eval_harness.py
    ├── exemplar_library.py
    ├── models.py
    ├── fact_library.py
    ├── rendering.py
    ├── storage.py
    ├── validators.py
    ├── orchestrator.py
    └── validate_run.py

.codex/agents/
├── custom-resume-writer.toml
├── custom-resume-asu-writer.toml
├── custom-resume-auditor.toml
└── custom-resume-hr-reviewer.toml

.agents/prompts/custom-resume/
├── jd-analysis.md
├── jd-analysis-game-production.md
├── jd-analysis-community.md
├── jd-analysis-game-designer.md
├── writer.md
├── writer-game-production.md
├── writer-game-designer.md
├── asu-writer.md
├── asu-writer-game-production.md
├── asu-writer-game-designer.md
├── capability-transfer.md
├── experience-selection.md
├── selection-audit.md
├── story-planner.md
├── fusion.md
├── auditor.md
└── hr-reviewer.md

tests/custom_resume/
├── fixtures/
└── test_*.py

profile/resume-exemplars/              # 私有且 Git 忽略
└── <exemplar_id>/
    ├── metadata.json                  # 角色、相似度、用途边界、质量和来源哈希
    └── content-master.md              # 用户批准的不可变参考快照
```

`SKILL.md` 仅保留触发边界、主流程和硬约束；Schema、量表和详细流程按需读取，符合渐进披露原则。

## 6. 公开输入接口

### 6.1 调用

```text
$custom-resume <application_dir | jd_text | jd_url>
```

解析优先级：

1. 参数是已存在目录：读取其中 `jd.md` 和 `manifest.json`（若存在）。
2. 参数是 HTTP(S) URL：获取可见 JD 文本并保存来源 URL、抓取时间和内容哈希。
3. 其他输入：视为 JD 文本。

如果无法可靠识别公司或岗位名称，必须询问用户；不得生成猜测目录名。

### 6.2 规范化输入包

```json
{
  "schema_version": "1.5",
  "run_id": "cr_YYYYMMDDTHHMMSS_<suffix>",
  "application_dir": "applications/<company>_<role>",
  "role_family": "ai_product_manager|game_production_pm|community_operations|community_product_manager|game_designer",
  "role_track": null,
  "jd": {"source_type": "directory|text|url", "sha256": "..."},
  "fact_snapshot": {"source": "profile/01-candidate-profile.md", "sha256": "..."},
  "preferences_sha256": "...",
  "reference_cards": [],
  "approved_requirement_ids": [],
  "approved_fact_ids": []
}
```

Writer 与 ASu Writer 必须收到内容等价、摘要一致的输入包。

规范化阶段按角色族、条件性方向和 JD 关键词阈值查找私有模范简历；匹配条目的元数据、内容哈希与方法卡共同进入 `reference_cards_sha256` 冻结摘要。没有匹配条目时，该摘要保持原方法卡字节哈希，以兼容历史行为。模范内容只在选材审计和双 Writer 包中以 `approved_resume_exemplars` 暴露，并固定携带 `fact_source=false`、`selection_approval=false`。

`role_family` 与条件性 `role_track` 由协调器根据岗位语义提出并由用户确认。Schema 1.5 的合法组合如下：

| `role_family` | `role_track` | 路由 |
|---|---|---|
| `ai_product_manager` | `null` | 既有 AI PM Prompt 与方法卡 |
| `game_production_pm` | `null` | 既有游戏制作 PM Prompt 与方法卡 |
| `community_operations` | `community\|content\|growth\|integrated` | 社区运营分析 Prompt + 对应方向指南 |
| `community_product_manager` | `null` | 社区产品分析 Prompt 与方法卡 |
| `game_designer` | `system\|combat\|writing\|narrative\|general` | 游戏策划分析 Prompt + 对应方向指南 |

`community_operations` 与 `game_designer` 缺少方向、方向越界或其他角色携带非空方向时硬失败。每次运行只有一个主方向；相邻方向要求仍可进入 JD 要求和迁移映射，但不能改变模范简历隔离键或把近邻证据升级为主方向直接经验。

Schema 1.0–1.4 的旧输入继续按各自兼容策略只读解析，但官方入口不允许其产生新的批准。Schema 1.5 不允许缺少 `role_family`，也不允许需要方向的角色缺少 `role_track`。

### 6.3 角色内容指南与自我能力变体

新增岗位不复制完整 Writer/Fusion/Auditor 协议。协调器根据已确认路由加载方法卡和结构化 `role_content_guidance`：运营指南区分社区、内容、增长与社区产品证据；游戏策划指南区分系统、战斗、文案、叙事与综合方向证据。通用 Writer 只使用当前角色指南，不能读取其他方向指南制造能力。

自我能力第三项由 `role_family` 确定性派生：

| 角色族 | 第三项 |
|---|---|
| `ai_product_manager` | 三项结构：`专业硬技能`、`综合软技能`、`个人优势`；语言证据并入综合软技能，不生成游戏经历 |
| `game_production_pm`、`game_designer` | `游戏经历` |
| `community_operations`、`community_product_manager` | `行业/平台经历` |

Schema 1.5 写入器只能生成派生后的名称；加载器继续只读接受历史不可变运行中的 `游戏体验`。

## 7. 事实库协议

### 7.1 Markdown 元数据

```markdown
### 某公司｜某岗位｜2026/01–2026/03 <!-- experience_id: EXP-WORK-001 -->

- 已确认原子事实。 <!-- fact_id: FACT-WORK-001-01; provenance: observed -->
- 用户接受的估值区间。 <!-- fact_id: FACT-WORK-001-02; provenance: accepted_estimate; confirmed_at: 2026-08-22; source_run: cr_xxx; estimate_basis: 用户确认模型估值区间 -->
```

规则：

- 元数据只附加到已有标题或原子事实，不改变原文含义。
- `experience_id` 格式为 `EXP-<CATEGORY>-<NNN>`。
- `fact_id` 格式为 `FACT-<CATEGORY>-<NNN>-<NN>`。
- ID 大小写固定、全库唯一、分配后不复用。
- `observed` 表示用户直接提供或既有已确认事实；`accepted_estimate` 表示用户接受的模型估值区间。
- 事实 ID 迁移必须先生成只含元数据变化的 diff，经用户确认后写入。

### 7.2 证据等级

- `direct`：单一事实明确支持要求。
- `composite`：多个事实组合支持，不新增动作或结果。
- `accepted_estimate`：使用已确认估值事实。
- `candidate`：待确认补全，不得进入干净稿。
- `unsupported`：没有事实 ID 支持。

## 8. 运行产物 Schema

每个 JSON 顶层都必须包含 `schema_version`、`run_id`、`created_at` 和来源摘要。

| 文件 | 核心字段 | 责任方 |
|---|---|---|
| `run.json` | 状态、输入哈希、产物清单、错误、修订次数 | 协调器 |
| `jd-analysis.json` | 岗位目标、要求、优先级、关键词、风险、理想证据蓝图 | 协调器 |
| `capability-transfer-map.json` | 事实源动作、目标能力/要求、迁移距离、置信度、可写边界和候选追问 | 协调器 |
| `evidence-map.json` | requirement_id、coverage、fact_ids、选择状态、真实缺口 | 协调器 |
| `experience-selection.json` | 完整经历池、岗位匹配分、组合价值、相似分组、等级、覆盖增量、例外、要点预算和选择理由 | 协调器 |
| `selection-audit-pre.json` | 写作前逐经历 keep/auxiliary/drop/reconsider 结果 | Auditor |
| `fact-diff.json` | add/replace、旧值、新值、provenance、确认状态 | 协调器 |
| `draft-writer.json` | 四板块、要点、fact_ids、candidate 标记 | Writer |
| `draft-asu.json` | 与 Writer 相同的草稿 Schema | ASu Writer |
| `draft-quality-audit.json` | 两份草稿逐经历基础质量审计与当前草稿哈希 | Auditor/协调器 |
| `fusion.json` | 融合稿、来源代理、选择/重写理由、fact_ids | 协调器 |
| `audit.json` | 硬校验、真实性审计、五维评分、问题、修订历史 | Auditor/协调器 |
| `hr-review.json` | 逐经历招聘决策、遗漏事实、面试影响、修订/补问/重选路由 | HR Reviewer/协调器 |

`reference-research.json` 记录来源类型、合格性、脱敏选择规则和降级批准；岗位方法卡本身不能构成同岗位简历样例。

V1.5 新产物使用 Schema `1.4`；`1.0`–`1.3` 历史运行继续只读，绝不原地迁移或重写。

### 8.1 能力迁移链

每条 `CapabilityTransfer` 至少包含：

```json
{
  "transfer_id": "TR-001",
  "experience_id": "EXP-PROJECT-009",
  "fact_ids": ["FACT-PROJECT-009-02"],
  "source_action": "对接海外开发商与国内发行商并保障按时交付",
  "target_capability": "跨职能协作与交付推进",
  "requirement_ids": ["REQ-002"],
  "distance": "adjacent",
  "confidence": "high",
  "writable_scope": "可概括为本地化项目协同和交付推进；不可写团队管理或正式研发排期",
  "candidate_question_id": null
}
```

`distance` 为 `direct|adjacent|analogical|candidate`。`direct`、`adjacent`、`analogical` 必须引用能够语义蕴含源动作的事实；`candidate` 可记录岗位惯例或合理流程假设，但只能连接事实问题，不能进入分数或 Writer 输入。

映射器对每段经历固定扫描八类能力：

1. 规划与项目推进；
2. 协作与利益相关方；
3. 质量与风险；
4. 用户与研究；
5. 数据与分析；
6. 内容与沟通；
7. 产品与技术；
8. 运营、商业与行业。

每一类必须返回 `supported|candidate|none`，防止模型因经历标题而提前剪枝；只有 `supported` 可以形成前三种迁移距离。系统不要求每段经历拥有全部能力，禁止用常识批量补齐。

岗位匹配仍为 100 分：岗位职责 30、过程/交付 20、结果 15、行业 10、覆盖增量 15、证据强度 10。迁移距离对相关分项使用确定性上限系数 `direct=1.0`、`adjacent=0.8`、`analogical=0.6`、`candidate=0`，防止不同场景的能力被归零，也防止类比能力反超直接事实。代码复算分项、总分和 70/55 等级；仅有行业亲和且无源动作链的 `affinity_only` 经历封顶 54。

### 8.2 组合价值与选材

每段经历另有 0–20 的 `portfolio_value_score`，由板块补足、能力多样性、叙事独特性和非同质化各 0–5 组成并由代码复算。该分数与岗位匹配分并列展示，不相加；协调器必须解释为何组合价值足以改变最终排序。

选择必须满足：

- WORK/PROJECT 合计选择 1–4 段；
- 每段按独立语义单元给出建议要点数，但数量不作为质量门槛；
- 同一 `similarity_group` 的个人开发项目最多 2 项；
- 排除更高岗位匹配分或更高组合价值经历时记录机会成本；
- 低于 55 分的经历、无法形成至少两个互补意图的经历和没有行动加结果/影响证据的经历不得用于凑数；
- 不要求最低 WORK 数量，不使用 `section_balance_override`；
- 每个入选 WORK/PROJECT 的 `fact_ids` 必须等于事实库中该经历的完整已确认事实集合；要点引用可以取子集，但 Writer/HR 输入不得先隐藏事实。

每段入选经历还必须生成 `story-plan.json`：一个求职卖点、事实绑定的背景/行动/方法/困难/结果证据、一个或多个由语义决定的不同意图和只供内部校验的 `ownership_guard`。用户批准记录同时绑定选材哈希和故事计划哈希；意图或要点数量不作为通过配额。

Markdown 视图由已通过 Schema 的 JSON 生成或逐字段转写，不能成为结构化状态的反向解析来源。

## 9. 状态机

合法状态：

```text
not_started
  → analyzing
  → needs_input / awaiting_reference_approval
  → awaiting_selection_approval
  → drafting
  → auditing
  → hr_reviewing
  → ready_for_user_review
  → approved
```

第三个候选仍未通过时转 `quality_failed`；执行异常转 `failed`；`approved` 在引用事实变化时转 `stale`。非法跳转必须由确定性代码拒绝。

融合后机会成本审计返回 `reselect_required` 时回到故事规划与选材批准。协调器归档被替代产物、清除下游当前产物，并保留回执绑定的历史。

Schema 1.5 中，Auditor 全部通过后进入 `hr_reviewing`，不能直接进入内容验收。HR Reviewer 通过只进入 `ready_for_user_review`；语言或融合问题只重写 Fusion，单 Writer 问题只重写该稿，选材或故事问题返回 Story Plan，事实冲突进入 `needs_input`。初稿加最多两次修复，共 3 个候选；达到上限转 `quality_failed`。

`applications/<公司>_<岗位>/manifest.json` 增加：

```json
{
  "resume_content": {
    "status": "approved",
    "current_pointer": "resume-content/current.json",
    "approved_run_id": "cr_...",
    "updated_at": "..."
  }
}
```

文档中的语义名 `resume_content_status` 对应存储路径 `manifest.resume_content.status`；`resume-content/current.json` 保存相同状态和批准运行指针。该字段不得写入或推导申请主状态，校验器必须拒绝两处不一致。

### 9.1 主 Harness 与投递链路接入

T28 完成并获用户发布批准后，`china-job-search` 对本版本五个受支持角色族默认先调用本模块；在此之前新增角色族不得宣称已经接入默认路由。本模块的依赖方向和内容边界不变。下游只有在 `current.json` 与 `manifest.resume_content` 一致且状态为 `approved` 时，才读取批准运行内不可变的 `content-master.md` 制版。

下游读取前要求 `current.json` 为 Schema 1.5 `approved`，并校验最终内容哈希、不可变用户批准记录、运行状态账本、故事计划、质量门、HR 审查和代理回执。旧 Schema 新批准、阻断状态、无用户批准、无效 current 或任一哈希不一致都会 fail closed。PDF/ATS 验收后，`manifest-draft.json` 记录 `content_pipeline: custom-resume` 和内容摘要。岗位批准脚本生成 Schema 2 清单，冻结内容运行 ID、批准事务、内容母版、JD、答案快照、review 与附件哈希。浏览器执行器在打开页面前重新校验这些证据；内容指针变为 `stale`、运行切换或任一文件改变都会使清单失效。内容批准、PDF 通过、岗位批准和最终提交是四个独立门禁，不能互相推导。

旧优化器只保留 `legacy-explicit-fallback`：必须记录用户明确批准和原因，仍执行 PDF/ATS、岗位批准及浏览器复验。它不得成为 out-of-scope 或故障时的静默回退。

## 10. Agent 与 Prompt 边界

- Prompt 只定义语义任务、输入字段和输出 Schema，不写文件、不推进状态。
- 自定义代理配置只定义角色、只读权限和输出责任，不复制完整产品文档。
- 协调器不生成两个初始草稿，但负责 JD 分析、能力迁移映射、组合选材、融合裁决和唯一文件写入。
- Writer 输入只包含用户批准的经历、这些经历的全部已确认事实和 `direct|adjacent|analogical` 迁移链；选材控制经历、迁移链和预算，不控制经历内部的事实可见性。`writable_scope` 是表达上限，不能成为新的候选人事实。
- Writer packet 额外携带由 `role_family + role_track` 决定的 `role_content_guidance`。指南只约束证据判断、整稿分工、方向差异和可写上限，不新增候选人事实，也不改变人工选材门禁。
- 教育由固定基线生成器逐字段复制；Writer 不得改写课程或用课程推导岗位能力。新运行的自我能力子类第三项按第 6.3 节确定性派生；Artifact 模型继续接受历史不可变运行中的游戏体验名称，但当前内容校验器不再为新稿生成该旧称。
- Auditor 以三个互相独立的调用运行：写作前审计完整经历池和选材表；双稿后逐稿逐经历审计基础简历质量；融合后读取融合稿、最高价值落选项、证据映射和事实快照，先审真实性，再审正向证据、选材质量和 HR 质量。草稿质量 Auditor 不得参与写作或融合，且其通过工件必须绑定两份草稿哈希。
- HR Reviewer 是第三种独立只读调用，只在融合后 Auditor 通过时运行。它读取目标 JD、故事计划、融合稿、完整选中事实、基础审计和最终 bullet ID，按招聘决策而非 Schema 合规评分；只有 `strong_push`、总分不低于 9.0、角色契合、叙事完整、证据具体、决策就绪、可信度和内容充实度六维均不低于 8.0，且评分引用实际经历和 bullet，才通过。
- HR Reviewer 必须返回逐经历缺陷、遗漏事实 ID、合理要点数和三路路由：现有事实定向修订、事实补问或重新选材；它不能编辑稿件或自行补事实。HR 返回的 `passed` 和分数只有在确定性质量门、独立 Auditor、回执和全部哈希同时通过时才有效。
- Writer、Fusion、Auditor 与 HR Reviewer 使用字符型内容充实度门禁：整稿至少 1,200 个中文字符，核心经历至少 180 个，辅助经历至少 120 个。要点数量仅作可观测指标，不设通过配额；机械拆句、同义反复和弱经历填充仍失败。事实支持的能力前置标签可保留，内部审计标签和验证备注不得进入正文。
- 所有代理默认继承当前 Codex 模型和推理配置，不接入外部 Provider。

## 11. 写入与一致性

- 新运行先写入临时运行目录；全部必需产物通过 Schema 后，使用同一文件系统内原子重命名提交为最终 `run_id` 目录。
- `needs_input`、`awaiting_selection_approval` 与 `drafting` 人工门禁使用 `resume-content/.pending/<run_id>.json` 原子 checkpoint 跨进程恢复；它不是已提交历史运行，最终运行提交成功后立即移除。
- 已提交运行目录不可修改；三轮候选的被替代产物作为有序历史在提交前归档。
- `current.json` 只在用户批准最终内容哈希、硬校验、独立审计、HR、回执和运行状态全部通过后原子替换。
- `run-status.jsonl` 追加记录 `approved|superseded|user_rejected|schema_invalid|revoked`。阻断记录优先于旧 `run.json` 的批准字段；撤销当前运行时指针改为 `no_approved_content`，不自动回退到另一个旧稿。
- 事实差异写回前再次校验源事实库哈希；哈希变化则停止并重新生成 diff。
- 已批准的 `add/replace` 操作原子写回后记录结果哈希，并把运行恢复为 `analyzing`：所有分析和证据映射必须基于新事实快照重新生成，之后才可进入选材批准。
- manifest 摘要与 `current.json` 必须由同一提交动作更新；校验器检测不一致。

## 12. 错误与降级

| 场景 | 行为 |
|---|---|
| JD 为空或无法识别岗位 | 停止并请求有效输入 |
| 公司/岗位无法可靠识别 | 请求用户确认，不猜目录名 |
| 角色族或方向不合法/不明确 | 停止并请求用户确认，不静默路由到 Legacy 或相近方向 |
| 事实库缺失或 ID 重复 | 硬失败，不启动 Writer |
| 能力迁移链无事实、源动作或可写边界 | 硬失败，不进入选材 |
| 仅存在可能流程、没有事实支持 | 生成 `candidate` 问题，计分为 0 |
| 只有一段强 WORK/PROJECT | 允许选材；按语义规划要点，不限制条数，但仍须满足整稿与核心经历字符门禁 |
| 入选经历少于 2 个互补要点或缺行动/结果证据 | 删除、仅在同一真实主体内合并，或进入 `needs_input`；不得保留凑版面 |
| 同类个人开发项目超过 2 项 | 硬拒绝选材批准，要求比较并淘汰同质项 |
| 用户拒绝 fact diff | 保留运行记录，事实库不变 |
| 子代理不可用 | 暂停，请用户选择重试或显式降级 |
| 单个 Writer 失败 | 不融合单稿，先重试或转人工 |
| 确定性校验失败 | 不启动 Auditor，返回具体错误 |
| Auditor 不通过 | 按缺陷来源重写；第三个候选仍失败则转 `quality_failed` |
| HR Reviewer 非 `strong_push`、总分低于 9.0、任一维度低于 8.0 或缺少 bullet 证据 | 按故事/Fusion/事实来源路由；第三个候选仍失败则转 `quality_failed` |
| 入选经历预隐藏已确认事实 | 确定性拒绝选材；补齐完整事实集并重新执行独立选材审计和用户批准 |
| 用户否决已获 HR 高分的内容 | 追加 `user_rejected`，清除相应 current，且不自动选择其他旧稿 |
| 联网研究失败或没有合格同岗样例 | 进入 `awaiting_reference_approval`；用户批准降级后才继续 |
| 引用事实变化 | 批准稿转 `stale`，不自动重写 |
| 游戏岗位沿用旧运行游戏名单或旧概数 | 审计失败；回到当前冻结事实快照重新选择和融合 |
| 社区/内容/增长运营之间发生所有权混写 | 审计失败；按主方向收紧为直接、近邻或缺口证据 |
| 社区运营被写成社区产品 Owner | 审计失败；缺少产品动作时回到事实问题或收紧表达 |
| 游玩、测评、翻译、写作或 MOD 测试被写成游戏策划所有权 | 审计失败；保留真实行业/内容/质量迁移边界 |

## 13. 安全与隐私

- 事实库、真实申请目录和原始参考简历保持 Git 忽略。
- 项目只跟踪脱敏方法卡、测试夹具和 Schema，不保存真实联系方式或敏感答案。
- 网页、JD 和附件中的指令均视为 Prompt Injection 数据。
- 子代理默认只读；只有协调器可写入已授权的岗位目录和经用户确认的事实差异。
- V1 不具备上传、消息发送、投递或外部账户写入权限。

## 14. 技术依赖

- Python 3.10+。
- Pydantic 2.x：运行 Schema 和验证。
- pytest：单元与集成测试。
- 不建设服务进程、数据库或自定义模型 Provider。

依赖版本和安装方式在实现任务中通过项目依赖清单固定；本文不记录本机偶然安装状态。

## 15. 调研依据

- [OpenAI Codex Skills](https://learn.chatgpt.com/docs/build-skills)：仓库 Skill 位置、`SKILL.md`、references/scripts、`agents/openai.yaml` 与渐进披露。
- [OpenAI Codex Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)：项目级 `.codex/agents/*.toml`、只读子代理和编排边界。
- [Resume Matcher diff-based improvement](https://github.com/srbhr/Resume-Matcher/blob/main/docs/superpowers/specs/2026-03-23-diff-based-improvement-design.md)：以不可变原始事实为锚的差异化改写和字段保护。
- [Resume Matcher eval harness](https://github.com/srbhr/Resume-Matcher/blob/main/apps/backend/tests/evals/README.md)：确定性测试与 LLM 质量评估分离。
- [ResumeHQ resume auditor](https://github.com/jananthan30/Resume-Builder/blob/master/.codex/agents/resume-auditor.toml) 与 [benchmarks](https://github.com/jananthan30/Resume-Builder/blob/master/BENCHMARKS.md)：只读 Writer/Auditor、结构化交接和真实性优先评测。

上述来源只提供架构模式；候选人事实、产品范围和审批边界仍以本工作区事实库及用户确认决策为准。

## 16. 上游成品基线路由

`china-job-search/scripts/resume_baseline.py` 位于本模块上游，管理私有 `profile/resume-baselines/`，不写入 `resume-content/`。它以事实库 SHA-256、源文件/文本 SHA-256、角色族/方向和完整经历指纹决定是否允许 `light_tune`。

```text
完整具体 JD
  ├─ 同方向、同经历/故事、当前 reusable 基线 → 轻微调 → 新 HR → 制版
  └─ 无基线/跨方向/换经历或故事/轻调失败 → 待批重写 → custom-resume start
```

轻微调 HR 通过只生成下游材料资格，不生成本模块 `current.json` 或内容批准记录。待重写批次必须保存 `must_not_start_dual_writers=true`，直至用户批准；批准后不允许从基线快照伪造本模块中间产物。

## 17. `fast-assemble` 并行产品通道

`profile/01-candidate-profile.md` 继续是唯一原子事实源，`profile/resume-claims.json` 是绑定 `fact_ids` 的批准表达层。`china-job-search/scripts/fast_resume.py` 负责导入、装配、单 Writer 补缺、路由、RenderCV YAML 和确定性 PDF QA；本模块保持只读边界。岗位批准清单以 `content_pipeline: fast-assemble` 冻结事实、表达、JD、选材、内容、HR、YAML 和 PDF 哈希，但 HR 通过不能代替用户的岗位投递批准。
