# 定制简历 Agent V1.5 任务清单

> 状态：V1.5 文档已确认，T25–T27 已完成，T28 进行中
> 规则：V1.5 文档获用户确认前不得开始 T25 及之后的实现任务。每次只执行一个 Task。

## 状态说明

- `completed`：目标和验证完成。
- `in_progress`：实现或验证仍在进行。
- `in_review`：产物已生成，等待用户确认。
- `pending`：依赖尚未满足或尚未开始。
- `blocked`：存在明确外部阻塞。

## T00 安全基线

- 优先级：P0
- 状态：completed
- 目标：建立可追溯且不包含个人敏感资料的本地 Git 基线。
- 依赖：无。
- 范围：检查 `.gitignore`；排除事实库、答案库、申请产物和临时缓存；脱敏脚本示例；首次本地提交。
- 验收：`git check-ignore` 确认敏感目录被忽略；暂存扫描无真实联系方式；存在 root commit。
- 测试：`git status --ignored`、`git grep --cached`、`git log -1`。

## T01 建立模块文档

- 优先级：P0
- 状态：completed
- 目标：形成决策完整、互不冲突的产品与开发文档。
- 依赖：T00。
- 范围：PRD、Architecture、Agent 协议、Eval Plan、Development、Tasks；根规则入口；Legacy 开发流程入口。
- 验收：六份文档覆盖全局规范要求；产品范围、状态、Schema、质量门槛和阶段门禁一致。
- 测试：链接检查、术语搜索、状态/数字/门槛一致性检查、Git diff review。

## T02 Skill 脚手架与依赖清单

- 优先级：P0
- 状态：completed
- 目标：建立可发现但尚不执行完整业务的 `$custom-resume` Skill 骨架和 Python 测试环境。
- 依赖：T01 用户确认。
- 范围：`SKILL.md`、`agents/openai.yaml`、必要 references/scripts 目录、项目依赖清单、测试目录。
- 验收：显式和隐式触发描述清楚；PDF 请求排除；无占位文本；依赖可安装。
- 测试：Skill Creator `quick_validate.py`；Pydantic/pytest 导入检查。

## T03 领域 Schema 与状态机

- 优先级：P0
- 状态：completed
- 目标：实现所有结构化接口和合法状态转换。
- 依赖：T02。
- 范围：运行清单、JD 分析、证据映射、事实差异、草稿、融合、审计模型；严格枚举；状态机。
- 验收：未知字段拒绝；错误枚举和非法转换有清晰错误；Schema 可导出。
- 测试：模型正反例、缺失字段、未知字段、非法状态转换。

## T04 事实库解析与 ID 迁移预览

- 优先级：P0
- 状态：completed
- 目标：为现有 Markdown 事实库建立稳定 ID，不改变事实文本。
- 依赖：T03。
- 范围：解析、ID 校验、迁移预览、diff、来源元数据、源哈希并发保护。
- 验收：迁移前后移除 HTML 元数据后的正文完全一致；ID 唯一稳定；不直接写事实库。
- 测试：真实事实库只读预览、重复 ID、损坏元数据、并发哈希变化。
- 人工门禁：用户审核迁移 diff 后，另开任务执行写回。

## T05 事实 ID 迁移写回

- 优先级：P0
- 状态：completed
- 目标：把已批准的 ID-only diff 原子写入事实库。
- 依赖：T04 和用户明确批准 diff。
- 范围：仅增加隐藏元数据；生成备份摘要和验证报告。
- 验收：事实正文不变；重新解析通过；所有 ID 唯一。
- 测试：写前源哈希、写后正文对比、解析和 ID 校验。

## T06 不可变运行与产物存储

- 优先级：P0
- 状态：completed
- 目标：实现运行目录、原子提交、当前指针和精准失效。
- 依赖：T03、T04。
- 范围：run ID、临时目录、产物清单、current pointer、manifest 摘要、引用事实 digest。
- 验收：历史运行不可覆盖；指针与 manifest 一致；仅引用事实变化触发 stale。
- 测试：重复 run ID、写入中断、无关/相关事实变化、指针不一致。

## T07 Prompt 与只读自定义代理

- 优先级：P0
- 状态：completed
- 目标：实现 JD 分析、Writer、ASu Writer、Fusion、Auditor Prompt 和三个项目级只读代理。
- 依赖：T03、T05。
- 范围：`.agents/prompts/custom-resume/` 和 `.codex/agents/`；继承当前模型，不配置外部 Provider。
- 验收：每个 Prompt 明确输入、输出 Schema 和失败行为；Writer 互不可见；代理只读。
- 测试：配置解析、Prompt 契约静态检查、独立最小样例输出。

## T08 协调器工作流

