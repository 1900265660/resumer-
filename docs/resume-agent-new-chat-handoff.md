# 独立对话：简历修改 Agent 训练交接

在新对话的第一条消息中粘贴以下内容（可按岗位替换 JD 路径）：

```text
Use $resume-training-agent to train and run a Chinese resume optimization agent.

This is an evidence-grounded training task. Do not create past experience, launches, metrics, or results from a JD, market research, reference resume, or hypothetical plan.

Read these materials directly before drafting:
- Workspace rules: E:\zhuomian\简历\项目\Codex-求职助手\AGENTS.md
- Confirmed candidate evidence library: E:\zhuomian\简历\项目\Codex-求职助手\profile\01-candidate-profile.md
- Candidate preferences: E:\zhuomian\简历\项目\Codex-求职助手\profile\preferences.md
- Existing optimizer prompt: E:\zhuomian\简历\项目\Codex-求职助手\.agents\prompts\campus-resume-optimizer.md
- Existing optimizer-agent configuration: E:\zhuomian\简历\项目\Codex-求职助手\.agents\agents\resume-optimizer-agent.md
- Reference-resume benchmark: E:\zhuomian\简历\项目\Codex-求职助手\docs\reference-resume-benchmark-2026-08-17.md
- Reference resumes: E:\zhuomian\简历\优秀简历
- Historical resumes: E:\zhuomian\简历\最新汇总

Target JD: [paste a JD or give its file path]

First run a baseline diagnosis. Then propose one precise prompt revision, test it against the same JD and evidence, and report the A/B comparison using the skill output contract. Do not produce a PDF or overwrite project files unless I explicitly ask.
```

## 建议训练顺序

1. 先用一个真实 JD 做基线诊断；重点检查经历取舍、核心项目深度、JD 覆盖和 AI 味。
2. 每轮只调整一个明确问题，例如“无关经历误入选”或“核心项目被过度压缩”。
3. 固定同一 JD 与事实库做 A/B 对照，确认改动没有破坏真实性、筛选逻辑或可读性。
4. 达到稳定效果后，再换第二类岗位验证泛化能力。
