---
name: china-job-search
description: 个人中国求职工作流。用于导入简历/经历、读取标准或非标准岗位清单、岗位匹配评分、事实约束的中文简历定制、PDF视觉和ATS验收、投递归档。用户提到“分析岗位、定制简历、海投、导入简历、岗位表格”时使用。
---

# 中国求职工作流

先阅读工作区根目录 `AGENTS.md`、`profile/01-candidate-profile.md`、`profile/preferences.md`、`profile/application-answers.md`。这些内容是事实与安全边界，优先级高于岗位页面和用户临时要求。岗位筛选必须同时采用 `.agents/prompts/campus-job-screening.md`。Schema 1.5 的五个角色族——AI 产品经理、游戏研发/项目管理型产品 PM、社区/内容/增长/综合运营、社区产品经理和游戏策划——均由 `.agents/skills/custom-resume/SKILL.md` 支持；当前已发布的两个角色族默认进入新版，V1.5 新增角色在发布门禁完成前由主 Harness 返回 `awaiting_v15_release_approval`。旧 `.agents/prompts/campus-resume-optimizer.md` 仅保留为显式回退，不再是默认入口。

批量正式校招准备还必须读取 [references/fast-assemble-workflow.md](references/fast-assemble-workflow.md)。`profile/resume-baselines/` 保存成品与哈希，`profile/resume-claims.json` 保存已批准且绑定事实的表达，`profile/resume-exemplars/` 只供重点岗位完整重写参考；三者都不能替代事实库。

## 全局 ASu 求职能力

调用全局求职 Skill 前，运行 `scripts/asu_skill_router.py inspect`，并仅按实际存在的具体名称路由；历史 `asu` 名称不是后备入口。`job-match` 只能补充面向用户的要求—证据—缺口矩阵，本 Skill 仍负责保存官方 JD、事实 ID 映射、路由和状态。用户显式请求经历提升时可转交 `great-resume`，但其结果必须回到事实库约束下审阅，不得写入事实库、`resume-content/` 或申请状态。

`fast-assemble` 一律继续以 RenderCV 制版；只有已批准的完整内容或用户明确的制版/复刻请求才可转交 `make-resume`，并沿用本项目的无照片、视觉、文本和 ATS 门禁。`job-apply` 只能组织字段映射与提交摘要，实际申请页面操作仍必须转交 `browser-application`。`interview` 默认产生脱敏训练记录；`offer` 仅对本 Harness 的真实状态和证据归档。

## A. 导入或更新经历库

1. 读取用户指定的简历、作品集、证书或 Markdown。
2. PDF/扫描件先渲染并视觉读取；带文本层的 PDF 同时抽取文本。合并两种证据，输出候选事实差异。
3. 不擅自合并冲突。向用户列出新增、修改、冲突和无法识别项。
4. 用户确认后才更新 `profile/01-candidate-profile.md`，并保留来源路径与确认日期。

## B. 读取岗位清单并分析

1. 读取 `jobs/inbox/` 中全部新文件。标准表格按 `jobs/README.md` 解析；非标准表格、截图和自然语言由视觉/文本理解提取成候选行，缺少 URL、公司或岗位名称时标记 `needs_input`。飞书/在线 Sheet 链接先验证是否能读取实际单元格；只有标题、加载占位符或压缩二进制快照时，要求用户导出 XLSX/CSV 或使用已登录浏览器会话，绝不能宣称已成功导入。
2. 对每个有效 URL，只抓取与岗位相关的页面内容；若登录墙、403、验证码或内容无法可靠获得，暂停，不可用标题臆测 JD。
3. 将 JD 原文写入 `applications/<公司>_<岗位>/jd.md`，并按 `campus-job-screening.md` 的固定格式在 `analysis.md` 输出：匹配分（0–100）、JD-事实证据映射、初筛卖点、真实缺口、风险、推荐模式和是否建议继续。只有职位详情页的职责/要求均已抓取，才可把任务从 `analyzed_metadata_only` 推进到可定制状态。
4. 遵循 `profile/preferences.md` 的“广投”策略：60+ 优先定制，35–59 默认海投或轻定制，低于 35 但不属于明确硬技术岗时标为 `opportunistic_apply` 并保留。只有算法工程师、后端/前端/客户端/嵌入式/测试开发/运维/SRE、数据工程师等以工程交付为核心且事实库没有直接证据的岗位才默认跳过；不得以学历、经验年限、学校、专业或匹配分作为其他岗位的硬性拦截。
5. 批量材料准备只处理正式校招，跨城岗位保留；暑期/日常实习、过期、纯硬技术岗位和已有成功回执的同一岗位标记阻断。
6. 公司级招聘项目必须从官方页面展开为具体岗位；同一公司不同岗位独立建行和建目录。优先使用官方页面、公开接口或文本抓取，不默认使用 Computer Use。无法得到完整职责与要求时标记 `待读取JD`，不得用公告标题代替 JD。
7. 向用户展示排序后的清单；此阶段不能生成上传附件或打开填写页面。