- 优先级：P0
- 状态：completed
- 目标：完成单 JD 内容闭环。
- 依赖：T05、T06、T07。
- 范围：三种输入、参考路由、JD 分析、最多 5 个问题、fact diff、人工检查点、双稿、融合、审计、两轮修订、批准。
- 验收：所有步骤由状态机驱动；人工门禁不可跳过；子代理失败不伪装成功。
- 测试：正常、事实不足、diff 拒绝、估值接受、代理失败和降级场景。

## T09 确定性内容校验器

- 优先级：P0
- 状态：completed
- 目标：在 Auditor 前阻止结构和真实性硬错误。
- 依赖：T03、T05、T08。
- 范围：事实引用、不可变字段、新数字、候选泄漏、四板块、产物完整性和内容预算报告。
- 验收：每类硬错误有稳定错误码、文件和字段定位。
- 测试：中文数字、百分比、区间、组合事实推导、缺失板块、非法候选。

## T10 主 Harness 集成

- 优先级：P1
- 状态：completed
- 目标：让 `china-job-search` 可显式调用新 Skill，同时保持旧流程默认可用。
- 依赖：T08、T09。
- 范围：调用边界、岗位 manifest 的 `resume_content` 摘要、内容状态与申请状态隔离。
- 验收：不生成 PDF；不推进申请状态；旧入口仍可运行。
- 测试：集成夹具、状态隔离、PDF/投递调用否定测试。

## T11 固定评测集与自动回归

- 优先级：P1
- 状态：completed
- 目标：建立 5 类脱敏 JD 的公平旧/新基线和盲评产物。
- 依赖：T08、T09、T10。
- 范围：夹具、旧流程重跑、新流程运行、匿名化、硬校验和评分表。
- 验收：五类样本齐全；同事实快照；可重复运行；不包含个人敏感字段。
- 测试：完整 pytest、fixture run validator、盲评包一致性。
- 证据：`docs/custom-resume-agent/eval-results/fixed-v1/`；五案真实性与质量门槛均通过，严格匿名 trace 不含 lane 身份。

## T12 切换与旧入口停用标记

- 优先级：P1
- 状态：completed
- 目标：满足发布门槛后把主 Harness 默认入口切到 `$custom-resume`。
- 依赖：T11 达标和用户明确批准。
- 范围：路由切换、旧 Prompt/Agent 标记 deprecated、文档更新；不删除历史文件。
- 验收：默认入口为新 Skill；旧入口可显式回退；无 PDF/投递行为回归。
- 测试：完整自动回归和一次真实内容验收演练。
- 证据：用户在完成深蓝 V1.4 内容验收和 T22 前向测试后明确要求接入自动投递流程；`china-job-search` 已将受支持岗位族默认路由至 `$custom-resume`，旧 Agent/Prompt 标记 deprecated 且只允许显式回退。批准清单 Schema 2 冻结内容运行、批准事务、`content-master.md`、JD、答案、review 和附件哈希，浏览器打开前由独立脚本复验；篡改内容母版的集成夹具被拒绝。完整 105 项 pytest、`compileall`、三个 Skill 的 `quick_validate.py`、PowerShell 语法检查和 `git diff --check` 均通过；未生成真实 PDF、未打开网站、未推进申请状态。

## T13 游戏研发 PM 角色族扩展与真实内容验收

- 优先级：P1
- 状态：completed
- 目标：在不改变 T12 默认路由的前提下，支持游戏研发/项目管理型产品 PM，并用用户指定 JD 运行到内容验收。
- 依赖：T11 和用户对范围扩展的明确授权。
- 范围：`game_production_pm` Schema、角色路由、方法卡、JD 分析 Prompt、脱敏扩展回归，以及“产品PM深蓝”真实运行。
- 验收：AI PM 五案证据继续有效；游戏扩展案例真实性及四项质量均过门槛；真实运行提交为 `needs_content_review`；不生成 HTML/PDF、不更新批准指针、不推进申请主状态。
- 测试：Schema/路由单测、正向游戏案例、事实缺口和对抗用例、全量 pytest、Skill 校验、真实运行产物校验。

## T14 V1.2 选材正确性修复

- 优先级：P0
- 状态：completed
- 目标：修复深蓝真实验收暴露的行业亲和替代岗位证据、强经历遗漏和审计自洽问题。
- 依赖：T13 失败复盘和用户批准的 V1.2 计划。
- 范围：参考降级审批、逐经历分项评分、70/55 阈值、行业亲和封顶、辅助 25% 配额、前后机会成本审计、短稿策略和 Schema 1.0 只读兼容。
- 验收：自动测试覆盖全部新门禁；深蓝旧稿脱敏负例因选材质量失败；旧真实运行不被修改。
- 测试：完整 pytest、compileall、Skill Creator 校验、Schema 导出和新运行验证。

## T15 深蓝 V1.2 重新选材与内容验收

