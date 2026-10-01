# 工程师交接与故障定位手册

## 当前版本事实

- Git 远程：`origin` 指向现有 GitHub 仓库；当前分支为 `master`。
- 工作树不是干净基线：审计时已有 66 个已跟踪文件修改和一批未跟踪源码/文档/测试。
- `profile/`、`applications/`、`jobs/approved/`、`outputs/` 是本地私有或生成数据，不应提交。
- 浏览器工具代码在 `tools/browser-application/`，生产 MCP 运行的是忽略的 `dist/server.js`。

## 先做什么

```powershell
git status --short
python -m pytest -q
Set-Location tools\browser-application
pnpm build
pnpm check
pnpm test
pnpm test:upstream
```

不要从测试失败直接重写模块；先依据本文件的复现证据定位根因。

## 已复现故障

### 1. 真实事实库不能通过 metadata 校验

复现：`python -m pytest -q`。

`fact_library.py` 仅允许 `observed` 与 `accepted_estimate`，但真实资料已含 `provenance: user_confirmed`。结果是事实库预览与解析测试失败。修复前需先决定 `user_confirmed` 是否是正式枚举值及其必填/禁填元数据；然后同步模型、解析器、Schema、文档和正反测试。

### 2. MCP 工具发现断言过期

`tools/browser-application/tests/mcp.test.ts` 期待 11 个工具，而实际 `src/server.ts` 注册 13 个。测试应校验允许的工具名称/能力集合，或引用版本化 manifest，而非脆弱的长度常量。

### 3. 中文 PowerShell 脚本在旧宿主失败

系统 Windows PowerShell 解析 `validate_approved_manifest.ps1` 会把 UTF-8 中文内容错误解码；项目配置调用 PowerShell 7 时已成功返回 `validation_pass`。生产要求必须明确为 PowerShell 7；若要支持 Windows PowerShell，需另行决定编码策略并加入测试。

## 日志定位

| 问题 | 优先查看 |
| --- | --- |
| 内容状态/哈希/审批 | `applications/<job>/resume-content/`、`manifest.json`、`review.md` |
| 批准包失败 | `jobs/approved/*.json`、源 `manifest-draft.json`、`scripts/approval_manifest_common.ps1` |
| 浏览器卡住/恢复 | `applications/<job>/browser-application/`、MCP `application_status` |
| 页面字段/扩展问题 | `tools/browser-application/src/`、`extension/` 及其测试 |
| 岗位采集与批量处理 | `outputs/` 的对应 JSON/NDJSON；仅本地查阅 |

## 数据安全

禁止把 `profile/`、`applications/`、浏览器 profile、Cookie、截图、PDF、DOCX、XLSX 或 `outputs/` 推送到 GitHub。提交前运行：

```powershell
git diff --cached --check
git diff --cached --name-only
git status --ignored
```

`%SystemDrive%/`、`undefined/`、`.tmp/` 是异常或临时输出；先追溯来源，未经确认不要删除。

## 建议的首个修复 PR

只包含 P0：provenance 枚举、MCP 测试契约、构建后测试和对应文档。不要顺带改投递流程或清理私有目录。PR 必须附上完整测试输出和不含敏感数据的失败复现说明。