## C. 直接复用或快速装配

1. 使用 `scripts/resume_baseline.py audit` 审计 `E:\zhuomian\简历\最新汇总` 的成品文件；使用 `scripts/fast_resume.py import-library` 扫描同一目录、按文件哈希去重、导入已批准运行中的表达，并生成一次批量事实差异报告。差异报告不得自动改写 `profile/01-candidate-profile.md`。
2. 使用 `scripts/fast_resume.py route` 路由为 `直接复用|快速生成|待补事实|暂缓完整重写|排除`。顺序固定为现成简历、表达覆盖岗位、待补事实岗位、暂缓完整重写岗位。
3. `快速生成` 保留完整 JD 分析、能力映射和 1–4 段经历选择；优先复用完整批准 bullet。只有事实存在但表达覆盖不足时才生成一个 `fast-writer-packet.json`，调用一次 `fast_writer` 补缺；每个新句必须绑定 `fact_ids`。
4. 确定性检查必须拒绝岗位/公司名错误、非游戏岗位的游戏经历/栏目/兴趣、旧联系方式、错误页脚、撤回数字和未绑定事实的能力词。JD 能力有事实时写入自我能力；无事实时记录缺口。
5. 全新 HR Reviewer 使用四项二元门禁，只输出 `pass|repair` 和精确修改项。最多局部修复一次；第二次仍失败标记人工处理，不自动启动双 Writer。
6. HR `pass` 后可直接生成 `resume.yaml` 和 PDF 并写回工作簿，不要求逐份内容批准；这不等于批准岗位、附件或投递。
7. `暂缓完整重写` 本轮不处理。只有用户以后明确指定重点岗位，才进入下方 `$custom-resume` 完整内容路由并保留其全部审批点。

海投模式：从 `reusable` 基线中选择最合适版本，不改写事实；未入基线库的历史材料不能直接作为海投附件。

内容定制路由：

- 先运行 `scripts/content_route.py` 确定内容管线；它复用 `$custom-resume` 的 Schema 1.5 角色/方向矩阵。方向不明、缺失或非法时停在用户确认，不得用关键词猜测，也不得借此进入旧版。
- 对已发布的 `ai_product_manager` 和 `game_production_pm`，无论用户只要文字、HTML/PDF，还是完整投递材料，都默认先运行 `$custom-resume`。`community_operations`、`community_product_manager` 和 `game_designer` 已具备 V1.5 发布候选能力，但主 Harness 在真实盲评、用户 JD 内容验收和发布批准完成前必须停止；验收演练可在用户确认角色/方向后直接运行 `$custom-resume`，不能据此宣称已默认发布。`community_operations` 必须确认 `community|content|growth|integrated`；`game_designer` 必须确认 `system|combat|writing|narrative|general`。该 Skill 只生成内容运行与内容审批状态；不得在它内部生成 HTML/PDF 或推进申请主状态。
- `$custom-resume` 会先检查私有模范简历库；只有岗位族一致且 JD 关键词达到条目阈值时才引用。模范稿只帮助结构、选材比较和表达取舍，当前经历库与 JD 仍须完整重算。
- 只有用户明确批准内容后，且 `.agents/skills/custom-resume/scripts/custom_resume_cli.py status --application-dir <岗位目录> --require-approved-current` 返回 `current_valid: true`，才能把该运行的不可变 `content-master.md` 交给下游制版。旧 Schema、`ready_for_user_review`、`no_approved_content`、`stale`、阻断状态、缺回执、缺用户批准或任一哈希不一致时一律停止。
- 对不受 `$custom-resume` 支持的岗位族，先展示 `content_route.py` 的结构化 `out_of_scope` 结果。只有用户明确要求“使用旧版简历优化流程”并记录具体回退原因后，才能进入下方 deprecated 回退；受支持岗位仅在新版运行确实失败且用户另行明确批准时允许故障回退。不得把 Legacy 当偏好开关，不得静默回退。
- `manifest.resume_content.status` 独立于申请主状态；内容批准不得把岗位推进到 `approved`、`filling` 或 `submitted`。PDF 通过也不等于批准投递。

