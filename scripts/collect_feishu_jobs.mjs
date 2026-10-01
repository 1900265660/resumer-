#!/usr/bin/env node

/**
 * Collect filtered rows from a public Feishu Sheet and export them to XLSX.
 *
 * The Feishu Sheet renders cells on canvas, so ordinary HTML scrapers cannot
 * read the grid. This script lets Feishu load its own read-only workbook model
 * in Chromium, then reads cell text from that model without editing the source.
 *
 * Example:
 *   node scripts/collect_feishu_jobs.mjs \
 *     --url "https://example.feishu.cn/wiki/..." \
 *     --output "outputs/feishu-jobs.xlsx" \
 *     --industries "互联网,游戏"
 *
 * Generic filter example:
 *   node scripts/collect_feishu_jobs.mjs \
 *     --url "https://example.feishu.cn/wiki/..." \
 *     --output "outputs/central-state-owned-jobs.xlsx" \
 *     --filter-column "企业类型" \
 *     --filter-values "国央企"
 */

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const DEFAULT_MODULE_ROOT =
  "C:\\Users\\Administrator\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules";
const DEFAULT_EDGE_PATH =
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (!value.startsWith("--")) {
      throw new Error(`Unexpected argument: ${value}`);
    }
    const key = value.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
    } else {
      args[key] = next;
      index += 1;
    }
  }
  return args;
}

