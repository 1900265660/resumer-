# 定制简历 Agent 开发规范

> 状态：V1.5 文档已确认，T25–T27 已实现，T28 发布验收进行中
> 版本：0.5
> 适用范围：`custom-resume` 模块的文档、Skill、子代理、Prompt、验证脚本和测试

## 1. 标准流程

每个任务严格执行：

```text
Understand → Inspect → Plan → Implement → Test → Review
```

### Understand

- 阅读 `PRD.md`、`ARCHITECTURE.md`、`TASKS.md` 和 `EVAL_PLAN.md`。
- 明确当前 Task、依赖、验收条件和明确不做的范围。
- 若任务与文档冲突，停止并请求用户决定。

### Inspect

- 阅读相关现有 Prompt、Skill、脚本和测试。
- 用仓库事实确认当前实现，不依据聊天记忆猜测。
- 搜索官方方案、成熟开源实现或现有组件，避免重复实现。

### Plan

- 说明当前实现、拟修改行为、预计修改文件和验证命令。
- 保持任务边界，不自动开始后续 Task。

### Implement

- 使用最小改动完成当前 Task。
- Prompt、Schema、领域规则和文件系统操作分离。
- 确定性逻辑不得转交 LLM。
- 不修改真实申请产物或用户事实，除非当前 Task 明确是经确认的事实 ID 迁移。

### Test

- 新增行为必须有对应自动测试。
- 先运行最小相关测试，再运行模块完整回归。
- 失败时定位根因，不删除测试、不跳过断言、不降低标准。

### Review

- 检查 diff 是否只有当前 Task 改动。
- 检查文档、Schema、Prompt 和测试是否一致。
- 报告完成内容、文件、测试、风险和下一个 Task，然后停止。

## 2. 阶段门禁

1. 产品范围已确认但 V1.5 文档未由用户验收前，只允许修改 `docs/custom-resume-agent/`、必要的文档入口和隐私规则。
2. 文档确认后，按 `TASKS.md` 一次实现一个任务。
3. 事实 ID 迁移必须先产生预览 diff，用户确认后才能写事实库。
4. 固定回归未通过前，旧优化器保持可用且不得删除。
5. 用户批准切换前，`china-job-search` 不得默认路由到新 Skill。

## 3. 修改范围约束

- 运行能力集中在 `.agents/skills/custom-resume/`、`.codex/agents/`、`.agents/prompts/custom-resume/` 和 `tests/custom_resume/`。
- 根 `AGENTS.md` 只保存跨任务安全边界和文档入口。
- 不重构 PDF、浏览器投递、Offer、Contributor 或模板系统。
- 不引入常驻服务、数据库、外部模型 Provider 或前端 UI。
- 不把原始外部简历、真实岗位申请或候选人敏感资料加入 Git。
- 私有模范简历只能写入已忽略的 `profile/resume-exemplars/`；代码和测试不得硬编码候选人姓名、联系方式或真实快照正文。
- 不硬编码当前本机路径、模型名、用户身份或联系方式。

## 4. 依赖政策

- Python 最低版本为 3.10。
- 运行依赖只引入 Pydantic 2.x。
- 测试依赖引入 pytest。
- 新增依赖前必须说明无法用标准库或现有依赖可靠完成的原因。
- 使用项目依赖清单固定兼容版本范围，不依赖本机偶然安装状态。

## 5. Prompt 政策

