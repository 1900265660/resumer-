import {ApplicationRuntime} from '../src/runtime.js';
import path from 'node:path';
import {readdir, readFile} from 'node:fs/promises';

const root = process.env.CODEX_APPLICATION_ROOT || path.resolve('../../');
const company = process.env.CODEX_APPLICATION_COMPANY || '灵犀互娱';
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
  const page = (app as any).bridge.page;
  // click 加入意向单 and see what happens
  const add = page.locator('text=加入意向单').first();
  if (await add.count()) {
    await add.click();
    await page.waitForTimeout(2500);
  }
  const state = await page.evaluate(`(() => ({
    url: location.href,
    body: document.body.innerText.slice(0, 1500),
    inputs: Array.from(document.querySelectorAll('input,textarea,select')).map(n => ({tag: n.tagName.toLowerCase(), type: n.type, ph: n.placeholder, role: n.getAttribute('role')})).slice(0, 20),
    buttons: Array.from(document.querySelectorAll('button,a')).map(n => (n.innerText || '').trim()).filter(Boolean).slice(0, 25),
  }))()`);
  console.error('ALIBABA', JSON.stringify(state));
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
}
