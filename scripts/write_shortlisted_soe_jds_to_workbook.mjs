#!/usr/bin/env node

/** Add the verified shortlisted JD sheet to the existing SOE assessment workbook. */

import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile } from "@oai/artifact-tool";

const dir = path.resolve("outputs/01a08935-0096-7c41-adee-5d333da0685e");
const inputPath = path.join(dir, "央国企校招岗位_分类评估_2026-09-14.xlsx");
const dataPath = path.join(dir, "央国企可投岗位JD_2026-09-14.json");
const outputPath = path.join(dir, "央国企校招岗位_分类评估_2026-09-14.xlsx");
const previewPath = path.join(dir, "央国企校招岗位_分类评估_2026-09-14.shortlisted-jd.preview.png");

const FONT = "Microsoft YaHei";
const HEADERS = [
  "申请建议", "公司", "具体岗位", "岗位方向", "部门/业务线", "工作地点", "学历要求", "资格风险",
  "岗位职责", "任职要求", "截止时间", "在招状态", "招聘类型", "官方JD/投递链接", "岗位ID", "核验说明",
];

function cellText(value) {
  return String(value ?? "").replace(/\u0000/gu, "").slice(0, 30_000);
}

const input = new Uint8Array(await fs.readFile(inputPath));
const workbook = await SpreadsheetFile.importXlsx(input);
let sheet;
try {
  sheet = workbook.worksheets.getItem("可投岗位JD");
  for (const existingTable of sheet.tables.items) existingTable.delete();
  sheet.unmergeCells("A1:P1");
  sheet.unmergeCells("A2:P2");
  sheet.getUsedRange()?.clear({ applyTo: "all" });
} catch {
  sheet = workbook.worksheets.add("可投岗位JD");
}

const payload = JSON.parse(await fs.readFile(dataPath, "utf8"));
const rows = payload.rows;
const firstDataRow = 8;
const lastDataRow = firstDataRow + rows.length - 1;

sheet.showGridLines = false;
sheet.tabColor = "#0B5A8C";
sheet.mergeCells("A1:P1");
sheet.getRange("A1").values = [["央国企 2027 校招｜可投岗位完整 JD"]];
sheet.getRange("A1:P1").format = {
  fill: "#123B5D",
  font: { name: FONT, size: 18, bold: true, color: "#FFFFFF" },
  verticalAlignment: "center",
};
sheet.getRange("A1:P1").format.rowHeight = 38;

sheet.mergeCells("A2:P2");
sheet.getRange("A2").values = [["仅收录：此前已筛选方向中，职责与任职要求可核验、仍在招或入口可用的正式校招非硬技术岗位。学历/专业不匹配保留为机会型风险，不代表已通过资格审查。"]];
sheet.getRange("A2:P2").format = {
  fill: "#EAF3F8",
  font: { name: FONT, size: 10, color: "#23465E" },
  wrapText: true,
  verticalAlignment: "center",
};
sheet.getRange("A2:P2").format.rowHeight = 34;

sheet.getRange("A4:H5").values = [
  ["岗位总数", "", "优先定制", "", "海投/轻定制", "", "机会型风险", ""],
  ["", "", "", "", "", "", "", ""],
];
for (const [labelCell, valueCell, formula] of [
  ["A4", "A5", `=COUNTA(C${firstDataRow}:C${lastDataRow})`],
  ["C4", "C5", `=COUNTIF(A${firstDataRow}:A${lastDataRow},\"优先定制\")+COUNTIF(A${firstDataRow}:A${lastDataRow},\"优先定制（上海）\")`],
  ["E4", "E5", `=COUNTIF(A${firstDataRow}:A${lastDataRow},\"海投/轻定制\")`],
  ["G4", "G5", `=COUNTIF(A${firstDataRow}:A${lastDataRow},\"机会型（学历/专业风险）\")`],
]) {
  sheet.mergeCells(`${labelCell}:${String.fromCharCode(labelCell.charCodeAt(0) + 1)}4`);
  sheet.mergeCells(`${valueCell}:${String.fromCharCode(valueCell.charCodeAt(0) + 1)}5`);
  sheet.getRange(labelCell).format = { fill: "#DCEAF3", font: { name: FONT, size: 10, bold: true, color: "#24465F" }, horizontalAlignment: "center", verticalAlignment: "center" };
  sheet.getRange(valueCell).formulas = [[formula]];
  sheet.getRange(valueCell).format = { fill: "#F7FBFD", font: { name: FONT, size: 18, bold: true, color: "#0B5A8C" }, horizontalAlignment: "center", verticalAlignment: "center" };
}
sheet.getRange("A4:H5").format.borders = { preset: "all", style: "thin", color: "#B8CEDD" };
sheet.getRange("A4:H5").format.rowHeight = 26;

