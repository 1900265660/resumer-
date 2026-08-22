# 定制简历 Agent 开发规范

> 状态：已确认
> 版本：0.1
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

1. 产品文档未由用户确认前，只允许修改 `docs/custom-resume-agent/`、必要的文档入口和隐私规则。
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
- Prompt 修改必须运行至少一个正向、一个事实缺口和一个对抗用例。

## 6. Schema 与兼容政策

- 所有 JSON 包含 `schema_version`。
- V1 Schema 使用 `1.x`；新增可选字段可提升次版本，破坏性修改必须提升主版本并提供迁移策略。
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
7. 未验证部分被明确记录；
8. 输出最终报告并停止，不自动开始下一 Task。

## 10. 最终报告格式

- 完成内容；
- 主要修改文件；
- 执行的测试及结果；
- 关键决策或文档同步；
- 剩余风险与未验证内容；
- 推荐的下一个 Task。
