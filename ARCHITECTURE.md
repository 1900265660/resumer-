# 历史架构审计（已被工程交接架构取代）

> 本文件保留 2026-08-31 的审计上下文，不能作为当前运行说明。请以 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、[docs/ENGINEER_HANDOFF.md](docs/ENGINEER_HANDOFF.md) 和实际代码为准。

# 当前简历生成系统代码架构审计

审计日期：2026-08-31  
审计对象：当前工作区（包括 Git 已跟踪文件、被 `.gitignore` 忽略但实际存在的 `profile/`、`applications/` 与运行脚本）。  
口径：只描述当前文件、代码、测试和现存运行产物能证明的事实。`docs/custom-resume-agent/` 中的产品或架构声明不自动视为已实现。

最先需要说明的事实：这个仓库不是一个有统一 CLI、服务进程或 Python `main()` 的端到端简历生成应用。用户侧入口是 Codex 对 Skill 文本的发现与执行；Python 部分提供数据模型、状态约束、校验和存储函数。当前仓库里真正留下的完整运行，则依赖某个岗位目录下的一组一次性 Python 脚本和人工/外部生成的 JSON 文件。

## 1. 文件结构

以下目录树排除了 `.git/`、`__pycache__/`、`.pytest_cache/` 和 Chrome profile 内部缓存文件；这些目录不是本项目源码。对数量较多且职责完全相同的快照、模板和结果文件用范围表示，但范围中的文件确实各自存在。

### 1.1 根目录

```text
AGENTS.md                              工作区全局规则；约束事实源、内容审批、PDF 和投递边界。
README.md                              面向 Codex 用户的文字入口；说明这是“Codex 直接执行”的工作区，不是常驻应用。
requirements.txt                      运行依赖；只有 pydantic>=2.13,<3。
requirements-dev.txt                  测试依赖；pytest，以及 Python<3.11 时的 tomli。
.gitignore                            忽略个人事实库、岗位目录、生成物和临时目录。
定制简历agent.txt                      早期需求草稿；当前代码和 Skill 没有引用它。
参考prompt.txt                         早期长 Prompt；当前代码和 Skill 没有引用它。
ARCHITECTURE.md                        本文；当前实现审计，不是目标架构说明。
```

### 1.2 `.agents/`：Codex 可发现入口、提示词、Schema 和 Python 库

```text
.agents/agent开发流程.txt                         兼容入口，文字指向现行开发规范。
.agents/agents/resume-optimizer-agent.md          Deprecated 旧版简历优化 Agent 协议；仅文字回退路径引用。
.agents/prompts/campus-job-screening.md           岗位筛选 Prompt。
.agents/prompts/campus-resume-optimizer.md        Deprecated 旧版单 Prompt 简历优化流程；评测仍把它当 legacy 基线。
.agents/references/email-monitoring.md             招聘邮件监控说明，与定制内容状态机无代码依赖。
```

#### `.agents/skills/custom-resume/`

```text
SKILL.md                                           Codex 的主入口说明；按自然语言规定阶段、人工门禁和代理分工。
agents/openai.yaml                                 Skill 发现元数据；只含 display_name、description、default_prompt。

references/workflow.md                            文字工作流说明；Python 不解析此文件。
references/schemas.md                             文字 Schema 说明；Python 不解析此文件。
references/quality-rubric.md                      质量评分说明；Python 硬校验不读取它。
references/ai-pm-method-cards.md                  AI 产品经理本地方法卡；normalize_run_input() 读取并计算哈希。
references/game-production-pm-method-cards.md     游戏制作 PM 本地方法卡；normalize_run_input() 读取并计算哈希。
references/game-production-content-judgment.md    游戏岗位内容判断说明；只有 Skill/Prompt 文字要求读取。

scripts/models.py                                 所有 Pydantic 类型、枚举、状态转换表及 JSON Schema 导出 CLI。
scripts/orchestrator.py                           CoordinatorRun 状态对象、输入规范化、包构造、校验调用、提交和审批编排；没有 main()。
scripts/validators.py                             融合稿确定性校验和运行目录必需文件检查。
scripts/storage.py                                checkpoint、staging、不可变 run、current 指针及 manifest.resume_content 写入。
scripts/fact_library.py                           Markdown 事实库解析、稳定 ID 迁移、经批准 fact diff 写回；有独立 CLI。
scripts/exemplar_library.py                       私有模范简历元数据校验、关键词匹配、内容哈希冻结；无 CLI。
scripts/validate_run.py                           已提交 run 的结构/哈希/类型校验 CLI。
scripts/eval_harness.py                           固定 fixture、盲评打包、解盲和汇总 CLI；不调用模型生成或评分。

schemas/input-packet.schema.json                  NormalizedInputPacket 的导出快照。
schemas/jd-analysis.schema.json                   JDAnalysisArtifact 的导出快照。
schemas/evidence-map.schema.json                  EvidenceMapArtifact 的导出快照。
schemas/capability-transfer-map.schema.json       CapabilityTransferMapArtifact 的导出快照。
schemas/experience-selection.schema.json          ExperienceSelectionArtifact 的导出快照。
schemas/selection-audit.schema.json               SelectionAuditArtifact 的导出快照。
schemas/fact-diff.schema.json                     FactDiffArtifact 的导出快照。
schemas/draft.schema.json                         DraftArtifact 的导出快照。
schemas/fusion.schema.json                        FusionArtifact 的导出快照。
schemas/validation.schema.json                    DeterministicValidationArtifact 的导出快照。
schemas/audit.schema.json                         AuditArtifact 的导出快照。
schemas/hr-review.schema.json                     HrReviewArtifact 的导出快照。
schemas/reference-research.schema.json            ReferenceResearchArtifact 的导出快照。
schemas/run-checkpoint.schema.json                RunCheckpointArtifact 的导出快照。
schemas/run.schema.json                           RunManifestArtifact 的导出快照。
schemas/current.schema.json                       CurrentPointer 的导出快照。
schemas/agent-failure.schema.json                 AgentFailureArtifact 的导出快照。
```

2026-08-31 重新运行 `models.py --export-dir <临时目录>` 后，上述 17 个 Schema 与当前 `schemas/` 文件逐文件 SHA-256 一致。

#### `.agents/prompts/custom-resume/`

```text
jd-analysis.md                                    AI 产品经理 JD 分析任务 Prompt；约定输出 JDAnalysisArtifact。
jd-analysis-game-production.md                    游戏制作 PM JD 分析任务 Prompt；约定输出 JDAnalysisArtifact。
capability-transfer.md                            全经历八类能力迁移扫描 Prompt；约定输出 CapabilityTransferMapArtifact。
experience-selection.md                          经历打分和选材 Prompt；约定输出 ExperienceSelectionArtifact。
selection-audit.md                               写作前选材审计 Prompt；约定输出 SelectionAuditArtifact。
writer.md                                         AI PM Writer Prompt；约定输出 DraftArtifact(agent=writer)。
writer-game-production.md                         游戏 PM Writer Prompt；约定输出 DraftArtifact(agent=writer)。
asu-writer.md                                     AI PM ASu Writer Prompt；约定输出 DraftArtifact(agent=asu_writer)。
asu-writer-game-production.md                     游戏 PM ASu Writer Prompt；约定输出 DraftArtifact(agent=asu_writer)。
fusion.md                                         双稿 bullet 级融合 Prompt；约定输出 FusionArtifact。
auditor.md                                        写作前/融合后 Auditor Prompt；约定输出 SelectionAuditArtifact 或 AuditArtifact。
hr-reviewer.md                                    Schema 1.3 HR Reviewer Prompt；约定输出 HrReviewArtifact。
```

这些 Markdown 文件没有被任何 Python 模块打开、拼接或传给模型客户端。

#### 其他 Skill、资产和第三方快照

```text
.agents/skills/china-job-search/SKILL.md           上游求职文字工作流；文字上把两类岗位路由到 custom-resume。
.agents/skills/browser-application/SKILL.md        下游浏览器投递文字工作流；读取已批准内容/PDF 清单。
.agents/skills/resume/SKILL.md                     HTML/PDF 简历制作 Skill，与 custom-resume Python 状态机分离。
.agents/skills/asu/SKILL.md                        导入的 ASu 经历改写 Skill。
.agents/skills/asu-resume/SKILL.md                 导入的 ASu 简历制作 Skill。
.agents/skills/offer/SKILL.md                      投递进度记录 Skill。
.agents/skills/contributor/SKILL.md                GitHub 贡献 Skill。
.agents/skills/*/agents/openai.yaml                对应 Skill 的发现元数据，不是模型调用代码。
.agents/third_party/asu-skills/*                   ASu-skills 的导入说明、锁文件和许可证。
.agents/assets/resume-data-template.json           通用简历数据示例。
.agents/assets/resume-template-editable.html       可编辑单页 HTML 模板。
.agents/assets/resume-template-two-page.html       两页 HTML 模板。
.agents/assets/asu-resume-template.html            ASu HTML 模板。
.agents/assets/application-tracker.html            投递追踪器 HTML。
.agents/assets/templates-html/01..18-*.html         18 份静态大厂极简 HTML 模板；custom-resume 不读取。
.agents/assets/icons/*.svg                         HTML 模板图标。
.agents/assets/logos/*.svg                         HTML 模板品牌 Logo。
.agents/assets/*.png|*.jpg|*.svg                   Skill 文档和模板预览素材；custom-resume 不读取。
```

