import {ApplicationRuntime} from '../src/runtime.js';
import path from 'node:path';
import {readdir, readFile, writeFile, mkdir} from 'node:fs/promises';

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
  if (!apply) { console.error('NO_APPLY'); } else {
    snap = await app.formAdvance(snap.snapshotId, apply.actionId);
    const hasConsent = snap.actions.some((a: any) => a.kind === 'consent');
    console.error('AFTER_APPLY', JSON.stringify({url: snap.url, consentVisible: hasConsent, fieldCount: snap.fields.length, actions: snap.actions.filter((a: any) => a.label).map((a: any) => ({label: a.label, kind: a.kind}))}));
    if (hasConsent) {
      console.error('CONSENT_REQUIRED: 请在浏览器里亲自点击「我已阅读并同意」，脚本每 3 秒检测一次');
      for (let i = 0; i < 120; i++) {
        await new Promise(r => setTimeout(r, 3000));
        try { snap = await app.formInspect(); } catch { continue; }
        const stillConsent = snap.actions.some((a: any) => a.kind === 'consent');
        if (!stillConsent && (snap.fields.length > 1 || /\/apply/.test(snap.url))) break;
        if (i % 10 === 9) console.error('WAITING_CONSENT', JSON.stringify({consent: stillConsent, fieldCount: snap.fields.length, url: snap.url}));
      }
    }
  }
  const out = {
    url: snap.url, loginRequired: snap.loginRequired, fieldCount: snap.fields.length,
    fields: snap.fields.map((f: any) => ({fieldId: f.fieldId, name: f.name, label: f.label, kind: f.kind, placeholder: f.placeholder, options: f.options, required: f.required, widgetRole: f.widget?.role, multiSelect: f.widget?.multiSelect, value: f.value})),
    actions: snap.actions.filter((a: any) => a.label).map((a: any) => ({actionId: a.actionId, label: a.label, kind: a.kind, disabled: a.disabled})),
    errors: snap.errors,
  };
  await mkdir(path.join(root, 'tools', 'browser-application', '.local'), {recursive: true});
  await writeFile(path.join(root, 'tools', 'browser-application', '.local', 'real-scan.json'), JSON.stringify(out, null, 2));
  console.error('SCAN_DONE', JSON.stringify(out));
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
  console.error('CLOSED');
}
