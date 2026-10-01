import {ApplicationRuntime} from '../src/runtime.js';
import path from 'node:path';
import {readdir, readFile} from 'node:fs/promises';

const root = process.env.CODEX_APPLICATION_ROOT || path.resolve('../../');
const company = process.env.CODEX_APPLICATION_COMPANY || '作业帮';
const approvedDir = path.join(root, 'jobs', 'approved');
let approvedPath = '';
for (const name of await readdir(approvedDir)) {
  if (!name.toLowerCase().endsWith('.json')) continue;
  const data = JSON.parse(await readFile(path.join(approvedDir, name), 'utf8'));
  if (data.manifest?.company === company) { approvedPath = path.join(approvedDir, name); break; }
}
const app = new ApplicationRuntime(root);
try {
  await app.applicationPrepare(approvedPath, [{resumePath: 'personal.name', value: '测试候选人', sourceQuote: '测试候选人'}], '全部开始投递');
  let snap = await app.browserStart();
  const apply = snap.actions.find((a: any) => a.kind === 'expand');
  if (apply) snap = await app.formAdvance(snap.snapshotId, apply.actionId);
  const consent = snap.actions.find((a: any) => a.kind === 'consent');
  if (consent) snap = await app.formAdvance(snap.snapshotId, consent.actionId);
  for (let i = 0; i < 30 && snap.fields.length <= 1; i++) {
    await new Promise(r => setTimeout(r, 1000));
    try { snap = await app.formInspect(); } catch { continue; }
  }
  const page = (app as any).bridge.page;
  // Date picker: click birth date and dump panel
  await page.locator('input[placeholder="出生日期 (年龄)"]').first().click();
  await new Promise(r => setTimeout(r, 1000));
  const datePanel = await page.evaluate(`(() => {
    const nodes = Array.from(document.querySelectorAll('*')).filter((n) => {
      const c = String(n.className || '') + ' ' + String(n.getAttribute('role') || '');
      return /date|calendar|picker|day|year|month|cell|panel/i.test(c) && (n.innerText || '').trim() && (n.innerText || '').trim().length < 80;
    }).slice(0, 50).map((n) => ({tag: n.tagName.toLowerCase(), cls: String(n.className || '').slice(0, 70), role: n.getAttribute('role'), text: (n.innerText || '').trim().slice(0, 30)}));
    return nodes;
  })()`);
  console.error('DATE_PANEL', JSON.stringify(datePanel));
  await page.keyboard.press('Escape').catch(() => {});
  // School search: click school, type, dump options
  await page.locator('input[placeholder="请输入就读学校"]').first().click();
  await page.locator('input[placeholder="请输入就读学校"]').first().fill('上海大学');
  await new Promise(r => setTimeout(r, 1200));
  const schoolOptions = await page.evaluate(`(() => {
    const nodes = Array.from(document.querySelectorAll('*')).filter((n) => {
      const c = String(n.className || '');
      return /option|item|menu|select|result|school|search/i.test(c) && (n.innerText || '').trim() && (n.innerText || '').trim().includes('上海');
    }).slice(0, 40).map((n) => ({tag: n.tagName.toLowerCase(), cls: String(n.className || '').slice(0, 70), text: (n.innerText || '').trim().slice(0, 40)}));
    return nodes;
  })()`);
  console.error('SCHOOL_OPTIONS', JSON.stringify(schoolOptions));
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
}
