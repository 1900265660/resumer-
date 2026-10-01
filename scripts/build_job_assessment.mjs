#!/usr/bin/env node

/**
 * Build a categorized, evidence-labelled job assessment workbook from the
 * Feishu collection JSON and the URL crawl JSON.
 *
 * This is intentionally conservative: reachable company/program pages are
 * not treated as a fully verified JD unless an exact role was visible in the
 * captured page text. No application state is mutated by this script.
 */

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import {
  MATERIAL_STATUSES,
  WORKFLOW_HEADERS,
  mergeConcretePositions,
} from "./update_job_resume_workbook.mjs";

const DEFAULT_MODULE_ROOT =
  "C:\\Users\\Administrator\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules";

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith("--")) throw new Error(`Unexpected argument: ${key}`);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) args[key.slice(2)] = true;
    else {
      args[key.slice(2)] = next;
      index += 1;
    }
  }
  return args;
}

function excelColumnName(columnNumber) {
  let value = columnNumber;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function rowObject(headers, row) {
  return Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ""]));
}

async function previousResumeProgress(FileBlob, SpreadsheetFile, outputPath) {
  try {
    await fs.access(outputPath);
  } catch {
    return { genericBySource: new Map(), concretePositions: [] };
  }
  const previous = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
  const sheet = previous.worksheets.items.find((item) => item.name === "岗位评估");
  if (!sheet) return { genericBySource: new Map(), concretePositions: [] };
  const matrix = sheet.getUsedRange(true)?.values ?? [];
  if (matrix.length < 2) return { genericBySource: new Map(), concretePositions: [] };
  const headers = matrix[0].map((value) => String(value ?? "").trim());
  const genericBySource = new Map();
  const concretePositions = [];
  for (const row of matrix.slice(1)) {
    const value = rowObject(headers, row);
    const sourceRow = Number(value["源表行号"]);
    if (!Number.isFinite(sourceRow)) continue;
    if (!String(value["具体岗位"] ?? "").trim()) {
      genericBySource.set(sourceRow, value);
      continue;
    }
    concretePositions.push({
      source_row: sourceRow,
      company: value["公司"],
      concrete_job: value["具体岗位"],
      jd_url: value["具体JD地址"],
      application_url: value["具体投递地址"],
      resume_strategy: value["简历策略"],
      baseline_id: value["基线简历ID"],
      hr_result: value["HR复核结果"],
      resume_path: value["简历文件地址"],
      attachments: value["配套附件地址"],
      material_status: value["材料状态"],
      notes: value["处理说明"],
      application_status: value["投递状态"],
    });
  }
  return { genericBySource, concretePositions };
}

function cleanUrlCandidate(raw) {
  return String(raw ?? "").replace(/[，。；;、）》】\]}>'"\s]+$/gu, "").trim();
}

