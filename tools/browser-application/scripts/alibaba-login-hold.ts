import {ApplicationRuntime} from '../src/runtime.js';
import path from 'node:path';
import {readdir, readFile} from 'node:fs/promises';

const root = process.env.CODEX_APPLICATION_ROOT || path.resolve('../../');
const jobTitle = '游戏策划（卡牌）';
const approvedDir = path.join(root, 'jobs', 'approved');
let approvedPath = '';
for (const name of await readdir(approvedDir)) {
  if (!name.toLowerCase().endsWith('.json')) continue;
  const data = JSON.parse(await readFile(path.join(approvedDir, name), 'utf8'));
  if (data.manifest?.job_title === jobTitle) { approvedPath = path.join(approvedDir, name); break; }
}
if (!approvedPath) throw new Error('no approved manifest for job: ' + jobTitle);
const app = new ApplicationRuntime(root);
try {
  await app.applicationPrepare(approvedPath, [{resumePath: 'personal.name', value: '测试候选人', sourceQuote: '测试候选人'}], '全部开始投递');
  let snap = await app.browserStart();
  const page = (app as any).bridge.page;
  console.error('OPENED', JSON.stringify({job: jobTitle, url: page.url()}));
  const add = page.locator('text=加入意向单').first();
  if (await add.count()) {
    await add.click();
    await page.waitForTimeout(2500);
  }
  console.error('AFTER_ADD', JSON.stringify({url: page.url(), loginText: /mozi-login|密码登录|短信登录/.test(await page.locator('body').innerText())}));
  console.error('LOGIN_REQUIRED: 请在打开的浏览器窗口完成阿里账号登录（密码或短信），脚本每 3 秒检测一次');
  for (let i = 0; i < 160; i++) {
    await new Promise(r => setTimeout(r, 3000));
    try {
      const url = page.url();
      if (!/mozi-login/.test(url)) {
        const body = await page.locator('body').innerText();
        if (!/密码登录|短信登录|登录/.test(body.slice(0, 300))) {
          console.error('LOGGED_IN', JSON.stringify({url}));
          break;
        }
      }
    } catch { continue; }
    if (i % 10 === 9) console.error('WAITING_LOGIN');
  }
  const state = await page.evaluate(`(() => ({
    url: location.href,
    body: document.body.innerText.slice(0, 2000),
    inputs: Array.from(document.querySelectorAll('input,textarea,select')).map(n => ({tag: n.tagName.toLowerCase(), type: n.type, ph: n.placeholder, role: n.getAttribute('role')})).slice(0, 30),
    buttons: Array.from(document.querySelectorAll('button,a')).map(n => (n.innerText || '').trim()).filter(Boolean).slice(0, 35),
  }))()`);
  console.error('POST_LOGIN', JSON.stringify(state));
  await new Promise(() => {});
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
  await app.applicationClose();
}
