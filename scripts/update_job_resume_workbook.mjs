#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const DEFAULT_MODULE_ROOT =
  "C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules";

export const WORKFLOW_HEADERS = [
  "具体岗位",
  "具体JD地址",
  "具体投递地址",
  "简历策略",
  "基线简历ID",
  "HR复核结果",
  "简历文件地址",
  "配套附件地址",
  "材料状态",
  "处理说明",
];

export const MATERIAL_STATUSES = [
  "待读取JD",
  "待快速生成",
  "HR复核中",
  "可投递",
  "待补事实",
  "暂缓完整重写",
  "待人工处理",
  "待用户确认",
  "阻断",
];

function parseArgs(argv) {
  const result = {};
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (!value.startsWith("--")) throw new Error(`Unexpected argument: ${value}`);
    const key = value.slice(2);
    if (key === "self-test" || key === "no-backup") {
      result[key] = true;
      continue;
    }
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) throw new Error(`Missing value for --${key}`);
    result[key] = next;
    index += 1;
  }
  return result;
}

function excelColumnName(index) {
  let value = index;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

function normalizeText(value) {
  return String(value ?? "").trim();
}

function normalizeUrl(value) {
  const input = normalizeText(value);
  if (!input) return "";
  try {
    const url = new URL(input);
    // Hash-based recruitment apps encode the concrete job in the fragment
    // (for example `#/job/<position-id>`). Preserve those SPA routes; plain
    // document anchors are presentation-only and may be discarded for dedupe.
    if (!/^#\//u.test(url.hash)) url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      if (/^(utm_|spm$|from$|source$|sessionid$|click_id$)/iu.test(key)) {
        url.searchParams.delete(key);
      }
    }
    return url.toString().replace(/\/$/u, "").toLowerCase();
  } catch {
    return input.toLowerCase();
  }
}

function headerMap(headers) {
  return Object.fromEntries(headers.map((header, index) => [header, index]));
}

function rowObject(headers, row) {
  return Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ""]));
}

function concreteKey(value) {
  const jdUrl = normalizeUrl(value["具体JD地址"] ?? value.jd_url);
  if (jdUrl) return `jd:${jdUrl}`;
  return `job:${normalizeText(value["公司"] ?? value.company).toLowerCase()}|${normalizeText(
    value["具体岗位"] ?? value.concrete_job,
  ).toLowerCase()}`;
}

function isFormalCampus(row) {
  const batch = normalizeText(row["批次"]);
  return /秋招|提前批|正式校招|校园招聘/iu.test(batch) && !/实习/iu.test(batch);
}

function defaultWorkflow(row) {
  const category = normalizeText(row["分类"]);
  if (!isFormalCampus(row)) {
    return { materialStatus: "阻断", notes: "当前策略仅处理正式校招。" };
  }
  if (category.startsWith("7-")) {
    return { materialStatus: "阻断", notes: "岗位已过期或入口失效。" };
  }
  if (category.startsWith("8-")) {
    return { materialStatus: "阻断", notes: "纯硬技术专项不进入默认准备队列。" };
  }
  const note = normalizeText(row["投递状态"]) === "已投递"
    ? "存在公司级已投记录；展开具体岗位时仍需逐岗去重。"
    : "等待从官方招聘页展开为具体岗位并读取完整 JD。";
  return { materialStatus: "待读取JD", notes: note };
}

function concretePositionBlockReason(position, base) {
  const baseDefault = defaultWorkflow(base);
  if (baseDefault.materialStatus === "阻断") return baseDefault.notes;
  if (position.is_internship === true || /实习/iu.test(normalizeText(position.employment_type))) {
    return "暑期/日常实习不进入正式校招材料生成队列。";
  }
  if (position.is_expired === true) return "具体岗位已过期。";
  if (position.is_pure_hard_tech === true) return "纯硬技术岗位不进入默认材料生成队列。";
  if (
    position.has_success_receipt === true
    || /^(已投递|投递成功|submitted)$/iu.test(normalizeText(position.application_status))
  ) {
    return "该具体岗位已有成功回执，拒绝重复生成或投递。";
  }
  return "";
}

