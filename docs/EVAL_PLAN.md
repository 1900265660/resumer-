# 验证与评测计划

## 必跑命令

在仓库根目录：

```powershell
python -m pytest -q
python -m compileall -q .agents\skills\custom-resume\scripts .agents\skills\china-job-search\scripts scripts
```

在 `tools/browser-application/`：

```powershell
pnpm install --frozen-lockfile
pnpm build
pnpm check
pnpm test
pnpm test:upstream
node scripts/doctor.mjs
```

批准清单复验必须使用项目配置的 PowerShell 7：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe' -NoProfile -File scripts\validate_approved_manifest.ps1 -ApprovedPath <approved-json>
```

## 门禁

| 范围 | 通过条件 |
| --- | --- |
| Python | pytest 全绿；事实库真实样本可解析；Schema/哈希/状态反例被拒绝 |
| MCP | 工具发现由契约测试覆盖；生命周期、严格输入、批准包、恢复、上传、一次提交通过 |
| 扩展 | 字段扫描、映射、日期、多选、敏感数据脱敏、确认页和日志导出通过 |
| 投递材料 | 批准清单返回 `validation_pass`，PDF 文本/视觉 QA 和附件哈希一致 |
| 安全 | 不出现原始身份证、Cookie、密钥、完整敏感答案或未批准附件 |

## 当前基线（2026-10-01）

- Python：249 项中 246 通过、3 失败。
- 浏览器工具：9 项中 8 通过、1 失败；扩展 75 项全通过。
- 失败项不是可发布基线；详见 `ENGINEER_HANDOFF.md`。

## 回归补充

- 每次新增事实 provenance 枚举，必须覆盖真实事实库解析和写回预览。
- 每次增删 MCP 工具，测试不得硬编码旧数量；应断言名称集合或版本化工具清单。
- 每次改 PowerShell 脚本，必须同时验证 PowerShell 7 与明确声明的不支持环境。
- 每次改 `.gitignore`，运行 `git status --ignored` 并确认私有数据没有被暂存。