### 1.3 `.codex/agents/`：声明式子 Agent 配置

```text
custom-resume-writer.toml             Writer 的只读 developer_instructions；不指定 model。
custom-resume-asu-writer.toml         ASu Writer 的只读 developer_instructions；不指定 model。
custom-resume-auditor.toml            选材/融合后 Auditor 的只读 developer_instructions；不指定 model。
custom-resume-hr-reviewer.toml        HR Reviewer 的只读 developer_instructions；不指定 model。
```

这里没有 Coordinator、JD Analyst、Capability Mapper、Selection Scorer 或 Fusion Judge 的独立 Agent 配置。它们由当前主 Codex 按 Markdown Prompt 文字执行，是否真的隔离不能由仓库代码证明。

### 1.4 根 `scripts/`：内容系统之外的下游脚本

```text
scripts/create_job_workbook.py             把岗位数据写成 XLSX 工作簿；不调用 custom-resume。
scripts/render_resume_pdf.ps1              使用 Chrome/Edge 打印 HTML 到 PDF，并调用 PDF 工具做页数/文本检查。
scripts/approval_manifest_common.ps1       投递批准清单的公共规范化、哈希和内容指针复验函数。
scripts/create_approved_manifest.ps1       Dry Run 或提交不可变投递批准清单。
scripts/validate_approved_manifest.ps1     投递前重新验证批准清单、JD、答案、PDF 和内容指针。
```

这些脚本属于 PDF/投递门禁。`CoordinatorRun.commit_for_review()` 不调用它们。

### 1.5 `tests/`

```text
tests/custom_resume/test_models.py                 Pydantic 字段、枚举、跨字段规则和状态转换测试。
tests/custom_resume/test_orchestrator.py           CoordinatorRun 各方法和人工构造产物的状态测试。
tests/custom_resume/test_validators.py             融合稿硬校验测试。
tests/custom_resume/test_storage.py                staging、run、指针、审批和 stale 测试。
tests/custom_resume/test_fact_library.py           Markdown 事实解析、ID 迁移、fact diff 写回测试。
tests/custom_resume/test_exemplar_library.py       模范简历读取、哈希和关键词匹配测试。
tests/custom_resume/test_agent_prompts.py          检查 Prompt 是否包含指定文字；不执行 Prompt。
tests/custom_resume/test_eval_harness.py            评测 fixture、盲评打包、解盲和汇总测试。
tests/custom_resume/test_harness_integration.py     Skill/脚本之间的字符串级集成约束测试。
tests/custom_resume/test_skill_scaffold.py          SKILL.md 和 openai.yaml 元数据测试。
tests/custom_resume/fixtures/evals/*                5 个 AI PM 固定评测案例、事实快照和评分规则。
tests/custom_resume/fixtures/game-production-*      游戏制作 PM 扩展案例和规则。
tests/custom_resume/fixtures/selection-v1.2/*       选材反例输入。
tests/custom_resume/fixtures/transfer-v1.3/*        能力迁移反例输入。
tests/custom_resume/fixtures/hr-v1.4/*              HR 高标准反例输入。
tests/mock-ats.html                                 本地 ATS 页面模拟器。
tests/prompt-acceptance.md                          旧版 Prompt 手工验收记录。
```

当前测试结果：`110 passed in 8.07s`。测试没有真实模型客户端、网络模型调用或 Codex Agent 调用。

### 1.6 `docs/`

```text
docs/custom-resume-agent/PRD.md                     当前产品需求声明，不是运行入口。
docs/custom-resume-agent/ARCHITECTURE.md            目标/声明式模块架构；部分描述超过实际代码可证明范围。
docs/custom-resume-agent/agent.md                   角色和协作协议。
docs/custom-resume-agent/EVAL_PLAN.md               评测计划。
docs/custom-resume-agent/DEVELOPMENT.md             开发和验证规范。
docs/custom-resume-agent/TASKS.md                   任务状态记录。
docs/custom-resume-agent/RETROSPECTIVE_V1.1.md      V1.1 复盘。
docs/custom-resume-agent/RETROSPECTIVE_V1.2.md      V1.2 复盘。
docs/custom-resume-agent/eval-results/fixed-v1/*    5 个 AI PM 案例的历史生成、trace、盲评分和汇总快照。
docs/custom-resume-agent/eval-results/game-production-v1.1/* 1 个游戏 PM 案例的同类历史快照。
docs/*-2026-08-17.md                                旧版简历、ATS、飞书和策略回归记录。
docs/resume-agent-new-chat-handoff.md               旧对话迁移说明。
```

### 1.7 私有事实、岗位和实际运行目录

这些文件被 `.gitignore` 忽略，但在当前工作区真实存在并被代码读取。

```text
profile/01-candidate-profile.md            唯一候选人事实库；fact_library.py 解析其中的 HTML 注释 ID。
profile/preferences.md                     文风和选材偏好；normalize_run_input() 原样读成字符串。
profile/application-answers.md             网申答案；custom-resume Python 不读取。
profile/README.md                          私有资料目录和安全边界说明；custom-resume Python 不读取。
profile/resume-exemplars/README.md         私有模范简历格式说明。
profile/resume-exemplars/<id>/metadata.json       模范简历元数据和匹配条件。
profile/resume-exemplars/<id>/content-master.md  模范简历内容快照；当前实际有 1 份。
profile/drafts/                            个人草稿目录；custom-resume Python 不扫描。

applications/<公司>_<岗位>/jd.md          目录输入时的 JD 唯一读取位置。
applications/<公司>_<岗位>/manifest.json  岗位主 manifest；内容批准只更新其中 resume_content 子对象。
applications/<公司>_<岗位>/analysis.md    岗位分析文本；custom-resume Python 不读取。
applications/<公司>_<岗位>/resume-content/.pending/<run_id>.json  CoordinatorRun checkpoint。
applications/<公司>_<岗位>/resume-content/.pending/*-packet.json  手工运行留下的中间包；storage.py 不管理。
applications/<公司>_<岗位>/resume-content/.staging/<run>/*        commit 前 staging；当前有 1 个残留目录。
applications/<公司>_<岗位>/resume-content/runs/<run_id>/*         已提交不可变运行产物。
applications/<公司>_<岗位>/resume-content/current.json            只有内容明确批准后才存在；当前没有。
applications/<公司>_<岗位>/resume-content/work/*                  岗位专用人工运行代码和 JSON 中间件。
```

当前有 9 个 `applications/` 岗位目录。只有 `深蓝互动_产品PM-2027届校招（重返未来：1999）` 下存在 custom-resume 运行：11 个已提交 run、58 个 `.pending` 文件、1 个 `.staging` 残留目录和 13 个岗位专用 Python 脚本。11 个 run 的 `run.json.state` 全是 `needs_content_review`；没有 `resume-content/current.json`，所以当前没有已批准内容指针。

该岗位的 13 个一次性脚本实际职责如下：

```text
build_v14_checkpoint.py                 从旧 run 复制/改写分析、迁移、选材，构造新 checkpoint 和选材审计输入包。
advance_v14_to_drafting.py              读取选材审计 JSON，把 selection_approved 硬设为 true，生成 writer packet。
fuse_v14.py                             在源码中硬编码 Writer、ASu 和 Fusion 三套正文，构造对象并输出 Auditor packet。
prepare_hr_review_v14.py                重放 checkpoint、草稿和 fusion，读取 audit JSON，输出 HR Reviewer packet。
prepare_revision1_v14.py                在源码中构造首轮 HR 失败意见和修订版 Fusion，输出下一轮 Auditor packet。
prepare_hr_revision1_v14.py             读取修订轮 audit JSON，输出修订轮 HR packet。
commit_v14.py                           读取 HR response JSON，重放整条内存状态并 commit run。
rebuild_hr_response.py                  复制另一 run 的 HR JSON，替换 envelope、分数和文本后写成新响应。
writeback_mewgenics_facts.py            在源码中构造已批准 FactDiffArtifact 并直接写回事实库。
build_gamefit_revision_v14.py           复制旧 run，硬改自我能力、audit 和 HR 结果，直接提交一个新 run。
build_language_revision_v14.py          monkey-patch build_gamefit_revision_v14 的语言/游戏文本和评分，再调用其 main。
build_game_history_revision_v14.py      继续 monkey-patch 游戏经历和评分，再调用同一个 main。
build_game_reselection_revision_v14.py  再次 monkey-patch 游戏两条 bullet、评分和 HR 结果，生成当前最新 run。
```

### 1.8 其他实际目录

```text
jobs/inbox/                     待分析岗位文件；当前只有 .gitkeep。
jobs/approved/                  已批准投递清单；当前只有 .gitkeep。
jobs/README.md                  岗位输入和清单说明。
templates/                      当前为空。
.tmp/、tmp/                     历史打印、Chrome profile 和临时文件；不被 custom-resume 导入。
__pycache__/、.pytest_cache/    Python/pytest 缓存；不属于逻辑。
```

## 2. 真实执行路径

### 2.1 实际入口不是 Python 文件

1. 用户在 Codex 对话中提出“按 JD 定制简历”。
2. Codex 的 Skill 发现机制根据 `.agents/skills/custom-resume/SKILL.md:1-3` 或 `china-job-search/SKILL.md:8,31-35` 选择 Skill。
3. 主 Codex 阅读 `SKILL.md` 的自然语言步骤，自行决定何时读 Prompt、何时调用声明式子 Agent、何时调用 Python 函数。
4. 仓库没有一个文件把上述动作连成可执行程序；也没有 CLI 参数能从 JD 一路跑到 run。