function positionToWorkflow(position, existing = {}, base = {}) {
  const blockReason = concretePositionBlockReason(position, base);
  return {
    "具体岗位": position.concrete_job,
    "具体JD地址": position.jd_url,
    "具体投递地址": position.application_url,
    "简历策略": position.resume_strategy ?? existing["简历策略"] ?? "",
    "基线简历ID": position.baseline_id ?? existing["基线简历ID"] ?? "",
    "HR复核结果": position.hr_result ?? existing["HR复核结果"] ?? "",
    "简历文件地址": position.resume_path ?? existing["简历文件地址"] ?? "",
    "配套附件地址": position.attachments ?? existing["配套附件地址"] ?? "",
    "材料状态": blockReason ? "阻断" : (position.material_status ?? existing["材料状态"] ?? "待读取JD"),
    "处理说明": blockReason || position.notes || existing["处理说明"] || "",
  };
}

export function mergeConcretePositions(existingHeaders, existingRows, positions) {
  const baseHeaders = existingHeaders.filter((header) => !WORKFLOW_HEADERS.includes(header));
  if (!baseHeaders.includes("投递状态")) baseHeaders.push("投递状态");
  const outputHeaders = [...baseHeaders, ...WORKFLOW_HEADERS];
  const rowsBySource = new Map();
  for (const row of existingRows) {
    const object = rowObject(existingHeaders, row);
    const sourceRow = Number(object["源表行号"]);
    if (!Number.isFinite(sourceRow)) continue;
    if (!rowsBySource.has(sourceRow)) rowsBySource.set(sourceRow, []);
    rowsBySource.get(sourceRow).push(object);
  }
  const positionsBySource = new Map();
  for (const position of positions) {
    const sourceRow = Number(position.source_row);
    if (!Number.isInteger(sourceRow) || sourceRow < 1) {
      throw new Error(`Invalid source_row: ${position.source_row}`);
    }
    if (!positionsBySource.has(sourceRow)) positionsBySource.set(sourceRow, []);
    positionsBySource.get(sourceRow).push(position);
  }

  const output = [];
  const globalKeys = new Set();
  for (const [sourceRow, sourceRows] of rowsBySource.entries()) {
    const base = sourceRows[0];
    const supplied = positionsBySource.get(sourceRow) ?? [];
    if (supplied.length === 0) {
      for (const existing of sourceRows) {
        const defaults = defaultWorkflow(existing);
        const combined = {
          ...existing,
          "材料状态": existing["材料状态"] || defaults.materialStatus,
          "处理说明": existing["处理说明"] || defaults.notes,
        };
        output.push(outputHeaders.map((header) => combined[header] ?? ""));
      }
      continue;
    }
    const existingByKey = new Map(
      sourceRows
        .filter((item) => normalizeText(item["具体岗位"]))
        .map((item) => [concreteKey(item), item]),
    );
    for (const position of supplied) {
      if (normalizeText(position.company) !== normalizeText(base["公司"])) {
        throw new Error(
          `Company mismatch for source row ${sourceRow}: ${position.company} != ${base["公司"]}`,
        );
      }
      const key = concreteKey(position);
      if (globalKeys.has(key)) throw new Error(`Duplicate concrete job: ${key}`);
      globalKeys.add(key);
      const previous = existingByKey.get(key) ?? {};
      const combined = { ...base, ...previous, ...positionToWorkflow(position, previous, base) };
      if (position.application_status !== undefined) {
        combined["投递状态"] = position.application_status;
      }
      output.push(outputHeaders.map((header) => combined[header] ?? ""));
    }
  }
  const missingSources = [...positionsBySource.keys()].filter((key) => !rowsBySource.has(key));
  if (missingSources.length) {
    throw new Error(`Positions reference missing source rows: ${missingSources.join(", ")}`);
  }
  return { headers: outputHeaders, rows: output };
}

async function findSheet(workbook, name) {
  const sheet = workbook.worksheets.items.find((item) => item.name === name);
  if (!sheet) throw new Error(`Worksheet not found: ${name}`);
  return sheet;
}

async function readUsedMatrix(sheet) {
  const used = sheet.getUsedRange(true);
  const values = used?.values ?? [];
  return values.filter((row, index) => index === 0 || row.some((value) => value !== null && value !== ""));
}