- 优先级：P0
- 状态：in_review（运行已完成，但用户判定能力迁移、板块平衡和内容组合不通过）
- 目标：用 `产品PM深蓝.txt` 创建全新运行，先交付完整选材表，获批后生成新融合稿。
- 依赖：T14 完成并通过全部回归。
- 范围：内容分析、参考降级批准记录、选材表、双稿、融合和内容审计；不含 HTML/PDF/投递。
- 验收：游戏辅助经历不得为核心且总要点不超过 25%；强产品/项目经历均参与比较；内容评分达到 V1.2 门槛。

## T16 V1.3 能力迁移与板块平衡文档

- 优先级：P0
- 状态：completed
- 目标：把“能力发散、事实收敛”、双轴选材、板块平衡例外和固定内容结构转为可执行产品与工程协议。
- 依赖：T15 内容验收失败复盘，以及用户对全局选材原则的确认。
- 范围：更新 PRD、Architecture、Agent 协议、Eval Plan、Development 和 Tasks；不修改业务代码、Prompt、Skill、事实库或真实运行。
- 验收：能力迁移距离和可写边界明确；岗位匹配与组合价值分离；工作板块、同类项目、教育和自我能力规则互不冲突；Schema `1.2` 兼容策略清楚。
- 测试：文档链接/术语/版本检查、跨文档规则对照、Git diff review。
- 人工门禁：用户确认 V1.3 文档后才能开始 T17。

## T17 已确认事实与全局偏好写回

- 优先级：P0
- 状态：completed
- 目标：把已确认的教育展示规则和全局内容结构偏好写入唯一事实/偏好来源，并为翻译管理过程生成精确事实差异。
- 依赖：T16 用户确认。
- 范围：预览并原子执行“移除社会工作课程、固定汉语言文学课程”的事实差异；记录至少两项工作经历、同类个人项目最多两项和四类自我能力偏好；独立游戏翻译的分工、范围拆分、校对和进度事实必须先展示精确措辞，经用户另行确认后写回。
- 验收：事实修改有用户批准记录和源哈希保护；教育日期/专业等未授权事实不变；偏好可被后续运行读取；未确认翻译细节不入库。
- 测试：字节级 diff、事实解析、ID 稳定性、偏好读取和并发哈希冲突。
- 证据：事实库解析为 26 段经历、75 条唯一事实；`test_fact_library.py` 11 项通过；事实库与偏好文件均由 `.gitignore` 排除。

## T18 V1.3 能力迁移与组合选材实现

- 优先级：P0
- 状态：completed
- 目标：实现完整经历能力发散、证据收敛、双轴选材和可审计板块平衡。
- 依赖：T16 用户确认、T17 完成。
- 范围：Schema `1.2`、`capability-transfer-map.json`、迁移距离折算、组合价值、相似项目分组、工作数量、`section_balance_override`、教育锁定、自我能力分类，以及相应 Orchestrator/Writer/Fusion/Auditor Prompt 和验证器。
- 验收：每段经历均有事实支持的迁移链；`candidate` 不计分、不进入正文；两个分数不合并；例外不抬分且最多 2 个要点；Writer/Fusion 仍只能使用获批经历。
- 测试：模型、验证器、Prompt 契约、编排和存储单元/集成测试；Schema 导出；Skill Creator 校验；完整 pytest 与 compileall。
- 证据：Schema `1.2` 已导出 16 份 JSON Schema（含 `capability-transfer-map`）；84 项 `tests/custom_resume`/完整 pytest 全部通过；`compileall`、Schema JSON 解析、`git diff --check` 通过；Skill Creator `quick_validate.py` 在 Python UTF-8 模式下返回 `Skill is valid!`。

## T19 深蓝 V1.3 迁移与内容回归

- 优先级：P0
- 状态：in_progress（开发与深蓝内容回归已完成；等待用户内容验收）
- 目标：证明新系统既能发现独立游戏翻译的项目协同价值，也不会把合理推测伪装成事实。
- 依赖：T18 完成并通过自动回归。
- 范围：新增脱敏迁移正反例；用 `产品PM深蓝.txt` 创建全新运行，先停在能力迁移和选材确认，用户批准后再生成融合稿；不生成 HTML/PDF、不推进申请状态。
- 验收：翻译经历至少映射跨方协作、质量控制和按期交付；T17 已确认的范围拆分与成员分工可以迁移，但不得扩大为研发团队管理、产能/人才梯队或正式游戏版本排期；完整经历池、双轴选材、板块/同质化规则和五项质量门槛全部通过。
- 测试：定向夹具、旧稿负例、完整自动回归、运行目录校验和人工内容验收。
- 当前证据：首次运行 `cr_20260824T055322_c91e83` 因遗漏高价值 REQ-006 证据触发重新选材并作为失败谱系保留。用户批准 Round 1 后，事实库将社会工作二学位日期固定为 `2025/09–2027/06` 且不再写“预计毕业”；基于新事实快照创建运行 `cr_20260826T024240_29b940`，完成 22/22 经历复审、隔离双稿、融合和一次定向事实收紧。最终真实性审计通过，正向 JD 证据 8.0、选材质量 9.0、证据深度 9.0、HR 扫读 8.5、语言自然度 8.5，运行停在 `needs_content_review`；未生成 PDF、未更新批准指针、未推进投递状态。运行目录校验、Skill Creator 校验、`compileall`、`git diff --check` 与 84 项自动测试全部通过。

