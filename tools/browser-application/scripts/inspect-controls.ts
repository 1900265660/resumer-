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
  const targets = ['请选择', '请输入就读学校', '请输入专业名称', '出生日期 (年龄)', '日期（年月日）'];
  const dump = await (app as any).bridge.page.evaluate(`(() => {
    const out = [];
    const seen = new Set();
    for (const ph of ${JSON.stringify(targets)}) {
      const el = [...document.querySelectorAll('input')].find((n) => n.placeholder === ph || n.getAttribute('placeholder') === ph);
      if (!el) { out.push({ph, found: false}); continue; }
      if (seen.has(el)) continue;
      seen.add(el);
      const parent = el.parentElement;
      out.push({
        ph,
        tag: el.tagName.toLowerCase(),
        type: el.type,
        readonly: el.readOnly,
        role: el.getAttribute('role'),
        ariaAutocomplete: el.getAttribute('aria-autocomplete'),
        ariaExpanded: el.getAttribute('aria-expanded'),
        ariaHaspopup: el.getAttribute('aria-haspopup'),
        cls: String(el.className || '').slice(0, 80),
        parentCls: String(parent?.className || '').slice(0, 120),
        parentHtml: (parent?.outerHTML || '').slice(0, 300),
      });
    }
    return out;
  })()`);
  console.error('CONTROLS', JSON.stringify(dump));
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
}
