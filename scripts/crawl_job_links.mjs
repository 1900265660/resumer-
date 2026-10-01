#!/usr/bin/env node

/** Read every announcement/application URL from collect_feishu_jobs.mjs JSON. */

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
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      args[key.slice(2)] = true;
    } else {
      args[key.slice(2)] = next;
      index += 1;
    }
  }
  return args;
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
  if (matches.length === 0 && text.trim() && !text.includes("\n")) matches.push(text.trim());
  return [...new Set(matches.map(normalizeUrl).filter(Boolean))];
}

function accessState(text, title, finalUrl) {
  const sample = `${title}\n${text.slice(0, 20_000)}\n${finalUrl}`.toLowerCase();
  if (/captcha|验证码|安全验证|人机验证|verify you are human|滑块/u.test(sample)) return "captcha";
  if (/页面不存在|404 not found|not found|职位已下线|招聘已结束|停止招聘|已结束/u.test(sample)) return "closed_or_missing";
  if (/登录后查看|请先登录|扫码登录|账号登录|sign in|log in/u.test(sample)) return "login_required";
  return "ok";
}

function relevantAnchor(anchor) {
  return /校招|招聘|职位|岗位|应届|campus|graduate|job|career|position|apply|投递|产品|运营|策划|项目|内容|市场|人力|行政|用户|社区|编辑|翻译/iu.test(
    `${anchor.text} ${anchor.href}`,
  );
}

