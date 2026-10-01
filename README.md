# Codex 求职助手（中国版）

这是供 **Codex 直接执行** 的个人求职工作区，不是需要常驻运行的网页应用。工程师交接、运行命令、故障定位与当前风险见 [docs/ENGINEER_HANDOFF.md](docs/ENGINEER_HANDOFF.md)；系统边界见 [docs/PRD.md](docs/PRD.md) 与 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

你只需把文件放进对应目录，然后在 Codex 中说一句话：

- “导入我的简历，更新经历库。”
- “分析 `jobs/inbox` 里的岗位，按广投策略保留所有相邻岗位，先不要投。”
- “为评分 70 分以上的岗位定制简历并生成 PDF。”
- “执行已批准岗位的填表，最终提交前逐个停下来让我确认。”

## 工作流

```text
简历 / 经历材料 → 事实库与成品基线 → 具体正式校招 JD → 轻微调或待批准重写 → HR → PDF/ATS → 写回岗位表 → 用户自行网申
```

根目录的 [AGENTS.md](AGENTS.md) 是总规则；两个可发现的工作技能在 `.agents/skills/`：

- `china-job-search`：导入经历、读取任意格式岗位清单、评分、定制材料和归档。
- `custom-resume`：针对单个中文 AI 产品经理或游戏研发/项目管理型产品 PM JD，生成可追溯的定制内容、双稿融合和内容验收；现在是这些岗位族的默认内容入口，但自身仍不生成 HTML/PDF、不投递。
- Schema 1.5 定向修复已实现：故事计划、1–4 段选材、每段 2–4 个互补要点、三轮候选循环、确定性正文质量门、调用回执、HR 9.0/8.0 证据门、最终内容哈希用户批准和历史失效账本已接入。当前状态为“实现完成、等待真实 JD 产品验收”，验收前不自动批准真实岗位，也不把新增岗位默认接入主流程。
- `browser-application`：通过本地 MCP 自动启动可见 Chromium、加载扩展和批准材料，连续填写、翻页和上传；最终提交由用户在扩展确认页确认一次。安装及限制见 [网申工具说明](tools/browser-application/README.md)。

旧版简历优化 Prompt/Agent 已标记 deprecated，不再静默使用；仅当岗位不受 `custom-resume` 支持且你明确批准回退时可用。

项目还固定导入了 MIT 许可的 [ASu-skills](https://github.com/Hisn00w/ASu-skills) 快照：`/asu`、`/asu-resume`、`/resume`、`/offer` 与 `/contributor`。这些技能用于经历表达、简历制作、投递进度和开源贡献；它们仍受本项目的事实库与投递安全规则约束。导入版本见 `.agents/third_party/asu-skills/IMPORT.md`。

另外可接入全局安装的 ASu 求职能力：`job-match`（JD 证据矩阵）、`great-resume`（显式经历提升）、`make-resume`（完整内容的可编辑 HTML/PDF 制版）、`job-apply`（字段映射规范）、`interview`（面试训练）和 `offer`（进度归档）。这些能力不会替代项目的事实库、批准清单或浏览器执行器；完整策略与可用性检查见 [ASu skill 接入说明](docs/asu-skill-integration.md)。

## 你的数据

- 已确认经历库：[profile/01-candidate-profile.md](profile/01-candidate-profile.md)
- 网申个人资料与敏感答案：[profile/application-answers.md](profile/application-answers.md)
- 可自行修改的偏好与表达要求：[profile/preferences.md](profile/preferences.md)
- 私有模范简历库：`profile/resume-exemplars/`。只有你确认达到投递水准的成稿才会登记；相似岗位可借鉴结构和判断，但不会把旧稿当事实源或直接套用旧经历名单。
- 私有成品基线库：`profile/resume-baselines/`。它保存一次性审计后的内容快照、哈希和复用状态；只有事实有效、角色方向一致的 `reusable` 条目可进入轻微调。

这些文件及生成的简历都已被 `.gitignore` 排除；不要把这个目录推送到公开仓库。

## 岗位清单

将 XLSX、CSV、图片、网页截图或纯文本放入 `jobs/inbox/`。表格有标准列时优先使用：`URL`、`模式`（`海投`/`定制`）、`启用`、`优先级`、`指定简历`、`备注`。非标准格式由 Codex 读取后生成可确认的规范清单，绝不猜测 URL 或岗位。

批量准备默认只处理正式校招。公司招聘项目会从官方页面展开成具体岗位，同一公司不同岗位在“岗位评估”中独立成行；轻微调优先，完整重写先按批次确认。默认不再用 Computer Use 逐项填表。

飞书在线表格请优先**导出 XLSX/CSV 后放入 `jobs/inbox/`**。部分公开分享链接只向匿名访问者提供压缩快照，不提供可可靠读取的单元格行；这种情况需要使用你已登录的浏览器会话读取，不能把页面标题或“加载中”当作导入结果。

第一步建议直接对 Codex 说：

> 分析 jobs/inbox 中的岗位，按经历库评分，只生成清单和定制建议，不要打开投递页面。
