#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";

const moduleRoot =
  process.env.CODEX_SPREADSHEET_MODULE_ROOT
  || "C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";

const [inputValue, sheetName = "岗位评估", range = "A1:S18", outputValue] = process.argv.slice(2);
if (!inputValue) throw new Error("Usage: render_workbook_preview.mjs <input.xlsx> [sheet] [range] [output.png]");

const inputPath = path.resolve(inputValue);
const outputPath = path.resolve(outputValue || inputPath.replace(/\.xlsx$/iu, ".pre-edit.preview.png"));
const requireFromRuntime = createRequire(path.join(moduleRoot, "__workbook_preview_loader__.cjs"));
const { FileBlob, SpreadsheetFile } = requireFromRuntime("@oai/artifact-tool");
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
await fs.writeFile(outputPath, new Uint8Array(await preview.arrayBuffer()));
process.stdout.write(`${JSON.stringify({ input: inputPath, sheet: sheetName, range, output: outputPath })}\n`);