## T20 独立 HR 决策门禁与高标准修订

- 优先级：P0
- 状态：completed
- 目标：阻止“真实性和基础质量通过、但招聘方仍不愿推进”的诚实弱稿进入内容批准。
- 依赖：T19 的深蓝人工内容验收结论。
- 范围：Schema `1.3`、`hr_reviewing` 状态、独立只读 HR Reviewer、`hr-review.json`、逐经历叙事完整度与遗漏事实审查、`strong_push`/8.5 高门槛、现有事实修订/事实补问/重新选材三路路由、最多两轮全链路复审。
- 验收：基础 Auditor 通过后才能启动 HR Reviewer；HR 未通过不得批准；现有事实足够时按逐段意见定向修订，缺少事实时不得虚构扩写；历史 Schema 1.0–1.2 运行保持只读兼容。
- 测试：模型阈值与状态转换、产物完整性、修订上限、事实问题与重选路由、深蓝过度压缩负例、Prompt/Agent 隔离、完整自动回归。
- 证据：新增 Schema `1.3` 与 `hr-review.json`、`hr_reviewing` 状态、独立 `custom_resume_hr_reviewer`、`strong_push`/8.5 五维门槛、现有事实修订/事实补问/重选路由和批准阻断；深蓝 916 字/9 条且遗漏高价值事实的脱敏负例被固定为 HR `hesitate`。99 项完整 pytest、`compileall`、Skill Creator `quick_validate.py`、历史深蓝 Schema 1.2 运行校验及 `git diff --check` 全部通过。

## T21 证据叙事与关键词细节增强

- 优先级：P0
- 状态：completed
- 目标：把“简历讲故事”收敛为真实证据的选择、排序和讲透，并阻止职责清单、无细节关键词和弱经历注水通过内容门禁。
- 依赖：T20 完成；用户确认五项证据叙事规则。
- 范围：不改变 Schema 和四板块；更新 PRD、Agent 协议、Skill/Workflow、质量量表、Writer/ASu Writer/Fusion/Auditor/选材 Prompt 和 Prompt 契约测试。
- 验收：整稿遵循“岗位目标—核心证据—能力递进—可信结果”；核心经历整体覆盖问题/情境、个人行动、方法或决策、可信结果和个人边界；最强可核实证据优先；JD 关键词由工作/项目实际细节支撑。
- 测试：Prompt 契约定向测试、完整 `tests/custom_resume`、`compileall`、Skill Creator `quick_validate.py` 和 `git diff --check`。
- 证据：新增 T21 Prompt 契约回归；`tests/custom_resume/test_agent_prompts.py` 9 项、完整 `tests/custom_resume` 101 项、`compileall`、Skill Creator `quick_validate.py` 和 `git diff --check` 全部通过。未改 Schema、运行代码、四板块或投递状态边界。

## T22 游戏岗位内容判断蒸馏与前向测试

- 优先级：P0
- 状态：completed
- 目标：把深蓝简历从初稿到高标准稿形成的可泛化判断固化到游戏制作 PM 的事实重读、整稿定位、自我能力写作、融合、审计和 HR 决策中，供下一份 JD 直接复用。
- 依赖：T21 完成；用户确认当前深蓝稿基本达到可用水准，并明确要求复用本轮经验。
- 范围：新增游戏岗位内容判断参考；向 Writer packet 注入 `role_content_guidance`；更新游戏 Writer/ASu Writer、Fusion、Auditor、HR Reviewer、Agent 协议、PRD、Architecture 与 Eval Plan；不改变 Schema、事实库、真实运行、PDF 或投递状态。
- 验收：旧简历/旧运行不能作为事实源；事实摘要变化触发重新分析；游戏经历按目标产品、准确相近关系、深度证据、品类增量和区分度选择，不只按时长或罗列库存；语言能力与项目指标去重；游玩不得外推为产品能力；下一份游戏 JD 的独立前向测试能复述并应用这些规则。
- 测试：Prompt 契约、角色指南注入、完整 `tests/custom_resume`、`compileall`、Skill Creator `quick_validate.py`、`git diff --check` 和独立只读前向测试。
- 证据：新增 `game-production-content-judgment.md` 与结构化 `role_content_guidance`，游戏 Writer packet 集成断言和五角色 Prompt 契约均通过；完整 `tests/custom_resume` 103 项、`compileall`、Skill Creator `quick_validate.py` 和 `git diff --check` 通过。独立多人在线动作游戏制作 PM 前向测试未读取旧深蓝运行，重新选择《英雄联盟》《星际战甲》《漫威争锋》《艾尔登法环》《怪物猎人：世界》，主动舍弃FGO、炉石、大巴扎、以撒和博德之门3等高时长但低增量项，并将语言能力改为工作场景而非重复项目数量；同时保留正式 MMO 版本制作、研发/QA 内部依赖和线上事故复盘的真实缺口。

