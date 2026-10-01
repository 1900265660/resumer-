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
  const pickOption = async (optionText: string) => {
    const opt = page.locator('.sd-Select-common-item', { hasText: optionText }).first();
    await opt.click();
    await page.waitForTimeout(300);
  };
  // gender: click first 请选择, pick 男
  await page.locator('input[placeholder="请选择"]').first().click();
  await page.waitForTimeout(500);
  await pickOption('男');
  // school: fill search, pick 上海大学
  const school = page.locator('input[placeholder="请输入就读学校"]').first();
  await school.click();
  await school.fill('上海大学');
  await page.waitForTimeout(1200);
  await pickOption('上海大学');
  // major: fill search, pick 社会工作
  const major = page.locator('input[placeholder="请输入专业名称"]').first();
  await major.click();
  await major.fill('社会工作');
  await page.waitForTimeout(1200);
  await pickOption('社会工作（本科二学位）');
  // readback
  const readback = await page.evaluate(`(() => {
    const display = (sel) => { const el = document.querySelector(sel); const s = el?.parentElement?.querySelector?.('.sd-Input-display-value'); return (s?.innerText || el?.value || '').trim(); };
    return {
      gender: display('input[placeholder="请选择"]'),
      school: display('input[placeholder="请输入就读学校"]'),
      major: display('input[placeholder="请输入专业名称"]'),
    };
  })()`);
  console.error('PW_FILL_RESULT', JSON.stringify(readback));
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
}
