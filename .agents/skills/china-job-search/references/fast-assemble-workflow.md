# 快速装配工作流

## 知识边界

- `profile/01-candidate-profile.md` 是唯一原子事实源。
- `profile/resume-claims.json` 只保存通过事实检查且具有批准来源的完整表达。每条表达必须绑定 `fact_ids`、经历、适用角色和 `game|non_game|both` 场景。
- 旧简历扫描产生的新增、冲突、过期或撤回内容只进入批量差异报告。用户一次性确认后，才可继续使用现有 `fact-diff` 写回事实库。
- 表达可以作为事实候选的来源证据，但不能绕过确认直接升级为事实。

## 路由

按以下顺序处理：

1. `直接复用`：已有验收 PDF，且文件存在、SHA-256 匹配、具体岗位名称正确；不重新制版。
2. `快速生成`：完整 JD 可读，选择的 1–4 段经历在批准表达库中有足够覆盖；必要时只做一次事实绑定补写。
3. `待补事实`：关键 JD 能力没有任何已确认事实证据。
4. `暂缓完整重写`：缺少合适经历或表达，本轮停止；只有用户以后明确指定重点岗位才进入 `$custom-resume`。
5. `排除`：非正式校招、过期、纯硬技术无证据、重复成功投递或其他已有排除条件。

批量文件先运行 `fast_resume.py prioritize`，用上述顺序稳定排序；不得让“暂缓完整重写”占用本轮快速生成队列。

## 快速装配

1. 读取完整 JD、能力映射和常规经历选择结果。
2. 以完整 bullet 为最小复用单元，不拼接半句。
3. 对支持事实存在但表达缺失的能力，生成一个 `fast-writer-packet.json`。一次调用只补缺口；输出每句都要绑定事实 ID。
4. 非游戏岗位排除 `context=game` 的表达、游戏项目和“游戏经历”栏目。不得仅删除栏目标题而保留游戏兴趣正文。
5. 目标公司和岗位必须与具体 JD 一致。联系方式只读取 `profile/application-answers.md` 的已确认值。
6. JD 要求有事实证据时，正文或自我能力必须覆盖；无证据时写入 `fact_gaps`，不得伪装成能力关键词。

## 四项 HR 门禁

HR Reviewer 只返回 `pass|repair`：

1. 岗位、公司或游戏/非游戏语境是否错位；
2. 是否存在无关、冗余或削弱定位的描述；
3. 是否存在事实、数字、所有权或联系方式错误；
4. 是否遗漏已有事实支持的 JD 能力。

`repair` 必须给出精确位置和修改动作。初稿可局部修复一次；第二次仍为 `repair` 时标记人工处理。不得自动升级到双 Writer。

## PDF

- `resume.yaml` 是日常编辑源，RenderCV 固定为 2.8。
- 只允许本地生成器产生 YAML；拒绝 `photo`、`image`、`path`、外部模板等任意文件字段。
- 日常命令关闭 Markdown、HTML 和 PNG；RenderCV 2.8 的 `-notyp` 会连带关闭 PDF，因此实现应把临时 Typst 写到受控路径并在成功后删除。
- 认证模板后默认只跑确定性 QA。只有认证、页数变化、文本缺失或模板异常才渲染 PNG 进行视觉检查。
- RenderCV 试点失败时，使用单个持久 Chrome/CDP 会话批量打印现有 HTML，不逐份启动浏览器。

## 状态和哈希

快速通道清单记录 `content_pipeline: fast-assemble`，并冻结事实库、表达库、JD、经历选择、内容、YAML 和 PDF 的 SHA-256。HR 通过、PDF 通过和岗位投递批准仍是彼此独立的门禁。

`fast_resume.py apply-writer` 是唯一的单 Writer 结果写入口：它只接受 `supported_coverage_gaps` 中的 requirement ID，只接受事实库已有的 `fact_ids`，并拒绝第二次调用。RenderCV 环境通过 `scripts/setup_rendercv.ps1` 和 `requirements-rendercv.txt` 固定为 2.8。