## T23 私有模范简历库与相似岗位复用

- 优先级：P1
- 状态：completed
- 目标：把用户确认达到投递水准的成型简历保存为私有不可变参考，并在后续相似岗位中复用已验证的结构和判断。
- 依赖：T22 完成；用户明确要求将最新成稿纳入模范简历。
- 范围：Git 忽略的 `profile/resume-exemplars/`、角色族与 JD 关键词匹配、内容哈希冻结、选材审计/Writer 输入、非事实与非批准边界、深蓝最新成稿登记；不改变源运行内容状态，不生成 PDF 或触发投递。
- 验收：相似游戏制作 JD 命中，不相似/跨角色 JD 不命中；篡改快照硬失败；模范稿只能影响声明的结构、证据分工、排序、密度和选材比较，当前事实与经历仍完整重算。
- 测试：匹配/隔离/篡改单测、Writer 与选材审计包集成、Prompt 契约、完整 pytest、compileall、Skill Creator 校验、真实私有条目哈希与源运行校验。
- 证据：私有条目 `game-production-deepblue-v1` 已登记运行 `cr_20260829T112758_games2` 的逐字节快照，源运行验证为 `review_ready`，快照 SHA-256 为 `05874d647551102b311330b9d3bb5e3bbb402095ede5a7297cc7a0cfca53bb2d`。真实深蓝 JD 命中版本规划、跨职能、进度和游戏产品体验等关键词；模范条目携带 `fact_source=false`、`selection_approval=false` 进入选材审计、双 Writer、Auditor 和 HR Reviewer。完整 110 项 pytest、`compileall`、两个 Skill 的 `quick_validate.py`、私有目录 Git 忽略校验和 `git diff --check` 全部通过。

## T24 V1.5 岗位扩展文档与 Schema 决策

- 优先级：P0
- 状态：completed
- 目标：把社区/内容/增长运营、社区产品经理与首批游戏策划方向转为一致的产品、架构、角色、评测和开发协议。
- 依赖：T23 完成；用户于 2026-08-31 确认推荐范围。
- 范围：更新 PRD、Architecture、Agent 协议、Eval Plan、Development 和 Tasks；确认 Schema 1.4、五角色族、条件性方向、动态自我能力第三项和首批游戏策划范围；不修改业务代码、Prompt、Skill、事实库或真实运行。
- 验收：角色族与方向组合无歧义；社区运营、社区产品和游戏策划证据边界明确；Schema 1.0–1.3 兼容策略、评测矩阵和发布门禁一致；根 `AGENTS.md` 的既有安全边界无需改变。
- 测试：文档版本/术语/链接检查、跨文档路由与兼容规则对照、`git diff --check`、工作区改动范围审查。
- 当前验证：本地链接、重复标题、术语对照、`compileall` 和文档 `git diff --check` 通过；用户于 2026-08-31 确认 V1.5 文档范围。事实库计数基线已在 T25 同步为 108 条并恢复绿色回归。
- 人工门禁：已通过；用户于 2026-08-31 明确确认 V1.5 文档并授权开始 T25。

## T25 Schema 1.4、角色路由与参考隔离

- 优先级：P0
- 状态：completed
- 目标：实现五角色族、条件性方向、角色指南路由和模范简历精确隔离。
- 依赖：T24 用户确认。
- 范围：`RoleFamily`、`RoleTrack`、Schema 1.4、规范化输入、方法卡映射、`role_content_guidance`、自我能力第三项派生、私有模范简历匹配；历史 1.0–1.3 只读兼容。
- 验收：合法矩阵全部可解析，非法组合硬失败；相邻方向模范简历不命中；旧角色行为与历史加载不退化。
- 测试：模型/路由/验证器/模范库单测，Schema 导出，AI PM 与游戏制作 PM 完整回归，`compileall` 和 Skill 校验。
- 证据：Schema 版本升级至 1.4，五角色族与条件性方向矩阵已进入输入包和 JD 分析校验；新增岗位按角色加载最小路由卡，并在 T26/T27 前以结构化 `role_strategy_pending` 阻止 Writer 误用相邻策略；自我能力第三项按角色族派生；模范简历 metadata 1.1 按角色族和方向精确匹配，旧 1.0 条目与 Schema 1.0–1.3 运行保持只读兼容。完整 `tests/custom_resume` 为 141 通过；17 份 JSON Schema 导出成功；`compileall`、Skill Creator 校验和 `git diff --check` 通过。

