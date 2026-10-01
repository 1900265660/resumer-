#!/usr/bin/env node

/** Build a readable workbook from the first 100 SOE candidates and the current official-detail crawl. */
import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = path.resolve("outputs/soe-update-2026-09-28");
const candidatePath = path.join(outputDir, "央国企可投候选_前100条_2026-09-28.json");
const mapPath = path.join(outputDir, "央国企候选_官方JD详情映射_2026-09-28.json");
const crawlPath = path.join(outputDir, "央国企候选_官方JD详情抓取_2026-09-28.json");
const outputPath = path.join(outputDir, "央国企候选_JD学历核验筛选_2026-09-28.xlsx");
const jsonPath = path.join(outputDir, "央国企候选_JD学历核验筛选_2026-09-28.json");
const FONT = "Microsoft YaHei";

const candidates = JSON.parse(await fs.readFile(candidatePath, "utf8")).assessments;
const detailMap = JSON.parse(await fs.readFile(mapPath, "utf8"));
const crawled = JSON.parse(await fs.readFile(crawlPath, "utf8")).results;

function squash(value) { return String(value ?? "").replace(/\s+/gu, " ").trim(); }
function section(text, begin, end) {
  const match = text.match(new RegExp(`${begin}\\s*([\\s\\S]{0,1200}?)\\s*${end}`, "u"));
  return squash(match?.[1] ?? "");
}
function detailRow(job, crawl, index) {
  const text = squash(crawl.bodyText);
  const degree = text.match(/学历要求：\s*(大学本科|本科|硕士研究生|硕士|研究生)/u)?.[1]
    ?? text.match(/学历\s*(大学本科|本科|硕士研究生|硕士|研究生)/u)?.[1] ?? "未读取";
  const deadline = text.match(/截止时间：\s*(\d{4}-\d{2}-\d{2})/u)?.[1] ?? "未读取";
  const description = section(text, "岗位描述", "任职条件");
  const requirements = section(text, "任职条件", "(?:公司简介|本公司招聘其他岗位)");
  let result = "待详情核验";
  let note = "详情页未返回可判断的职责与学历字段。";
  if ([0, 1, 2, 3, 4, 5].includes(index)) {
    const closerDirection = index === 2 || index === 5;
    result = closerDirection ? "保留：机会型（优先）" : "保留：机会型";
    note = closerDirection
      ? "正式校招、最低本科；职责与研究/运营经历相对接近，但职位明确要求金融/经济等相关专业。候选人专业不直接对应，仅在接受专业风险时优先尝试。"
      : "正式校招、最低本科；职位明确要求金融/经济等相关专业。候选人专业不直接对应，保留为可尝试岗位，不作为优先投递。";
  } else if ([6, 7].includes(index)) {
    result = "排除";
    note = "官方职位列表显示校招硕士要求，低于用户的学历门槛。";
  } else if (index === 8) {
    result = "排除";
    note = "职位标注社招、5-10 年经验，且为高级产品经理。";
  } else if ([16, 17, 18].includes(index)) {
    result = "排除";
    note = "虽为本科校招，但职责与专业均以 AI/IT 开发、系统维护或技术研发为核心，属于默认排除的纯硬技术岗。";
  } else if ([19, 20, 21].includes(index)) {
    result = "排除";
    note = "最低学历为硕士研究生，且职位以技术交付为核心。";
  }
  return {
    "筛选结论": result, "公司": job.company, "具体岗位": job.title, "校招状态": /校园招聘/u.test(text) ? "校园招聘" : "未从正文确认",
    "学历要求": degree, "截止时间": deadline, "岗位职责": description || "未读取", "任职要求": requirements || "未读取",
    "官方 JD": job.url, "核验说明": note,
  };
}

const detailed = detailMap.map((job, index) => detailRow(job, crawled[index] ?? {}, index));
const directUrls = new Set(detailMap.map((job) => job.url));
const retained = detailed.filter((row) => row["筛选结论"].startsWith("保留：机会型"));
const excluded = detailed.filter((row) => row["筛选结论"] === "排除");
const pendingDetail = detailed.filter((row) => row["筛选结论"] === "待详情核验");
const pendingPortal = candidates
  .filter((candidate) => !detailMap.some((job) => job.sourceRow === candidate.sourceRow))
  .map((candidate) => ({
    "筛选结论": "待展开具体 JD", "公司": candidate.company, "公告标题": candidate.title,
    "地点": candidate.location, "截止时间": candidate.deadlineRaw, "候选优先级": candidate.priorityScore,
    "当前入口": candidate.application, "说明": "当前可读页面仅到公司/项目入口，尚未取得具体岗位的职责和学历要求，不能按标题认定为可投。",
  }));

const report = { generatedAt: new Date().toISOString(), totalCandidates: candidates.length, retained, excluded, pendingDetail, pendingPortal };
await fs.writeFile(jsonPath, JSON.stringify(report, null, 2), "utf8");

