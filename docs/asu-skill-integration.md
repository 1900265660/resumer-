# ASu 求职技能接入

## 目标与权威边界

全局安装的 ASu 求职 Skill 是能力层，不是本工作区的事实、审批或投递状态来源。`profile/01-candidate-profile.md`、`profile/application-answers.md`、岗位目录、批准清单和 `browser-application` 始终优先。

先执行以下命令检查当前机器实际安装的能力；历史名称 `asu` 不参与自动回退：

```powershell
python .agents/skills/china-job-search/scripts/asu_skill_router.py inspect
```

`custom_resume_asu_writer` 仍是 `$custom-resume` 双 Writer 的第二 Writer。它使用项目内受控的 Agent 配置和 Prompt，不依赖全局 `asu` Skill。

## 路由

| 用户意图 | 全局能力层 | 项目权威执行者 | 不允许的行为 |
| --- | --- | --- | --- |
| JD 匹配分析 | `job-match` | `china-job-search` | 用矩阵替代官方 JD 或事实 ID 映射 |
| 经历提升、定位、开场白 | `great-resume` | 人工/事实审阅 | 写事实库、进入双 Writer/Fusion、推进状态 |
| 完整内容的制版/复刻 | `make-resume` | `resume` + 项目 QA | 对 `fast-assemble` 替换 RenderCV、使用占位照片 |
| 网申字段映射与摘要 | `job-apply` | `browser-application` | Kimi WebBridge 或其他控制器填写、上传或提交 |
| 面试预测、模拟、复练 | `interview` | 脱敏岗位训练记录 | 虚构回答、更新事实或申请状态 |
| 投递进度归档 | `offer` | Harness 状态与回执 | 新建独立追踪器、无回执写 `submitted` |

## 强制门禁

- `great-resume` 是双 Writer 之外的用户显式能力，不能取代 `custom_resume_asu_writer`，也不产生 `DraftArtifact`、Fusion 或调用回执。
- `fast-assemble` 继续使用 RenderCV；其输入、HR 和 PDF 验收均通过后才可成为投递材料。完整定制内容只有在 `custom_resume_cli.py status --require-approved-current` 有效后才能进入 HTML/PDF 制版。
- `job-apply` 不能绕开不可变批准清单、附件哈希、敏感字段授权、最终人工确认和成功回执。`browser-application` 是唯一页面操作执行器。
- 任一全局 Skill 缺失时，路由器返回 `degraded`。调用者必须向用户报告缺失能力，不得静默替换成另一全局 Skill。