## T26 社区运营与社区产品经理支持

- 优先级：P0
- 状态：completed
- 目标：支持社区、内容、增长、综合运营和社区产品经理的事实约束选材与写作审计。
- 依赖：T25 完成。
- 范围：方法卡、JD 分析 Prompt、共享角色 Writer 指南、Fusion/Auditor/HR 判断、社区四方向与社区产品脱敏夹具；不接入 PDF 或投递。
- 验收：内容生产不会自动获得增长所有权，社群维护不会自动获得产品 Owner 身份；五类正向案例达到真实性、五项质量与 HR 门槛；事实缺口与方向混淆被正确降级。
- 测试：每个方向正向案例，每个角色族至少一个缺口和对抗案例，Prompt 契约、路由、全量 pytest、`compileall` 和 Skill 校验。
- 证据：社区运营四方向和社区产品已从 `role_strategy_pending` 释放，确定性路由选择 `jd-analysis-community.md` 与共享双 Writer；`community-content-judgment.md`、能力迁移、选材、Fusion、Auditor 和 HR Reviewer 均约束内容→增长、规模→健康度、活动→留存及运营→产品 Owner 的越级。五类脱敏正向夹具记录真实性、五项质量 8+ 和 HR `strong_push`/8.5+ 预期门槛，两个角色族各有事实缺口与对抗夹具。完整 `tests/custom_resume` 为 151 通过；社区夹具 CLI 校验、`compileall`、Skill Creator 校验和 `git diff --check` 通过。实际扩展盲评与用户 JD 发布演练仍由 T28 执行。

## T27 游戏策划五方向支持

- 优先级：P0
- 状态：completed
- 目标：支持系统、战斗、文案、叙事和综合游戏策划的方向化证据判断。
- 依赖：T25 完成。
- 范围：游戏策划方法卡、方向判断指南、JD 分析 Prompt、共享角色 Writer 指南、Fusion/Auditor/HR 判断及五方向脱敏夹具；本轮不含数值、关卡、任务和技术策划专用方向。
- 验收：五方向各有独立正向回归；游玩、测评、翻译、普通写作和 MOD 测试不被升级为策划所有权；`general` 不绕过方向缺口。
- 测试：五方向正向、至少一个事实缺口、跨方向对抗、模范简历隔离、Prompt 契约、全量 pytest、`compileall` 和 Skill 校验。
- 证据：系统、战斗、文案、叙事和综合策划已从 `role_strategy_pending` 释放，并分别路由 `jd-analysis-game-designer.md`、独立双 Writer 与 `game-designer-content-judgment.md`。能力迁移、选材、Fusion、Auditor 和 HR Reviewer 均要求主方向设计动作/产物、验证方法与个人边界；玩家/评测、本地化/普通写作、MOD/QA 和相邻策划方向不会自动获得直接所有权，`general` 必须有至少两个方向的直接证据。五方向脱敏正向夹具记录真实性、五项质量 8+ 和 HR `strong_push`/8.5+ 预期门槛，并覆盖事实缺口与四类方向对抗。完整 `tests/custom_resume` 为 160 通过；五方向夹具 CLI 校验、`compileall`、Skill Creator 校验和 `git diff --check` 通过。实际扩展盲评与用户 JD 发布演练仍由 T28 执行。

## T28 主 Harness 接入与 V1.5 发布验收

