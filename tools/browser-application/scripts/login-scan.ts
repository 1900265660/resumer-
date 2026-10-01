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
if (!approvedPath) throw new Error('no approved manifest for company: ' + company);

const app = new ApplicationRuntime(root);
const answers = [{resumePath: 'personal.name', value: '测试候选人', sourceQuote: '测试候选人'}];
try {
  const prepared = await app.applicationPrepare(approvedPath, answers, '全部开始投递');
  let snap = await app.browserStart();
  console.error('OPENED', JSON.stringify({company: prepared.company, job: prepared.job, loginRequired: snap.loginRequired, captcha: snap.captcha}));
  if (snap.loginRequired || snap.captcha) {
    console.error('LOGIN_REQUIRED: 请在打开的浏览器窗口完成登录/验证，脚本会每 3 秒检测一次');
    for (let i = 0; i < 120; i++) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        snap = await app.formInspect();
      } catch { continue; }
      if (!snap.loginRequired && !snap.captcha) break;
      if (i % 10 === 9) console.error('WAITING_LOGIN', JSON.stringify({loginRequired: snap.loginRequired, captcha: snap.captcha}));
    }
    if (snap.loginRequired || snap.captcha) {
      console.error('LOGIN_TIMEOUT');
    } else {
      console.error('LOGGED_IN');
    }
  }
  const apply = snap.actions.find((a: any) => a.kind === 'expand');
  if (apply) {
    console.error('CLICK_APPLY', apply.label);
    snap = await app.formAdvance(snap.snapshotId, apply.actionId);
  }
  const out = {
    url: snap.url, title: snap.title, loginRequired: snap.loginRequired, captcha: snap.captcha,
    fieldCount: snap.fields.length,
    fields: snap.fields.map((f: any) => ({fieldId: f.fieldId, name: f.name, label: f.label, kind: f.kind, placeholder: f.placeholder, options: f.options, required: f.required, widgetRole: f.widget?.role, multiSelect: f.widget?.multiSelect, value: f.value})),
    actions: snap.actions.map((a: any) => ({actionId: a.actionId, label: a.label, kind: a.kind, disabled: a.disabled})).filter((a: any) => a.label),
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
