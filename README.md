# Codex 求职助手（中国版）

这是供 **Codex 直接执行** 的个人求职工作区，不是需要常驻运行的网页应用。

你只需把文件放进对应目录，然后在 Codex 中说一句话：

- “导入我的简历，更新经历库。”
- “分析 `jobs/inbox` 里的岗位，按广投策略保留所有相邻岗位，先不要投。”
- “为评分 70 分以上的岗位定制简历并生成 PDF。”
- “执行已批准岗位的填表，最终提交前逐个停下来让我确认。”

## 工作流

```text
简历 / 经历材料 ─→ 事实库 ─→ 岗位分析 ─→ 你批准 ─→ 定制简历 ─→ PDF视觉验收 ─→ 浏览器填表 ─→ 最终确认提交
```

根目录的 [AGENTS.md](AGENTS.md) 是总规则；两个可发现的工作技能在 `.agents/skills/`：

- `china-job-search`：导入经历、读取任意格式岗位清单、评分、定制材料和归档。
- `browser-application`：浏览器填表和最终投递，严格要求人工批准。

项目还固定导入了 MIT 许可的 [ASu-skills](https://github.com/Hisn00w/ASu-skills) 快照：`/asu`、`/asu-resume`、`/resume`、`/offer` 与 `/contributor`。这些技能用于经历表达、简历制作、投递进度和开源贡献；它们仍受本项目的事实库与投递安全规则约束。导入版本见 `.agents/third_party/asu-skills/IMPORT.md`。

## 你的数据

- 已确认经历库：[profile/01-candidate-profile.md](profile/01-candidate-profile.md)
- 网申个人资料与敏感答案：[profile/application-answers.md](profile/application-answers.md)
- 可自行修改的偏好与表达要求：[profile/preferences.md](profile/preferences.md)

这些文件及生成的简历都已被 `.gitignore` 排除；不要把这个目录推送到公开仓库。

## 岗位清单

将 XLSX、CSV、图片、网页截图或纯文本放入 `jobs/inbox/`。表格有标准列时优先使用：`URL`、`模式`（`海投`/`定制`）、`启用`、`优先级`、`指定简历`、`备注`。非标准格式由 Codex 读取后生成可确认的规范清单，绝不猜测 URL 或岗位。

飞书在线表格请优先**导出 XLSX/CSV 后放入 `jobs/inbox/`**。部分公开分享链接只向匿名访问者提供压缩快照，不提供可可靠读取的单元格行；这种情况需要使用你已登录的浏览器会话读取，不能把页面标题或“加载中”当作导入结果。

第一步建议直接对 Codex 说：

> 分析 jobs/inbox 中的岗位，按经历库评分，只生成清单和定制建议，不要打开投递页面。
