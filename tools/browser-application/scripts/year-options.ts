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
  await page.locator('input[placeholder="年"]').first().click();
  await page.waitForTimeout(800);
  const dump = await page.evaluate(`(() => {
    const all = Array.from(document.querySelectorAll('*')).filter((n) => {
      const c = String(n.className || '') + ' ' + String(n.getAttribute('role') || '');
      return /option|item|menu|select|year/i.test(c) && (n.innerText || '').trim() && (n.innerText || '').trim().length < 30;
    }).slice(0, 40).map((n) => ({cls: String(n.className || '').slice(0, 70), role: n.getAttribute('role'), text: (n.innerText || '').trim().slice(0, 20)}));
    return all;
  })()`);
  console.error('YEAR_OPTIONS', JSON.stringify(dump));
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
}
