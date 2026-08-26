# 定制简历 Agent V1.4 架构

> 状态：已确认
> 版本：0.5
> 日期：2026-08-26

## 1. 架构目标

V1 是 Codex 内部可发现的内容工作流，不是常驻应用或外部 LLM 服务。架构需保证：

- 事实和候选补全严格分层；
- 能力发散有完整证据链，选材扩大化不等于事实扩大化；
- LLM 只承担语义分析、写作、融合和质量判断；
- Schema、状态、引用、数字和不可变字段由确定性代码校验；
- 并行子代理只读，协调器是唯一文件写入者；
- 所有中间结果可恢复、可审查、可回归。

## 2. 当前架构

当前内容流程由 `.agents/prompts/campus-resume-optimizer.md` 与 `.agents/agents/resume-optimizer-agent.md` 驱动，直接输出长篇 Markdown。它具备 JD 拆解、经历选择、改写和 HR 扫读规则，但缺少：

- 稳定事实标识和结构化事实映射；
- 统一输入输出 Schema；
- 独立 Writer/ASu Writer 上下文；
- 可机器校验的融合决策与状态；
- 自动化内容回归和审批失效机制。

现有 PDF、浏览器和投递脚本位于下游，不属于本模块 V1。

## 3. 目标架构与依赖方向

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
        approved input packet
          ┌────┴────┐
          ▼         ▼
       Writer    ASu Writer       （只读、互相隔离）
          └────┬────┘
               ▼
         Coordinator fusion
               ▼
      deterministic validation
               ▼
            Auditor             （只读、两遍基础审计）
               ▼
          HR Reviewer           （只读、招聘决策门禁）
               ▼
      immutable run artifacts / content approval
```

依赖只能从应用编排指向领域规则和基础设施适配器。领域 Schema 不得依赖具体模型、浏览器、网页或文件路径。

## 4. 模块边界

### 4.1 领域层

计划位于 `.agents/skills/custom-resume/scripts/` 的 Python 模块，使用 Pydantic 2：

- 事实、JD 要求、证据映射、事实差异、草稿、融合决策、审计和运行清单模型；
- 能力迁移链、组合价值、相似项目分组和板块平衡例外模型；
- 内容状态转换规则；
- 事实引用、数字来源、不可变字段、四板块和候选泄漏校验；
- 引用事实摘要与 `stale` 判定。

领域层不调用 LLM，不访问网页，不决定文案质量。

### 4.2 应用层

`.agents/skills/custom-resume/SKILL.md` 负责：

- 输入路由和人工检查点；
- 参考研究策略；
- 子代理启动、隔离、等待和失败处理；
- 融合与审计修订循环；
- 运行产物的提交顺序；
- 内容批准，不处理 PDF 或投递。

### 4.3 基础设施层

- Markdown 事实库适配器；
- 岗位目录和不可变运行目录适配器；
- 本地参考方法卡读取器；
- Codex Web/Browser 研究 Provider；
- Codex 项目级自定义子代理。

联网、子代理和文件系统异常必须转换为结构化错误，不得让 LLM 自行猜测成功。

## 5. 目标目录

```text
.agents/skills/custom-resume/
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── workflow.md
│   ├── schemas.md
│   ├── quality-rubric.md
│   └── reference-method-cards/
└── scripts/
    ├── models.py
    ├── fact_library.py
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
├── writer.md
├── writer-game-production.md
├── asu-writer.md
├── asu-writer-game-production.md
├── fusion.md
├── auditor.md
└── hr-reviewer.md

tests/custom_resume/
├── fixtures/
└── test_*.py
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
  "schema_version": "1.3",
  "run_id": "cr_YYYYMMDDTHHMMSS_<suffix>",
  "application_dir": "applications/<company>_<role>",
  "role_family": "ai_product_manager|game_production_pm",
  "jd": {"source_type": "directory|text|url", "sha256": "..."},
  "fact_snapshot": {"source": "profile/01-candidate-profile.md", "sha256": "..."},
  "preferences_sha256": "...",
  "reference_cards": [],
  "approved_requirement_ids": [],
  "approved_fact_ids": []
}
```

Writer 与 ASu Writer 必须收到内容等价、摘要一致的输入包。

`role_family` 由协调器根据岗位语义提出并由用户确认。`ai_product_manager` 路由到 AI PM 分析 Prompt/方法卡，`game_production_pm` 路由到游戏研发 PM 分析 Prompt/方法卡；两者共享后续证据映射、双稿、融合、校验、审计和存储协议。旧输入缺少该字段时按 `ai_product_manager` 解析，以保持 V1 `1.x` 产物兼容。

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
| `fusion.json` | 融合稿、来源代理、选择/重写理由、fact_ids | 协调器 |
| `audit.json` | 硬校验、真实性审计、五维评分、问题、修订历史 | Auditor/协调器 |
| `hr-review.json` | 逐经历招聘决策、遗漏事实、面试影响、修订/补问/重选路由 | HR Reviewer/协调器 |

`reference-research.json` 记录来源类型、合格性、脱敏选择规则和降级批准；岗位方法卡本身不能构成同岗位简历样例。

V1.4 新产物使用 Schema `1.3`；`1.0`、`1.1` 和 `1.2` 历史运行继续只读，绝不原地迁移或重写。

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

### 8.2 组合价值与板块平衡

每段经历另有 0–20 的 `portfolio_value_score`，由板块补足、能力多样性、叙事独特性和非同质化各 0–5 组成并由代码复算。该分数与岗位匹配分并列展示，不相加；协调器必须解释为何组合价值足以改变最终排序。

选择必须满足：

- 同一 `similarity_group` 的个人开发项目最多 2 项；
- 默认至少 2 项 `WORK`；
- 辅助经历要点占比不超过 25%；
- 排除更高岗位匹配分或更高组合价值经历时记录机会成本；
- 最多一个 `section_balance_override`。例外只能指向低于 55 分的 `WORK`，必须有用户批准时间、理由、比较过的替代项和最多 2 个要点；原始分数与等级保持不变。

`section_balance_override` 不得绕过事实引用、未确认候选隔离、教育锁定、分类或真实性校验。

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
  → needs_content_review
  → approved
```

