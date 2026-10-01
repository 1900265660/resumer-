# 开发与排障规范

## 开始前

1. 阅读 `AGENTS.md`、本目录文档及相关 Skill。
2. 运行 `git status --short`；当前工作区存在历史未提交改动，未经确认不得 reset、checkout 或覆盖。
3. 区分代码、私有数据、构建产物和一次性分析输出。
4. 先复现问题，再查源码/官方文档/已有实现，最后做最小修复。

## 运行与调试

- 浏览器工具：先在 `tools/browser-application/` 运行 `pnpm install --frozen-lockfile`、`pnpm build`、`node scripts/doctor.mjs`。
- MCP：由 `.codex/config.toml` 启动；如工具不可见，重新加载 MCP 或新开任务，不要改用无门禁脚本。
- custom-resume：先执行 `python .agents/skills/custom-resume/scripts/custom_resume_cli.py --help`；其 CLI 只协调状态，不调用模型 API。
- 批准清单：始终先运行 `validate_approved_manifest.ps1`；未见 `validation_pass` 不得打开申请页。

## 日志与证据

- `applications/<company>_<job>/`：JD、分析、manifest、review、内容 run、浏览器检查点和脱敏回执。
- `outputs/`：批处理、岗位采集、简历生成和检查的本地输出；不得提交。
- 浏览器扩展日志：仅可导出脱敏诊断；不要把 Cookie、原始字段值或整个 profile 提交到 Git。
- 每个缺陷报告至少包含：命令、时间、提交/工作树状态、输入的脱敏标识、预期、实际、堆栈/安全错误码、相关 run 或清单哈希。

## Definition of Done

- 修复有针对性回归测试；全套相关测试通过。
- source 与 `dist` 的构建关系已验证。
- 不改变事实、批准、附件上传或最终提交的安全边界。
- 文档同步更新，变更和未验证部分在 PR/交接中明确。
