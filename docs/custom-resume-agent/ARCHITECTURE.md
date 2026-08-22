# 定制简历 Agent V1 架构

> 状态：已确认
> 版本：0.1
> 日期：2026-08-22

## 1. 架构目标

V1 是 Codex 内部可发现的内容工作流，不是常驻应用或外部 LLM 服务。架构需保证：

- 事实和候选补全严格分层；
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
            Auditor             （只读、两遍审计）
               ▼
      immutable run artifacts / content approval
```

依赖只能从应用编排指向领域规则和基础设施适配器。领域 Schema 不得依赖具体模型、浏览器、网页或文件路径。

## 4. 模块边界

### 4.1 领域层

计划位于 `.agents/skills/custom-resume/scripts/` 的 Python 模块，使用 Pydantic 2：

- 事实、JD 要求、证据映射、事实差异、草稿、融合决策、审计和运行清单模型；
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
    ├── fact_store.py
    ├── artifact_store.py
    └── validate_run.py

.codex/agents/
├── custom-resume-writer.toml
├── custom-resume-asu-writer.toml
└── custom-resume-auditor.toml

.agents/prompts/custom-resume/
├── jd-analysis.md
├── writer.md
├── asu-writer.md
├── fusion.md
└── auditor.md

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
  "schema_version": "1.0",
  "run_id": "cr_YYYYMMDDTHHMMSS_<suffix>",
  "application_dir": "applications/<company>_<role>",
  "jd": {"source_type": "directory|text|url", "sha256": "..."},
  "fact_snapshot": {"source": "profile/01-candidate-profile.md", "sha256": "..."},
  "preferences_sha256": "...",
  "reference_cards": [],
  "approved_requirement_ids": [],
  "approved_fact_ids": []
}
```

Writer 与 ASu Writer 必须收到内容等价、摘要一致的输入包。

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
| `evidence-map.json` | requirement_id、coverage、fact_ids、选择状态、真实缺口 | 协调器 |
| `fact-diff.json` | add/replace、旧值、新值、provenance、确认状态 | 协调器 |
| `draft-writer.json` | 四板块、要点、fact_ids、candidate 标记 | Writer |
| `draft-asu.json` | 与 Writer 相同的草稿 Schema | ASu Writer |
| `fusion.json` | 融合稿、来源代理、选择/重写理由、fact_ids | 协调器 |
| `audit.json` | 硬校验、真实性审计、四维评分、问题、修订历史 | Auditor/协调器 |

Markdown 视图由已通过 Schema 的 JSON 生成或逐字段转写，不能成为结构化状态的反向解析来源。

## 9. 状态机

合法状态：

```text
not_started
  → analyzing
  → needs_input
  → awaiting_selection_approval
  → drafting
  → auditing
  → needs_content_review
  → approved
```

任意执行状态可转 `failed`；`approved` 在引用事实变化时转 `stale`。非法跳转必须由确定性代码拒绝。

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
- 协调器不生成两个初始草稿，但负责 JD 分析、融合裁决和唯一文件写入。
- Auditor 只读融合稿、证据映射和事实快照；先审真实性，再审 HR 质量。
- 所有代理默认继承当前 Codex 模型和推理配置，不接入外部 Provider。

## 11. 写入与一致性

- 新运行先写入临时运行目录；全部必需产物通过 Schema 后，使用同一文件系统内原子重命名提交为最终 `run_id` 目录。
- 已提交运行目录不可修改；审计修订作为同一运行中的有序 revision 产物，在提交前完成。
- `current.json` 只在用户批准且硬校验通过后原子替换。
- 事实差异写回前再次校验源事实库哈希；哈希变化则停止并重新生成 diff。
- manifest 摘要与 `current.json` 必须由同一提交动作更新；校验器检测不一致。

## 12. 错误与降级

| 场景 | 行为 |
|---|---|
| JD 为空或无法识别岗位 | 停止并请求有效输入 |
| 公司/岗位无法可靠识别 | 请求用户确认，不猜目录名 |
| 事实库缺失或 ID 重复 | 硬失败，不启动 Writer |
| 用户拒绝 fact diff | 保留运行记录，事实库不变 |
| 子代理不可用 | 暂停，请用户选择重试或显式降级 |
| 单个 Writer 失败 | 不融合单稿，先重试或转人工 |
| 确定性校验失败 | 不启动 Auditor，返回具体错误 |
| Auditor 不通过 | 最多定向修订 2 轮，之后转人工 |
| 联网研究失败 | 使用本地方法卡，标记研究降级 |
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