所以“从入口文件开始 trace”只能分成两层：一层是 Skill 文字协议；另一层是被主 Codex 或一次性脚本按需调用的 Python 状态机。

### 2.2 通用 Python 状态机的完整路径

#### A. 输入规范化：`normalize_run_input()`

入口：`.agents/skills/custom-resume/scripts/orchestrator.py:188`。

1. `repo_root.resolve()`；`now` 为空时取当前 UTC；`run_id` 为空时调用 `storage.create_run_id()`。
2. 按 `source_type` 分支：
   - `directory`：必须传 `application_dir`；目录必须是仓库内 `applications/` 的直接子目录；必须已有 `jd.md`；读取并规范化换行（`orchestrator.py:204-222`）。
   - `text` 或 `url`：两者走完全相同的分支；必须传已确认 `company`、`role` 和已经取得的 `jd_text`。`url` 不会发 HTTP 请求。代码创建 `applications/<company>_<role>/jd.md`，如果已有内容不同则拒绝覆盖；若无 `manifest.json`，写入最小的 `status/company/role/jd_source`（`orchestrator.py:223-244`）。
3. 固定读取：
   - `profile/01-candidate-profile.md`
   - `profile/preferences.md`
   - 与 `role_family` 对应的本地 method card
4. `role_family` 只能是 `ai_product_manager` 或 `game_production_pm`，因为 `REFERENCE_CARDS[role_family]` 直接索引；其他值在 Pydantic 枚举阶段失败。
5. 调用 `load_matching_resume_exemplars()`：
   - 没有私有库目录：返回空 tuple。
   - metadata 不是 `approved_reference` 或岗位族不同：跳过。
   - JD 命中关键词少于阈值：跳过。
   - 内容哈希、质量门禁、时间或 run_id 不合法：整个规范化失败。
   - 匹配结果按关键词数、HR 分数、ID 排序，最多 2 份（`exemplar_library.py:165-194`）。
6. 计算 4 个 source digest。`reference_cards_sha256` 在有 exemplar 时实际是“method card + exemplar 元数据”的 bundle hash（`orchestrator.py:271-277`）。
7. 返回内存 `NormalizedRunInput`；其中 `NormalizedInputPacket` 是 Pydantic 对象，JD、事实、偏好和方法卡仍是裸字符串。

#### B. 创建或恢复：`CoordinatorRun.create()/resume()`

- `create()`（`orchestrator.py:427-444`）默认先构造一个 `mode=degraded` 的 `ReferenceResearchArtifact`，并把状态从 `not_started` 推到 `analyzing`。它不会执行网络研究。
- `resume()`（`orchestrator.py:447-480`）只恢复 checkpoint 中的分析、迁移、选材和选材审计；如果 source digest、application_dir 或 role_family 不一致，拒绝恢复。
- checkpoint Schema 只允许 `analyzing`、`needs_input`、`awaiting_reference_approval`、`awaiting_selection_approval`、`drafting`（`models.py:1487-1495`）。融合、审计、HR 状态不能从 checkpoint 恢复。

#### C. 参考资料分支

1. 调用者可用 `record_reference_research()` 注入一个外部构造的 `ReferenceResearchArtifact`。
2. `qualified=true` 的条件由 Pydantic 校验：至少一份合格 resume sample、一份合格 official role source，并且有 selection rules（`models.py:1424-1434`）。仓库没有抓取或构造这些 source 的实现。
3. 未达标时必须是 `degraded`；分析完成后状态进入 `awaiting_reference_approval`。
4. `approve_reference_degradation()` 只有在该状态、`approval_granted=true`、reason 非空时通过；随后进入选材门禁。

#### D. JD 分析、证据映射、事实问题

1. 调用者必须一次性交给 `record_analysis()` 三个已经构造好的对象：`JDAnalysisArtifact`、`EvidenceMapArtifact`、`FactDiffArtifact`（`orchestrator.py:569-604`）。该方法本身不做语义分析。
2. 三个对象必须与 input packet 的 run_id、schema_version、source_digests 一致；JD role family 必须一致；evidence map 不得预批准。
3. 事实分支：
   - `confirmation_status=pending` 且 questions 或 operations 非空：进入 `needs_input`。
   - pending 但 questions/operations 都为空：被当作“没有未解决事项”，直接进入参考/选材分支。
   - questions-only 的 approved/rejected 结果由 `resolve_fact_diff()` 接收。
   - 有 approved operations 时不能用 `resolve_fact_diff()`；必须走 `apply_confirmed_fact_diff()`。
4. `apply_confirmed_fact_diff()` 会原子写回 `profile/01-candidate-profile.md`、重算事实哈希、清空 transfer/selection/audit，并回到 `analyzing`（`orchestrator.py:649-713`）。

#### E. 能力迁移、选材和人工批准

1. 调用者先用 `fact_library.parse_fact_records()` 把 Markdown 事实库变成 `ExperienceRecord`/`FactRecord` 字典。
2. Schema 1.2/1.3 必须调用 `record_capability_transfer_map()`：
   - 必须覆盖所有 WORK/PROJECT experience。
   - 每段经历必须有 8 个 category scan。
   - candidate transfer 必须关联现有事实问题，不能带事实或 writable scope。
   - 其他 transfer 的事实必须属于同一 experience。
3. `record_experience_selection()`：
   - 选材提案不能预批准。
   - 必须覆盖完整 WORK/PROJECT 池。
   - Schema 1.2/1.3 必须引用 capability map 的 canonical hash。
   - transfer credit 不能超过 distance multiplier，也不能超过对应组件分数。
   - Pydantic 另行重算总分、tier、至少两段 WORK、个人项目相似组上限、低分 WORK override 和 25% auxiliary quota。
4. `selection_auditor_packet()` 生成一个裸 `dict`；代码不调用 Auditor。
5. 外部返回 `SelectionAuditArtifact` 后，`record_selection_audit()` 只检查 envelope、phase、行 ID 集合和 `passed`。失败直接抛 `HumanGateError`，没有自动重算。
6. `approve_selection()` 要求：
   - selection 与提案除 `selection_approved/approved_at` 外完全相同。
   - 选材审计已经通过。
   - 至少一段入选。
   - 方法把入选 requirement/fact/experience/transfer ID 写回新的 input packet，状态进入 `drafting`。

#### F. 写作、融合和确定性校验

1. `writer_packet()` 返回裸 `dict`，包含已批准 WORK/PROJECT、固定 EDU/SKILL baseline、事实、transfer、偏好、exemplar 和 content budget（`orchestrator.py:988-1095`）。
2. 代码不读取 `writer.md`/`asu-writer.md`，也不调用 `.codex/agents/*.toml`。调用者必须自行得到两个 `DraftArtifact`。
3. 正常模式 `record_drafts()` 要求一个 `writer` 和一个 `asu_writer`，但只检查 envelope 和 agent 枚举；不检查实际 prompt、模型、调用隔离或 packet hash。
4. 子 Agent 不可用时，调用者必须显式把 mode 改成 `single_agent_degraded`，才可记录一个 Writer 稿；代码会补一份 ASu `AgentFailureArtifact`。
5. 调用者自行构造 `FusionArtifact` 并调用 `record_fusion()`：
   - state 只能是 `drafting` 或 `auditing`。
   - blind_dual 时两个 draft 必须存在。
   - 最多允许 3 个 fusion（初稿 + 2 次修订）。
   - 除第一次外，前一 fusion 必须已有 audit。
   - 调用 `validate_fusion_content()`。
6. 硬校验分支包括：未批准选材、板块/能力标题变化、未知/重复经历、板块错位、immutable heading 改动、未知或跨经历事实、未确认 provenance、教育基线不一致、未知 requirement、无事实支持的数字、遗漏入选经历、超 bullet budget、auxiliary 超 25%、候选建议泄漏。1500 中文字符和 14 条经历 bullet 只产生 warning。
7. 有任一 hard finding：抛 `DeterministicGateError`，fusion 不进入 history，也不会调用 Auditor。
8. 通过：记录 fusion/validation；首次从 `drafting` 进入 `auditing`。

#### G. Auditor、HR Reviewer 和修订分支

1. `auditor_packet()` 只在当前 validation 通过且 fusion 尚未审计时生成裸 `dict`。
2. 外部 `AuditArtifact` 进入 `record_audit()`：
   - 必须逐字回显 deterministic pass/findings。
   - `revisions` 数量必须等于当前 fusion revision count。
   - `reselect_required=true`：走 `_return_to_selection()`。
   - disposition=`passed` 且 schema=1.3：进入 `hr_reviewing`。
   - disposition=`passed` 且旧 schema：进入 `needs_content_review`。
   - 未通过且已经第 2 次修订：进入 `needs_content_review`。
   - 未通过且未到上限：状态保持 `auditing`，等待调用者再交一个 FusionArtifact。
3. `_return_to_selection()`：
   - 已有 selection revision 少于 2：记录一次，清空批准 ID、draft、selection audit，回到 `awaiting_selection_approval`。
   - 已经有 2 次：直接进入 `needs_content_review`，不再重选。
