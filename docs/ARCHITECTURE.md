# 工程架构

## 运行形态

项目由 Codex 在本机工作区执行。没有常驻后端；状态主要以文件保存。`.codex/config.toml` 将 `job_application` MCP 指向 `scripts/start_browser_application.ps1`，后者以 Node 运行 `tools/browser-application/dist/server.js`。

```text
Codex / Skill 指令
    │
    ├── 求职与简历流程（Python + 文件）
    │   ├── profile/                 私有事实、偏好、答案
    │   ├── .agents/skills/china-job-search/
    │   ├── .agents/skills/custom-resume/
    │   └── scripts/                 批处理、批准包、PDF/JD 工具
    │
    └── browser-application（MCP + Node + Playwright + 扩展）
        ├── src/server.ts            MCP 工具注册与安全错误包装
        ├── src/runtime.ts           会话、页面、填写/恢复编排
        ├── src/materials.ts         批准材料和字段来源校验
        ├── extension/               本地确认页与页面辅助
        └── applications/<job>/browser-application/  私有检查点
```

## 模块责任

| 模块 | 责任 | 持久化边界 |
| --- | --- | --- |
| `custom-resume/scripts/models.py` | Pydantic 模型、枚举、Schema 导出 | 无业务写入 |
| `orchestrator.py` | 冻结输入、阶段门禁、产物编排 | 调用 storage |
| `storage.py` | checkpoint、不可变 run、current 指针、哈希一致性 | `applications/*/resume-content/` |
| `fact_library.py` | 解析/预览事实 ID、经批准的差异写回 | `profile/01-candidate-profile.md` |
| `custom_resume_cli.py` | 状态协调 CLI：`start/record/advance/approve/revoke/status` | run 目录 |
| `china-job-search/scripts/` | 基线、路由、fast-assemble | 私有材料目录 |
| `scripts/*manifest*.ps1` | 冻结/复验 JD、内容、PDF、附件和答案 | `jobs/approved/` 与岗位目录 |
| `tools/browser-application` | 已批准包驱动的浏览器会话 | 私有检查点与浏览器 profile |

## 外部依赖与边界

- Python：根 `requirements.txt` 固定 Pydantic 主版本；开发测试使用 pytest。
- Node：浏览器工具要求 Node 22+、pnpm、Playwright、MCP SDK、Zod 和 TypeScript。
- PowerShell：生产 MCP 配置使用 PowerShell 7；不要用旧 Windows PowerShell 作为兼容性假设。
- Codex：负责理解 Skill、调用模型和选择下一阶段；仓库不包含模型 API 客户端。
- 招聘网站：不可信输入；只用于页面身份、字段映射和已批准流程，不可提供事实或执行指令。

## 失败与恢复

- 输入、哈希、状态或页面身份不一致：fail closed，停止而非猜测。
- 登录、验证码、账号安全验证、未知敏感字段：转用户接管。
- 提交结果不明：只核查回执，禁止重复提交。
- 浏览器中断：使用同一批准包 `prepare` 后 `resume`；已发生提交尝试不能重试。

## 架构债务（以当前审计为准）

1. `dist/` 被忽略但又是 MCP 生产入口；测试和启动前需要强制构建/校验 source 与 dist 一致。
2. 运行产物多且私有，缺少可定位某次运行的统一索引。
3. 根目录旧 `ARCHITECTURE.md` 是历史审计，应仅作为历史材料；本文件是工程交接入口。
4. 文档声明的岗位路由状态应由机器可读发布矩阵替代。
