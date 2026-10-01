#!/usr/bin/env node

import path from "node:path";
import { createRequire } from "node:module";

const moduleRoot =
  process.env.CODEX_SPREADSHEET_MODULE_ROOT
  || "C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const requireFromRuntime = createRequire(path.join(moduleRoot, "__list_priority_rewrites_loader__.cjs"));
const { FileBlob, SpreadsheetFile } = requireFromRuntime("@oai/artifact-tool");

const [, , inputValue] = process.argv;
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(path.resolve(inputValue)));
const sheet = workbook.worksheets.items.find((item) => item.name === "岗位评估");
if (!sheet) throw new Error("missing 岗位评估 sheet");
const values = sheet.getUsedRange(true)?.values ?? [];
const headers = (values[0] ?? []).map((value) => String(value ?? "").trim());
const idx = Object.fromEntries(headers.map((h, i) => [h, i]));
const rows = [];
for (let r = 1; r < values.length; r += 1) {
  const row = values[r];
  const category = String(row[idx["分类"]] ?? "").trim();
  const strategy = String(row[idx["简历策略"]] ?? "").trim();
  if (!/^(1-立即投递|2-优先可投)$/.test(category)) continue;
  if (!/重写/.test(strategy)) continue;
  rows.push({
    source_row: String(row[idx["源表行号"]] ?? "").trim(),
    category,
    company: String(row[idx["公司"]] ?? "").trim(),
    job: String(row[idx["具体岗位"]] ?? "").trim(),
    direction: String(row[idx["岗位方向"]] ?? "").trim(),
    jd: String(row[idx["具体JD地址"]] ?? "").trim(),
    strategy,
    material_status: String(row[idx["材料状态"]] ?? "").trim(),
  });
}
process.stdout.write(JSON.stringify({ count: rows.length, rows }, null, 2) + "\n");