4. Schema 1.3 的 `hr_reviewer_packet()` 要求 base audit passed，输出裸 `dict` 和 8.5 高标准门禁。
5. `record_hr_review()` 分支：
   - `passed=true`：进入 `needs_content_review`。
   - `reselect_required=true`：走 `_return_to_selection()`。
   - disposition=`revise`：回到 `auditing`，等待新 FusionArtifact。
   - disposition=`needs_input` 或 `needs_review`：都进入 `needs_content_review`；不会回到前面的 `needs_input` 事实问答状态。

#### H. 提交与内容批准

1. `commit_for_review()` 只要求 state=`needs_content_review` 和各必需产物存在。它允许“审计/HR 未通过但修订已耗尽”的 run 被提交，只是之后不能批准。
2. `RunStage` 先写入 `resume-content/.staging/<run_uuid>/`，计算每个文件 SHA-256，再原子移动到 `resume-content/runs/<run_id>/`。
3. 生成的 `content-master.md` 与 `one-page-density.md` 当前写入完全相同的字符串（`orchestrator.py:1590-1594`）。
4. `run.json.state` 固定写成 `needs_content_review`。
5. `approve_content()/finalize_content()` 只有在用户批准、base audit passed、Schema 1.3 HR passed 时调用 `storage.approve_run()`。
6. `approve_run()` 不修改不可变 run 的 `run.json`；它写 `resume-content/current.json`，并更新岗位 `manifest.json.resume_content`。内存 state 变成 `approved`，已提交 run 仍显示 `needs_content_review`。
7. `refresh_stale_status()` 可在引用事实值改变时把 current pointer 和 manifest summary 标成 `stale`，但当前没有生产入口自动调用它。

### 2.3 当前最新实际 run 的执行路径

现存最新 run 是 `cr_20260829T112758_games2`。它不是由一个通用入口产生，而是运行：

`applications/深蓝互动_产品PM-2027届校招（重返未来：1999）/resume-content/work/build_game_reselection_revision_v14.py`

真实顺序如下：

1. 该脚本 import `build_game_history_revision_v14`；后者 import `build_gamefit_revision_v14`。
2. import 过程中通过修改 `base.OLD_RUN_DIR`、`base.RUN_ID`、`base.CREATED_AT`、正文数组和函数引用，连续 monkey-patch 基础脚本（`build_game_history_revision_v14.py:8-15,33-60,131-132`；`build_game_reselection_revision_v14.py:8-16,41-116,191-192`）。
3. `if __name__ == "__main__"` 调用被 patch 后的 `base.main()`。
4. `base.main()` 调用通用 `normalize_run_input()` 和 `CoordinatorRun.create()`。
5. 它从上一个 run 读取 `reference-research.json`、`jd-analysis.json`、`evidence-map.json`、`capability-transfer-map.json`、`experience-selection.json`、`selection-audit-pre.json`、两个 draft、fusion、audit 和 HR review，然后替换成新 run 的 envelope（`build_gamefit_revision_v14.py:90-104,222-300`）。
6. 它把 `REQ-006` evidence mapping 和自我能力事实硬改为脚本内的值。
7. 它创建 `pending + 空 questions/operations` 的 FactDiffArtifact；通用状态机把它视为无需提问。
8. 它复用旧 capability map、selection 和 selection audit，只替换 envelope；随后在代码中把 selection 改为 `selection_approved=true`，没有读取新的用户批准记录（`build_gamefit_revision_v14.py:267-287`）。
9. 它复用旧 Writer/ASu draft 并改写能力区；最新脚本额外插入新的游戏 bullet。
10. 它复用旧 FusionArtifact，改写能力区和 decisions，运行 deterministic validation。
11. validation 失败：打印 report 并抛错；这是该路径唯一会阻止提交的自动质量分支。
12. validation 通过：`build_audit_payload()` 复制旧 audit，把 truth、quality、disposition 和分数硬设为通过；`build_hr_payload()` 复制旧 HR review，把 recommendation、分数、缺陷和 disposition 硬设为通过（基础实现在 `build_gamefit_revision_v14.py:126-205`，后续脚本继续覆盖具体分数）。
13. Pydantic 接受这两个对象后，脚本调用 `record_audit()`、`record_hr_review()`、`commit_for_review()`。
14. 结果 run 的结构和哈希有效，`validate_run.py` 返回 `passed=true, review_ready=true`；但这条路径没有发生新的独立 Auditor 或 HR Reviewer 模型调用。

### 2.4 较早的分段人工路径

同一岗位目录还保留另一套分段路径：

```text
build_v14_checkpoint.py
  -> 生成 selection-auditor-packet.json
  -> 外部/人工放入 selection audit JSON（仓库无调用记录）
advance_v14_to_drafting.py
  -> 自动把提案标为 approved
  -> 生成 writer-packet.json
fuse_v14.py
  -> 不读取模型 writer response；直接在源码中构造 Writer/ASu/Fusion
  -> 生成 auditor-packet.json
prepare_hr_review_v14.py
  -> 读取外部 audit JSON
  -> 生成 hr-reviewer-packet.json
prepare_revision1_v14.py / prepare_hr_revision1_v14.py
  -> 重放并构造修订
commit_v14.py
  -> 读取 HR JSON 并提交
```

这套路径与 2.2 的通用状态机共用 Pydantic 和校验函数，但执行编排、正文生成、反馈修改和 JSON 文件搬运都写在岗位专用脚本里。

## 3. LLM 调用清单

### 3.1 grep 结果

在当前工作区源码（包括被忽略的岗位专用脚本）检索了 OpenAI/Anthropic/Responses/Chat Completions/messages/create、`model=`、API key、base URL、LiteLLM、LangChain、Ollama 和 DeepSeek 等调用模式。结果为 0。

| 调用位置（文件:行号） | 用的什么模型 | system prompt 在哪/多长 | 输入输出结构 |
| --- | --- | --- | --- |
| 无 | 无；仓库没有模型 API 客户端 | 无 | 无 |

`requirements.txt` 也只有 Pydantic，不包含任何模型 SDK。`eval_harness.py` 的 `--generated` 和 `--scores` 都是外部已经生成的文件输入，不是模型调用。

### 3.2 存在的 Agent 配置不是调用代码

| 声明位置 | model | developer/system 级文字 | 约定输出 |
| --- | --- | --- | --- |
| `.codex/agents/custom-resume-writer.toml:1-6` | 未指定，由 Codex 宿主决定 | 同文件 `developer_instructions`，584 字符 | DraftArtifact 或 AgentFailureArtifact |
| `.codex/agents/custom-resume-asu-writer.toml:1-6` | 未指定，由 Codex 宿主决定 | 同文件 `developer_instructions`，635 字符 | DraftArtifact 或 AgentFailureArtifact |
| `.codex/agents/custom-resume-auditor.toml:1-6` | 未指定，由 Codex 宿主决定 | 同文件 `developer_instructions`，983 字符 | SelectionAuditArtifact、AuditArtifact 或 AgentFailureArtifact |
| `.codex/agents/custom-resume-hr-reviewer.toml:1-6` | 未指定，由 Codex 宿主决定 | 同文件 `developer_instructions`，881 字符 | HrReviewArtifact |

这些 TOML 没有 `model` 字段。run manifest、draft、audit 和 HR review 也没有 model、provider、prompt hash、agent invocation ID 或 response ID 字段。

### 3.3 阶段 Prompt 清单

下表是仓库里的任务 Prompt，而不是由 Python 绑定的 system prompt。长度按当前 UTF-16 字符串 `.Length` 统计；行号为当前文件。

| Prompt 文件 | 长度 | 声明输入 | 声明输出 |
| --- | ---: | --- | --- |
| `jd-analysis.md:7-20` | 1,611 字符 / 28 行 | envelope、JD、source metadata、方法卡 | JDAnalysisArtifact |
| `jd-analysis-game-production.md:7-21` | 2,061 / 29 | envelope、JD、role_family、游戏方法卡 | JDAnalysisArtifact |
| `capability-transfer.md:7-21` | 2,225 / 29 | envelope、JD analysis、完整经历池、facts、evidence map、questions | CapabilityTransferMapArtifact |
| `experience-selection.md:3-23` | 3,146 / 31 | JD analysis、经历池、facts、transfer map/hash、规则、exemplars、preferences | ExperienceSelectionArtifact |
| `selection-audit.md:5-23` | 2,607 / 31 | 完整池、facts、JD、transfer、两套分数、偏好、exemplars、proposal | SelectionAuditArtifact |
| `writer.md:7-46` | 5,002 / 54 | writer_packet 中的批准事实和边界 | DraftArtifact(writer) |
| `writer-game-production.md:7-37` | 5,381 / 45 | 游戏岗位 writer_packet | DraftArtifact(writer) |
| `asu-writer.md:7-37` | 4,491 / 45 | 与 Writer 同语义包 | DraftArtifact(asu_writer) |
| `asu-writer-game-production.md:7-37` | 4,992 / 45 | 游戏岗位同语义包 | DraftArtifact(asu_writer) |
| `fusion.md:7-25` | 4,154 / 33 | 两稿、事实、边界、baseline、mode | FusionArtifact |
| `auditor.md:7-42` | 6,023 / 50 | pre_draft 或 post_fusion 包 | SelectionAuditArtifact 或 AuditArtifact |
| `hr-reviewer.md:7-54` | 5,491 / 62 | schema 1.3 fusion、base audit、facts、selection、高标准门禁 | HrReviewArtifact |