async function ensureBackup(inputPath) {
  const directory = path.dirname(inputPath);
  const extension = path.extname(inputPath);
  const stem = path.basename(inputPath, extension);
  const names = await fs.readdir(directory);
  const existing = names.find((name) => name.startsWith(`${stem}.backup-`) && name.endsWith(extension));
  if (existing) return path.join(directory, existing);
  const stamp = new Date().toISOString().replace(/[:.]/gu, "-");
  const backup = path.join(directory, `${stem}.backup-${stamp}${extension}`);
  await fs.copyFile(inputPath, backup);
  return backup;
}

async function updateSummary(workbook, headers, rows) {
  const summary = await findSheet(workbook, "摘要");
  const indices = headerMap(headers);
  const counts = new Map();
  for (const row of rows) {
    const category = normalizeText(row[indices["分类"]]);
    counts.set(category, (counts.get(category) ?? 0) + 1);
  }
  const matrix = summary.getRange("A5:C12").values;
  for (const row of matrix) row[1] = counts.get(normalizeText(row[0])) ?? 0;
  summary.getRange("A5:C12").values = matrix;
  summary.getRange("A14:H14").values = [[
    "口径：公司招聘项目会逐步展开为可验证的具体正式校招岗位。同公司不同岗位独立统计；暑期/日常实习、过期岗位、纯硬技术岗位和已有成功回执的同一岗位不进入材料生成。材料“可投递”不等于已批准上传或提交。",
  ]];
}

async function updateWorkbook(args) {
  if (!args.input) throw new Error("Required: --input <workbook.xlsx>");
  const inputPath = path.resolve(args.input);
  const positionsPayload = args.positions
    ? JSON.parse(await fs.readFile(path.resolve(args.positions), "utf8"))
    : { schema_version: "1.0", positions: [] };
  if (positionsPayload.schema_version !== "1.0" || !Array.isArray(positionsPayload.positions)) {
    throw new Error("Invalid concrete position batch; expected schema_version 1.0 and positions[]");
  }
  const moduleRoot = path.resolve(String(args["module-root"] || DEFAULT_MODULE_ROOT));
  const requireFromRuntime = createRequire(path.join(moduleRoot, "__job_resume_workbook_loader__.cjs"));
  const { FileBlob, SpreadsheetFile } = requireFromRuntime("@oai/artifact-tool");
  const backupPath = args["no-backup"] ? null : await ensureBackup(inputPath);
  const blob = await FileBlob.load(inputPath);
  const workbook = await SpreadsheetFile.importXlsx(blob);
  const sheet = await findSheet(workbook, "岗位评估");
  const matrix = await readUsedMatrix(sheet);
  if (matrix.length < 2) throw new Error("岗位评估 worksheet has no data rows");
  const existingHeaders = matrix[0].map(normalizeText);
  const existingRows = matrix.slice(1);
  const merged = mergeConcretePositions(
    existingHeaders,
    existingRows,
    positionsPayload.positions,
  );
  const lastColumn = excelColumnName(merged.headers.length);
  const oldLastColumn = excelColumnName(existingHeaders.length);
  const clearRows = Math.max(existingRows.length, merged.rows.length) + 1;
  sheet.getRange(`A1:${oldLastColumn}${clearRows}`).clear({ applyTo: "contents" });
  sheet.getRange(`A1:${lastColumn}1`).values = [merged.headers];
  sheet.getRange(`A2:${lastColumn}${merged.rows.length + 1}`).values = merged.rows;

  const existingTable = sheet.tables.items[0];
  const tableName = existingTable?.name || "岗位评估Table";
  const tableStyle = existingTable?.style || "TableStyleMedium2";
  for (const table of [...sheet.tables.items]) table.delete();
  const table = sheet.tables.add(
    `A1:${lastColumn}${merged.rows.length + 1}`,
    true,
    tableName,
  );
  table.style = tableStyle;
  table.showFilterButton = true;
  const indices = headerMap(merged.headers);
  const headerStart = indices[WORKFLOW_HEADERS[0]] + 1;
  const body = sheet.getRange(`A2:${lastColumn}${merged.rows.length + 1}`);
  body.format.font = { name: "Arial", size: 9, color: "#1F1F1F" };
  body.format.verticalAlignment = "center";
  body.format.wrapText = true;
  body.format.rowHeight = 46;
  sheet.getRange(`${excelColumnName(headerStart)}1:${lastColumn}1`).format = {
    fill: "#1F4E78",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
  };
  const widths = {
    具体岗位: 34,
    具体JD地址: 52,
    具体投递地址: 52,
    简历策略: 14,
    基线简历ID: 24,
    HR复核结果: 24,
    简历文件地址: 58,
    配套附件地址: 52,
    材料状态: 18,
    处理说明: 48,
  };
  for (const [header, width] of Object.entries(widths)) {
    sheet.getRange(`${excelColumnName(indices[header] + 1)}:${excelColumnName(indices[header] + 1)}`).format.columnWidth = width;
  }
  for (const header of ["具体JD地址", "具体投递地址", "简历文件地址", "配套附件地址"]) {
    const column = excelColumnName(indices[header] + 1);
    sheet.getRange(`${column}2:${column}${merged.rows.length + 1}`).format.font = {
      name: "Arial",
      size: 9,
      color: "#0563C1",
    };
  }
  const materialColumn = excelColumnName(indices["材料状态"] + 1);
  sheet.getRange(`${materialColumn}2:${materialColumn}${merged.rows.length + 1}`).dataValidation.clear();
  sheet.dataValidations.add({
    range: `${materialColumn}2:${materialColumn}${merged.rows.length + 1}`,
    rule: { type: "list", values: MATERIAL_STATUSES },
  });
  await updateSummary(workbook, merged.headers, merged.rows);
  workbook.recalculate();

  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 200 },
    summary: "job resume workbook formula error scan",
  });
  const preview = await workbook.render({
    sheetName: "岗位评估",
    range: `A1:${lastColumn}${Math.min(merged.rows.length + 1, 18)}`,
    scale: 1,
    format: "png",
  });
  const previewPath = inputPath.replace(/\.xlsx$/iu, ".resume-workflow.preview.png");
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
  const temporaryPath = inputPath.replace(/\.xlsx$/iu, `.tmp-${process.pid}.xlsx`);
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(temporaryPath);
  await fs.copyFile(temporaryPath, inputPath);
  await fs.unlink(temporaryPath);
  await fs.unlink(`${temporaryPath}.inspect.ndjson`).catch((error) => {
    if (error?.code !== "ENOENT") throw error;
  });
  return {
    workbook: inputPath,
    backup: backupPath,
    preview: previewPath,
    row_count: merged.rows.length,
    column_count: merged.headers.length,
    concrete_position_count: merged.rows.filter((row) => normalizeText(row[indices["具体岗位"]])).length,
    formula_errors: errors.ndjson,
  };
}

