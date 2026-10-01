#!/usr/bin/env node

import path from "node:path";
import { createRequire } from "node:module";

const moduleRoot =
  process.env.CODEX_SPREADSHEET_MODULE_ROOT
  || "C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";
const requireFromRuntime = createRequire(path.join(moduleRoot, "__check_register_loader__.cjs"));
const { FileBlob, SpreadsheetFile } = requireFromRuntime("@oai/artifact-tool");

const [, , inputValue, ...sourceRows] = process.argv;
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(path.resolve(inputValue)));
const sheet = workbook.worksheets.items.find((item) => item.name === "岗位评估");
if (!sheet) throw new Error("missing 岗位评估 sheet");
const values = sheet.getUsedRange(true)?.values ?? [];
const headers = (values[0] ?? []).map((value) => String(value ?? "").trim());
const targets = new Set(sourceRows);
const interesting = ["公司", "具体岗位", "简历策略", "基线简历ID", "HR复核结果", "简历文件地址", "材料状态", "处理说明"];
const idx = Object.fromEntries(interesting.map((h) => [h, headers.indexOf(h)]));
for (let r = 1; r < values.length; r += 1) {
  const row = values[r];
  const source = String(row[headers.indexOf("源表行号")] ?? "").trim();
  if (!targets.has(source)) continue;
  const out = { 源表行号: source };
  for (const h of interesting) out[h] = row[idx[h]] ?? "";
  process.stdout.write(JSON.stringify(out, null, 2) + "\n");
}
