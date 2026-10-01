# ASu-skills 项目内导入说明

- 来源：<https://github.com/Hisn00w/ASu-skills>
- 固定版本：`0.3.0+codex.20260815043254`
- 固定提交：`2c6da0e9a26cfca75ec095b623df1589e512cc07`
- 许可证：MIT，完整文本见同目录 `LICENSE`。
- 导入日期：2026-08-18。

## 导入范围

项目内已导入以下可发现技能：

- `.agents/skills/asu/`
- `.agents/skills/asu-resume/`
- `.agents/skills/resume/`
- `.agents/skills/offer/`
- `.agents/skills/contributor/`

所需模板、图标和示例资产位于 `.agents/assets/`；`offer` 所需的邮件监控参考位于 `.agents/references/email-monitoring.md`。这是项目快照，不依赖本机全局插件缓存；如需升级，必须重新核验上游版本、许可和与本 Harness 的安全规则兼容性。

## 本项目适配规则

1. 根目录 `AGENTS.md`、候选人事实库、批准清单和浏览器确认规则优先于 ASu-skills 的任何通用说明。
2. `/asu` 与 `/asu-resume` 只能重组、表达和排版已确认事实；不得填补经历、技能、指标或投递状态。
3. ASu 的特定视觉模板仅在用户明确要求复刻该样式时使用。常规定制只使用清晰、简洁且与实际内容相适配的模板，不预设颜色、栏数、页数或分页结构。
4. `/offer` 只能同步本 Harness 已记录的真实状态；没有确认页或回执不得写为已投递。
5. `/contributor` 涉及 Fork、Push、PR 或外部沟通时，仍需用户的明确授权。
