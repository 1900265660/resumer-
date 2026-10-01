# Codex 网申填写工具

基于固定版本的 AI-Resume-Form-Filling-Assistant 扩展，接入当前 Codex 的判断能力，不需要额外模型 API Key。源码来源和 GPL-3.0 见 [UPSTREAM.md](UPSTREAM.md)。

## 安装与连接

需要 Node.js 22+、pnpm、PowerShell 7；Windows 中文目录受支持。在本目录运行：

```powershell
pnpm install --frozen-lockfile
node scripts/setup.mjs
```

setup 编译服务、下载 Playwright 对应 Chromium 并运行 doctor。首次浏览器下载约 200 MB，实际安装空间更大；缓存与下载临时目录默认放在本模块 `.local/`，不占用系统盘默认缓存，不修改日常 Chrome/Edge。后续浏览器缺失时 browser_start 也会自动安装。

工作区 `.codex/config.toml` 已配置 `job_application` MCP；使用本机绝对路径。换电脑需改 command/args。重新加载 MCP 或打开项目新任务使配置生效；不假定现有任务能热加载新增工具。

自检和回归：

```powershell
node scripts/doctor.mjs
pnpm build
pnpm test:upstream
pnpm test
```

## 使用

在 Codex 中说：“执行已批准岗位的填写，提交前让我确认。”Codex 按本项目 browser-application Skill 读取批准清单、整理有证据的字段并自动传入。你只需处理登录/验证码、缺失答案，以及最终确认页。确认页显示实际字段和附件 SHA256；确认后 Codex 才点击网站提交。

工具入口：prepare、start、inspect、fill、advance、upload、prepare/commit submission、status、resume、close。没有任意脚本执行、任意路径上传或通用 click 接口。服务器绑定当前工作区；stdio 无公网监听。

完美世界卡牌游戏策划岗位已确认的详情页“申请职位”会进入填写表单：登录后可通过 `form_advance` 执行扫描出的 `expand` 动作，再重新扫描表单，无需为此入口重复确认。规则限定到已确认岗位详情页，不扩展到其他同名按钮；具体适用条件见 [站点流程](../../docs/browser-application-agent/PRD.md#完美世界已确认入口)。最终投递仍需用户亲自确认摘要。

材料转换支持批准答案和带文字层 PDF。每项保留来源原文，不自动增加事实；扫描 PDF 或只有 DOCX 且缺少结构化答案时须先准备批准的答案快照。敏感字段的逐项批准必须写在已冻结答案中。

## 恢复与限制

- 检查点、独立浏览器配置在岗位 `browser-application/`，由现有 applications 隐私规则排除版本控制。浏览器配置包含个人资料与登录 cookie，不要上传或分享。
- 网站断线后使用相同清单和答案 prepare，再 resume；会重扫页面。已发生提交尝试的会话只核查结果，绝不重试提交。
- 页面身份无法核对、跨域跳转、iframe 内控件、复杂自定义控件、上传无确认信号等会停下，不承诺全站通用。
- 网站原生可见文件名是上传确认信号；出现错误则不进入最终提交。只有 input 选中文件、但网站没有显示文件名时转人工。
- 同一岗位已有 receipt.md 即阻断重复投递，包含尚需人工核验的旧回执文件。
- 材料校验失败时在工作区运行 `scripts/validate_approved_manifest.ps1 -ApprovedPath <清单>` 查看原因；工具不把可能包含个人信息的底层异常打印到公共日志。
- 若安装下载失败，修复网络后重新 setup，不需要重做简历或安装扩展。不要使用 stealth、验证码破解或修改网页来绕过限制。

真实网站状态及本地验证结果见 [VALIDATION.md](../../docs/browser-application-agent/VALIDATION.md)。