代码没有记录一次实际调用究竟加载了上述哪个 Prompt、加载了多长内容或使用了哪个模型。现存 JSON 只能证明满足了 Schema，不能证明其来源是对应 Prompt。

## 4. 核心循环

### 4.1 循环实现在哪里

代码里没有 `while`/`for` 形式的“生成 -> 评审 -> 再生成”执行循环。现有实现是 `CoordinatorRun` 的几个状态方法组成的协议：

```text
record_fusion()      orchestrator.py:1215-1250
auditor_packet()     orchestrator.py:1252-1302
record_audit()       orchestrator.py:1304-1331
hr_reviewer_packet() orchestrator.py:1371-1430
record_hr_review()   orchestrator.py:1432-1512
_return_to_selection() orchestrator.py:1150-1213
```

调用者必须在这些方法之间自行调用模型或自行构造下一个 Artifact。方法的 bool 返回值也没有统一上层消费代码。

### 4.2 触发“再生成”的实际条件

这里需要区分“重新生成 Writer/ASu 草稿”和“再交一个 FusionArtifact”。

- 确定性校验失败：`record_fusion()` 抛 `DeterministicGateError`。调用者需要修 FusionArtifact 后重试；失败的 fusion 不计入轮数。
- Auditor `reselect_required=true`：清空两个 draft，回到选材；重新批准后才进入 `drafting`，这是唯一明确允许重新记录 Writer/ASu drafts 的反馈路径。
- Auditor 未通过但不要求重选：状态保持 `auditing`。`record_drafts()` 只接受 `drafting`，因此不能替换 Writer/ASu drafts；调用者只能提交另一个 FusionArtifact。
- HR `disposition=revise`：从 `hr_reviewing` 回到 `auditing`。同样不能重新记录 Writer/ASu drafts，只能修 FusionArtifact。
- HR `reselect_required=true`：回选材，之后可重跑 drafts。
- HR `needs_input`：直接进入 `needs_content_review`，没有回到事实提问环节，也不会自动再生成。

因此当前“内容修订循环”本质上是“FusionArtifact -> validation -> Audit -> HR -> 新 FusionArtifact”，不是完整的“双 Writer 重新生成 -> 再融合”。

### 4.3 最大轮数

- `record_fusion()` 在 `len(fusion_history) >= 3` 时拒绝新稿（`orchestrator.py:1230-1233`）。即最多 1 个初始 fusion + 2 个修订 fusion。
- `RevisionRecord.round` 只允许 1..2，AuditArtifact.revisions 最多 2（`models.py:1170-1184`）。
- `HrReviewArtifact.revision_round` 只允许 0..2（`models.py:1248-1250`）。
- `_return_to_selection()` 单独允许最多 2 次 selection revision（`orchestrator.py:1153-1167`）。选材重选次数和内容 fusion 修订次数是两套计数。
- 第 2 次内容修订后仍不通过，状态进入 `needs_content_review`，但无法 `approve_content()`。

### 4.4 循环现在是否生效

状态和轮数约束在单元测试中生效；自动循环不存在。

当前真实岗位脚本存在两种绕法：

1. `fuse_v14.py:45-112,159-234` 直接在源码中写 Writer、ASu、Fusion 文本，不调用生成 Agent。
2. `build_gamefit_revision_v14.py:126-205` 及三个派生脚本直接构造通过的 Audit/HR 数据，再由 Pydantic 验证结构。最新 run 没有走独立反馈调用。

所以，“最大两轮”对通过 `CoordinatorRun.record_fusion()` 提交的对象有效；“评审意见触发模型再生成”没有代码实现，是否发生完全依赖当前主 Codex 的人工编排。

## 5. 数据结构

以下是 `scripts/models.py` 当前实际 Pydantic 字段定义的直接摘录。为避免把数百行 validator 重复贴入本文，字段后的交叉约束仍以源文件 validator 和已导出的 JSON Schema 为准；这里没有把字段改写成另一个自创 Schema。

### 5.1 公共 envelope 和输入包

```python
class SourceDigests(StrictModel):
    jd_sha256: Sha256
    fact_snapshot_sha256: Sha256
    preferences_sha256: Sha256
    reference_cards_sha256: Sha256 | None = None


class ArtifactBase(StrictModel):
    schema_version: Literal["1.0", "1.1", "1.2", "1.3"] = SCHEMA_VERSION
    run_id: RunId
    created_at: datetime
    source_digests: SourceDigests


class NormalizedInputPacket(ArtifactBase):
    application_dir: str = Field(pattern=r"^applications[\\/][^\r\n]+$")
    source_type: SourceType
    source_locator: str
    role_family: RoleFamily = RoleFamily.AI_PRODUCT_MANAGER
    approved_requirement_ids: list[RequirementId] = Field(default_factory=list)
    approved_fact_ids: list[FactId] = Field(default_factory=list)
    approved_experience_ids: list[ExperienceId] = Field(default_factory=list)
    approved_transfer_ids: list[TransferId] = Field(default_factory=list)
```

`NormalizedRunInput` 不是 Pydantic Schema，而是内存 dataclass：

```python
@dataclass(frozen=True)
class NormalizedRunInput:
    packet: NormalizedInputPacket
    application_dir: Path
    jd_text: str
    fact_text: str
    preferences_text: str
    reference_cards_text: str
    resume_exemplars: tuple[ResumeExemplarMatch, ...] = ()
```

### 5.2 JD、证据和能力迁移

```python
class JobRequirement(StrictModel):
    requirement_id: RequirementId
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1)
    priority: RequirementPriority
    rationale: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)


class IdealEvidenceItem(StrictModel):
    requirement_id: RequirementId
    evidence_description: str = Field(min_length=1)
    candidate_specific: Literal[False] = False


class JDAnalysisArtifact(ArtifactBase):
    role_family: RoleFamily = RoleFamily.AI_PRODUCT_MANAGER
    job_goal: str = Field(min_length=1)
    business_problems: list[str] = Field(min_length=1)
    requirements: list[JobRequirement] = Field(min_length=1)
    ideal_evidence_blueprint: list[IdealEvidenceItem] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class EvidenceMapping(StrictModel):
    requirement_id: RequirementId
    coverage: CoverageLevel
    fact_ids: list[FactId] = Field(default_factory=list)
    selected: bool = False
    rationale: str = Field(min_length=1)
    gap_summary: str | None = None


class EvidenceMapArtifact(ArtifactBase):
    mappings: list[EvidenceMapping] = Field(min_length=1)
    selection_approved: bool = False
    approved_at: datetime | None = None


class CapabilityTransfer(StrictModel):
    transfer_id: TransferId
    experience_id: ExperienceId
    category: CapabilityCategory
    fact_ids: list[FactId] = Field(default_factory=list)
    source_action: str = Field(min_length=1)
    target_capability: str = Field(min_length=1)
    requirement_ids: list[RequirementId] = Field(min_length=1)
    distance: TransferDistance
    confidence: TransferConfidence
    credit_multiplier: Annotated[float, Field(ge=0, le=1)]
    writable_scope: str | None = None
    candidate_question_id: str | None = Field(default=None, pattern=r"^Q-[0-9]{3}$")


class CapabilityCategoryScan(StrictModel):
    experience_id: ExperienceId
    category: CapabilityCategory
    status: CapabilityStatus
    transfer_ids: list[TransferId] = Field(default_factory=list)
    rationale: str = Field(min_length=1)


class CapabilityTransferMapArtifact(ArtifactBase):
    experience_ids: list[ExperienceId] = Field(min_length=1)
    transfers: list[CapabilityTransfer] = Field(default_factory=list)
    scans: list[CapabilityCategoryScan] = Field(min_length=1)
```

### 5.3 选材和事实差异