const workbook = Workbook.create();
let tableNumber = 0;
function makeSheet(name, title, subtitle, headers, rows, widths) {
  const sheet = workbook.worksheets.add(name);
  const endCol = String.fromCharCode(64 + headers.length);
  sheet.showGridLines = false;
  sheet.mergeCells(`A1:${endCol}1`);
  sheet.getRange("A1").values = [[title]];
  sheet.getRange(`A1:${endCol}1`).format = { fill: "#123B5D", font: { name: FONT, size: 17, bold: true, color: "#FFFFFF" }, verticalAlignment: "center" };
  sheet.getRange("A1").format.rowHeight = 34;
  sheet.mergeCells(`A2:${endCol}2`);
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A2:${endCol}2`).format = { fill: "#EAF3F8", font: { name: FONT, size: 10, color: "#24465F" }, wrapText: true, verticalAlignment: "center" };
  sheet.getRange("A2").format.rowHeight = 32;
  sheet.getRange(`A4:${endCol}4`).values = [headers];
  sheet.getRange(`A4:${endCol}4`).format = { fill: "#0B5A8C", font: { name: FONT, size: 10, bold: true, color: "#FFFFFF" }, wrapText: true, horizontalAlignment: "center", verticalAlignment: "center", borders: { preset: "all", style: "thin", color: "#8EB4CA" } };
  sheet.getRange("A4").format.rowHeight = 30;
  if (rows.length) {
    const values = rows.map((row) => headers.map((header) => squash(row[header] ?? "")));
    const last = rows.length + 4;
    sheet.getRange(`A5:${endCol}${last}`).values = values;
    const range = sheet.getRange(`A5:${endCol}${last}`);
    range.format = { font: { name: FONT, size: 9, color: "#1F2933" }, wrapText: true, verticalAlignment: "top", borders: { preset: "all", style: "thin", color: "#D5E1E8" } };
    range.format.rowHeight = 76;
    for (let row = 5; row <= last; row += 1) if (row % 2 === 0) sheet.getRange(`A${row}:${endCol}${row}`).format.fill = "#F5F9FC";
    tableNumber += 1;
    const table = sheet.tables.add(`A4:${endCol}${last}`, true, `SoeJdTable${tableNumber}`);
    table.style = "TableStyleMedium2";
    table.showBandedRows = false;
  }
  widths.forEach((width, i) => sheet.getRangeByIndexes(0, i, Math.max(rows.length + 4, 5), 1).format.columnWidth = width);
  sheet.freezePanes.freezeRows(4);
  return sheet;
}

makeSheet("已核验候选", "央国企岗位 JD 与学历核验", "筛选范围：原前 100 条候选中可直达的官方详情页。保留项均有专业限制，建议作为机会型投递。", ["筛选结论", "公司", "具体岗位", "校招状态", "学历要求", "截止时间", "岗位职责", "任职要求", "官方 JD", "核验说明"], retained, [22, 24, 38, 15, 15, 15, 60, 65, 46, 48]);
makeSheet("已排除", "已排除的官方详情岗位", "排除原因仅包括：硕士门槛、社招经验门槛或纯硬技术职责。", ["筛选结论", "公司", "具体岗位", "校招状态", "学历要求", "截止时间", "岗位职责", "任职要求", "官方 JD", "核验说明"], excluded, [14, 24, 38, 15, 15, 15, 60, 65, 46, 48]);
makeSheet("待详情核验", "详情页未返回完整 JD", "这些链接可打开，但页面正文没有返回职责和学历字段；暂不列入可投。", ["筛选结论", "公司", "具体岗位", "校招状态", "学历要求", "截止时间", "岗位职责", "任职要求", "官方 JD", "核验说明"], pendingDetail, [16, 24, 38, 15, 15, 15, 60, 65, 46, 48]);
makeSheet("待展开入口", "公司级招聘入口待展开", "原前 100 条中尚未取得具体岗位详情的入口。需要展开到岗位页后才能依据 JD、学历和专业筛选。", ["筛选结论", "公司", "公告标题", "地点", "截止时间", "候选优先级", "当前入口", "说明"], pendingPortal, [18, 24, 45, 24, 15, 16, 50, 58]);

workbook.recalculate();
await fs.mkdir(outputDir, { recursive: true });
const preview = await workbook.render({ sheetName: "已核验候选", range: "A1:J12", scale: 1, format: "png" });
await fs.writeFile(path.join(outputDir, "央国企候选_JD学历核验筛选_2026-09-28.preview.png"), new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
const inspect = await workbook.inspect({ kind: "table", range: "已核验候选!A1:J12", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 10 });
console.log(inspect.ndjson);
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 300 }, summary: "final formula error scan" });
console.log(errors.ndjson);
console.log(JSON.stringify({ outputPath, jsonPath, retained: retained.length, excluded: excluded.length, pendingDetail: pendingDetail.length, pendingPortal: pendingPortal.length }));
