# 开发规范

按 Understand → Inspect → Plan → Implement → Test → Review 执行。用户已明确授权实施整份方案；文档只落地已确认范围。

修改局限于 tools/browser-application、模块文档、browser-application Skill、MCP 项目配置及必要隐私规则，不覆盖仓库既有改动。复用上游扫描和填充函数，变更保留来源。安装依赖固定 lockfile。

每次改动运行对应单元/集成测试；发布前类型检查、上游测试、真实 Chromium E2E 和 stdio smoke。连续两次修复失败先重新查询官方资料与源码。禁止把真实投递用于无人确认的开发测试。

完成报告须区分已实现、自动验证、真实网站未验证；给出安装入口、MCP 启用方式、日志位置与已知限制。不提交个人材料、浏览器配置、日志、缓存或依赖目录。