function normalizeUrl(raw) {
  let value = cleanUrlCandidate(raw);
  if (!value) return "";
  if (/^www\./iu.test(value) || /^[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)+(?:\/[^\s]*)?$/iu.test(value)) {
    value = `https://${value}`;
  }
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

const ROLE_OVERRIDES = {
  13: ["产品/运营/内容/社区方向（官网需选岗）", "招聘项目已确认"],
  20: ["游戏策划、运营、市场/职能（官网需选岗）", "2027秋招流程已确认"],
  25: ["研究/算法/工程岗位为主", "招聘项目已确认"],
  135: ["产品、运营方向（校招站需筛选）", "招聘项目已确认"],
  191: ["音乐内容、产品、运营方向（网易校招站需筛选）", "仅项目入口"],
  207: ["软件开发、应用科学等硬技术岗位", "具体岗位已识别"],
  208: ["岗位未可靠识别", "官网标题仍为2022校招"],
  214: ["运营管培生、产品经理", "具体岗位已识别"],
  223: ["产品经理、平台产品经理、增长产品运营、海外运营", "具体岗位已识别"],
  232: ["产品、运营、市场/职能（网易校招站需筛选）", "仅项目入口"],
  242: ["产品、运营、市场/职能（网易互联网需筛选）", "招聘项目已确认"],
  252: ["新浪集团管培生", "具体项目已识别"],
  253: ["卡牌游戏策划/系统玩法等游戏岗位", "已有具体岗位分析"],
  258: ["Sea全球管培生（GMAP）", "具体项目已识别"],
  259: ["微博明星运营、微博剧综运营", "具体岗位已识别"],
  265: ["食杂零售管培生、市场营销、产品/运营支持", "具体岗位/方向已识别"],
  266: ["网易星火计划HR培训生", "具体项目已识别"],
  269: ["京东新锐之星/人力资源等方向", "项目方向已识别"],
  280: ["系统策划、战斗策划、数值策划", "具体岗位已识别"],
  303: ["游戏策划、运营、市场/职能（需选岗）", "招聘项目已确认"],
  310: ["游戏策划、运营、发行/市场（需选岗）", "招聘项目已确认"],
  321: ["产品、运营、市场、项目/职能（需选岗）", "招聘项目已确认"],
  322: ["项目管理类、市场类、产品/运营方向", "岗位大类已识别"],
  323: ["全球管理培训生（GMT）", "具体项目已识别"],
  325: ["游戏策划、游戏运营、平台业务/职能", "岗位大类已识别"],
  337: ["AI产品经理/培训生、游戏策划培训生、市场", "具体岗位已识别"],
  341: ["游戏系统/商业化/文案/数值策划", "具体岗位已识别"],
  342: ["产品、运营、市场/职能（蚂蚁校招站需筛选）", "招聘项目已确认"],
  343: ["产品经理、企业AI产品经理、AI产品经理（直播产品）", "具体岗位已识别"],
  345: ["产品、运营、市场/职能（小米校招站需筛选）", "招聘项目已确认"],
  346: ["策划、产品、运营、营销、项目管理", "岗位方向已识别"],
  347: ["文娱产品、运营、内容/市场方向（需选岗）", "招聘项目已确认"],
  350: ["游戏策划、运营、职能", "岗位大类已识别"],
  351: ["招聘专员（可转正实习）、游戏系统策划", "具体岗位已识别"],
  361: ["千问办公产品、运营方向（业务筛选需复核）", "招聘项目已确认"],
  364: ["飞猪产品、运营、市场方向（缺投递入口）", "仅公告"],
  365: ["阿里健康产品、运营、市场/职能（需选岗）", "招聘项目已确认"],
  367: ["旅行产品、运营、市场/职能（需选岗）", "招聘项目已确认"],
  369: ["产品运营、新媒体运营、用户运营", "具体岗位已识别"],
  373: ["产研岗位为主；非技术岗位未确认", "仅公告"],
  375: ["产品、运营方向未确认；缺投递入口", "仅公告"],
  376: ["游戏岗位未可靠识别", "投递链接页面不存在"],
  380: ["用户运营、AI产品运营", "具体岗位已识别"],
  381: ["阿里云管培生（商业技术方向）", "具体项目已识别"],
  386: ["项目管理、产品运营、市场营销/游戏品牌营销", "具体岗位/方向已识别"],
  389: ["岗位未识别；公告抓取超时且无投递链接", "链接证据不足"],
  396: ["游戏策划、产品/运营方向（需选岗）", "招聘项目已确认"],
  397: ["网易雷火游戏策划方向（需选岗）", "招聘项目已确认"],
  398: ["AI产品经理、大模型数据运营、Agent数据运营", "具体岗位已识别"],
  399: ["用户/内容/品牌运营、市场、项目方向", "具体岗位/方向已识别"],
  423: ["游戏策划、运营、市场", "岗位大类已识别"],
  426: ["百度移动生态P-STAR产品培训生", "具体项目已识别，页面需人工打开"],
  428: ["腾讯PCG青云计划（顶尖技术专项）", "具体项目已识别"],
  429: ["腾讯WXG青云计划（顶尖技术专项）", "具体项目已识别"],
  438: ["项目管理、游戏编剧、国内版本/产品运营", "已有具体岗位分析"],
  440: ["游戏策划、游戏运营、平台业务/职能", "官网岗位大类已识别；公告错链到远景"],
  446: ["滴滴未来精英（顶尖技术专项）", "仅公告，缺投递入口"],
  460: ["产品类、市场&职能、游戏策划/项目管理", "岗位大类已识别"],
  478: ["货拉拉全球拓展管培生（GMT）", "具体项目已识别，缺投递入口"],
  495: ["产品、运营、市场/职能（百度校招站需筛选）", "招聘项目已确认"],
  523: ["HR精英实习生：游戏校招、雇主品牌等方向", "具体项目/方向已识别"],
  535: ["游戏策划、产品、市场/职能（需选岗）", "招聘项目已确认"],
  536: ["京东TET管理培训生", "具体项目已识别"],
  543: ["飞猪产品、运营、市场方向（需选岗）", "招聘项目已确认；公告触发验证码"],
  608: ["百度IDG/Apollo顶尖技术人才计划", "具体项目已识别"],
  629: ["美团业务研发平台北斗计划（技术专项）", "具体项目已识别"],
  683: ["游戏发行、运营方向（需选岗）", "招聘项目已确认"],
};

const PRIORITY_ROWS = new Set([13, 214, 223, 252, 253, 259, 280, 322, 337, 341, 343, 346, 351, 369, 380, 381, 386, 398, 399, 426, 438, 460, 523, 543]);
const OPPORTUNITY_ROWS = new Set([258, 269, 303, 310, 323, 325, 347, 350, 367, 396, 397, 423, 440, 478, 535, 536, 683]);
const TECH_ONLY_ROWS = new Set([25, 207, 428, 429, 446, 608, 629]);
const MANUAL_ROWS = new Set([208, 266, 364, 373, 375, 376, 389]);
const EXISTING_ROWS = {
  223: "已有回响科技多岗位分析（产品/运营等）；无成功回执，投前按规范化URL去重",
  253: "已有完美世界卡牌游戏策划分析；无成功回执",
  396: "已有盛趣AI游戏制作实践项目分析；它不是岗位投递回执",
  438: "已有鹰角项目管理、游戏编剧等分析；无成功回执",
};

function roleDirection(role, industry) {
  const tags = [];
  const rules = [
    ["AI产品", /AI产品|大模型|Agent数据/u],
    ["产品/产品运营", /产品经理|产品运营|产品方向|产品类/u],
    ["游戏策划", /游戏策划|系统策划|战斗策划|数值策划|文案策划/u],
    ["内容/社区运营", /内容|社区|用户运营|新媒体|明星运营|剧综运营/u],
    ["项目管理", /项目管理/u],
    ["人力资源/招聘", /人力资源|招聘专员|HR/u],
    ["市场/品牌", /市场|营销|品牌/u],
    ["管培/综合", /管培|培训生|GMT|GMAP|新锐之星/u],
    ["运营", /运营/u],
  ];
  for (const [label, pattern] of rules) if (pattern.test(role)) tags.push(label);
  if (tags.length === 0) tags.push(String(industry).includes("游戏") ? "游戏综合" : "互联网综合");
  return [...new Set(tags)].slice(0, 5).join("、");
}

function deadlineState(value, now) {
  const text = String(value ?? "").trim();
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/u.exec(text);
  if (iso) {
    const due = Date.UTC(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
    const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
    const days = Math.round((due - today) / 86_400_000);
    if (days < 0) return { label: "已过期", days };
    if (days <= 7) return { label: `仅剩${days}天`, days };
    return { label: `剩余${days}天`, days };
  }
  if (/26年[1-8]月/u.test(text)) return { label: "已过期", days: -1 };
  if (/9月上旬/u.test(text)) return { label: "截止待核验（可能已过）", days: null };
  return { label: text || "未明确", days: null };
}

function chooseCategory({ sourceRow, batch, deadline, appStates, appUrls, location }) {
  const allAppsClosed = appUrls.length > 0 && appStates.length > 0 && appStates.every((state) => state === "closed_or_missing");
  if (deadline.label === "已过期" || allAppsClosed) return "7-已过期/失效";
  if (String(batch).includes("暑期实习")) return "6-暑期实习·时效复核";
  if (TECH_ONLY_ROWS.has(sourceRow)) return "8-默认跳过·硬技术专项";
  if (MANUAL_ROWS.has(sourceRow) || appUrls.length === 0) return "5-需人工复核";
  if (deadline.days !== null && deadline.days <= 7) return "1-立即投递";
  if (PRIORITY_ROWS.has(sourceRow)) return "2-优先可投";
  if (OPPORTUNITY_ROWS.has(sourceRow) || !String(location).includes("上海")) return "4-机会型·跨城/专项";
  return "3-可投·先选具体岗位";
}

function actionFor(category) {
  return {
    "1-立即投递": "今天先选1–2个匹配岗位，核验JD后定制简历",
    "2-优先可投": "优先进入官网选岗；核验完整JD后加入候选清单",
    "3-可投·先选具体岗位": "官网可达，但需筛出非硬技术具体岗位",
    "4-机会型·跨城/专项": "接受城市/项目条件时再投，优先级低于上海岗位",
    "5-需人工复核": "入口缺失、错链或截止不明；人工打开后再决定",
    "6-暑期实习·时效复核": "多为较早批次；先确认仍开放及是否接受当前时间投递",
    "7-已过期/失效": "不投当前链接；仅在官网发现新岗位时重新评估",
    "8-默认跳过·硬技术专项": "与当前非硬工程偏好不符，除非发现产品/运营独立岗位",
  }[category];
}

function fitReason(category, direction, location) {
  if (category === "8-默认跳过·硬技术专项") return "当前事实库不支持算法/研发类硬技术岗位";
  if (category === "7-已过期/失效") return "当前链接或明确截止时间失效";
  if (category === "6-暑期实习·时效复核") return "方向可能匹配，但批次时效风险高";
  if (category === "5-需人工复核") return "证据不足，不能据此确认可投";
  const city = String(location).includes("上海") ? "含上海" : "需跨城";
  return `${direction}与候选人产品/运营/项目/内容/游戏方向相邻；${city}`;
}

function rowUrls(crawlResults, sourceRow, kind) {
  return crawlResults
    .filter((item) => item.references?.some((reference) => reference.sourceRow === sourceRow && reference.kind === kind))
    .map((item) => item.url);
}

function statesFor(crawlByUrl, urls) {
  return urls.map((url) => crawlByUrl.get(url)?.accessState ?? "not_crawled");
}

function addTableSheet(workbook, name, headers, rows, widths, style = "TableStyleMedium2") {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const lastColumn = excelColumnName(headers.length);
  sheet.getRange(`A1:${lastColumn}1`).values = [headers];
  sheet.getRange(`A1:${lastColumn}1`).format = {
    fill: "#1F4E78",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
  };
  if (rows.length > 0) {
    sheet.getRange(`A2:${lastColumn}${rows.length + 1}`).values = rows;
    const body = sheet.getRange(`A2:${lastColumn}${rows.length + 1}`);
    body.format.font = { name: "Arial", size: 9, color: "#1F1F1F" };
    body.format.verticalAlignment = "center";
    body.format.wrapText = true;
    body.format.rowHeight = name === "链接检查" ? 30 : 38;
    const table = sheet.tables.add(`A1:${lastColumn}${rows.length + 1}`, true, `${name.replace(/[^\p{L}\p{N}]/gu, "")}Table`);
    table.style = style;
    table.showFilterButton = true;
  }
  headers.forEach((header, index) => {
    sheet.getRange(`${excelColumnName(index + 1)}:${excelColumnName(index + 1)}`).format.columnWidth = widths[header] ?? 16;
  });
  sheet.getRange("1:1").format.rowHeight = 34;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(name === "岗位评估" ? 3 : 2);
  return sheet;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.collection || !args.crawl || !args.output) {
    throw new Error("Required: --collection <json> --crawl <json> --output <xlsx>");
  }
  const moduleRoot = path.resolve(String(args["module-root"] || DEFAULT_MODULE_ROOT));
  const requireFromRuntime = createRequire(path.join(moduleRoot, "__codex_assessment_loader__.cjs"));
  const { FileBlob, SpreadsheetFile, Workbook } = requireFromRuntime("@oai/artifact-tool");
  const output = path.resolve(String(args.output));
  const previousProgress = await previousResumeProgress(FileBlob, SpreadsheetFile, output);
  const collection = JSON.parse(await fs.readFile(path.resolve(String(args.collection)), "utf8"));
  const crawl = JSON.parse(await fs.readFile(path.resolve(String(args.crawl)), "utf8"));
  const crawlByUrl = new Map(crawl.results.map((item) => [item.url, item]));
  const assessmentDate = String(args.date || "2026-09-10").slice(0, 10);
  const now = new Date(`${assessmentDate}T12:00:00`);
  const headerIndex = Object.fromEntries(collection.headers.map((header, index) => [header, index]));

  const assessments = collection.rows.map((row) => {
    const value = (header) => row.values[headerIndex[header]] ?? "";
    const appUrls = rowUrls(crawl.results, row.sourceRow, "application");
    const announcementUrls = rowUrls(crawl.results, row.sourceRow, "announcement");
    const appStates = statesFor(crawlByUrl, appUrls);
    const announcementStates = statesFor(crawlByUrl, announcementUrls);
    const deadline = deadlineState(value("投递截止时间"), now);
    const [role, evidence] = ROLE_OVERRIDES[row.sourceRow] ?? [
      String(value("所属行业")).includes("游戏")
        ? "游戏策划、运营、市场/职能（官网需选岗）"
        : "产品、运营、市场、项目/职能（官网需选岗）",
      "仅招聘项目/入口",
    ];
    const direction = roleDirection(role, value("所属行业"));
    const category = chooseCategory({
      sourceRow: row.sourceRow,
      batch: value("类型"),
      deadline,
      appStates,
      appUrls,
      location: value("地点（可筛选）"),
    });
    const linkState = [
      `投递:${appUrls.length ? [...new Set(appStates)].join("/") : "缺失"}`,
      `公告:${announcementUrls.length ? [...new Set(announcementStates)].join("/") : "缺失"}`,
    ].join("；");
    const reviewNotes = [];
    if (appUrls.length === 0) reviewNotes.push("无可提取投递链接");
    if (appStates.includes("closed_or_missing")) reviewNotes.push("投递页已下线/不存在");
    if (announcementStates.includes("captcha")) reviewNotes.push("公告页触发验证码");
    if (announcementStates.includes("error")) reviewNotes.push("公告页抓取超时");
    if (row.sourceRow === 208) reviewNotes.push("官网标题为“2022校园招聘”");
    if (row.sourceRow === 440) reviewNotes.push("一个公告链接错跳到远景；正确畅游官网可达");
    if (deadline.label.includes("待核验")) reviewNotes.push(deadline.label);
    return {
      sourceRow: row.sourceRow,
      category,
      direction,
      company: value("公司名称"),
      title: value("公告标题"),
      batch: value("类型"),
      location: value("地点（可筛选）"),
      deadlineRaw: value("投递截止时间"),
      deadlineState: deadline.label,
      role,
      evidence,
      fit: fitReason(category, direction, value("地点（可筛选）")),
      action: actionFor(category),
      linkState,
      review: reviewNotes.join("；") || "无",
      existing: EXISTING_ROWS[row.sourceRow] ?? "无",
      appUrls,
      announcementUrls,
      raw: row.values,
    };
  });

  const categoryOrder = ["1-立即投递", "2-优先可投", "3-可投·先选具体岗位", "4-机会型·跨城/专项", "5-需人工复核", "6-暑期实习·时效复核", "7-已过期/失效", "8-默认跳过·硬技术专项"];
  assessments.sort((left, right) => {
    const categoryDiff = categoryOrder.indexOf(left.category) - categoryOrder.indexOf(right.category);
    if (categoryDiff) return categoryDiff;
    const cityDiff = Number(!left.location.includes("上海")) - Number(!right.location.includes("上海"));
    return cityDiff || left.sourceRow - right.sourceRow;
  });

  const workbook = Workbook.create();
  const summary = workbook.worksheets.add("摘要");
  summary.showGridLines = false;
  summary.getRange("A1:H1").merge();
  summary.getRange("A1").values = [["互联网 / 游戏校招采集与可投性整理"]];
  summary.getRange("A1").format = { font: { name: "Arial", size: 16, bold: true, color: "#1F1F1F" }, verticalAlignment: "center" };
  summary.getRange("A2:H2").merge();
  summary.getRange("A2").values = [[`评估日期：${assessmentDate}｜来源表：${collection.sheetName}｜筛选：${collection.industries.join("、")}`]];
  summary.getRange("A4:C4").values = [["分类", "数量", "建议"]];
  const summaryRows = categoryOrder.map((category) => [category, assessments.filter((item) => item.category === category).length, actionFor(category)]);
  summary.getRange(`A5:C${4 + summaryRows.length}`).values = summaryRows;
  summary.getRange("E4:F4").values = [["链接采集", "数量"]];
  const crawlCounts = ["ok", "login_required", "captcha", "closed_or_missing", "error"].map((state) => [state, crawl.results.filter((item) => item.accessState === state).length]);
  summary.getRange(`E5:F${4 + crawlCounts.length}`).values = crawlCounts;
  summary.getRange("A14:H14").merge();
  summary.getRange("A14").values = [["口径：公司招聘项目会逐步展开为可验证的具体正式校招岗位。同公司不同岗位独立统计；暑期/日常实习、过期岗位、纯硬技术岗位和已有成功回执的同一岗位不进入材料生成。材料“可投递”不等于已批准上传或提交。"]];
  summary.getRange("A14").format = { fill: "#FFF2CC", font: { name: "Arial", size: 10, color: "#7F6000" }, wrapText: true, verticalAlignment: "center" };
  summary.getRange("A4:C4").format = { fill: "#1F4E78", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" } };
  summary.getRange("E4:F4").format = { fill: "#1F4E78", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" } };
  summary.getRange("A5:C12").format = { font: { name: "Arial", size: 10 }, wrapText: true, verticalAlignment: "center" };
  summary.getRange("E5:F9").format = { font: { name: "Arial", size: 10 } };
  summary.getRange("A:A").format.columnWidth = 28;
  summary.getRange("B:B").format.columnWidth = 10;
  summary.getRange("C:C").format.columnWidth = 62;
  summary.getRange("D:D").format.columnWidth = 4;
  summary.getRange("E:E").format.columnWidth = 24;
  summary.getRange("F:F").format.columnWidth = 12;
  summary.getRange("14:14").format.rowHeight = 56;
  summary.freezePanes.freezeRows(2);

  const baseAssessmentHeaders = ["分类", "岗位方向", "公司", "公告标题", "批次", "地点", "截止时间", "时效", "可关注岗位/方向", "证据强度", "匹配判断", "下一步", "链接状态", "人工复核项", "已有记录/去重", "投递链接", "公告链接", "源表行号", "投递状态", ...WORKFLOW_HEADERS];
  const baseAssessmentRows = assessments.map((item) => {
    const previous = previousProgress.genericBySource.get(item.sourceRow) ?? {};
    return [
      item.category, item.direction, item.company, item.title, item.batch, item.location,
      item.deadlineRaw, item.deadlineState, item.role, item.evidence, item.fit, item.action,
      item.linkState, item.review, item.existing, item.appUrls.join("\n"), item.announcementUrls.join("\n"), item.sourceRow,
      previous["投递状态"] ?? "",
      ...WORKFLOW_HEADERS.map((header) => previous[header] ?? ""),
    ];
  });
  const mergedAssessment = mergeConcretePositions(
    baseAssessmentHeaders,
    baseAssessmentRows,
    previousProgress.concretePositions,
  );
  const assessmentHeaders = mergedAssessment.headers;
  const assessmentRows = mergedAssessment.rows;
  const categoryIndex = assessmentHeaders.indexOf("分类");
  const concreteSummaryRows = categoryOrder.map((category) => [
    category,
    assessmentRows.filter((row) => row[categoryIndex] === category).length,
    actionFor(category),
  ]);
  summary.getRange(`A5:C${4 + concreteSummaryRows.length}`).values = concreteSummaryRows;
  const assessmentSheet = addTableSheet(workbook, "岗位评估", assessmentHeaders, assessmentRows, {
    分类: 25, 岗位方向: 26, 公司: 18, 公告标题: 38, 批次: 18, 地点: 28, 截止时间: 17, 时效: 18,
    "可关注岗位/方向": 46, 证据强度: 24, 匹配判断: 40, 下一步: 44, 链接状态: 28,
    人工复核项: 38, "已有记录/去重": 46, 投递链接: 52, 公告链接: 52, 源表行号: 10, 投递状态: 14,
    具体岗位: 34, 具体JD地址: 52, 具体投递地址: 52, 简历策略: 14, 基线简历ID: 24,
    HR复核结果: 24, 简历文件地址: 58, 配套附件地址: 52, 材料状态: 18, 处理说明: 48,
  });
  assessmentSheet.getRange(`P2:Q${assessmentRows.length + 1}`).format.font = { name: "Arial", size: 9, color: "#0563C1" };
  assessmentSheet.getRange(`U2:V${assessmentRows.length + 1}`).format.font = { name: "Arial", size: 9, color: "#0563C1" };
  assessmentSheet.getRange(`Z2:AA${assessmentRows.length + 1}`).format.font = { name: "Arial", size: 9, color: "#0563C1" };
  const materialStatusColumn = excelColumnName(assessmentHeaders.indexOf("材料状态") + 1);
  assessmentSheet.getRange(`${materialStatusColumn}2:${materialStatusColumn}${assessmentRows.length + 1}`).dataValidation.clear();
  assessmentSheet.dataValidations.add({
    range: `${materialStatusColumn}2:${materialStatusColumn}${assessmentRows.length + 1}`,
    rule: { type: "list", values: MATERIAL_STATUSES },
  });

  const linkHeaders = ["源表行号", "公司", "链接类型", "访问状态", "HTTP状态", "页面标题", "原始链接", "最终链接", "备注"];
  const linkRows = crawl.results.flatMap((item) => item.references.map((reference) => [
    reference.sourceRow,
    reference.company,
    reference.kind === "application" ? "投递" : "公告",
    item.accessState,
    item.status ?? "",
    item.title ?? "",
    item.url,
    item.finalUrl ?? "",
    item.error ? String(item.error).split("\n")[0] : "",
  ])).sort((left, right) => left[0] - right[0] || String(left[2]).localeCompare(String(right[2])));
  const linkSheet = addTableSheet(workbook, "链接检查", linkHeaders, linkRows, {
    源表行号: 10, 公司: 18, 链接类型: 10, 访问状态: 18, HTTP状态: 12, 页面标题: 38,
    原始链接: 56, 最终链接: 56, 备注: 44,
  }, "TableStyleMedium4");
  linkSheet.getRange(`G2:H${linkRows.length + 1}`).format.font = { name: "Arial", size: 9, color: "#0563C1" };

  const rawHeaders = ["源表行号", ...collection.headers, "公告链接（提取）", "投递链接（提取）"];
  const rawRows = collection.rows.map((row) => [
    row.sourceRow,
    ...row.values,
    extractUrls(row.values[headerIndex["公告链接"]]).join("\n"),
    extractUrls(row.values[headerIndex["投递官网链接"]]).join("\n"),
  ]);
  const rawWidths = Object.fromEntries(rawHeaders.map((header) => [header, 18]));
  Object.assign(rawWidths, { 公司名称: 18, 公告标题: 40, "地点（可筛选）": 28, 公告链接: 44, 投递官网链接: 48, "公告链接（提取）": 48, "投递链接（提取）": 52 });
  const rawSheet = addTableSheet(workbook, "采集原表", rawHeaders, rawRows, rawWidths, "TableStyleMedium9");
  const rawLast = excelColumnName(rawHeaders.length);
  rawSheet.getRange(`${excelColumnName(rawHeaders.length - 1)}2:${rawLast}${rawRows.length + 1}`).format.font = { name: "Arial", size: 9, color: "#0563C1" };

  workbook.recalculate();
  const inspect = await workbook.inspect({
    kind: "table",
    range: `岗位评估!A1:AC${Math.min(assessmentRows.length + 1, 15)}`,
    include: "values,formulas",
    tableMaxRows: 15,
    tableMaxCols: 29,
  });
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 100 },
    summary: "final formula error scan",
  });

  await fs.mkdir(path.dirname(output), { recursive: true });
  const previewSpecs = [
    ["摘要", "A1:H14", ".summary.preview.png"],
    ["岗位评估", "A1:AC16", ".assessment.preview.png"],
    ["链接检查", "A1:I14", ".links.preview.png"],
    ["采集原表", `A1:${rawLast}14`, ".source.preview.png"],
  ];
  const previewPaths = [];
  for (const [sheetName, range, suffix] of previewSpecs) {
    const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
    const previewPath = output.replace(/\.xlsx$/iu, suffix);
    await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
    previewPaths.push(previewPath);
  }
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(output);
  const detailPath = output.replace(/\.xlsx$/iu, ".json");
  await fs.writeFile(detailPath, JSON.stringify({ generatedAt: new Date().toISOString(), assessments }, null, 2), "utf8");

  process.stdout.write(`${JSON.stringify({
    output,
    previewPaths,
    detailPath,
    rowCount: assessmentRows.length,
    linkCount: crawl.results.length,
    categories: Object.fromEntries(categoryOrder.map((category) => [category, assessments.filter((item) => item.category === category).length])),
    inspect: inspect.ndjson,
    formulaErrors: errors.ndjson,
  }, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message || String(error)}\n`);
  process.exitCode = 1;
});