- 每个 Prompt 明确 Input、Output、Schema、失败行为和禁止事项。
- 长 Prompt 存放在 `.agents/prompts/custom-resume/`，不得硬编码进 Python。
- Prompt 只能要求结构化输出；不得依赖从自然语言报告反向解析状态。
- Writer、ASu Writer 和 Auditor Prompt 不得互相复制草稿或泄漏预期答案。
- 双稿完成后必须启动全新的只读草稿质量 Auditor；它逐稿逐经历检查展开度、成果背书、信息密度和自然扫读，未通过时 `record_fusion` 必须拒绝继续。
- HR Reviewer 必须是全新只读调用，不得由 Writer、融合器或基础 Auditor 复用上下文自证质量。
- Schema 1.5 只有在确定性质量门、字符型内容充实度门禁、独立 Auditor、匹配调用回执和 `hr-review.json` 同时有效，HR 推荐 `strong_push`、总分达到 9.0、六维均达到 8.0 且引用实际 bullet 后，才可进入用户审阅；最终批准还需要用户对内容哈希的明确批准记录。
- HR 意见修订后必须重跑确定性校验、基础 Auditor 和全新的 HR Reviewer；缺少事实时只生成问题，不得用行业常识扩写。
- Prompt 修改必须运行至少一个正向、一个事实缺口和一个对抗用例。
- 能力迁移 Prompt 必须同时输出源事实、源动作、目标能力、迁移距离和可写边界；禁止只输出无证据的能力标签。
- “发散能力”和“生成简历事实”必须是两个阶段：合理但未经确认的流程只能进入 `candidate` 问题，不能进入打分或 Writer 输入。
- 选材 Prompt 必须分别输出岗位匹配与组合价值，不能让 LLM 自行合成最终总分；分项和距离系数由代码复算。
- 写作、融合和审计 Prompt 必须区分整稿叙事、经历完整性和单条要点：整稿检查统一岗位定位，核心经历整体检查问题/情境—个人行动—方法或决策—可信结果—个人边界，不要求每条要点机械套模板。
- 所有候选 WORK/PROJECT（包括未入选项）的全部已确认事实必须进入评分与独立选材 Auditor；协调器以代码拒绝任一候选经历的事实子集，防止低估被遗漏经历的机会成本。入选经历的同一完整事实集继续进入 Story Plan、Writer、Auditor 与 HR。
- 1,200 字/10 条只作为完成度诊断；低于两线时 Prompt 必须逐经历对照完整事实集并解释未用高价值事实。能力前置标签与内部审计标签必须分别判断，不能一概删除。
- JD 关键词必须由事实支持的工作/项目实际细节支撑。
- 角色专用 Prompt 必须读取规范化 `role_family` 和条件性 `role_track`，不得从岗位标题字符串自行覆盖已确认路由。
- 新角色优先共享通用 Writer、Fusion、Auditor 和 HR Reviewer 契约，通过按需加载的 `role_content_guidance` 提供方向判断；只有输入/输出或推理任务确实不同才新增独立 Prompt，避免复制整套流程。
- 社区/内容/增长运营、社区产品和游戏策划方向之间必须保留所有权边界；每次相关 Prompt 修改都要增加方向混淆断言。

## 6. Schema 与兼容政策

- 所有 JSON 包含 `schema_version`。
- 新产物使用 Schema `1.5`；加载器继续只读接受 `1.0`–`1.4` 历史运行，绝不原地迁移或覆盖历史产物，官方入口拒绝旧版本产生新批准。
- Schema 1.5 的 `role_track` 是条件字段：社区运营和游戏策划必须填写合法方向，其他角色族必须为空。兼容加载器不得把旧产物反向补写为 1.5。
- 官方状态变更只通过 `scripts/custom_resume_cli.py`。直接写 Markdown、`run.json`、HR 分数或 `current.json` 不构成有效运行。
- 每次代理输出必须有匹配的 `AgentInvocationReceipt`；审批时复验 prompt、input、output 和最终内容哈希。
- 改动公共模型后运行 `models.py --export-dir schemas`，并逐文件比较导出结果，禁止手改 Schema 与模型分叉。
- Pydantic 模型是 JSON 结构的代码级来源，`ARCHITECTURE.md` 记录公共语义。
- 未知字段默认拒绝，避免 LLM 静默发明接口。
- 状态、枚举和文件名不得仅在 Prompt 中定义。

## 7. 测试政策

### 必需检查