任意执行状态可转 `failed`；`approved` 在引用事实变化时转 `stale`。非法跳转必须由确定性代码拒绝。

融合后机会成本审计返回 `reselect_required` 时允许 `auditing → awaiting_selection_approval`。协调器保存重选记录、清除获批经历和当前草稿；最多重选两轮。

Schema 1.3 中，Auditor 全部通过后进入 `hr_reviewing`，不能直接进入内容验收。HR Reviewer 通过才进入 `needs_content_review`；可由现有事实修复时 `hr_reviewing → auditing` 并重跑全链路；需要换经历时返回 `awaiting_selection_approval`；需要新事实或两轮后仍不足时提交为不可批准的 `needs_content_review` 运行并展示问题。

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

## 10. Agent 与 Prompt 边界

- Prompt 只定义语义任务、输入字段和输出 Schema，不写文件、不推进状态。
- 自定义代理配置只定义角色、只读权限和输出责任，不复制完整产品文档。
- 协调器不生成两个初始草稿，但负责 JD 分析、能力迁移映射、组合选材、融合裁决和唯一文件写入。
- Writer 输入只包含用户批准的经历、事实和 `direct|adjacent|analogical` 迁移链；`writable_scope` 是表达上限，不能成为新的候选人事实。
- 教育由固定基线生成器逐字段复制；Writer 不得改写课程或用课程推导岗位能力。自我能力子类由确定性枚举校验为专业硬技能、综合软技能、游戏体验、语言能力。
- Auditor 以两个独立调用运行：写作前读取完整经历池和选材表，融合后读取融合稿、最高价值落选项、证据映射和事实快照；先审真实性，再审正向证据、选材质量和 HR 质量。
- HR Reviewer 是第三种独立只读调用，只在融合后 Auditor 通过时运行。它读取目标 JD、融合稿、完整选中事实、基础审计和已使用事实，按招聘决策而非 Schema 合规评分；只有 `strong_push` 且总分、五维均不低于 8.5 才通过。
- HR Reviewer 必须返回逐经历缺陷、遗漏事实 ID、合理要点数和三路路由：现有事实定向修订、事实补问或重新选材；它不能编辑稿件或自行补事实。
- 所有代理默认继承当前 Codex 模型和推理配置，不接入外部 Provider。

## 11. 写入与一致性

- 新运行先写入临时运行目录；全部必需产物通过 Schema 后，使用同一文件系统内原子重命名提交为最终 `run_id` 目录。
- `needs_input`、`awaiting_selection_approval` 与 `drafting` 人工门禁使用 `resume-content/.pending/<run_id>.json` 原子 checkpoint 跨进程恢复；它不是已提交历史运行，最终运行提交成功后立即移除。
- 已提交运行目录不可修改；审计修订作为同一运行中的有序 revision 产物，在提交前完成。
- `current.json` 只在用户批准且硬校验通过后原子替换。
- 事实差异写回前再次校验源事实库哈希；哈希变化则停止并重新生成 diff。
- 已批准的 `add/replace` 操作原子写回后记录结果哈希，并把运行恢复为 `analyzing`：所有分析和证据映射必须基于新事实快照重新生成，之后才可进入选材批准。
- manifest 摘要与 `current.json` 必须由同一提交动作更新；校验器检测不一致。

## 12. 错误与降级

| 场景 | 行为 |
|---|---|
| JD 为空或无法识别岗位 | 停止并请求有效输入 |
| 公司/岗位无法可靠识别 | 请求用户确认，不猜目录名 |
| 事实库缺失或 ID 重复 | 硬失败，不启动 Writer |
| 能力迁移链无事实、源动作或可写边界 | 硬失败，不进入选材 |
| 仅存在可能流程、没有事实支持 | 生成 `candidate` 问题，计分为 0 |
| 工作经历不足 2 项 | 等待用户选择已确认工作经历；确实不足时可批准一次板块平衡例外 |
| 同类个人开发项目超过 2 项 | 硬拒绝选材批准，要求比较并淘汰同质项 |
| 用户拒绝 fact diff | 保留运行记录，事实库不变 |
| 子代理不可用 | 暂停，请用户选择重试或显式降级 |
| 单个 Writer 失败 | 不融合单稿，先重试或转人工 |
| 确定性校验失败 | 不启动 Auditor，返回具体错误 |
| Auditor 不通过 | 最多定向修订 2 轮，之后转人工 |
| HR Reviewer 低于 `strong_push`/8.5 | 现有事实足够则定向修订并重跑全部审计；缺事实则生成问题；需换经历则回到选材；总计最多 2 轮 |
| 联网研究失败或没有合格同岗样例 | 进入 `awaiting_reference_approval`；用户批准降级后才继续 |
| 引用事实变化 | 批准稿转 `stale`，不自动重写 |

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