- 优先级：P1
- 状态：completed
- 目标：在全部扩展回归通过并获用户批准后，把新角色加入 `china-job-search` 默认新版路由。
- 依赖：T26、T27 完成并达到 `EVAL_PLAN.md` 发布门槛；用户明确批准发布。
- 范围：主 Harness 路由、入口文档、状态隔离、内容批准溯源和显式 Legacy 回退；不自动生成 PDF、不上传附件、不提交岗位。
- 验收：五角色族均正确进入新版 Agent；未知/未支持方向停止确认而非静默走旧版；内容批准与 PDF、岗位批准、提交四个门禁保持独立。
- 测试：完整自动回归、扩展盲评、状态/PDF/投递否定测试、批准清单篡改拒绝、一次用户指定 JD 的内容验收演练。
- 当前证据：`china-job-search/scripts/content_route.py` 已复用 Schema 1.4 矩阵；已发布的两个角色族保持默认新版路由，10 个 V1.5 新增合法角色/方向组合在发布批准前返回 `awaiting_v15_release_approval`，未知/非法方向、out-of-scope 与 Legacy 行为均有否定测试。内容、PDF、批准清单和最终提交门禁继续隔离，篡改与越级均被回归阻止。社区与游戏策划各 5 个用例的真实旧/新稿盲评均通过；用户否决的首版回响运行继续作为不可回归负例。历史运行 `cr_20260901T034747_echo02` 虽曾由融合后 Auditor 与 HR Reviewer 给出通过结论，但用户于 2026-09-02 指出经历展开、成果背书和一笔带过等基础质量缺陷；全新只读 post-draft Auditor 追溯审计后，Writer 四维为 7.6/7.8/8.2/8.3，ASu 为 7.0/8.1/7.1/7.3，均失败。该不可变运行保留为旧门禁负例，不再构成发布证据。流程已新增绑定双稿哈希、逐获批经历 8 分门槛的融合前审计；缺失、失败或过期时禁止融合。完整 `tests/custom_resume` 182 通过，`compileall` 与 `git diff --check` 通过。当前待重新选材或补充 5G 项目事实后生成新双稿并完成全部审计；用户内容验收和其后单独的 V1.5 发布批准仍未完成。

## T29 Schema 1.5 定向质量与批准链修复

- 优先级：P0
- 状态：implemented_pending_product_acceptance
- 目标：修复 HR 自报放行、单句经历凑版面、负面边界正文、事实库照抄和历史坏稿重新生效。
- 范围：Schema 1.5 故事计划、1–4 段选材、每段 2–4 个互补要点、三轮候选循环、确定性正文质量门、调用回执、最终内容哈希用户批准、追加式运行状态账本、下游 fail-closed 和历史坏稿失效；不接外部模型 API，不生成真实岗位 PDF，不执行投递。
- 实现：唯一入口为 `custom_resume_cli.py start|record|advance|approve|revoke|status`；Writer/ASu Writer 共用已批准故事计划，独立草稿分别过确定性校验和 Auditor，Fusion 再过质量门、Auditor 和 HR；HR 通过只进入 `ready_for_user_review`。旧 Schema 1.0–1.4 只读，不能产生新批准。
- 历史处理：`cr_20260901T020649_echoct`、`cr_20260901T034747_echo02` 标记 `user_rejected`；`cr_20260902T165644_c9e31f` 标记 `schema_invalid`。阻断运行不自动被其他旧稿替代。
- 自动验收：真实三份坏稿导入失败；单条/空条规避、负面责任声明、内部流程语言、事实照抄/近似照抄、缺回执、哈希不一致、手写 HR、撤销后下游使用、三轮路由与上限均有回归。完整 pytest 200 项、`compileall`、24 份 Schema 重导出一致性、四个相关 Skill 的 `quick_validate.py`、19 个存量 run 目录扫描、批准清单集成和 `git diff --check` 已通过；存量扫描结果为 14 个旧 Schema run 可读、2 个用户拒绝 run 被账本阻断、3 个手工目录缺少 `run.json`。盛趣旧 current 指向缺 `run.json` 的 `cr_20260903T142512_zlrev1`，已追加 `schema_invalid/MISSING_RUN_MANIFEST` 并改为 `no_approved_content`，历史目录和既有 PDF 未删除。
- 产品验收：已使用回响科技真实 JD 和最新事实库从零完成 Schema 1.5 盲跑 `cr_20260903T084342_da977c`。首轮双稿被独立 post-draft Auditor 拒绝后按缺陷路由重写；修订稿、Fusion、确定性门、post-fusion Auditor 和 HR 均通过，HR 为 `strong_push/9.1`，运行停在 `ready_for_user_review`。完整 pytest 更新为 201 项；24 份 Schema 一致；20 个存量 run 扫描为 15 通过、2 个用户拒绝阻断、3 个缺 `run.json`。当前仍等待用户最终接受内容及其后单独的 V1.5 发布批准；不得自动批准、生成 PDF 或投递。
# 2026-09-11 AI 产品能力区结构修订

- 状态：已确认，实施中。
- 目标：AI 产品岗位不再生成游戏经历或独立单句语言栏目，改为“专业硬技能、综合软技能、个人优势”，并要求个人优势绑定已确认的 Owner 意识与交付证据。
- 范围：Schema 1.5 模型、确定性验证、Writer 提示词及对应回归测试；历史运行只读兼容，游戏与社区角色结构不变。
- 验收：AI 产品 Writer packet 派生三项标题；三项结构通过模型与确定性门禁；旧四项 AI 产品结构在新验证中被拒绝；游戏和社区角色回归不变。

## T30 HR 内容充实度门禁与非数量化要点

