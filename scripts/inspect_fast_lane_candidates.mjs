#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const moduleRoot =
  process.env.CODEX_SPREADSHEET_MODULE_ROOT
  || "C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";

const [inputValue, outputValue] = process.argv.slice(2);
if (!inputValue || !outputValue) {
  throw new Error("Usage: inspect_fast_lane_candidates.mjs <input.xlsx> <output.json>");
}

const inputPath = path.resolve(inputValue);
const outputPath = path.resolve(outputValue);
const requireFromRuntime = createRequire(path.join(moduleRoot, "__fast_lane_inspect_loader__.cjs"));
const { FileBlob, SpreadsheetFile } = requireFromRuntime("@oai/artifact-tool");
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.items.find((item) => item.name === "岗位评估");
if (!sheet) throw new Error("找不到工作表：岗位评估");

const values = sheet.getUsedRange(true)?.values ?? [];
const headers = (values[0] ?? []).map((value) => String(value ?? "").trim());
const rows = values.slice(1).map((row, index) => ({
  excel_row: index + 2,
  values: Object.fromEntries(headers.map((header, column) => [header, row[column] ?? ""])),
}));
const strategyCounts = {};
for (const row of rows) {
  const key = String(row.values["简历策略"] ?? "").trim() || "(空)";
  strategyCounts[key] = (strategyCounts[key] ?? 0) + 1;
}

const fullRewrite = rows.filter(({ values: row }) =>
  /(完整重写|需重写|重写)/u.test(String(row["简历策略"] ?? "")),
);
const fields = [
  "公司", "具体岗位", "岗位族", "岗位方向", "分类", "批次", "地点", "具体JD地址",
  "具体投递地址", "JD要求", "简历策略", "基线简历ID", "HR复核结果", "简历文件地址",
  "材料状态", "处理说明", "源表行号", "投递状态",
];
const payload = {
  input: inputPath,
  sheet: sheet.name,
  row_count: rows.length,
  headers,
  strategy_counts: strategyCounts,
  full_rewrite_count: fullRewrite.length,
  full_rewrite: fullRewrite.map(({ excel_row: excelRow, values: row }) => ({
    excel_row: excelRow,
    ...Object.fromEntries(fields.map((field) => [field, row[field] ?? ""])),
  })),
};

await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.writeFile(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify({ output: outputPath, rows: rows.length, full_rewrite: fullRewrite.length })}\n`);
