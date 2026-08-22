# 简历 V2 完整回归测试｜2026-08-17

## 测试对象

- Master Prompt：`.agents/prompts/campus-resume-optimizer.md`
- 子代理训练：`.agents/agents/resume-optimizer-agent.md`
- 内容稿：`applications/测试_淘宝闪购_AI产品经理/resume-optimizer-v2.md`
- 可编辑源：`applications/测试_淘宝闪购_AI产品经理/resume-tailored.html`
- PDF：`applications/测试_淘宝闪购_AI产品经理/候选人_淘宝闪购_AI产品经理_定制简历.pdf`

## 结果

| 测试 | 结果 |
| --- | --- |
| Master Prompt 八阶段与七类输出 | 通过 |
| JD 硬性 / 优先 / 加分分类规则 | 通过 |
| 最终简历 Bullet 上限 | 通过：8 条 |
| 未支持关键词隔离 | 通过：SQL、RAG、模型训练、算法/后端协作未进入简历正文 |
| HTML 可编辑源 | 通过 |
| Chrome PDF 生成 | 通过 |
| A4 页数 | 通过：1 页 |
| PDF 文本层 | 通过 |
| 联系信息与毕业时间 | 通过 |
| 视觉检查 | 通过：无截断、重叠、乱码或孤立分区 |
| 批准清单 dry-run | 通过：有效草稿被接受，错误 PDF 哈希被拒绝，未写文件 |
| PDF SHA-256 | `AA335B30426DFBDF86455ABFB76DD52CF5BBD3792946997C2F0CD429BBF6D820` |

## 发现并修复

1. 首次 ATS 检查用“多 Agent Workflow”作为连续字符串，Chrome 文本层在中英文之间插入空格，造成假阴性；改为稳定的 `Agent Workflow` 检查，同时保留中文语义人工核对。
2. 初次视觉渲染正文偏小且底部留白较多；提高正文、标题和行距，并恢复更舒适的页边距。第二轮仍保持一页。
3. HTML 仍包含旧模板示例，但位于原生 `<template>` 且带隐藏类，不进入运行时打印内容；实际 PDF 文本层未出现虚构示例。
4. 批准文件名原先会删除中文公司和岗位，只剩模糊的 `ai-时间.json`；清洗规则已改为保留 Unicode 字母与数字，便于批次追溯。

## 尚未执行

- 未创建批准清单。
- 未登录、上传、填写或提交真实网申。
- 未验证真实招聘网站是否接受该 PDF 附件。
