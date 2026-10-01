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
  const dump = await page.evaluate(`(() => {
    const out = [];
    const labels = ['就读时间', '起止时间', '日期（年月日）', '目前职位'];
    for (const ph of labels) {
      const els = [...document.querySelectorAll('input')].filter((n) => n.placeholder === ph || (n.getAttribute('placeholder') || '').includes(ph));
      for (const el of els) {
        const parent = el.parentElement?.parentElement;
        out.push({
          ph: el.getAttribute('placeholder'),
          type: el.type,
          readonly: el.readOnly,
          role: el.getAttribute('role'),
          aria: el.getAttribute('aria-label') || el.getAttribute('aria-haspopup') || '',
          parentCls: String(parent?.className || '').slice(0, 100),
        });
      }
    }
    // the 年/月 month inputs
    const monthInputs = [...document.querySelectorAll('input')].filter((n) => ['年','月'].includes(n.placeholder)).map((n) => ({
      ph: n.placeholder, readonly: n.readOnly, role: n.getAttribute('role'), cls: String(n.className || '').slice(0,60), parentCls: String(n.parentElement?.className || '').slice(0,80),
    }));
    return {out, monthInputs};
  })()`);
  console.error('DATE_RANGE', JSON.stringify(dump));
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
}