```python
class TransferScoreCredit(StrictModel):
    transfer_id: TransferId
    component: ScoreComponent
    base_points: Annotated[int, Field(ge=0, le=30)]
    credited_points: Annotated[int, Field(ge=0, le=30)]


class PortfolioValue(StrictModel):
    section_balance: Annotated[int, Field(ge=0, le=5)]
    capability_diversity: Annotated[int, Field(ge=0, le=5)]
    narrative_uniqueness: Annotated[int, Field(ge=0, le=5)]
    non_redundancy: Annotated[int, Field(ge=0, le=5)]
    total: Annotated[int, Field(ge=0, le=20)]


class SectionBalanceOverride(StrictModel):
    experience_id: ExperienceId
    reason: str = Field(min_length=1)
    compared_alternative_ids: list[ExperienceId] = Field(min_length=1)
    approved_at: datetime
    max_bullets: Literal[2] = 2


class ExperienceCandidateScore(StrictModel):
    experience_id: ExperienceId
    fact_ids: list[FactId] = Field(min_length=1)
    responsibility_score: Annotated[int, Field(ge=0, le=30)]
    process_delivery_score: Annotated[int, Field(ge=0, le=20)]
    result_score: Annotated[int, Field(ge=0, le=15)]
    domain_score: Annotated[int, Field(ge=0, le=10)]
    incremental_coverage_score: Annotated[int, Field(ge=0, le=15)]
    evidence_strength_score: Annotated[int, Field(ge=0, le=10)]
    job_task_evidence: JobTaskEvidenceLevel
    total_score: Annotated[int, Field(ge=0, le=100)]
    tier: ExperienceTier
    matched_requirement_ids: list[RequirementId] = Field(default_factory=list)
    incremental_requirement_ids: list[RequirementId] = Field(default_factory=list)
    selected: bool = False
    proposed_bullet_count: Annotated[int, Field(ge=0, le=14)] = 0
    rationale: str = Field(min_length=1)
    omission_reason: str | None = None
    user_override_reason: str | None = None
    capability_transfer_ids: list[TransferId] = Field(default_factory=list)
    transfer_score_credits: list[TransferScoreCredit] = Field(default_factory=list)
    portfolio_value_score: PortfolioValue | None = None
    similarity_group: str | None = Field(default=None, min_length=1, max_length=80)
    is_personal_development: bool = False


class ExperienceSelectionArtifact(ArtifactBase):
    candidates: list[ExperienceCandidateScore] = Field(min_length=1)
    capability_transfer_map_sha256: Sha256 | None = None
    section_balance_override: SectionBalanceOverride | None = None
    honest_weak_draft: bool = False
    selection_approved: bool = False
    approved_at: datetime | None = None


class SelectionAuditRow(StrictModel):
    experience_id: ExperienceId
    verdict: SelectionAuditVerdict
    rationale: str = Field(min_length=1)


class SelectionAuditArtifact(ArtifactBase):
    phase: SelectionAuditPhase
    rows: list[SelectionAuditRow] = Field(min_length=1)
    passed: bool
    reselect_required: bool = False
    issue_codes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class FactDiffOperation(StrictModel):
    operation_id: str = Field(pattern=r"^FD-[0-9]{3}$")
    action: DiffAction
    experience_id: ExperienceId
    target_fact_id: FactId | None = None
    proposed_fact_id: FactId | None = None
    old_value: str | None = None
    new_value: str = Field(min_length=1)
    provenance: FactProvenance
    estimate_basis: str | None = None
    confirmation_status: ConfirmationStatus = ConfirmationStatus.PENDING
    confirmed_at: datetime | None = None


class FactQuestionOption(StrictModel):
    option_id: str = Field(pattern=r"^[A-Z]$")
    label: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1)


class FactGapQuestion(StrictModel):
    question_id: str = Field(pattern=r"^Q-[0-9]{3}$")
    requirement_ids: list[RequirementId] = Field(min_length=1)
    prompt: str = Field(min_length=1)
    options: list[FactQuestionOption] = Field(min_length=2, max_length=4)
    status: QuestionStatus = QuestionStatus.UNANSWERED
    selected_option_id: str | None = Field(default=None, pattern=r"^[A-Z]$")
    answer_text: str | None = None


class FactDiffArtifact(ArtifactBase):
    source_fact_sha256: Sha256
    result_fact_sha256: Sha256 | None = None
    confirmation_status: ConfirmationStatus = ConfirmationStatus.PENDING
    questions: list[FactGapQuestion] = Field(default_factory=list, max_length=5)
    operations: list[FactDiffOperation] = Field(default_factory=list)
```

事实库解析后实际传给 orchestrator 的类型不是 JSON Schema，而是：

```python
@dataclass(frozen=True)
class FactRecord:
    fact_id: str
    experience_id: str
    value: str
    provenance: str
    line_number: int
    metadata: dict[str, str]


@dataclass(frozen=True)
class ExperienceRecord:
    experience_id: str
    category: str
    heading: str
    immutable_tokens: tuple[str, ...]
    facts: tuple[FactRecord, ...]
```

### 5.4 草稿、融合和校验

```python
class CandidateSuggestion(StrictModel):
    suggestion_id: str = Field(pattern=r"^CAND-[0-9]{3}$")
    category: Literal["process", "tool", "result", "estimate"]
    question: str = Field(min_length=1)
    suggested_text: str = Field(min_length=1)
    estimate_range: str | None = None


class ResumeBullet(StrictModel):
    bullet_id: BulletId
    text: str = Field(min_length=1)
    fact_ids: list[FactId] = Field(min_length=1)
    requirement_ids: list[RequirementId] = Field(default_factory=list)
    primary_value: str = Field(min_length=1)


class ResumeEntry(StrictModel):
    experience_id: ExperienceId
    heading: str = Field(min_length=1)
    bullets: list[ResumeBullet] = Field(min_length=1)


class ResumeSection(StrictModel):
    name: ResumeSectionName
    entries: list[ResumeEntry] = Field(default_factory=list)


class DraftArtifact(ArtifactBase):
    agent: DraftAgent
    sections: list[ResumeSection] = Field(min_length=4, max_length=4)
    candidate_suggestions: list[CandidateSuggestion] = Field(default_factory=list)


class FusionDecision(StrictModel):
    decision_id: str = Field(pattern=r"^DEC-[0-9]{3}$")
    action: FusionAction
    source_bullet_ids: list[BulletId] = Field(min_length=1)
    output_bullet_id: BulletId | None = None
    output_text: str | None = None
    fact_ids: list[FactId] = Field(default_factory=list)
    requirement_ids: list[RequirementId] = Field(default_factory=list)
    rationale: str = Field(min_length=1)


class FusionArtifact(ArtifactBase):
    sections: list[ResumeSection] = Field(min_length=4, max_length=4)
    decisions: list[FusionDecision] = Field(min_length=1)


class AuditFinding(StrictModel):
    error_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    severity: Severity
    artifact: str = Field(min_length=1)
    field_path: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ContentMetrics(StrictModel):
    chinese_character_count: Annotated[int, Field(ge=0)]
    experience_bullet_count: Annotated[int, Field(ge=0)]
    total_bullet_count: Annotated[int, Field(ge=0)]


class DeterministicValidationArtifact(ArtifactBase):
    passed: bool
    findings: list[AuditFinding] = Field(default_factory=list)
    metrics: ContentMetrics
```

固定 section 顺序和能力标题是代码常量：

```python
EXPECTED_SECTION_ORDER = [
    ResumeSectionName.EDUCATION,
    ResumeSectionName.WORK,
    ResumeSectionName.PRACTICE,
    ResumeSectionName.ABILITIES,
]
EXPECTED_ABILITY_HEADINGS = ["专业硬技能", "综合软技能", "游戏经历", "语言能力"]
LEGACY_ABILITY_HEADINGS = ["专业硬技能", "综合软技能", "游戏体验", "语言能力"]
```

### 5.5 Auditor 和 HR Reviewer

```python
class TruthAudit(StrictModel):
    passed: bool
    findings: list[AuditFinding] = Field(default_factory=list)


class QualityDimension(StrictModel):
    score: Annotated[float, Field(ge=0, le=10)]
    evidence: list[str] = Field(min_length=1)
    recommendations: list[str] = Field(default_factory=list)


class QualityAudit(StrictModel):
    jd_coverage: QualityDimension
    selection_quality: QualityDimension | None = None
    evidence_depth: QualityDimension
    hr_scan: QualityDimension
    language_naturalness: QualityDimension
    gap_disclosure_passed: bool = True
    passed: bool
    override_reason: str | None = None


class RevisionRecord(StrictModel):
    round: Annotated[int, Field(ge=1, le=2)]
    issue_codes: list[str] = Field(min_length=1)
    changes: list[str] = Field(min_length=1)


class AuditArtifact(ArtifactBase):
    deterministic_passed: bool
    deterministic_findings: list[AuditFinding] = Field(default_factory=list)
    truth: TruthAudit
    quality: QualityAudit
    reselect_required: bool = False
    selection_issue_codes: list[str] = Field(default_factory=list)
    revisions: list[RevisionRecord] = Field(default_factory=list, max_length=2)
    disposition: AuditDisposition


class HrDecisionDimension(StrictModel):
    score: Annotated[float, Field(ge=0, le=10)]
    evidence: list[str] = Field(min_length=1)
    recommendations: list[str] = Field(default_factory=list)


class HrExperienceReview(StrictModel):
    experience_id: ExperienceId
    ten_second_impression: str = Field(min_length=1)
    effective_requirement_ids: list[RequirementId] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    defects: list[str] = Field(default_factory=list)
    omitted_fact_ids: list[FactId] = Field(default_factory=list)
    severity_score: Annotated[float, Field(ge=0, le=10)]
    interview_impact: InterviewImpact
    recommended_bullet_count: Annotated[int, Field(ge=1, le=4)]
    revision_instructions: list[str] = Field(default_factory=list)
    missing_fact_questions: list[str] = Field(default_factory=list)


class HrReviewArtifact(ArtifactBase):
    revision_round: Annotated[int, Field(ge=0, le=2)]
    recommendation: HrRecommendation
    overall_score: Annotated[float, Field(ge=0, le=10)]
    role_fit: HrDecisionDimension
    narrative_completeness: HrDecisionDimension
    evidence_specificity: HrDecisionDimension
    decision_readiness: HrDecisionDimension
    credibility: HrDecisionDimension
    experience_reviews: list[HrExperienceReview] = Field(min_length=1)
    issue_codes: list[str] = Field(default_factory=list)
    existing_fact_revision_sufficient: bool
    fact_questions_required: bool
    reselect_required: bool
    passed: bool
    disposition: HrReviewDisposition
```

### 5.6 checkpoint、run 和批准指针

