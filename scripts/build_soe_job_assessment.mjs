#!/usr/bin/env node

/** Build a categorized workbook for the Feishu 国央企 batch. */

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const DEFAULT_MODULE_ROOT =
  "C:\\Users\\Administrator\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules";
const CONTENT_RESUME_PATH = "E:\\zhuomian\\简历\\项目\\Codex-求职助手\\outputs\\soe-resumes-2026-09-27\\内容宣传与新媒体运营\\测试候选人_内容宣传与新媒体运营简历.pdf";

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (!key.startsWith("--")) throw new Error(`Unexpected argument: ${key}`);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) args[key.slice(2)] = true;
    else {
      args[key.slice(2)] = next;
      i += 1;
    }
  }
  return args;
}

function colName(number) {
  let value = number;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function normalizeUrl(raw) {
  let value = String(raw ?? "").replace(/[，。；;、）》】\]}>'"\s]+$/gu, "").trim();
  if (!value) return "";
  if (/^www\./iu.test(value) || /^[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)+(?:\/[^\s]*)?$/iu.test(value)) value = `https://${value}`;
  if (!/^https?:\/\//iu.test(value)) return "";
  try {
    const url = new URL(value);
    if (url.hostname === "mp.weixinbridge.com") {
      const nested = url.searchParams.get("url");
      if (nested && /^https?:\/\//iu.test(nested)) return new URL(nested).href;
    }
    return url.href;
  } catch {
    return value;
  }
}

function extractUrls(raw) {
  const text = String(raw ?? "");
  const matches = text.match(/https?:\/\/[^\s<>{}"']+/giu) ?? [];
  if (matches.length === 0 && text.trim() && !text.includes("\n")) matches.push(text.trim());
  return [...new Set(matches.map(normalizeUrl).filter(Boolean))];
}

function extractEmails(raw) {
  return [...new Set(String(raw ?? "").match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/giu) ?? [])];
}

const VERIFIED_ROLES = {
  6: [
    ["交投新光管培生", "管培/综合", "杭州", "岗位名称及招录人数", "集团管培生45名；具体资格需打开岗位页核验"],
  ],
  19: [
    ["战略开发", "研究/综合管理", "杭州", "完整职责与要求", "政策/行业研究、公文写作、AI辅助办公；要求硕士及以上"],
    ["综合行政", "行政/文秘", "杭州", "完整职责与要求", "公文、会议纪要、信息整理；要求硕士及以上，汉语言文学相关"],
    ["国际商务", "市场/商务", "杭州", "完整职责与要求", "跨境合规、英文商务沟通；要求硕士及以上"],
    ["国际物流", "运营/商务", "杭州", "完整职责与要求", "跨境物流、客户洽谈、英文单证；要求硕士及以上"],
  ],
  27: [
    ["管培生", "管培/综合", "厦门/福州/杭州", "官网岗位类别", "已显示岗位名称；职责与要求待读取"],
    ["营销管理", "市场/营销", "厦门/福州/杭州", "官网岗位类别", "已显示岗位名称；职责与要求待读取"],
  ],
  73: [
    ["业务管理", "综合运营", "北京/上海/杭州/成都/南京", "官网岗位类别", "中国移动门户类别；需确认是否属于咪咕本批次"],
    ["战略运营", "战略/运营", "北京/上海/杭州/成都/南京", "官网岗位类别", "中国移动门户类别；需确认是否属于咪咕本批次"],
    ["市场策划", "市场/品牌", "北京/上海/杭州/成都/南京", "官网岗位类别", "中国移动门户类别；需确认是否属于咪咕本批次"],
    ["人力资源", "人力资源", "北京/上海/杭州/成都/南京", "官网岗位类别", "中国移动门户类别；需确认是否属于咪咕本批次"],
  ],
  113: [
    ["总部菁英管培生", "管培/综合", "全国", "招聘公告项目", "已确认专项名称；具体岗位职责与专业要求待读取"],
  ],
  119: [
    ["AI产品岗(J33240)", "AI产品", "深圳", "2027职位清单", "全职校招；职责与要求需进入详情页"],
    ["品牌管理岗(J33238)", "品牌/内容", "深圳", "2027职位清单", "全职校招；职责与要求需进入详情页"],
    ["商业运营岗(J33235)", "商业运营", "深圳", "2027职位清单", "全职校招；职责与要求需进入详情页"],
    ["运营管理岗(J33232)", "运营管理", "深圳", "2027职位清单", "全职校招；职责与要求需进入详情页"],
    ["综合管理岗(J33230)", "综合管理", "深圳/香港", "2027职位清单", "全职校招；职责与要求需进入详情页"],
    ["电商运营岗(J33223)", "电商运营", "深圳", "2027职位清单", "全职校招；职责与要求需进入详情页"],
    ["游轮产品策划岗(J33225)", "产品策划", "深圳", "2027职位清单", "全职校招；职责与要求需进入详情页"],
  ],
  132: [
    ["总行管培生", "管培/综合", "广州", "官网项目名称", "职责、学历和专业要求待读取"],
    ["分行管培生", "管培/综合", "广东省内及南京", "官网项目名称", "职责、学历和专业要求待读取"],
  ],
  139: [
    ["新媒体运营岗", "内容/新媒体运营", "泉州", "完整职责", "宣传策划、抖音/视频号运营、官网内容、文案及品牌活动"],
  ],
  146: [
    ["人力资源管理岗(J10036)", "人力资源", "北京", "2027职位清单", "全职校招；职责与要求需进入详情页"],
    ["综合管理岗(J10035)", "综合管理", "北京", "2027职位清单", "全职校招；职责与要求需进入详情页"],
    ["运营管理岗(J10030)", "运营管理", "北京", "2027职位清单", "全职校招；职责与要求需进入详情页"],
    ["市场开发岗(J10028)", "市场/商务", "北京", "2027职位清单", "全职校招；职责与要求需进入详情页"],
    ["海外项目管理岗(J10037)", "项目管理", "海外", "2027职位清单", "全职校招；职责与要求需进入详情页"],
  ],
  164: [
    ["图书编辑", "编辑/内容", "北京", "官网岗位类别", "3个职位；具体职责与要求需进入详情页"],
    ["产品经理", "产品", "北京", "官网岗位类别", "2个职位；具体职责与要求需进入详情页"],
    ["新媒体运营", "内容/新媒体运营", "北京", "官网岗位类别", "2个职位；具体职责与要求需进入详情页"],
    ["电商运营", "电商运营", "北京", "官网岗位类别", "1个职位；具体职责与要求需进入详情页"],
  ],
  166: [
    ["研究发展业务助理", "研究/分析", "北京/上海/广州/深圳", "2027职位清单", "截止2026-10-12；职责与要求需进入详情页"],
    ["机构业务助理", "机构业务", "北京/上海/深圳", "2027职位清单", "职责与要求需进入详情页"],
    ["托管业务助理", "运营/业务支持", "北京/上海/深圳", "2027职位清单", "职责与要求需进入详情页"],
    ["国际业务助理", "国际业务", "北京/上海", "2027职位清单", "职责与要求需进入详情页"],
    ["财富管理业务助理", "财富管理", "北京/石家庄", "2027职位清单", "截止2026-10-12；职责与要求需进入详情页"],
    ["风险管理业务助理", "风控", "北京/上海", "2027职位清单", "职责与要求需进入详情页"],
    ["法律合规业务助理", "法务/合规", "北京", "2027职位清单", "截止2026-10-12；法律专业要求待核验"],
  ],
  174: [
    ["产品类", "产品", "合肥/北京/上海/成都", "官网岗位类别", "中国电信门户类别；需筛选中电信量子具体岗位"],
    ["市场类", "市场", "合肥/北京/上海/成都", "官网岗位类别", "中国电信门户类别；需筛选中电信量子具体岗位"],
    ["云网运营", "运营", "合肥/北京/上海/成都", "官网岗位类别", "中国电信门户类别；需筛选中电信量子具体岗位"],
  ],
  183: [
    ["客户经理", "客户/市场", "全国多地", "官网岗位类别", "营销方向；具体职责与要求需进入详情页"],
    ["MKT经理-商务", "市场/商务", "全国多地", "官网岗位类别", "营销方向；具体职责与要求需进入详情页"],
    ["人力资源经理", "人力资源", "全国多地", "官网岗位类别", "运营支撑方向；具体职责与要求需进入详情页"],
  ],
  201: [
    ["综合能源市场代表", "市场/项目", "泰州/盐城", "完整职责", "市场调研、新能源项目开发、方案编制、商务洽谈及实施"],
  ],
  261: [
    ["项目执行岗", "项目管理/投行", "深圳/上海/北京", "2027职位清单", "具体职责与专业要求需进入详情页"],
    ["客户服务岗", "客户运营", "深圳/上海/北京", "2027职位清单", "具体职责与专业要求需进入详情页"],
    ["客群运营岗", "用户/运营", "深圳", "2027职位清单", "具体职责与专业要求需进入详情页"],
    ["综合调研岗", "研究/文秘", "深圳", "2027职位清单", "具体职责与专业要求需进入详情页"],
    ["党委事务岗", "党务/综合", "深圳", "2027职位清单", "具体职责与政治面貌要求需进入详情页"],
    ["研究策划及产品助理岗", "研究/产品", "深圳/上海/北京", "2027职位清单", "具体职责与专业要求需进入详情页"],
    ["项目管理岗", "项目管理", "深圳", "2027职位清单", "金融科技部门；技术背景要求待核验"],
  ],
  282: [
    ["科技创新与规划运营", "运营/项目", "武汉", "完整职位页", "技术品牌传播、新闻稿/专访稿、内容选题和全平台运营"],
    ["组织与流程变革", "项目/流程管理", "武汉", "完整职位页", "流程体系、项目推进与组织协同；专业要求需逐项核验"],
    ["产品线-赛事运营", "活动/运营", "武汉", "完整职位页", "赛事和产品线运营；专业要求需逐项核验"],
    ["业务架构与质量运营", "运营/流程", "武汉", "完整职位页", "业务架构、质量运营；专业要求需逐项核验"],
  ],
  293: [
    ["AI产品经理（2027届金融科技专场）", "AI产品", "深圳", "2027职位清单", "截止2026-09-20；完整职责与要求需进入详情页"],
  ],
  333: [
    ["运营类", "运营", "上海", "官网岗位类别", "6个职位；具体岗位名称、职责与要求需进入详情页"],
    ["市场类", "市场", "上海", "官网岗位类别", "2个职位；具体岗位名称、职责与要求需进入详情页"],
    ["综合类", "综合管理", "上海", "官网岗位类别", "6个职位；具体岗位名称、职责与要求需进入详情页"],
  ],
  647: [
    ["职能支撑类", "人力/管理/法务", "北京", "完整公告类别", "要求2026/2027届硕士及以上；专业含人力、管理、法学等"],
    ["前台业务类", "金融业务", "北京", "完整公告类别", "要求2026/2027届硕士及以上；专业以经金财会等为主"],
  ],
  927: [
    ["心翼萃材管培生", "管培/综合", "北京", "官网项目名称", "招聘项目含2027届；批次与全职性质需复核"],
    ["职能管理类/品牌建设方向", "品牌/综合", "北京", "官网岗位类别", "中国航发融媒体中心/品牌建设中心；具体岗位职责待核验"],
  ],
};

const PRIORITY_ROWS = new Set([6, 27, 73, 119, 132, 139, 146, 164, 166, 174, 183, 201, 261, 282, 293, 333]);
const CONDITION_RISK_ROWS = new Set([19, 109, 147, 189, 647, 927]);
const HARD_TECH_ROWS = new Set([350, 503, 577]);

function parseDeadline(raw, assessmentDate) {
  const text = String(raw ?? "").trim();
  // Require the day token to end at a digit boundary. Without this guard, a
  // recruiting period such as "2026.9-2027.6" is misread as 2026-09-20.
  const match = /(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})(?!\d)/u.exec(text);
  if (match) {
    const due = Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    const baseParts = assessmentDate.split("-").map(Number);
    const base = Date.UTC(baseParts[0], baseParts[1] - 1, baseParts[2]);
    const days = Math.round((due - base) / 86_400_000);
    if (days < 0) return { label: "已过期", days };
    if (days <= 7) return { label: `仅剩${days}天`, days };
    return { label: `剩余${days}天`, days };
  }
  if (/9月上旬/u.test(text)) return { label: "可能已截止", days: null };
  if (/^9月$|9月截止/u.test(text)) return { label: "本月截止，尽快核验", days: null };
  return { label: text || "未明确", days: null };
}

function rowResults(crawl, sourceRow, kind) {
  return crawl.results.filter((result) => result.references?.some((reference) =>
    reference.sourceRow === sourceRow && (!kind || reference.kind === kind)));
}

function stateSummary(results) {
  if (results.length === 0) return "缺失";
  return [...new Set(results.map((item) => item.accessState))].join("/");
}

function sectorHint(industry) {
  const text = String(industry ?? "");
  if (/银行/u.test(text)) return "建议筛选：管培、运营、客户服务、综合管理、人力资源";
  if (/券商|资管|基金|期货|金融|信托|保险|租赁|投资/u.test(text)) return "建议筛选：运营、研究支持、客户服务、市场、综合职能";
  if (/通信|软件|电子|半导体|智能硬件|物联网/u.test(text)) return "建议筛选：产品、市场、运营、项目管理、人力资源";
  if (/地产|建筑|能源|电力|制造|机械|汽车|航空|军工|有色/u.test(text)) return "建议筛选：项目管理、市场、品牌宣传、行政人力、综合管理";
  if (/传媒/u.test(text)) return "建议筛选：编辑、内容、产品、新媒体、电商运营";
  return "建议筛选：产品、运营、项目、市场、行政人力、综合管理";
}

function isEmptyPortal(results) {
  return results.some((item) => /全部职位（共\s*0\s*个）|暂时没有符合条件的职位/u.test(item.bodyText ?? ""));
}

function chooseCategory({ row, batch, title, deadline, appResults, hasEmail }) {
  const sourceRow = row.sourceRow;
  if (deadline.label === "已过期" || isEmptyPortal(appResults) ||
      (appResults.length > 0 && appResults.every((item) => item.accessState === "closed_or_missing"))) return "7-已过期/无在招岗位";
  if (String(batch).includes("暑期实习") || /实习生招聘|实习招募|博士后|博士招聘/u.test(title)) return "6-实习/专项批次复核";
  if (HARD_TECH_ROWS.has(sourceRow)) return "8-默认跳过·硬技术专项";
  if (deadline.days !== null && deadline.days <= 7) return "1-立即核验/投递";
  if (PRIORITY_ROWS.has(sourceRow)) return "2-优先可投·已识别方向";
  if (CONDITION_RISK_ROWS.has(sourceRow)) return "4-机会型·条件风险";
  const readableApplication = appResults.some((item) => item.accessState === "ok");
  if (!readableApplication && !hasEmail) return "5-待读取JD/人工复核";
  return "3-可投·先选具体岗位";
}

function nextAction(category) {
  return {
    "1-立即核验/投递": "先打开具体职位并核验职责、要求和截止时间；匹配则优先准备材料",
    "2-优先可投·已识别方向": "从已识别方向进入具体职位详情；只把完整JD加入材料准备清单",
    "3-可投·先选具体岗位": "公司入口有效；先筛选非硬技术的正式校招职位",
    "4-机会型·条件风险": "保留机会型投递；先核验学历、专业、地点或专项资格",
    "5-待读取JD/人工复核": "入口缺失或受限；人工取得具体职位职责与要求后再判断",
    "6-实习/专项批次复核": "不进入正式校招材料批次；仅在确认全职校招性质后重新纳入",
    "7-已过期/无在招岗位": "不使用当前链接投递；官网出现新职位时重新评估",
    "8-默认跳过·硬技术专项": "当前事实库不支持以深度工程/科研为核心的岗位",
  }[category];
}

function fitSummary(category, row, roleCount, location) {
  if (category === "8-默认跳过·硬技术专项") return "缺少对应的深度研发/算法/科研交付证据";
  if (category === "7-已过期/无在招岗位") return "当前批次已截止、职位页失效或官网显示0个职位";
  if (category === "6-实习/专项批次复核") return "不属于默认批量准备的正式校招，或专项资格不明";
  if (category === "5-待读取JD/人工复核") return "没有可靠读取到具体职位职责与要求";
  if (category === "4-机会型·条件风险") return "方向可迁移，但学历、专业、地点或专项资格存在明显风险";
  const city = String(location).includes("上海") ? "含上海" : "需考虑跨城";
  return roleCount > 0
    ? `已识别与内容、产品、运营、项目、市场或综合职能相邻的方向；${city}`
    : `招聘入口可用，但尚未取得完整具体JD；${city}`;
}

function isCandidateBatch(assessment) {
  return ["1-立即核验/投递", "2-优先可投·已识别方向", "3-可投·先选具体岗位"].includes(assessment.category) &&
    !/实习|暑期|日常/u.test(assessment.batch) &&
    !/closed_or_missing/u.test(assessment.linkState);
}

function roleApplicationStatus(assessment, role) {
  if (/新媒体运营岗/u.test(role[0]) && assessment.company === "招商积余") return "待投递（材料已验收）";
  return "待投递";
}

function roleResumePath(assessment, role) {
  if (/新媒体运营岗/u.test(role[0]) && assessment.company === "招商积余") return CONTENT_RESUME_PATH;
  return "未生成";
}

function candidatePriority(assessment) {
  let score = assessment.category === "1-立即核验/投递" ? 60 :
    assessment.category === "2-优先可投·已识别方向" ? 50 : 0;
  if (assessment.location.includes("上海")) score += 40;
  if (/产品|运营|项目|市场|品牌|内容|编辑|行政|人力|综合|管培|调研|客户|公关|策划|传播|文秘|用户/u.test(
    `${assessment.title} ${assessment.directions} ${assessment.industry}`,
  )) score += 30;
  if (/^仅剩/u.test(assessment.deadlineState)) score += 25;
  else if (/^剩余/u.test(assessment.deadlineState)) score += 15;
  return score;
}

function addTableSheet(workbook, name, headers, rows, widths, tableName, style) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const last = colName(headers.length);
  sheet.getRange(`A1:${last}1`).values = [headers];
  sheet.getRange(`A1:${last}1`).format = {
    fill: "#274C77",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
  };
  if (rows.length > 0) {
    sheet.getRange(`A2:${last}${rows.length + 1}`).values = rows;
    const body = sheet.getRange(`A2:${last}${rows.length + 1}`);
    body.format.font = { name: "Arial", size: 9, color: "#1F1F1F" };
    body.format.verticalAlignment = "top";
    body.format.wrapText = true;
    body.format.rowHeight = name === "链接检查" ? 30 : 40;
    sheet.tables.add(`A1:${last}${rows.length + 1}`, true, tableName).style = style;
  }
  headers.forEach((header, index) => {
    sheet.getRange(`${colName(index + 1)}:${colName(index + 1)}`).format.columnWidth = widths[header] ?? 17;
  });
  sheet.getRange("1:1").format.rowHeight = 34;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(name === "公司批次" ? 3 : 2);
  return sheet;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.collection || !args.crawl || !args.output) throw new Error("Required: --collection --crawl --output");
  const collectionPath = path.resolve(String(args.collection));
  const crawlPath = path.resolve(String(args.crawl));
  const output = path.resolve(String(args.output));
  const assessmentDate = String(args.date || "2026-09-14").slice(0, 10);
  const candidateLimit = Number(args["candidate-limit"] || 0);
  if (!Number.isInteger(candidateLimit) || candidateLimit < 0) {
    throw new Error("--candidate-limit must be a non-negative integer");
  }
  const collection = JSON.parse(await fs.readFile(collectionPath, "utf8"));
  const crawl = JSON.parse(await fs.readFile(crawlPath, "utf8"));
  const headerIndex = Object.fromEntries(collection.headers.map((header, index) => [header, index]));
  const runtimeRequire = createRequire(path.join(path.resolve(String(args["module-root"] || DEFAULT_MODULE_ROOT)), "__codex_soe_loader__.cjs"));
  const { SpreadsheetFile, Workbook } = runtimeRequire("@oai/artifact-tool");

  const assessments = collection.rows.map((row) => {
    const value = (header) => row.values[headerIndex[header]] ?? "";
    const appResults = rowResults(crawl, row.sourceRow, "application");
    const announcementResults = rowResults(crawl, row.sourceRow, "announcement");
    const deadline = parseDeadline(value("投递截止时间"), assessmentDate);
    const emails = extractEmails(value("投递官网链接"));
    const verifiedRoles = VERIFIED_ROLES[row.sourceRow] ?? [];
    const category = chooseCategory({ row, batch: value("类型"), title: value("公告标题"), deadline, appResults, hasEmail: emails.length > 0 });
    const appUrls = appResults.map((item) => item.url);
    const announcementUrls = announcementResults.map((item) => item.url);
    const review = [];
    if (appUrls.length === 0 && emails.length === 0) review.push("无可提取投递入口");
    if (emails.length > 0) review.push("邮箱投递，未执行");
    if (appResults.some((item) => item.accessState === "login_required")) review.push("投递页需登录");
    if (appResults.some((item) => item.accessState === "captcha")) review.push("投递页触发验证码");
    if (announcementResults.some((item) => item.accessState === "captcha")) review.push("公告页触发验证码");
    if (isEmptyPortal(appResults)) review.push("官网显示0个在招职位");
    if (row.sourceRow === 19 || row.sourceRow === 647) review.push("已读岗位要求硕士及以上；候选人当前为本科/本科二学位");
    if (row.sourceRow === 380) review.push("投递表包含父母所在城市、独生子女等敏感问题，必须逐项人工确认");
    if (deadline.label === "可能已截止") review.push("截止时间可能已过");
    const directions = [...new Set(verifiedRoles.map((role) => role[1]))].join("、");
    return {
      sourceRow: row.sourceRow,
      category,
      company: value("公司名称"),
      title: value("公告标题"),
      industry: value("所属行业"),
      batch: value("类型"),
      location: value("地点（可筛选）"),
      deadlineRaw: value("投递截止时间"),
      deadlineState: deadline.label,
      directions: directions || sectorHint(value("所属行业")),
      evidence: verifiedRoles.length > 0 ? `${verifiedRoles.length}个岗位/方向已识别` : "公司级入口，完整JD待读取",
      fit: fitSummary(category, row, verifiedRoles.length, value("地点（可筛选）")),
      action: nextAction(category),
      linkState: `投递:${stateSummary(appResults)}；公告:${stateSummary(announcementResults)}`,
      review: review.join("；") || "无",
      duplicate: "未发现该公司/岗位的成功投递回执",
      application: [...new Set([...appUrls, ...emails])].join("\n"),
      announcement: [...new Set(announcementUrls)].join("\n"),
      roles: verifiedRoles,
      raw: row.values,
    };
  });

  const categories = [
    "1-立即核验/投递", "2-优先可投·已识别方向", "3-可投·先选具体岗位", "4-机会型·条件风险",
    "5-待读取JD/人工复核", "6-实习/专项批次复核", "7-已过期/无在招岗位", "8-默认跳过·硬技术专项",
  ];
  if (candidateLimit) {
    const candidates = assessments
      .filter(isCandidateBatch)
      .map((assessment) => ({ ...assessment, priorityScore: candidatePriority(assessment) }))
      .sort((a, b) => b.priorityScore - a.priorityScore || a.sourceRow - b.sourceRow)
      .slice(0, candidateLimit);
    assessments.splice(0, assessments.length, ...candidates);
  } else {
    assessments.sort((a, b) => categories.indexOf(a.category) - categories.indexOf(b.category) ||
      Number(!a.location.includes("上海")) - Number(!b.location.includes("上海")) || a.sourceRow - b.sourceRow);
  }

  const roleRows = assessments.flatMap((assessment) => assessment.roles.map((role) => [
    assessment.category, assessment.company, role[0], role[1], role[2], role[3], role[4],
    assessment.deadlineRaw, assessment.deadlineState, assessment.application, assessment.sourceRow,
    roleApplicationStatus(assessment, role), roleResumePath(assessment, role),
  ]));

  const workbook = Workbook.create();
  const summary = workbook.worksheets.add("摘要");
  summary.showGridLines = false;
  summary.getRange("A1:H1").merge();
  summary.getRange("A1").values = [[candidateLimit ? `央国企校招候选清单（前${assessments.length}条）` : "央国企校招岗位整理"]];
  summary.getRange("A1").format = { font: { name: "Arial", size: 16, bold: true, color: "#1F1F1F" } };
  summary.getRange("A2:H2").merge();
  const filter = collection.filter ?? { column: "企业类型", values: ["国央企"] };
  summary.getRange("A2").values = [[`评估日期：${assessmentDate}　来源：${collection.sheetName}　筛选：${filter.column}=${filter.values.join("、")}`]];
  summary.getRange("A2").format = { font: { name: "Arial", size: 10, italic: true, color: "#666666" } };
  summary.getRange("A4:C4").values = [["分类", "数量", "处理建议"]];
  const summaryRows = categories.map((category) => [category, assessments.filter((item) => item.category === category).length, nextAction(category)]);
  summary.getRange("A5:C12").values = summaryRows;
  summary.getRange("E4:F4").values = [["链接状态", "数量"]];
  const states = ["ok", "captcha", "login_required", "closed_or_missing", "error"];
  summary.getRange("E5:F9").values = states.map((state) => [state, crawl.results.filter((item) => item.accessState === state).length]);
  summary.getRange("A14:H14").merge();
  const selectionNote = candidateLimit
    ? `从${collection.rows.length}条公司批次中按正式校招、入口状态、岗位方向、上海地点和时效筛选前${assessments.length}条。`
    : `共采集${collection.rows.length}条公司批次、${crawl.results.length}个唯一链接，识别${roleRows.length}个具体岗位或岗位方向。`;
  summary.getRange("A14").values = [[`${selectionNote} 公司级入口不等于完整JD；只有“完整职责与要求/完整职位页”可直接用于资格核验，其余需进入具体职位详情。未填写、未上传、未提交申请。`]];
  summary.getRange("A14").format = { fill: "#FFF2CC", font: { name: "Arial", size: 10, color: "#7F6000" }, wrapText: true, verticalAlignment: "center" };
  for (const range of ["A4:C4", "E4:F4"]) summary.getRange(range).format = { fill: "#274C77", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" } };
  summary.getRange("A5:C12").format = { font: { name: "Arial", size: 10 }, wrapText: true, verticalAlignment: "center" };
  summary.getRange("E5:F9").format = { font: { name: "Arial", size: 10 } };
  summary.getRange("A:A").format.columnWidth = 30;
  summary.getRange("B:B").format.columnWidth = 10;
  summary.getRange("C:C").format.columnWidth = 66;
  summary.getRange("D:D").format.columnWidth = 4;
  summary.getRange("E:E").format.columnWidth = 24;
  summary.getRange("F:F").format.columnWidth = 12;
  summary.getRange("14:14").format.rowHeight = 58;

  const roleHeaders = ["分类", "公司", "具体岗位/方向", "岗位方向", "地点", "证据层级", "职责/要求摘要", "截止时间", "时效", "投递入口", "源表行号", "投递状况", "简历地址"];
  const roleSheet = addTableSheet(workbook, "具体岗位", roleHeaders, roleRows, {
    分类: 27, 公司: 20, "具体岗位/方向": 38, 岗位方向: 22, 地点: 24, 证据层级: 20,
    "职责/要求摘要": 58, 截止时间: 20, 时效: 20, 投递入口: 55, 源表行号: 10, 投递状况: 25, 简历地址: 72,
  }, "VerifiedRolesTable", "TableStyleMedium2");
  if (roleRows.length) roleSheet.getRange(`J2:J${roleRows.length + 1}`).format.font = { name: "Arial", size: 9, color: "#0563C1" };
  if (roleRows.length) roleSheet.getRange(`M2:M${roleRows.length + 1}`).format.font = { name: "Arial", size: 9, color: "#0563C1" };

  const assessmentHeaders = candidateLimit
    ? ["优先级分", "分类", "公司", "公告标题", "行业", "批次", "地点", "截止时间", "时效", "已识别方向/建议筛选", "证据情况", "匹配判断", "下一步", "链接状态", "人工复核项", "去重结果", "投递入口", "公告链接", "源表行号"]
    : ["分类", "公司", "公告标题", "行业", "批次", "地点", "截止时间", "时效", "已识别方向/建议筛选", "证据情况", "匹配判断", "下一步", "链接状态", "人工复核项", "去重结果", "投递入口", "公告链接", "源表行号"];
  const assessmentRows = assessments.map((item) => {
    const base = [item.category, item.company, item.title, item.industry, item.batch, item.location,
      item.deadlineRaw, item.deadlineState, item.directions, item.evidence, item.fit, item.action, item.linkState, item.review,
      item.duplicate, item.application, item.announcement, item.sourceRow];
    return candidateLimit ? [item.priorityScore, ...base] : base;
  });
  const assessmentSheet = addTableSheet(workbook, "公司批次", assessmentHeaders, assessmentRows, {
    优先级分: 12, 分类: 27, 公司: 21, 公告标题: 40, 行业: 18, 批次: 18, 地点: 32, 截止时间: 22, 时效: 20,
    "已识别方向/建议筛选": 48, 证据情况: 28, 匹配判断: 42, 下一步: 50, 链接状态: 28,
    人工复核项: 46, 去重结果: 34, 投递入口: 55, 公告链接: 55, 源表行号: 10,
  }, "CompanyBatchesTable", "TableStyleMedium2");
  const applicationColumn = candidateLimit ? "Q" : "P";
  const announcementColumn = candidateLimit ? "R" : "Q";
  assessmentSheet.getRange(`${applicationColumn}2:${announcementColumn}${assessmentRows.length + 1}`).format.font = { name: "Arial", size: 9, color: "#0563C1" };

  const linkHeaders = ["源表行号", "公司", "链接类型", "访问状态", "HTTP状态", "页面标题", "原始链接", "最终链接", "备注"];
  const linkRows = crawl.results.flatMap((item) => item.references.map((reference) => [reference.sourceRow, reference.company,
    reference.kind === "application" ? "投递" : "公告", item.accessState, item.status ?? "", item.title ?? "", item.url,
    item.finalUrl ?? "", item.error ? String(item.error).split("\n")[0] : ""])).sort((a, b) => a[0] - b[0]);
  const linkSheet = addTableSheet(workbook, "链接检查", linkHeaders, linkRows, {
    源表行号: 10, 公司: 20, 链接类型: 10, 访问状态: 18, HTTP状态: 12, 页面标题: 40,
    原始链接: 58, 最终链接: 58, 备注: 46,
  }, "LinkChecksTable", "TableStyleMedium4");
  linkSheet.getRange(`G2:H${linkRows.length + 1}`).format.font = { name: "Arial", size: 9, color: "#0563C1" };

  const rawHeaders = ["源表行号", ...collection.headers, "公告链接（提取）", "投递链接（提取）"];
  const rawSourceRows = candidateLimit
    ? assessments.map((assessment) => ({ sourceRow: assessment.sourceRow, values: assessment.raw }))
    : collection.rows;
  const rawRows = rawSourceRows.map((row) => [row.sourceRow, ...row.values,
    extractUrls(row.values[headerIndex["公告链接"]]).join("\n"), extractUrls(row.values[headerIndex["投递官网链接"]]).join("\n")]);
  const rawWidths = Object.fromEntries(rawHeaders.map((header) => [header, 18]));
  Object.assign(rawWidths, { 公司名称: 20, 公告标题: 42, "地点（可筛选）": 32, 公告链接: 48, 投递官网链接: 52, "公告链接（提取）": 52, "投递链接（提取）": 52 });
  const rawSheet = addTableSheet(workbook, "采集原表", rawHeaders, rawRows, rawWidths, "CollectedSourceTable", "TableStyleMedium9");
  const rawLast = colName(rawHeaders.length);
  rawSheet.getRange(`${colName(rawHeaders.length - 1)}2:${rawLast}${rawRows.length + 1}`).format.font = { name: "Arial", size: 9, color: "#0563C1" };

  workbook.recalculate();
  const inspect = await workbook.inspect({ kind: "table", range: `具体岗位!A1:M${Math.min(roleRows.length + 1, 18)}`, include: "values,formulas", tableMaxRows: 18, tableMaxCols: 13 });
  const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan" });
  await fs.mkdir(path.dirname(output), { recursive: true });
  const previews = [
    ["摘要", "A1:H14", ".summary.preview.png"],
    ["具体岗位", `A1:M${Math.min(roleRows.length + 1, 18)}`, ".roles.preview.png"],
    ["公司批次", "A1:N16", ".companies.preview.png"],
    ["链接检查", "A1:I14", ".links.preview.png"],
    ["采集原表", `A1:${rawLast}14`, ".source.preview.png"],
  ];
  const previewPaths = [];
  for (const [sheetName, range, suffix] of previews) {
    const blob = await workbook.render({ sheetName, range, scale: 1, format: "png" });
    const previewPath = output.replace(/\.xlsx$/iu, suffix);
    await fs.writeFile(previewPath, new Uint8Array(await blob.arrayBuffer()));
    previewPaths.push(previewPath);
  }
  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(output);
  const detailPath = output.replace(/\.xlsx$/iu, ".json");
  await fs.writeFile(detailPath, JSON.stringify({ assessmentDate, assessments, verifiedRoleRows: roleRows }, null, 2), "utf8");
  process.stdout.write(`${JSON.stringify({ output, previewPaths, detailPath, sourceRows: assessments.length,
    uniqueLinks: crawl.results.length, verifiedRoles: roleRows.length,
    categories: Object.fromEntries(categories.map((category) => [category, assessments.filter((item) => item.category === category).length])),
    inspect: inspect.ndjson, formulaErrors: errors.ndjson }, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message || String(error)}\n`);
  process.exitCode = 1;
});