function splitCsv(value) {
  return String(value ?? "")
    .split(/[,，]/u)
    .map((item) => item.trim())
    .filter(Boolean);
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

function cleanUrlCandidate(raw) {
  return raw.replace(/[，。；;、）》】\]}>'"\s]+$/gu, "").trim();
}

function normalizeUrl(raw) {
  let value = cleanUrlCandidate(String(raw ?? ""));
  if (!value) return "";
  if (/^www\./iu.test(value) || /^[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)+(?:\/[^\s]*)?$/iu.test(value)) {
    value = `https://${value}`;
  }
  if (!/^https?:\/\//iu.test(value)) return "";
  try {
    const url = new URL(value);
    if (url.hostname === "mp.weixinbridge.com") {
      const nested = url.searchParams.get("url");
      if (nested && /^https?:\/\//iu.test(nested)) return nested;
    }
    return url.href;
  } catch {
    return value;
  }
}

function extractUrls(raw) {
  const text = String(raw ?? "");
  const matches = text.match(/https?:\/\/[^\s<>{}"']+/giu) ?? [];
  if (matches.length === 0 && text.trim() && !text.includes("\n")) {
    matches.push(text.trim());
  }
  const urls = matches.map(normalizeUrl).filter(Boolean);
  return [...new Set(urls)];
}

function parseDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/u.exec(String(value ?? "").trim());
  if (!match) return value;
  return new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
}

async function resolveRuntime(moduleRoot) {
  const loader = path.join(moduleRoot, "__codex_feishu_loader__.cjs");
  const requireFromRuntime = createRequire(loader);
  const { chromium } = requireFromRuntime("playwright");
  const { SpreadsheetFile, Workbook } = requireFromRuntime("@oai/artifact-tool");
  return { chromium, SpreadsheetFile, Workbook };
}

async function collectRows({ chromium, url, sheetName, filterColumn, filterValues, edgePath }) {
  const launchOptions = { headless: true };
  try {
    await fs.access(edgePath);
    launchOptions.executablePath = edgePath;
  } catch {
    launchOptions.channel = "msedge";
  }

  const browser = await chromium.launch(launchOptions);
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 120_000 });
    await page.waitForFunction(
      ({ requestedSheet }) => {
        const sheets = globalThis.spread?.sheets;
        if (!Array.isArray(sheets) || sheets.length === 0) return false;
        const sheet = requestedSheet
          ? sheets.find((candidate) => candidate?._name === requestedSheet)
          : sheets[globalThis.spread?._activeSheetIndex ?? 0];
        return Boolean(sheet && sheet.getText?.(0, 0));
      },
      { requestedSheet: sheetName },
      { timeout: 120_000 },
    );

    const collected = await page.evaluate(
      ({ requestedSheet, requestedFilterColumn, requestedFilterValues }) => {
        const sheets = globalThis.spread.sheets;
        const sheet = requestedSheet
          ? sheets.find((candidate) => candidate?._name === requestedSheet)
          : sheets[globalThis.spread._activeSheetIndex ?? 0];
        if (!sheet) throw new Error(`Sheet not found: ${requestedSheet}`);

        const columnCount = sheet.getColumnCount();
        const headers = Array.from({ length: columnCount }, (_, column) =>
          String(sheet.getText(0, column) ?? "").trim(),
        );
        let usedColumnCount = headers.length;
        while (usedColumnCount > 0 && !headers[usedColumnCount - 1]) usedColumnCount -= 1;
        const usedHeaders = headers.slice(0, usedColumnCount);
        const filterColumnIndex = usedHeaders.indexOf(requestedFilterColumn);
        if (filterColumnIndex < 0) {
          throw new Error(`The source sheet has no ${requestedFilterColumn} column`);
        }

        const rows = [];
        for (let row = 1; row < sheet.getRowCount(); row += 1) {
          const values = Array.from({ length: usedColumnCount }, (_, column) =>
            String(sheet.getText(row, column) ?? "").trim(),
          );
          if (!values[0]) continue;
          const cellTags = values[filterColumnIndex]
            .split(/[,，]/u)
            .map((item) => item.trim())
            .filter(Boolean);
          if (
            requestedFilterValues.length > 0 &&
            !requestedFilterValues.some((filterValue) => cellTags.includes(filterValue))
          ) {
            continue;
          }
          rows.push({ sourceRow: row + 1, values });
        }
        return {
          title: document.title,
          sheetName: sheet._name,
          sheetId: sheet._id_,
          headers: usedHeaders,
          rows,
        };
      },
      {
        requestedSheet: sheetName,
        requestedFilterColumn: filterColumn,
        requestedFilterValues: filterValues,
      },
    );

    return collected;
  } finally {
    await browser.close();
  }
}

async function buildWorkbook({ SpreadsheetFile, Workbook, collected, url, filterColumn, filterValues, output }) {
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add("筛选岗位");
  sheet.showGridLines = false;
  sheet.tabColor = "#1F4E78";

  const originalHeaders = collected.headers;
  const headers = [
    "源表行号",
    ...originalHeaders,
    "公告链接（提取）",
    "投递链接（提取）",
  ];
  const announcementIndex = originalHeaders.indexOf("公告链接");
  const applicationIndex = originalHeaders.indexOf("投递官网链接");

  const dataRows = collected.rows.map(({ sourceRow, values }) => {
    const typedValues = values.map((value, index) => {
      const header = originalHeaders[index];
      return ["网申开始时间", "投递截止时间", "添加进表格时间"].includes(header)
        ? parseDate(value)
        : value;
    });
    const announcementUrls = extractUrls(values[announcementIndex]);
    const applicationUrls = extractUrls(values[applicationIndex]);
    return [
      sourceRow,
      ...typedValues,
      announcementUrls.join("\n"),
      applicationUrls.join("\n"),
    ];
  });

  const lastColumn = excelColumnName(headers.length);
  const headerRow = 5;
  const firstDataRow = headerRow + 1;
  const lastDataRow = firstDataRow + dataRows.length - 1;

  sheet.getRange(`A1:${lastColumn}1`).merge();
  sheet.getRange("A1").values = [["互联网与游戏校招岗位"]];
  sheet.getRange("A1").format = {
    font: { name: "Arial", size: 15, bold: true, color: "#1F1F1F" },
    verticalAlignment: "center",
  };
  sheet.getRange(`A2:${lastColumn}2`).merge();
  sheet.getRange("A2").values = [[`来源：${url}`]];
  sheet.getRange("A3:C3").values = [[
    "筛选条件",
    `${filterColumn}：${filterValues.join("、") || "全部"}`,
    `采集时间：${new Date().toISOString()}`,
  ]];
  sheet.getRange(`A${headerRow}:${lastColumn}${headerRow}`).values = [headers];

  if (dataRows.length > 0) {
    sheet.getRange(`A${firstDataRow}:${lastColumn}${lastDataRow}`).values = dataRows;
  }

  const usedRange = sheet.getRange(`A1:${lastColumn}${Math.max(lastDataRow, headerRow)}`);
  usedRange.format.font = { name: "Arial", size: 10, color: "#1F1F1F" };
  usedRange.format.verticalAlignment = "center";

  sheet.getRange("A1").format.font = {
    name: "Arial",
    size: 15,
    bold: true,
    color: "#1F1F1F",
  };
  sheet.getRange("A2").format.font = { name: "Arial", size: 9, color: "#0563C1" };
  sheet.getRange("A3:C3").format.font = { name: "Arial", size: 9, italic: true, color: "#666666" };
  sheet.getRange(`A${headerRow}:${lastColumn}${headerRow}`).format = {
    fill: "#1F4E78",
    font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
  };

  if (dataRows.length > 0) {
    const body = sheet.getRange(`A${firstDataRow}:${lastColumn}${lastDataRow}`);
    body.format.borders = {
      bottom: { style: "thin", color: "#E6E6E6" },
    };
    body.format.rowHeight = 34;
    sheet.getRange(`A${firstDataRow}:A${lastDataRow}`).format.horizontalAlignment = "right";

    for (const header of ["网申开始时间", "投递截止时间", "添加进表格时间"]) {
      const index = headers.indexOf(header) + 1;
      if (index > 0) {
        sheet
          .getRange(`${excelColumnName(index)}${firstDataRow}:${excelColumnName(index)}${lastDataRow}`)
          .setNumberFormat("yyyy-mm-dd");
      }
    }

    const extractedStart = headers.length - 1;
    sheet
      .getRange(`${excelColumnName(extractedStart)}${firstDataRow}:${lastColumn}${lastDataRow}`)
      .format.font = { name: "Arial", size: 10, color: "#0563C1" };

    sheet.tables.add(
      `A${headerRow}:${lastColumn}${lastDataRow}`,
      true,
      "FilteredJobsTable",
    ).style = "TableStyleMedium2";
  }

  const widthByHeader = {
    源表行号: 10,
    公司名称: 18,
    公告标题: 42,
    企业类型: 12,
    所属行业: 15,
    类型: 18,
    "地点（可筛选）": 30,
    网申开始时间: 15,
    投递截止时间: 18,
    公告链接: 36,
    投递官网链接: 40,
    添加进表格时间: 16,
    内推码: 14,
    "公告链接（提取）": 42,
    "投递链接（提取）": 48,
  };
  headers.forEach((header, index) => {
    sheet.getRange(`${excelColumnName(index + 1)}:${excelColumnName(index + 1)}`).format.columnWidth =
      widthByHeader[header] ?? 16;
  });

  for (const header of [
    "公告标题",
    "地点（可筛选）",
    "公告链接",
    "投递官网链接",
    "公告链接（提取）",
    "投递链接（提取）",
  ]) {
    const index = headers.indexOf(header) + 1;
    if (index > 0 && dataRows.length > 0) {
      sheet
        .getRange(`${excelColumnName(index)}${firstDataRow}:${excelColumnName(index)}${lastDataRow}`)
        .format.wrapText = true;
    }
  }

  sheet.freezePanes.freezeRows(headerRow);
  sheet.freezePanes.freezeColumns(2);
  sheet.getRange("1:1").format.rowHeight = 24;
  sheet.getRange(`${headerRow}:${headerRow}`).format.rowHeight = 32;

  workbook.recalculate();
  const check = await workbook.inspect({
    kind: "table",
    range: `筛选岗位!A1:${lastColumn}${Math.min(lastDataRow, 12)}`,
    include: "values,formulas",
    tableMaxRows: 12,
    tableMaxCols: headers.length,
  });
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 100 },
    summary: "final formula error scan",
  });

  await fs.mkdir(path.dirname(output), { recursive: true });
  const preview = await workbook.render({
    sheetName: "筛选岗位",
    range: `A1:${lastColumn}${Math.min(lastDataRow, 16)}`,
    scale: 1,
    format: "png",
  });
  const previewPath = output.replace(/\.xlsx$/iu, ".preview.png");
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(output);

  return {
    rowCount: dataRows.length,
    output,
    previewPath,
    inspect: check.ndjson,
    formulaErrors: errors.ndjson,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.url || (!args.output && !args["json-only"])) {
    throw new Error("Required: --url plus --output <file.xlsx>, or use --json-only with --json-output");
  }
  if (args["json-only"] && !args["json-output"]) {
    throw new Error("--json-only requires --json-output <file.json>");
  }

  const moduleRoot = path.resolve(
    String(args["module-root"] || process.env.JOB_COLLECTOR_NODE_MODULES || DEFAULT_MODULE_ROOT),
  );
  const legacyIndustries = splitCsv(args.industries || "互联网,游戏");
  const filterColumn = String(args["filter-column"] || "所属行业");
  const filterValues = args["filter-values"]
    ? splitCsv(args["filter-values"])
    : legacyIndustries;
  const sheetName = String(args.sheet || "总表（更新日期排序）");
  const output = args.output ? path.resolve(String(args.output)) : "";
  const edgePath = String(args.edge || DEFAULT_EDGE_PATH);
  const runtime = await resolveRuntime(moduleRoot);
  const collected = await collectRows({
    chromium: runtime.chromium,
    url: String(args.url),
    sheetName,
    filterColumn,
    filterValues,
    edgePath,
  });

  if (args["json-output"]) {
    const jsonOutput = path.resolve(String(args["json-output"]));
    await fs.mkdir(path.dirname(jsonOutput), { recursive: true });
    await fs.writeFile(
      jsonOutput,
      JSON.stringify({
        sourceUrl: args.url,
        filter: { column: filterColumn, values: filterValues },
        industries: filterColumn === "所属行业" ? filterValues : undefined,
        ...collected,
      }, null, 2),
      "utf8",
    );
  }

  if (args["json-only"]) {
    process.stdout.write(`${JSON.stringify({
      rowCount: collected.rows.length,
      sheetName: collected.sheetName,
      filter: { column: filterColumn, values: filterValues },
      jsonOutput: path.resolve(String(args["json-output"])),
    }, null, 2)}\n`);
    return;
  }

  const result = await buildWorkbook({
    SpreadsheetFile: runtime.SpreadsheetFile,
    Workbook: runtime.Workbook,
    collected,
    url: String(args.url),
    filterColumn,
    filterValues,
    output,
  });
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message || String(error)}\n`);
  process.exitCode = 1;
});