- 优先级：P0
- 状态：in_progress
- 目标：修复 HR 评估对短稿和过度压缩的误放行，同时避免用固定要点数量把完整叙述切碎。
- 依赖：用户于 2026-09-13 确认字符型内容门禁，并明确否定要点数量硬性要求。
- 范围：HR packet、协调器放行校验、Writer/Fusion/Auditor/HR Prompt、Skill/Workflow/质量量表、产品文档、Schema 约束和回归测试；不修改事实库、现有简历、PDF 或投递状态。
- 验收：整稿少于 1,200 个中文字符、核心经历少于 180 个或辅助经历少于 120 个时不能获得 HR 通过；要点数量不作为通过条件；机械拆句、重复表达、虚构或弱经历填充仍失败。
- 测试：字符门禁正反例、单条完整语义与多条机械拆分回归、Prompt 契约、完整 pytest、Schema 重导出一致性、`compileall`、Skill Creator 校验与 `git diff --check`。
- 证据：定向回归和新增门禁正反例均通过；排除工作区既有事实库计数断言后，`tests/custom_resume` 209 项通过；24 份 JSON Schema 已重导出，`compileall`、Skill Creator 校验和相关文件 `git diff --check` 均通过。完整测试唯一剩余失败为 `test_real_fact_library_parses_all_migrated_ids`：测试固定期待 26 段经历，当前事实库实际解析 25 段，与本任务无关且未擅自修改事实库。

## T31 成品复用优先与批量正式校招准备

- 优先级：P0
- 状态：completed
- 目标：把默认批量材料流程改为“具体正式校招 JD → 私有成品基线 → 轻微调或待批准重写 → HR/PDF/ATS → 原表写回”。
- 依赖：用户于 2026-09-14 确认只处理正式校招、跨城保留、同公司不同岗位独立成行、轻调 HR 通过即制版、完整重写按批次批准。
- 范围：基线审计/哈希失效、轻调路由和 HR 闸门、具体岗位批次 Schema、工作簿增量更新与生成器状态继承、入口文档；不自动填写、上传或提交网申。
- 验收：旧邮箱/撤回数字/重复成品可识别；轻调不改变经历组合或核心故事；无基线和选材/故事缺陷在双 Writer 前阻断；工作簿保留 A:S 并追加十列、同公司多岗位独立统计；所有 PDF 仍需视觉/文本层/ATS 验收。
- 测试：`tests/test_resume_baseline.py`、工作簿自测、真实基线审计、目标工作簿备份与读回检查、完整相关回归。
- 证据：真实成品目录按文本/文件哈希完成审计，得到 4 个 `reusable`、4 个 `repair_required`、1 个 `reference_only` 和 10 个 `blocked`；4 个可复用 PDF 均完成单页视觉与联系方式检查。原工作簿已先生成恢复副本，再由 A:S 增量扩展至 A:AC，96 条原记录逐格保持，表格/筛选范围为 `A1:AC97`、冻结窗格为 `D2`、材料状态校验覆盖 `AB2:AB97`，另外两张业务工作表未变，重复具体岗位、非法 URL 和公式错误均为 0。定向测试 21 项通过，其中基线/路由/HR/三岗位展开测试 7 项通过；完整 pytest 为 214 通过、1 个既有事实库数量断言失败，该失败已在 T30 记录且本任务未修改事实库。

## T32 网申快速装配与 RenderCV 通道

- 优先级：P0
- 状态：completed
- 目标：用事实层与批准表达层快速生成岗位简历，跳过批量岗位的双 Writer 重写，并把 PDF 改为可编辑 YAML 的确定性本地渲染。
- 范围：旧简历扫描/去重、候选事实差异、批准表达库、五态路由、1–4 段选材、单 Writer 补缺、四项 HR 门禁、RenderCV 2.8、PDF/ATS QA 和批准清单哈希追溯；不上传、不投递、不自动写入候选事实。
- 验收：三类中文试点通过字体、分页、文本提取与视觉检查；正常批量不生成 PNG；四项门禁分别可阻断；非游戏岗位无游戏内容；所有新句绑定确认事实；岗位批准前重新校验全部来源哈希。
- 当前证据：已从 4 个哈希有效的批准来源导入 52 条表达；批量差异保留 1,639 条原始记录。用户于 2026-09-23 确认最后 6 条候选，经去重全部映射到既有原子事实，没有新增重复 fact ID、没有改变事实库哈希，后续确认队列为 0。AI 产品、游戏策划和两页项目管理三份中文试点均通过四项 HR、文本层、乱码、联系方式、禁用内容、分页与逐页视觉检查；RenderCV 日常无 PNG 模式三份共 6.4372 秒，旧逐份 Chrome 共 20.7928 秒，速度提升 3.23 倍。定向回归 43 项通过；完整相关回归 235 项通过，唯一失败仍是 T30 已记录的事实库经历数量固定断言（期望 26、实际 25），本任务未修改事实库正文。
