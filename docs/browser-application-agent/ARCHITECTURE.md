# 架构

## 现状与目标

现有 Harness 已有 PowerShell 批准清单校验、岗位目录、状态和回执约定；此前没有 MCP 填表执行器。上游扩展将扫描、模型映射、填充绑在 startFill。固定上游提交 76c052d254da0b668ea1af9a1a2eb247dd3e62f8，保留 GPL-3.0 与导入说明。

目标：当前 Codex → stdio MCP → 本地执行器 → Playwright 专用持久上下文 → 扩展后台消息 → content script。无 HTTP 监听、无在线模型 Provider。Codex 负责原文结构化、字段语义映射及循环编排；服务负责 Schema、来源证据、批准状态与副作用门禁；扩展负责扫描和确定性填充。

## 接口

application_prepare 接收批准路径及可选结构化答案包；每项包含 resumePath、value、sourceQuote、sensitiveConfirmed。值必须由批准答案原文支持，日期等变换使用受限转换，不接受任意代码。普通资料传输授权及敏感确认必须有用户原文记录。

browser_start、application_enter、form_inspect、form_fill、form_advance、attachment_upload、submission_prepare、submission_commit、application_status、application_resume、application_close。`application_enter` 只在当前页唯一精确匹配已批准公司和岗位标题时点击其所在卡片的申请按钮，按钮不唯一或跳转不一致即停止。填写和按钮操作绑定 sessionId、snapshotId、fieldId/actionId。MCP 不提供任意 evaluate、任意本地文件上传或无门禁 click。

## 状态和证据

独立检查点保存到岗位 browser-application/，不保存原始字段值、cookie 或页面全文。检查点绑定批准清单哈希、会话与已尝试提交标记；恢复时重新 prepare 并验证材料，未决提交只能查回执，不能再次点击。为支持同一浏览器会话内的 MCP 重连，已获批准并已读回的当前页值仅暂存在专用浏览器扩展的本地会话状态，并与会话 ID、材料哈希绑定；不写入岗位检查点，主动关闭应用会清除。主状态仅在证据充分时向前推进，旧状态不一致时停止。

每个副作用前复验批准清单与附件、检查域名及重复回执。填写读回不一致累计两次转 manual_required。最终摘要绑定实际页面值摘要、已完成页记录、材料哈希及用户确认；点击前先持久化提交尝试，结果不明不重试。

## 故障与隐私

扩展后台重启可重建消息连接；页面改变必须重新扫描。暂停/断线保留检查点，重新开始不重放动作。日志只记事件类型及计数，回执截图对个人字段与页面文字遮蔽，仅显示核验过的成功片段。已批准原文仅通过 MCP 提供给当前 Codex，页面数据视为不可信。跨域 iframe、自定义控件无法可靠识别时报告限制。
