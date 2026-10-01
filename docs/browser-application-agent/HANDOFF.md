# 网申执行器当前状态（2026-09-24 交接备注）

## 已交付能力（真实页面验证过）

Moka 平台（`app.mokahr.com/campus-recruitment/*`）主流程已打通：启动可见浏览器 → 登录检测 → 申请职位 → 隐私协议同意 → 上传简历自动解析回填 → 补齐基础字段。可处理普通文本、Moka 下拉/搜索下拉、多选、只读日期面板。参考项目自带日期处理已复用并适配 Moka。

关键实现位置：`tools/browser-application/src/runtime.ts`（编排/Playwright 搜索下拉）、`extension/content.js`（Moka 控件、日期面板）、`extension/shared/fill-runtime.js`（日期精度）。

## 已确认并写回的事实

- 出生日期 2002/11/20、性别 男。
- 目前职位：应届生；教师资格证：无。
- 汉语言文学毕业 2025/06/30；社会工作毕业 2027/06/30。
- 事实源：`profile/01-candidate-profile.md`；答案库：`profile/application-answers.md`。

## 岗位状态

- 完美世界：已投（用户确认）。
- 作业帮：硬件业务，用户判定不该进可投榜单，已排除。
- 当前唯一“ready 且未投”：灵犀互娱两个岗位（阿里校招平台）。
- 已选：灵犀互娱·游戏策划（卡牌），position id `199907680014`。

## 下一步（阿里平台待适配）

阿里流程：职位详情 → “加入意向单” → `mozi-login.alibaba-inc.com` SSO 登录 → 意向单/申请表单。Moka 适配不适用，需：

1. 用户登录阿里账号（登录页已开过，脚本 `scripts/alibaba-login-hold.ts` 会等登录）。
2. 登录后扫描意向单/申请入口，适配阿里组件（预计 antd Select/DatePicker）。
3. 填表后停在前一步，最终提交仍须用户确认。

## 调试脚本（tools/browser-application/scripts/）

- `fill-hold.ts`：Moka 填完保活，供用户点提交。
- `alibaba-login-hold.ts`：阿里“加入意向单→登录→扫描”保活。
- 其余 `*-diag.ts`、`probe-*.ts`、`test-*.ts` 为真实页面诊断脚本，可删。

回归：上游 72 项 + 自有测试通过，`tsc` 无错误；改完 `src/` 或 `extension/` 后需重新编译 `tsc` 并重启 MCP 服务。