```python
class ReferenceSource(StrictModel):
    title: str = Field(min_length=1)
    url: str = Field(pattern=r"^https://[^\s]+$")
    retrieved_at: datetime
    source_type: ReferenceSourceType = ReferenceSourceType.OPEN_SOURCE_METHOD
    qualified: bool = False


class ReferenceResearchArtifact(ArtifactBase):
    mode: ReferenceResearchMode
    local_card_sha256: Sha256
    missing_topics: list[str] = Field(default_factory=list)
    sources: list[ReferenceSource] = Field(default_factory=list)
    sanitized_method_cards: list[str] = Field(default_factory=list)
    selection_rules: list[str] = Field(default_factory=list)
    qualified: bool = False
    degradation_approved_at: datetime | None = None
    degradation_approval_reason: str | None = None
    error: str | None = None


class SelectionRevisionRecord(StrictModel):
    round: Annotated[int, Field(ge=1, le=2)]
    prior_selected_experience_ids: list[ExperienceId] = Field(min_length=1)
    issue_codes: list[str] = Field(min_length=1)
    requested_at: datetime


class RunCheckpointArtifact(ArtifactBase):
    state: ContentState
    execution_mode: ExecutionMode = ExecutionMode.BLIND_DUAL
    input_packet: NormalizedInputPacket
    reference_research: ReferenceResearchArtifact
    jd_analysis: JDAnalysisArtifact
    evidence_map: EvidenceMapArtifact
    fact_diff: FactDiffArtifact
    capability_transfer_map: CapabilityTransferMapArtifact | None = None
    experience_selection: ExperienceSelectionArtifact | None = None
    selection_audit: SelectionAuditArtifact | None = None
    selection_revisions: list[SelectionRevisionRecord] = Field(default_factory=list, max_length=2)


class RunManifestArtifact(ArtifactBase):
    state: ContentState
    execution_mode: ExecutionMode = ExecutionMode.BLIND_DUAL
    input_packet: NormalizedInputPacket
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    revision_count: Annotated[int, Field(ge=0, le=2)] = 0
    selection_revision_count: Annotated[int, Field(ge=0, le=2)] = 0
    selection_revisions: list[SelectionRevisionRecord] = Field(default_factory=list, max_length=2)
    error: RunError | None = None


class ReferencedFactDigest(StrictModel):
    fact_id: FactId
    value_sha256: Sha256


class CurrentPointer(StrictModel):
    schema_version: Literal["1.0", "1.1", "1.2", "1.3"] = SCHEMA_VERSION
    status: ContentState
    approved_run_id: RunId
    run_relative_path: str = Field(
        pattern=r"^resume-content[\\/]runs[\\/]cr_[0-9]{8}T[0-9]{6}_[a-z0-9]{6}$"
    )
    approved_at: datetime
    updated_at: datetime
    transaction_id: str = Field(pattern=r"^approval_[a-f0-9]{32}$")
    referenced_facts: list[ReferencedFactDigest] = Field(min_length=1)


class ResumeContentSummary(StrictModel):
    status: ContentState
    current_pointer: Literal["resume-content/current.json"] = (
        "resume-content/current.json"
    )
    approved_run_id: RunId
    updated_at: datetime
    transaction_id: str = Field(pattern=r"^approval_[a-f0-9]{32}$")
```

### 5.7 各代理之间的包没有 Schema

以下方法返回普通 `dict[str, Any]`，没有 Pydantic model、TypedDict 或导出 JSON Schema：

| 阶段 | 构造位置 | 顶层键 |
| --- | --- | --- |
| pre-draft Auditor | `orchestrator.py:873-918` | schema_version, input_packet, jd_analysis, evidence_map, capability_transfer_map, experience_selection, approved_resume_exemplars, complete_experience_pool, fact_count |
| Writer/ASu | `orchestrator.py:988-1095` | schema_version, input_packet, jd_analysis, evidence_map, selected_experiences, baseline_experiences, confirmed_facts, experience_selection, approved_capability_transfers, fixed_education_baseline, fixed_ability_headings, role_content_guidance, approved_resume_exemplars, preferences, content_budget |
| post-fusion Auditor | `orchestrator.py:1252-1302` | schema_version, fusion, jd_analysis, evidence_map, experience_selection, approved_resume_exemplars, capability_transfer_map, validation, referenced_fact_values, candidate_fact_values, revision_count, execution_mode |
| HR Reviewer | `orchestrator.py:1371-1430` | schema_version, run_id, created_at, source_digests, revision_round, jd_analysis, fusion, base_audit, experience_selection, approved_resume_exemplars, selected_fact_values, selected_fact_ids_by_experience, cited_fact_ids, high_standard_gate |

这些 dict 是当前真实的 Agent 边界。Prompt 中提到的部分输入（例如 quality rubric、完整方法卡正文）并不都出现在这些 dict 中；是否另行拼入上下文由主 Codex 决定，代码不可见。

## 6. 存量问题

### 6.1 没有端到端执行器

- `orchestrator.py` 没有 `main()`；对 `normalize_run_input` 和 `CoordinatorRun` 的可追踪调用只来自测试和被忽略的岗位专用脚本。
- `SKILL.md` 写的是顺序协议，不会自动调用函数。
- 结果是同一流程既可以按状态机严谨重放，也可以由任意脚本直接构造满足 Schema 的对象。

具体位置：`.agents/skills/custom-resume/scripts/orchestrator.py:188,402-1676`；`tests/custom_resume/test_orchestrator.py`；`applications/.../resume-content/work/*.py`。

### 6.2 仓库没有任何模型调用，也没有模型/Prompt 追溯

- 无模型 SDK 依赖、无 API 调用。
- `.codex/agents/*.toml` 不指定 model。
- Artifact 和 run manifest 不记录 provider、model、reasoning、Prompt hash、调用 ID 或 response ID。
- 因此无法从一个 run 证明“谁生成、谁审计、是否隔离、是否用了指定 Prompt”。

### 6.3 “独立双稿/独立审计”只靠调用者自律

- `record_drafts()` 只检查 envelope 和 `agent` 枚举（`orchestrator.py:1097-1107`）。
- `record_selection_audit()` 只检查 envelope、phase、row ID 和 passed（`orchestrator.py:920-935`）。
- `record_audit()` 不绑定 fusion hash，只比对 deterministic report 和 revision 数（`orchestrator.py:1304-1318`）。
- `record_hr_review()` 不绑定 fusion/audit hash，只检查 envelope、round、experience IDs 和事实集合（`orchestrator.py:1432-1502`）。
- 岗位脚本实际通过替换旧 Artifact envelope 复用审计结果，说明这个缺口不是理论问题（`build_gamefit_revision_v14.py:94-104,126-205,222-323`）。

### 6.4 最新实际 run 的 Audit 和 HR 通过结果是脚本生成的

- `build_gamefit_revision_v14.py:126-165` 复制旧 `audit.json`，清空 finding，设置 truth/quality/disposition 为 passed。
- `build_gamefit_revision_v14.py:168-205` 复制旧 `hr-review.json`，设置 `strong_push`、分数、无缺陷和 passed。
- `build_language_revision_v14.py:62-106`、`build_game_history_revision_v14.py:58-132`、`build_game_reselection_revision_v14.py:118-192` 继续 monkey-patch 分数和评语。
- Schema 校验会接受这些数据，因为它只校验内部一致性，不校验评价来源。

### 6.5 Writer、ASu 和 Fusion 也有一套源码硬编码实现

- `fuse_v14.py:45-112` 把 Writer/ASu 两稿正文写在 Python 列表中。
- `fuse_v14.py:159-234` 把 Fusion 正文和 decisions 写在 Python 中。
- 这与 `.codex/agents/*writer.toml` + `writer*.md`/`asu-writer*.md` 是同一件事的两套实现。
- 后续 `build_gamefit_revision_v14.py` 又通过复制旧 draft/fusion 并改写数组形成第三层变体。

### 6.6 反馈循环不能在非重选修订中重新记录双稿

- `record_drafts()` 仅允许 `state=drafting`（`orchestrator.py:1097-1099`）。
- Auditor 普通失败保持 `auditing`；HR revise 也转到 `auditing`（`orchestrator.py:1329-1331,1508-1510`）。
- `record_fusion()` 允许 auditing 下的新 fusion，但没有方法替换 Writer/ASu drafts。
- 所以“每轮重新生成双稿”在状态机里做不到；只有重选路径清空 draft 后才重新进入 drafting。

### 6.7 Fusion 与源 drafts 的关系没有被验证

- `FusionArtifact` 只校验输出 bullet 和 decision output 一一对应（`models.py:1064-1090`）。
- `record_fusion()` 不检查 `source_bullet_ids` 是否真实存在于当前 Writer/ASu draft，也不检查 `output_text/fact_ids` 是否可由源 bullet 推出（`orchestrator.py:1215-1247`）。
- 因此调用者可以给任意 `WRITER-NNN`/`ASU-NNN` ID，直接写一段新的 fusion，只要事实 ID、数字和板块硬校验通过。

### 6.8 checkpoint 只能恢复到 drafting，审计阶段靠手工重放

- `RunCheckpointArtifact` 不含 writer draft、fusion、validation、audit 或 HR history（`models.py:1472-1483`）。
- 支持状态止于 `drafting`（`models.py:1487-1495`）。
- `CoordinatorRun.resume()` 也不恢复这些 history（`orchestrator.py:468-480`）。
- 岗位脚本为继续审计/HR，反复从 JSON 重建整条内存状态，例如 `prepare_hr_review_v14.py:37-105` 和 `prepare_revision1_v14.py:140-175`。

### 6.9 参考研究没有实现，只有 Artifact 接口

