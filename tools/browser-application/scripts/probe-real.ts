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
if (!approvedPath) throw new Error('no approved manifest for company: ' + company);

const app = new ApplicationRuntime(root);
const answers = [{resumePath: 'personal.name', value: '测试候选人', sourceQuote: '测试候选人'}];
const transferApproval = '全部开始投递';

try {
  const prepared = await app.applicationPrepare(approvedPath, answers, transferApproval);
  console.error('PREPARE', JSON.stringify({company: prepared.company, job: prepared.job, resumeProfileLoaded: prepared.resumeProfileLoaded}));
  const snap = await app.browserStart();
  console.error('REAL_PAGE', JSON.stringify({
    url: snap.url, loginRequired: snap.loginRequired, captcha: snap.captcha, fieldCount: snap.fields.length,
    fields: snap.fields.map(f => ({name: f.name, label: f.label, kind: f.kind, widgetRole: f.widget?.role, multiSelect: f.widget?.multiSelect})),
    actions: snap.actions.map(a => ({label: a.label, kind: a.kind})).filter(a => a.label),
  }));
  const apply = snap.actions.find((a: any) => a.kind === 'expand');
  if (apply) {
    const after = await app.formAdvance(snap.snapshotId, apply.actionId);
    let deep = {};
    try {
      deep = await (app as any).bridge.page.evaluate(() => {
        const out: any = {iframes: 0, shadowRoots: 0, controls: []};
        const walk = (node: any) => {
          if (!node || node.nodeType !== 1) return;
          const tag = String(node.tagName || '').toLowerCase();
          if (tag === 'iframe') out.iframes++;
          if (['input', 'textarea', 'select'].includes(tag)) out.controls.push({tag, name: node.getAttribute('name') || node.id || '', type: node.getAttribute('type') || '', role: node.getAttribute('role') || ''});
          if (node.shadowRoot) { out.shadowRoots++; walk(node.shadowRoot); }
          for (const c of node.children || []) walk(c);
        };
        walk(document.body);
        out.loginTexts = (document.body.innerText.match(/[^\n]*(登录|注册|扫码|验证码|手机号|短信|立即登录)[^\n]*/g) || []).slice(0, 8);
        return out;
      });
    } catch {}
    console.error('AFTER_APPLY', JSON.stringify({
      url: after.url, loginRequired: after.loginRequired, captcha: after.captcha, fieldCount: after.fields.length,
      fields: after.fields.map(f => ({name: f.name, label: f.label, kind: f.kind, widgetRole: f.widget?.role, multiSelect: f.widget?.multiSelect})),
      actions: after.actions.map(a => ({label: a.label, kind: a.kind})).filter(a => a.label),
      deep,
    }));
  } else {
    console.error('AFTER_APPLY no expand/apply action found');
  }
} catch (e) {
  console.error('REAL_PAGE_ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
}
