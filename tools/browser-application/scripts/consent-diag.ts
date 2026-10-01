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
  const dump = await (app as any).bridge.page.evaluate(`(() => {
    const clickables = [];
    const walk = (node) => {
      if (!node || node.nodeType !== 1) return;
      const tag = String(node.tagName || '').toLowerCase();
      const text = (node.innerText || node.value || node.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ').slice(0, 40);
      if (['button','a','input','label','span','div','i','em','strong'].includes(tag) && text && /同意|阅读|协议|隐私|开始|填写|继续|确认|下一步|投递|申请|提交/.test(text)) {
        clickables.push({tag, text, role: node.getAttribute('role') || '', type: node.getAttribute('type') || '', ariaChecked: node.getAttribute('aria-checked') || '', cls: String(node.className || '').slice(0, 60)});
      }
      if (node.shadowRoot) walk(node.shadowRoot);
      for (const c of node.children || []) walk(c);
    };
    walk(document.body);
    const inputs = Array.from(document.querySelectorAll('input,textarea,select')).map((el) => ({tag: el.tagName.toLowerCase(), type: el.type, name: el.name, placeholder: el.placeholder, value: el.value, checked: el.checked, role: el.getAttribute('role')}));
    return {clickables, inputs, body: document.body.innerText.slice(0, 3000)};
  })()`);
  console.error('DIAG', JSON.stringify(dump));
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
}
