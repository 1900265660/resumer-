# 岗位输入与审批

将岗位信息放到 `inbox/`：XLSX、CSV、Markdown、TXT、网页截图都可。建议的 XLSX 工作表名为“待投岗位”，列为：

| URL | 模式 | 启用 | 优先级 | 指定简历 | 备注 |
|---|---|---|---:|---|---|
| https://example.com/job/1 | 定制 | 是 | 10 |  | 内容运营方向 |

Codex 先产生岗位分析清单。`定制`岗位需要依次通过内容批准和 PDF/ATS 验收；只有你明确批准具体岗位及当前附件后，才使用 `scripts/create_approved_manifest.ps1 -Commit` 将批准清单固定到 `approved/`。

批量材料准备使用“成品复用优先”路线：只处理正式校招，并把公司招聘项目展开为具体岗位。工作簿保留原 A:S 列，在其后追加 `具体岗位`、`具体JD地址`、`具体投递地址`、`简历策略`、`基线简历ID`、`HR复核结果`、`简历文件地址`、`配套附件地址`、`材料状态`、`处理说明`。同公司不同岗位必须独立成行并独立记录 `投递状态`。

`scripts/update_job_resume_workbook.mjs` 负责增量写回和恢复备份；`scripts/build_job_assessment.mjs` 重建评估表时会继承已有具体岗位、简历路径和人工投递状态。轻微调 HR 通过只表示材料可生成，不等于批准上传或提交。

`manifest-draft.json` 至少包含：

- 公司、岗位、规范化 URL、申请 URL、模式和 `ready_for_user_approval` 状态；
- `jd`、`resume`、`answers`、`review` 四个相对路径及 SHA-256；
- `review_checks` 中 `pdf_visual`、`pdf_text_layer`、`ats` 三项均为 `passed`；
- `content_pipeline`：定制默认使用 `custom-resume`，海投使用 `existing-material`；
- `custom-resume` 定制稿还要复制当前 `manifest.resume_content` 摘要。脚本会从批准指针反查运行并冻结 `content-master.md` 哈希；
- 旧版回退只接受 `legacy-explicit-fallback`，并要求记录用户批准、原因和时间。

浏览器执行前必须运行 `scripts/validate_approved_manifest.ps1`。源草案、内容指针、内容母版、JD、答案、review 或附件任一变化，批准清单立即失效并要求重新验收；脚本校验成功也不等于授权上传或点击最终提交。