- `CoordinatorRun.create()` 总是创建 degraded reference（`orchestrator.py:427-442`）。
- 仓库没有搜索同岗位简历、官方岗位源或构造 `ReferenceSource` 的代码。
- `record_reference_research()` 只能接收调用者已经做好的结果。

### 6.10 `reference_cards_sha256` 的名字与实际内容不一致

- 无 exemplar 时它是 method card hash。
- 有 exemplar 时它是 method card + exemplar bundle hash（`orchestrator.py:275-277`，`exemplar_library.py:197-219`）。
- `ReferenceResearchArtifact.local_card_sha256` 又被要求等于这个字段（`orchestrator.py:547-550`）。
- 因而字段名 `reference_cards_sha256`/`local_card_sha256` 在有 exemplar 时都不是纯本地 card hash。

### 6.11 pending 空 FactDiff 的语义与状态名不一致

- `FactDiffArtifact` 没有 questions/operations 时必须保持 `pending`（`models.py:891-895`）。
- `record_analysis()` 又只在 pending 且有 questions/operations 时进入 `needs_input`（`orchestrator.py:595-602`）。
- 实际脚本依赖“pending 但空内容”表达“没有事实差异”，例如 `build_gamefit_revision_v14.py:250-260`。

### 6.12 HR `needs_input` 没有回到事实输入状态

- `HrReviewDisposition.NEEDS_INPUT` 存在（`models.py:225-230`）。
- `record_hr_review()` 对它没有单独分支；除 passed/reselect/revise 外全部进入 `needs_content_review`（`orchestrator.py:1503-1512`）。
- 所以“HR 需要新事实”只会提交一个不可批准的 review run，不会形成可恢复的问题 -> fact diff -> 重生成路径。

### 6.13 运行校验 CLI 的 `passed` 和 `review_ready` 是两种含义，退出码只看前者

- `validate_run_directory()` 的 `passed` 只表示没有结构/哈希 finding。
- `review_ready` 才要求 validation、audit 和 HR 通过（`validate_run.py:108-123`）。
- CLI 在 `passed=true` 时退出 0，即使 `review_ready=false`（`validate_run.py:134-142`）。
- 自动化如果只看进程退出码，会把“结构有效但质量未通过”的 run 当成成功。

### 6.14 两个输出文件名字不同，内容完全相同

- `commit_for_review()` 把同一个 `content` 同时写到 `content-master.md` 和 `one-page-density.md`（`orchestrator.py:1590-1594`）。
- 当前没有 density 变体生成逻辑；`one-page-density.md` 的命名暗示了不存在的差异。

### 6.15 内容批准后的状态分散在三处，值不相同

- 内存 `CoordinatorRun.state` 变成 `approved`（`orchestrator.py:1656`）。
- `current.json.status` 和 `manifest.resume_content.status` 变成 `approved`（`storage.py:271-290,368-379`）。
- 不可变 `runs/<id>/run.json.state` 仍是 `needs_content_review`。
- 这是当前实际存储方式；只看 run.json 无法知道它是否后来被批准。

### 6.16 选材批准在岗位脚本里被程序化补上

- `advance_v14_to_drafting.py:37-48` 读取审计 JSON 后直接复制 selection 并写 `selection_approved=true`。
- `build_gamefit_revision_v14.py:278-287` 复用旧 selection audit 后同样直接批准。
- 代码没有接收或保存用户批准语句；只有一个时间值。是否真的有用户批准无法从 run 证明。

### 6.17 `.pending` 同时被当 checkpoint 目录和任意工作文件目录

- `storage.checkpoint_path()` 只定义 `.pending/<run_id>.json`（`storage.py:202-224`）。
- 当前同一目录存在 58 个 `*-writer-packet.json`、`*-auditor-packet.json`、validation 等手工文件。
- `remove_checkpoint()` 只删除 `<run_id>.json`（`storage.py:235-242`），不会清理这些文件。

### 6.18 残留 staging 和大量一次性运行代码不在版本控制中

- 当前有 1 个 `.staging` 目录，且同 run ID 已有已提交 run。
- 13 个 `resume-content/work/*.py` 和它们生成的 JSON 全被 `.gitignore:8` 忽略。
- 这些脚本实际决定了最新 run 的正文、分数和审批时间，但 Git 无法审阅、diff 或回滚它们。

### 6.19 重复和遗留逻辑

- 旧版：`.agents/agents/resume-optimizer-agent.md` + `.agents/prompts/campus-resume-optimizer.md` 仍描述一套完整简历生成流程；当前 Skill 仅在文字层标记 deprecated，没有代码路由器。
- 新版：custom-resume Prompt/状态机是一套；岗位 `resume-content/work/*.py` 又是一套。
- `sha256_bytes()` 在 `orchestrator.py:138`、`storage.py:46`、`fact_library.py:93`、`eval_harness.py:161` 分别重复；`exemplar_library.py` 还有 `_sha256()`。
- current ability heading 在 Pydantic 和 deterministic validator 中分别校验（`models.py:993-1004`、`validators.py:172-188`）；两处规则并不完全相同，Pydantic 接受 legacy `游戏体验`，当前 deterministic validator 拒绝。

### 6.20 未被生产路径调用或接近死代码的部分

- 根目录 `定制简历agent.txt`、`参考prompt.txt`：全仓无引用。
- `SelectionAuditPhase.POST_FUSION` 和 SelectionAuditArtifact 的 post-fusion `reselect_required` 分支（`models.py:181-183,789-792`）：orchestrator 的融合后审计实际使用 AuditArtifact；除模型定义/测试名外无调用。
- `ContentState.FAILED`：转换表大量允许进入 failed，但 CoordinatorRun 没有 `fail()` 或任何 `_transition(ContentState.FAILED)` 调用。
- `ContentState.AUDITING -> APPROVED` 在转换表允许（`models.py:1665-1672`），实际批准只从 `needs_content_review` 发生。
- `finalize_content()`（`orchestrator.py:1665-1676`）只是 `approve_content()` 的别名；生产代码无调用，只有测试使用。
- `refresh_stale_status()`（`storage.py:437-480`）只有测试调用；Skill 文字要求复验 stale，但没有 Python 入口自动运行它。
- 18 个 `templates-html`、ASu/Resume HTML 资产与 custom-resume 内容状态机没有导入关系；它们属于另一套制版 Skill。

## 7. 你的困惑

1. **哪条路径才算“当前生产路径”不明确。** README/SKILL 表明应由 Codex 主对话编排；通用 Python 又没有入口；最新实际 run 则由被忽略的一次性脚本生成。三者同时存在。

2. **现存 audit/HR response JSON 的来源无法确认。** 部分文件看起来是外部 Agent 输出，部分明确由 `rebuild_hr_response.py` 或 `build_gamefit_revision_v14.py` 复制改写。run 里没有调用 ID、模型、Prompt hash 或签名，无法区分。

3. **“blind_dual”现在是事实还是标签无法确认。** execution_mode 默认是 `blind_dual`，但代码只检查两个 DraftArtifact 存在。岗位脚本在同一 Python 文件中同时构造 Writer 和 ASu 文本，仍被记录为 blind_dual。

4. **参考研究由谁执行不明确。** Schema 和门禁存在，但仓库没有检索实现，也没有 Coordinator Agent 配置。只能推测由当前主 Codex 在仓库外完成，但运行产物没有调用证据。

5. **Prompt 到包的拼装方式不明确。** `writer_packet()` 等只返回裸 dict；Prompt 中要求的 method cards、quality rubric 等并不总在 dict 里。当前主 Codex是否额外拼接、以什么顺序拼接，代码不可见。

6. **岗位 `resume-content/work/` 是临时脚手架还是长期组成部分不明确。** 它们被忽略、不在文档源树中，却实际生成最新 run；其中还包含 monkey-patch 链、硬编码正文和硬编码审核分数。

7. **当前为何保留 58 个 pending 文件和 1 个 staging 目录不明确。** storage API 只认识一个 checkpoint 文件，剩余文件没有生命周期管理；staging 对应的 run 已经存在。

8. **11 个 run 全部 review-ready 但没有 current pointer，是否是有意状态不明确。** 代码将“内容验收通过”和“用户内容批准”严格分开，因此这可能是正常等待批准；也可能是批准步骤从未执行。仅凭当前文件无法判断。

9. **现有 `docs/custom-resume-agent/ARCHITECTURE.md` 中的“独立调用、继承当前 Codex 模型、完整修订链路”有多少是运行事实不明确。** 代码能证明 Schema 和状态约束，不能证明模型调用、隔离或 Prompt 使用；岗位脚本还给出了相反的实际样本。

10. **最新 run 的质量结论是否应被视为有效评审不明确。** 它通过全部 Pydantic、deterministic 和 run integrity 检查，但 Audit/HR 评分由脚本复制和硬设，不是可证明的独立评审。

---

本次验证记录：

- `python -m pytest -q`：110 passed。
- `models.py --export-dir <temp>` 与 `.agents/skills/custom-resume/schemas/`：17/17 文件哈希一致。
- 对当前 11 个已提交 run 执行 `validate_run.py`：11/11 `passed=true` 且 `review_ready=true`。
- 全仓模型 API grep：0 个调用位置。

这些结果只说明当前代码、Schema 和现存 run 内部自洽，不说明模型调用、Agent 隔离、人工批准或评审来源真实发生。