function selfTest() {
  const headers = ["分类", "公司", "批次", "源表行号", "投递状态"];
  const rows = [["2-优先可投", "示例公司", "27届秋招/提前批", 7, ""]];
  const positions = [
    { source_row: 7, company: "示例公司", concrete_job: "产品经理", jd_url: "https://example.test/campus?sessionid=tracking#/job/position-1", application_url: "https://example.test/apply/1", resume_strategy: "快速生成", material_status: "待快速生成", application_status: "待投递" },
    { source_row: 7, company: "示例公司", concrete_job: "用户运营", jd_url: "https://example.test/campus?sessionid=tracking#/job/position-2", application_url: "https://example.test/apply/2", resume_strategy: "暂缓完整重写", material_status: "暂缓完整重写", application_status: "待投递" },
    { source_row: 7, company: "示例公司", concrete_job: "内容运营", jd_url: "https://example.test/jobs/3", application_url: "https://example.test/apply/3", material_status: "可投递", application_status: "投递成功", has_success_receipt: true },
  ];
  const result = mergeConcretePositions(headers, rows, positions);
  const statusIndex = result.headers.indexOf("材料状态");
  const applicationIndex = result.headers.indexOf("投递状态");
  if (
    result.rows.length !== 3
    || !WORKFLOW_HEADERS.every((header) => result.headers.includes(header))
    || result.rows[0][statusIndex] !== "待快速生成"
    || result.rows[1][statusIndex] !== "暂缓完整重写"
    || result.rows[2][statusIndex] !== "阻断"
    || new Set(result.rows.map((row) => row[applicationIndex])).size !== 2
  ) {
    throw new Error("self-test failed");
  }
  return { status: "passed", rows: result.rows.length, columns: result.headers.length };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const result = args["self-test"] ? selfTest() : await updateWorkbook(args);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

if (
  process.argv[1]
  && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href
) {
  main().catch((error) => {
    process.stderr.write(`${error.stack || error.message || String(error)}\n`);
    process.exitCode = 1;
  });
}