function decodeHtml(value) {
  return String(value ?? "")
    .replace(/&#(\d+);/gu, (_, code) => String.fromCodePoint(Number(code)))
    .replace(/&#x([0-9a-f]+);/giu, (_, code) => String.fromCodePoint(Number.parseInt(code, 16)))
    .replaceAll("&nbsp;", " ")
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'");
}

function htmlFallback(html, baseUrl) {
  const titleMatch =
    /<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']*)["'][^>]*>/iu.exec(html) ??
    /<title[^>]*>([\s\S]*?)<\/title>/iu.exec(html);
  const title = decodeHtml(titleMatch?.[1] ?? "").replace(/\s+/gu, " ").trim();
  const text = decodeHtml(
    html
      .replace(/<script\b[^>]*>[\s\S]*?<\/script>/giu, " ")
      .replace(/<style\b[^>]*>[\s\S]*?<\/style>/giu, " ")
      .replace(/<br\s*\/?\s*>/giu, "\n")
      .replace(/<\/p\s*>/giu, "\n")
      .replace(/<[^>]+>/gu, " "),
  )
    .replace(/[ \t]+/gu, " ")
    .replace(/\n\s+/gu, "\n")
    .replace(/\n{3,}/gu, "\n\n")
    .trim();
  const anchors = [];
  const seen = new Set();
  for (const match of html.matchAll(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/giu)) {
    try {
      const href = new URL(decodeHtml(match[1]), baseUrl).href;
      if (!/^https?:\/\//iu.test(href) || seen.has(href)) continue;
      seen.add(href);
      const anchor = {
        href,
        text: decodeHtml(match[2].replace(/<[^>]+>/gu, " ")).replace(/\s+/gu, " ").trim().slice(0, 300),
      };
      if (relevantAnchor(anchor)) anchors.push(anchor);
      if (anchors.length >= 300) break;
    } catch {
      // Ignore malformed third-party links.
    }
  }
  return { title, text, anchors };
}

async function crawlOne(context, item, timeoutMs) {
  const page = await context.newPage();
  const startedAt = new Date().toISOString();
  try {
    let response = null;
    let navigationError = null;
    try {
      response = await page.goto(item.url, {
        waitUntil: "domcontentloaded",
        timeout: timeoutMs,
      });
    } catch (error) {
      navigationError = error;
    }
    await page.waitForTimeout(2_000);
    let title = await page.title().catch(() => "");
    let finalUrl = page.url();
    let bodyText = await page.locator("body").innerText({ timeout: 5_000 }).catch(() => "");
    let anchors = await page
      .locator("a[href]")
      .evaluateAll((elements) =>
        elements.slice(0, 2_000).map((element) => ({
          text: String(element.textContent ?? "").replace(/\s+/gu, " ").trim().slice(0, 300),
          href: element.href,
        })),
      )
      .catch(() => []);
    let fallbackStatus = null;
    if (!bodyText.trim() && navigationError) {
      const fallbackResponse = await fetch(item.url, {
        headers: {
          "user-agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
            "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        },
        signal: AbortSignal.timeout(timeoutMs),
      });
      fallbackStatus = fallbackResponse.status;
      finalUrl = fallbackResponse.url || item.url;
      const parsed = htmlFallback(await fallbackResponse.text(), finalUrl);
      title = parsed.title || title;
      bodyText = parsed.text;
      anchors = parsed.anchors;
    }
    if (!bodyText.trim() && navigationError) throw navigationError;
    const uniqueAnchors = [];
    const seen = new Set();
    for (const anchor of anchors) {
      if (!/^https?:\/\//iu.test(anchor.href) || seen.has(anchor.href)) continue;
      seen.add(anchor.href);
      if (relevantAnchor(anchor)) uniqueAnchors.push(anchor);
      if (uniqueAnchors.length >= 300) break;
    }
    return {
      ...item,
      startedAt,
      finishedAt: new Date().toISOString(),
      status: response?.status() ?? fallbackStatus,
      finalUrl,
      title,
      accessState: accessState(bodyText, title, finalUrl),
      bodyText: bodyText.slice(0, 100_000),
      bodyLength: bodyText.length,
      relevantAnchors: uniqueAnchors,
      error: navigationError ? String(navigationError.message ?? navigationError).slice(0, 2_000) : null,
    };
  } catch (error) {
    return {
      ...item,
      startedAt,
      finishedAt: new Date().toISOString(),
      status: null,
      finalUrl: page.url(),
      title: "",
      accessState: "error",
      bodyText: "",
      bodyLength: 0,
      relevantAnchors: [],
      error: String(error?.message ?? error).slice(0, 2_000),
    };
  } finally {
    await page.close();
  }
}

async function runPool(items, concurrency, worker, onCheckpoint) {
  const results = new Array(items.length);
  let nextIndex = 0;
  let completed = 0;
  async function runWorker() {
    while (true) {
      const index = nextIndex;
      nextIndex += 1;
      if (index >= items.length) return;
      results[index] = await worker(items[index], index);
      completed += 1;
      if (completed % 10 === 0 || completed === items.length) {
        if (onCheckpoint) await onCheckpoint(results, completed);
        process.stdout.write(`Crawled ${completed}/${items.length}\n`);
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, runWorker));
  return results;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input || !args.output) {
    throw new Error("Required arguments: --input <collection.json> --output <crawl.json>");
  }
  const inputPath = path.resolve(String(args.input));
  const outputPath = path.resolve(String(args.output));
  const moduleRoot = path.resolve(
    String(args["module-root"] || process.env.JOB_COLLECTOR_NODE_MODULES || DEFAULT_MODULE_ROOT),
  );
  const edgePath = String(args.edge || DEFAULT_EDGE_PATH);
  const concurrency = Math.max(1, Math.min(12, Number(args.concurrency || 6)));
  const timeoutMs = Math.max(5_000, Math.min(120_000, Number(args.timeout || 25_000)));

  const source = JSON.parse(await fs.readFile(inputPath, "utf8"));
  const announcementColumn = source.headers.indexOf("公告链接");
  const applicationColumn = source.headers.indexOf("投递官网链接");
  if (announcementColumn < 0 || applicationColumn < 0) {
    throw new Error("Input JSON does not contain 公告链接 and 投递官网链接 columns");
  }

  const urlMap = new Map();
  for (const row of source.rows) {
    for (const [kind, column] of [
      ["announcement", announcementColumn],
      ["application", applicationColumn],
    ]) {
      for (const url of extractUrls(row.values[column])) {
        const existing = urlMap.get(url) ?? { url, references: [] };
        existing.references.push({ sourceRow: row.sourceRow, company: row.values[0], kind });
        urlMap.set(url, existing);
      }
    }
  }

  const runtimeRequire = createRequire(path.join(moduleRoot, "__codex_job_crawler__.cjs"));
  const { chromium } = runtimeRequire("playwright");
  const launchOptions = { headless: true };
  try {
    await fs.access(edgePath);
    launchOptions.executablePath = edgePath;
  } catch {
    launchOptions.channel = "msedge";
  }
  const browser = await chromium.launch(launchOptions);
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      locale: "zh-CN",
      userAgent:
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    });
    const items = [...urlMap.values()];
    let previousByUrl = new Map();
    if (args.resume) {
      try {
        const previous = JSON.parse(await fs.readFile(outputPath, "utf8"));
        previousByUrl = new Map(previous.results.map((result) => [result.url, result]));
      } catch {
        previousByUrl = new Map();
      }
    }
    const pendingItems = items.filter((item) => previousByUrl.get(item.url)?.accessState === "error" || !previousByUrl.has(item.url));
    await fs.mkdir(path.dirname(outputPath), { recursive: true });
    const writeSnapshot = async (currentResults, completed, isFinal = false) => {
      const currentByUrl = new Map(currentResults.filter(Boolean).map((result) => [result.url, result]));
      const results = items
        .map((item) => currentByUrl.get(item.url) ?? previousByUrl.get(item.url))
        .filter(Boolean);
      const payload = {
        source: inputPath,
        crawledAt: new Date().toISOString(),
        uniqueUrlCount: items.length,
        completedUrlCount: results.length,
        pendingUrlCount: items.length - results.length,
        checkpoint: !isFinal,
        results,
      };
      const temporaryPath = `${outputPath}.partial`;
      await fs.writeFile(temporaryPath, JSON.stringify(payload, null, 2), "utf8");
      await fs.rename(temporaryPath, outputPath).catch(async () => {
        await fs.copyFile(temporaryPath, outputPath);
        await fs.unlink(temporaryPath).catch(() => {});
      });
      return { results, completed };
    };
    const retried = await runPool(
      pendingItems,
      concurrency,
      (item) => crawlOne(context, item, timeoutMs),
      (currentResults, completed) => writeSnapshot(currentResults, completed),
    );
    const retriedByUrl = new Map(retried.map((result) => [result.url, result]));
    const results = items.map((item) => retriedByUrl.get(item.url) ?? previousByUrl.get(item.url));
    await writeSnapshot(retried, pendingItems.length, true);
    const summary = results.reduce((counts, result) => {
      counts[result.accessState] = (counts[result.accessState] ?? 0) + 1;
      return counts;
    }, {});
    process.stdout.write(`${JSON.stringify({ output: outputPath, summary }, null, 2)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message || String(error)}\n`);
  process.exitCode = 1;
});