```powershell
python -m pytest tests/custom_resume
python -m compileall .agents/skills/custom-resume/scripts tests/custom_resume
```

涉及 Skill 元数据时还需运行 Skill Creator 的 `quick_validate.py`。涉及运行产物时运行 `validate_run.py`。

能力迁移和组合选材变更还必须运行深蓝定向回归，验证“翻译跨方协作/质量/交付被发现”和“未经确认的人员分工不进入正文”同时成立；只验证其中一项不能视为通过。

模范简历路由变更必须覆盖：相似岗位命中、不相似岗位不命中、角色族隔离、内容篡改拒绝、无模范库兼容，以及 Writer/选材审计包的非事实边界。

V1.5 角色扩展还必须覆盖完整路由矩阵、条件性方向、角色指南选择、跨方向模范简历拒绝、动态自我能力第三项，以及每个新增角色族至少一个正向、事实缺口和对抗用例。游戏策划五方向必须各有独立正向回归。另需覆盖“任一候选经历预隐藏事实”确定性拒绝、短而真实但证据损失的 HR 负例、能力前置标签可用与审计微标签禁用。

### Lint 和类型检查

仓库当前没有 lint 或静态类型工具。V1 不为了形式强制引入；代码需通过 Python 编译、pytest、Pydantic 严格验证和人工 diff review。若后续引入 Ruff、mypy 等工具，先更新本文和依赖清单。

### 测试失败处理

1. 阅读完整错误和失败夹具；
2. 确认是实现、测试数据还是环境问题；
3. 修复最小根因；
4. 重跑失败测试；
5. 再跑模块完整回归；
6. 连续两次失败后重新检查官方文档、源码和已有解决方案。

## 8. Git 与隐私

- 开发前确认 `git status`，保留用户无关改动。
- 每个完成 Task 建议单独本地提交，提交前检查 staged diff。
- 不添加远端、不推送、不发布，除非用户另行授权。
- 提交前扫描姓名、手机号、邮箱、身份证和真实申请路径。
- `profile/`、`applications/`、`jobs/inbox/`、原始文档和 `tmp/` 必须保持忽略。

## 9. Definition of Done

一个 Task 只有同时满足以下条件才完成：

1. Task 的范围和验收条件全部实现；
2. 没有实现未授权的后续能力；
3. 相关单元和集成测试通过；
4. Schema、Prompt、文档和运行产物一致；
5. diff 无无关改动或敏感数据；
6. 失败和降级行为已验证；
7. 能力迁移回归同时达到迁移召回 100% 和可写迁移精度 100%；
8. 教育锁定、能力分类、同类项目上限、工作板块与例外均通过确定性测试；
9. 涉及角色扩展时，合法路由、方向隔离、模范简历隔离和相邻能力不越权均通过回归；
10. 未验证部分被明确记录；
11. 输出最终报告并停止，不自动开始下一 Task。

成品复用上游的完成定义另包括：基线库保持 Git 忽略；事实库或源文件变化会失效；工作簿重建保留具体岗位和人工状态；轻调 HR 通过不写 `manifest.resume_content.approved`；待重写批次获批前没有 Writer/ASu Writer 调用。

快速装配开发与验收命令：

```powershell
powershell -ExecutionPolicy Bypass -File .agents/skills/china-job-search/scripts/setup_rendercv.ps1
python -m pytest -q tests/test_fast_resume.py tests/test_resume_baseline.py
python -m compileall .agents/skills/china-job-search/scripts tests
node scripts/update_job_resume_workbook.mjs --self-test
```

旧简历扫描只生成 `fact-diff` 报告，不写事实库；`apply-writer` 只能运行一次；日常 PDF 只跑结构、文本层、联系方式、乱码、禁用字段和页数检查，异常时才生成 PNG。

## 10. 最终报告格式

- 完成内容；
- 主要修改文件；
- 执行的测试及结果；
- 关键决策或文档同步；
- 剩余风险与未验证内容；
- 推荐的下一个 Task。