sheet.getRange("A7:P7").values = [HEADERS];
sheet.getRange("A7:P7").format = {
  fill: "#0B5A8C",
  font: { name: FONT, size: 10, bold: true, color: "#FFFFFF" },
  wrapText: true,
  horizontalAlignment: "center",
  verticalAlignment: "center",
  borders: { preset: "all", style: "thin", color: "#8EB4CA" },
};
sheet.getRange("A7:P7").format.rowHeight = 32;

const matrix = rows.map((row) => [
  row["申请建议"], row["公司"], row["具体岗位"], row["岗位方向"], row["部门业务线"], row["工作地点"],
  row["学历要求"], row["资格风险"], row["岗位职责"], row["任职要求"], row["截止时间"], row["在招状态"],
  row["招聘类型"], row["官方JD及投递链接"], row["岗位ID"], row["核验说明"],
].map(cellText));
sheet.getRange(`A${firstDataRow}:P${lastDataRow}`).values = matrix;

const dataRange = sheet.getRange(`A${firstDataRow}:P${lastDataRow}`);
dataRange.format = {
  font: { name: FONT, size: 9, color: "#1F2933" },
  wrapText: true,
  verticalAlignment: "top",
  borders: { preset: "all", style: "thin", color: "#D5E1E8" },
};
dataRange.format.rowHeight = 92;
for (let rowIndex = firstDataRow; rowIndex <= lastDataRow; rowIndex += 1) {
  if ((rowIndex - firstDataRow) % 2 === 1) sheet.getRange(`A${rowIndex}:P${rowIndex}`).format.fill = "#F5F9FC";
}
sheet.getRange(`A${firstDataRow}:A${lastDataRow}`).format.font = { name: FONT, size: 9, bold: true, color: "#173A52" };
sheet.getRange(`N${firstDataRow}:N${lastDataRow}`).format.font = { name: FONT, size: 9, color: "#0563C1", underline: true };
sheet.getRange(`A${firstDataRow}:A${lastDataRow}`).conditionalFormats.add("beginsWith", { text: "优先定制", format: { fill: "#DDF3E4", font: { color: "#146C43", bold: true } } });
sheet.getRange(`A${firstDataRow}:A${lastDataRow}`).conditionalFormats.add("containsText", { text: "机会型", format: { fill: "#FFF1CC", font: { color: "#8A5A00", bold: true } } });
sheet.getRange(`A${firstDataRow}:A${lastDataRow}`).conditionalFormats.add("containsText", { text: "海投", format: { fill: "#E7EEF8", font: { color: "#244B78", bold: true } } });

const widths = [22, 25, 38, 21, 28, 22, 18, 46, 76, 76, 20, 22, 22, 42, 38, 48];
for (let col = 0; col < widths.length; col += 1) {
  sheet.getRangeByIndexes(0, col, lastDataRow, 1).format.columnWidth = widths[col];
}
sheet.freezePanes.freezeRows(7);
sheet.freezePanes.freezeColumns(3);
const table = sheet.tables.add(`A7:P${lastDataRow}`, true, "ShortlistedSoeJdTable");
table.style = "TableStyleMedium2";
table.showBandedRows = false;
table.showFilterButton = true;

workbook.recalculate();
const preview = await workbook.render({ sheetName: "可投岗位JD", range: `A1:P18`, scale: 1, format: "png" });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);

const inspect = await workbook.inspect({ kind: "region,formula", sheetId: "可投岗位JD", range: `A1:P${Math.min(lastDataRow, 20)}`, maxChars: 12000, options: { maxResults: 120 } });
await fs.writeFile(`${outputPath}.shortlisted-jd.inspect.ndjson`, inspect.ndjson, "utf8");
process.stdout.write(`Updated ${outputPath} with ${rows.length} shortlisted JDs\nPreview: ${previewPath}\n`);
