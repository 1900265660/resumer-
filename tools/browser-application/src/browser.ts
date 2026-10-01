import './environment.js';
import {chromium, type BrowserContext, type Page, type Worker} from 'playwright';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {exists} from './materials.js';

export const moduleDir = fileURLToPath(new URL('../', import.meta.url));
const exec = promisify(execFile);
export async function ensureBrowser() {
  if (await exists(chromium.executablePath())) return;
  const cli = path.join(moduleDir, 'node_modules', 'playwright', 'cli.js');
  await exec(process.execPath, [cli, 'install', 'chromium', '--no-shell', '--no-remove'], {timeout: 300000, maxBuffer: 4 * 1024 * 1024});
}
export class BrowserBridge {
  context!: BrowserContext;
  page!: Page;
  worker!: Worker;
  tabId!: number;
  extensionId!: string;
  panel?: Page;
  async start(profile: string, url: string) {
    await ensureBrowser();
    const extension = path.join(moduleDir, 'extension');
    this.context = await chromium.launchPersistentContext(profile, {channel: 'chromium', headless: false,
      args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]});
    this.context.setDefaultTimeout(10000);
    this.worker = this.context.serviceWorkers()[0] || await this.context.waitForEvent('serviceworker');
    this.extensionId = new URL(this.worker.url()).host;
    this.page = this.context.pages()[0] || await this.context.newPage();
    await this.page.goto(url, {waitUntil: 'domcontentloaded'});
    const tabs = await this.worker.evaluate(async () => (globalThis as any).chrome.tabs.query({}));
    const tab = tabs.find((t: any) => t.url === this.page.url());
    if (!tab) throw new Error('browser_tab_not_found');
    this.tabId = tab.id;
  }
  async state(patch?: Record<string, unknown>): Promise<any> {
    await this.ensureWorker();
    return this.worker.evaluate(async (patch) => {
      const chrome = (globalThis as any).chrome;
      const old = (await chrome.storage.local.get('codexState')).codexState || {};
      if (patch) await chrome.storage.local.set({codexState: {...old, ...patch}});
      return patch ? {...old, ...patch} : old;
    }, patch);
  }
  async command(message: Record<string, unknown>): Promise<any> {
    await this.ensureWorker();
    // Only fixed extension commands enter the isolated extension worker.
    return this.worker.evaluate(async ({tabId, message}) => (globalThis as any).codexCommand(tabId, message), {tabId: this.tabId, message});
  }
  private async ensureWorker() {
    try {
      // A suspended MV3 service worker restarts on demand through the same handle.
      // If it was genuinely torn down, re-acquire the current worker once.
      if (this.worker && await this.worker.evaluate(() => true)) return;
    } catch {
      this.worker = this.context.serviceWorkers()[0] || await this.context.waitForEvent('serviceworker', {timeout: 10000});
    }
  }
  async showPanel() {
    if (!this.panel || this.panel.isClosed()) this.panel = await this.context.newPage();
    await this.panel.goto(`chrome-extension://${this.extensionId}/codex-panel.html`);
    await this.panel.bringToFront();
  }
  async close() {await this.context?.close();}
}