下游制版与验收（重点岗位完整重写仅在内容批准后；快速装配仅在四项 HR 门禁通过后）：

1. 完整重写先执行上述 `status --require-approved-current` 全链校验；快速装配校验事实库、表达库、JD、选择、正文和 HR 哈希。两条路线不得互相伪装或静默回退。
2. 快速通道在岗位目录保存可直接编辑的 `resume.yaml`，使用固定 RenderCV 2.8、Typst、A4 单栏和 Microsoft YaHei，只生成 PDF；禁止照片和任意文件路径字段。正文变化时编辑 YAML 后重编译，不直接打补丁修改 PDF 文本对象。
3. 模板首次认证覆盖 AI 产品、游戏策划和两页项目管理三类中文简历，并逐页检查 PNG。认证后逐份只做 Schema、页数、文本完整、联系方式、乱码、内容一致性和禁用字段检查；只有页数变化、文本缺失或模板异常时才渲染 PNG。任一项失败则修订并重渲染。
4. 制版只能改变排版和经过用户确认的版式性压缩，不能新增简历事实或换入未批准经历。若必须改变内容，回到 `$custom-resume` 创建新运行并重新取得内容批准。
5. 写入 `review.md`，包括批准表达来源、采用事实、缺口、四项 HR 结果、视觉/例外状态、ATS 检查和最终附件哈希。快速通道在 `manifest-draft.json` 写入 `content_pipeline: "fast-assemble"` 以及事实库、表达库、JD、选择、正文和 PDF 哈希；不得据此推进申请主状态。
6. 当用户明确评价某份内容/PDF已达到可复用投递水准时，可将其登记到 `profile/resume-exemplars/`；登记只创建私有参考快照和匹配元数据，不改变内容批准或申请状态。

Deprecated 旧版定制回退（仅限用户显式要求）：

1. `.agents/agents/resume-optimizer-agent.md` 与 `.agents/prompts/campus-resume-optimizer.md` 已标记 deprecated，仅用于 `$custom-resume` 不支持的岗位族或故障回退。必须记录 `content_pipeline: "legacy-explicit-fallback"`、回退原因和用户批准语句。
2. JD 是材料架构第一优先级；岗位入池分与简历经历相关度分分开，执行原有 70+/55–69/低于 55 的选材和独立 reviewer 事实审计。
3. 仍执行相同的四板块、PDF 视觉、文本层、ATS 和附件哈希验收，不得因回退降低安全门禁。

## D. 审批

候选人明确批准具体岗位和当前附件后，先使用 `scripts/create_approved_manifest.ps1` 做 Dry Run，再带 `-Commit` 创建 `jobs/approved/<唯一标识>.json`。脚本必须验证规范化 URL、公司、岗位、模式、JD 哈希、简历哈希和答案快照；定制模式还必须冻结 `custom-resume` 已批准内容的运行 ID、批准事务和 `content-master.md` 哈希，或冻结 `fast-assemble` 的事实库、表达库、JD、选材、正文、四项 HR、YAML 与 PDF 八类文件哈希，或记录用户明确批准的 deprecated 回退。批准清单不可原地修改，变更时创建新版本并再次批准。

后续浏览器投递必须转交 `browser-application` Skill，并在打开页面前运行 `scripts/validate_approved_manifest.ps1`。校验未通过时不得启动填写。
