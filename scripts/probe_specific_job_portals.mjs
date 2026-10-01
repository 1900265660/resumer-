#!/usr/bin/env node

/** Capture public DOM and JSON/XHR payloads for the already shortlisted SOE roles. */

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
    const key = argv[index];
    if (!key.startsWith("--")) throw new Error(`Unexpected argument: ${key}`);
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) args[key.slice(2)] = true;
    else {
      args[key.slice(2)] = value;
      index += 1;
    }
  }
  return args;
}

function isHttpUrl(value) {
  return /^https?:\/\//iu.test(String(value ?? "").trim());
}

function looksUsefulPayload(url, contentType, body) {
  const sample = `${url}\n${body.slice(0, 20_000)}`;
  return /json|graphql/iu.test(contentType)
    || /岗位|职位|招聘|job|position|vacan|career|campus|recruit|duty|requirement/iu.test(sample);
}

async function atomicWrite(filePath, value) {
  const partial = `${filePath}.partial`;
  await fs.writeFile(partial, JSON.stringify(value, null, 2), "utf8");
  await fs.rename(partial, filePath).catch(async () => {
    await fs.copyFile(partial, filePath);
    await fs.unlink(partial).catch(() => {});
  });
}

async function probeOne(context, target, timeoutMs, clickText = "") {
  const page = await context.newPage();
  const responses = [];
  const seen = new Set();
  page.on("response", async (response) => {
    try {
      const url = response.url();
      const contentType = response.headers()["content-type"] ?? "";
      if (!/json|text|javascript|html|graphql/iu.test(contentType)) return;
      const key = `${response.status()} ${url}`;
      if (seen.has(key)) return;
      seen.add(key);
      const body = (await response.text()).slice(0, 2_000_000);
      if (!looksUsefulPayload(url, contentType, body)) return;
      responses.push({
        url,
        status: response.status(),
        contentType,
        requestMethod: response.request().method(),
        requestPostData: response.request().postData() ?? "",
        body,
      });
    } catch {
      // Cross-origin and streaming responses are allowed to be unreadable.
    }
  });
  let navigationError = null;
  try {
    await page.goto(target.url, { waitUntil: "domcontentloaded", timeout: timeoutMs });
  } catch (error) {
    navigationError = String(error?.message ?? error);
  }
  try {
    await page.waitForTimeout(3_000);
    if (clickText) {
      const candidate = page.getByText(clickText, { exact: true }).first();
      await candidate.click({ timeout: 8_000 });
      await page.waitForTimeout(2_000);
    }
    for (let index = 0; index < 3; index += 1) {
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(800);
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(500);
    const bodyText = await page.locator("body").innerText({ timeout: 5_000 }).catch(() => "");
    const anchors = await page.locator("a[href]").evaluateAll((items) => items.slice(0, 5_000).map((item) => ({
      text: String(item.textContent ?? "").replace(/\s+/gu, " ").trim().slice(0, 500),
      href: item.href,
    }))).catch(() => []);
    return {
      ...target,
      finalUrl: page.url(),
      title: await page.title().catch(() => ""),
      bodyText: bodyText.slice(0, 300_000),
      anchors,
      responses,
      navigationError,
      capturedAt: new Date().toISOString(),
    };
  } finally {
    await page.close();
  }
}

async function runPool(items, concurrency, worker, checkpoint) {
  const results = new Array(items.length);
  let nextIndex = 0;
  let complete = 0;
  async function runWorker() {
    while (true) {
      const index = nextIndex++;
      if (index >= items.length) return;
      results[index] = await worker(items[index]);
      complete += 1;
      await checkpoint(results.filter(Boolean), complete);
      process.stdout.write(`Probed ${complete}/${items.length}: ${items[index].url}\n`);
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, runWorker));
  return results;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if ((!args.input && !args.url) || !args.output) {
    throw new Error("Required: (--input <assessment.json> | --url <url>) --output <probe.json>");
  }
  const inputPath = args.input ? path.resolve(String(args.input)) : null;
  const outputPath = path.resolve(String(args.output));
  const moduleRoot = path.resolve(String(args["module-root"] || DEFAULT_MODULE_ROOT));
  const requireFromRuntime = createRequire(path.join(moduleRoot, "__probe_specific_job_portals_loader__.cjs"));
  const { chromium } = requireFromRuntime("playwright");
  const grouped = new Map();
  if (args.url) {
    const url = new URL(String(args.url)).href;
    grouped.set(url, { url, roles: [{ company: String(args.company || "single-url-probe"), role: String(args.role || "") }] });
  } else {
    const assessment = JSON.parse(await fs.readFile(inputPath, "utf8"));
    for (const row of assessment.verifiedRoleRows ?? []) {
      const [category, company, role, direction, location, evidence, summary, deadline, urgency, application, sourceRow] = row;
      if (!/^[1-4]-/u.test(String(category)) || !isHttpUrl(application)) continue;
      const url = new URL(application).href;
      const current = grouped.get(url) ?? { url, roles: [] };
      current.roles.push({ category, company, role, direction, location, evidence, summary, deadline, urgency, sourceRow });
      grouped.set(url, current);
    }
  }
  const targets = [...grouped.values()];
  const browser = await chromium.launch({
    executablePath: String(args.edge || DEFAULT_EDGE_PATH),
    headless: true,
    args: ["--disable-blink-features=AutomationControlled"],
  });
  const context = await browser.newContext({
    locale: "zh-CN",
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
  });
  const startedAt = new Date().toISOString();
  const checkpoint = async (results, complete) => atomicWrite(outputPath, {
    source: inputPath || String(args.url),
    startedAt,
    updatedAt: new Date().toISOString(),
    complete,
    total: targets.length,
    results,
  });
  try {
    const results = await runPool(
      targets,
      Math.max(1, Math.min(4, Number(args.concurrency || 3))),
      (target) => probeOne(
        context,
        target,
        Math.max(10_000, Number(args.timeout || 35_000)),
        String(args["click-text"] || ""),
      ),
      checkpoint,
    );
    await atomicWrite(outputPath, {
      source: inputPath || String(args.url),
      startedAt,
      finishedAt: new Date().toISOString(),
      complete: results.length,
      total: results.length,
      results,
    });
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message || String(error)}\n`);
  process.exitCode = 1;
});
