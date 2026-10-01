# Custom Resume V1.5 发布验收进度

## 门禁状态

| 门禁 | 状态 | 当前证据 |
|---|---|---|
| T25 Schema 1.4 与角色/方向基础 | 通过 | 五角色族、条件方向、动态能力标题、模范简历隔离回归 |
| T26 社区岗位支持 | 通过 | 5 个正向方向/角色夹具及缺口、对抗断言 |
| T27 游戏策划支持 | 通过 | 5 个方向正向夹具及缺口、跨方向对抗断言 |
| T28 主 Harness 发布候选路由 | 通过 | 已发布角色默认新版；新增 10 个组合返回 `awaiting_v15_release_approval` |
| 下游状态、PDF、批准与投递隔离 | 通过 | 否定依赖、内容/附件/清单篡改及最终确认回归 |
| 扩展真实旧/新稿盲评 | 通过 | 社区 5 例与游戏策划 5 例真实旧/新稿独立盲评均通过 |
| 用户指定 JD 内容验收 | 等待用户审阅 | Schema 1.5 新运行已触发一次双 Writer 重写并通过全部程序门，停在 `ready_for_user_review`；尚无最终内容批准 |
| V1.5 默认路由发布批准 | 未完成 | 必须在前两项完成后由用户明确批准 |

## 已通过

- Schema 1.4 五角色族与条件方向矩阵、动态自我能力标题和模范简历角色/方向隔离。
- 社区运营四方向与社区产品的 Prompt、判断指南、正向/缺口/对抗夹具。
- 游戏策划系统、战斗、文案、叙事、综合五方向的 Prompt、判断指南、正向/缺口/对抗夹具。
- 主 Harness 的确定性发布候选路由：已发布的两个角色族默认进入 `custom-resume`；10 个 V1.5 新增合法角色/方向组合在发布批准前返回 `awaiting_v15_release_approval`；未知/非法方向停在确认；Legacy 仅允许带原因的显式 out-of-scope 或已发布路线故障回退。
- 内容批准、PDF/ATS、岗位批准和最终提交保持四个独立门禁；内容、附件和批准清单篡改均由回归拒绝。
- 社区与游戏策划扩展各 5 个脱敏正向用例提供预期真实性、五项质量和 HR 门槛；合成 A/B 分数验证了盲化汇总代码契约。
- 社区扩展 5 个用例已完成相互隔离的旧版生成、新版生成和匿名评分；解盲后真实性与质量门禁均通过，V1.5 在 `jd_coverage`、`evidence_depth`、`hr_scan` 三项均有提升。可提交摘要见 `community-blind-summary.json`，匿名映射和过程稿只保留在忽略目录，不进入版本库。
- 游戏策划扩展 5 个用例经过三轮真实盲评：前两轮分别暴露并修复跨经历 trace、事实外推和综合方向跨项目概括；第三轮 5/5 新版稿通过真实性硬门槛，并在 `jd_coverage`、`evidence_depth`、`hr_scan`、`selection_quality` 四项提升。可提交摘要见 `game-designer-blind-summary.json`。

合成 A/B 分数仍只记作评分器契约测试；社区与游戏策划结论均来自真实旧/新稿和独立匿名评分。真实用户 JD 的旧选材曾通过独立审计并获用户批准，但不可变运行 `cr_20260901T034747_echo02` 的历史 `review_ready` 只证明旧工件完整，不再代表内容质量通过。Schema 1.5 新运行 `cr_20260903T084342_da977c` 从最新事实库和同一回响科技 JD 重新开始：初稿双 Lane 被 post-draft Auditor 拒绝，协调器路由到 Writer 局部重写；修订稿、Fusion、确定性质量门、post-fusion Auditor 和 HR 均通过，当前停在 `ready_for_user_review`。这仍不是内容批准或发布批准；用户内容人工验收和明确发布批准均未完成。

## 用户 JD 演练

已选用用户最初指定的回响科技招聘作为真实演练来源，并为“社区运营【校招全职/实习】”采用 `community_operations/content` 路由。首版 `cr_20260901T020649_echoct` 和第二版 `cr_20260901T034747_echo02` 均已按用户否决写入阻断账本；旧 HR 分数不再构成批准证据。

Schema 1.5 新运行 `cr_20260903T084342_da977c` 只选择独立游戏评测组、聚微校园招聘大使和《收获》编辑部三段经历，分别分配 3/2/3 条要点。首轮双稿虽通过确定性门，但独立 post-draft Auditor 识别出事实外方法、过度抽象和过载表达并判双 Lane 失败；协调器将 `generation_round` 推进为 1，仅退回两个 Writer 重写。修订稿确定性门均通过，独立审计最低维度为 Writer 8.4、ASu Writer 8.8；融合稿 862 个汉字、8 条经历要点、14 条总要点，无硬失败或警告。post-fusion Auditor 五项为 9.1/9.3/9.4/8.7/8.6；HR 为 `strong_push`、总分 9.1，五项为 9.3/9.0/9.4/9.0/9.2，并逐项引用最终 bullet。运行只进入 `ready_for_user_review`，未写入 current、未生成 PDF、未产生批准清单或投递动作；可提交机器摘要见 `echo-schema-v15-blind-run.json`。
## 最近验证

- `python -m pytest tests/custom_resume -q`：201 通过。
- `python -m compileall .agents/skills/custom-resume/scripts .agents/skills/china-job-search/scripts tests/custom_resume`：通过。
- 24 份 JSON Schema 重导出逐字节一致。
- 20 个存量 run 目录扫描：15 个通过，2 个用户拒绝 run 被账本阻断，3 个历史手工目录缺少 `run.json`。
- 回响 Schema 1.5 新运行目录校验通过，状态为 `ready_for_user_review`；`review_ready=false` 是因为尚无用户最终内容批准。
- Skill Creator `quick_validate.py`：`custom-resume` 与 `china-job-search` 均通过；Windows 上使用 `python -X utf8` 读取中文 UTF-8 文件。
- `git diff --check`：通过，仅报告工作区既有 LF/CRLF 转换提示。
