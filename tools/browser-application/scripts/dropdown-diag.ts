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
  // Click the first "请选择" select and dump its dropdown
  await page.locator('input[placeholder="请选择"]').first().click();
  await new Promise(r => setTimeout(r, 1500));
  const dump = await page.evaluate(`(() => {
    const portals = Array.from(document.querySelectorAll('.sugar-portal')).map((p) => p.innerText.trim()).filter(Boolean);
    const optionish = Array.from(document.querySelectorAll('*')).filter((n) => {
      const c = String(n.className || '') + ' ' + String(n.getAttribute('role') || '');
      return /option|menu|dropdown|listbox|popup|select/i.test(c) && (n.innerText || '').trim();
    }).slice(0, 60).map((n) => ({tag: n.tagName.toLowerCase(), cls: String(n.className || '').slice(0, 60), role: n.getAttribute('role'), text: (n.innerText || '').trim().slice(0, 40)}));
    return {portals, optionish};
  })()`);
  console.error('DUMP', JSON.stringify(dump));
  await page.keyboard.press('Escape');
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
}
