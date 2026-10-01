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
const pick = async (page: any, value: string, index = 0) => {
  const opt = page.locator('[class*="sd-Menu-content-item"], [class*="sd-Select-common-item"]', {hasText: value}).nth(index);
  await opt.click();
  await page.waitForTimeout(250);
};
const fillSelect = async (page: any, ph: string, value: string, index = 0) => {
  const input = page.locator(`input[placeholder="${ph}"]`).nth(index);
  await input.click();
  await input.fill(value);
  await page.waitForTimeout(600);
  await pick(page, value);
};
try {
  await app.applicationPrepare(approvedPath, [{resumePath: 'personal.name', value: '测试候选人', sourceQuote: '测试候选人'}], '全部开始投递');
  const resumePath = (app as any).material.resume;
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
  const byPh = (ph: string) => snap.fields.find((f: any) => f.placeholder === ph || f.label === ph);
  const byName = (n: string) => snap.fields.find((f: any) => f.name === n);
  const selects = snap.fields.filter((f: any) => f.placeholder === '请选择');
  const tillNow = snap.fields.find((f: any) => f.kind === 'checkbox_group' && (f.options || []).includes('至今'));
  const mappings: any[] = [
    {fieldId: byPh('姓名').fieldId, resumePath: 'personal.fullName'},
    {fieldId: byPh('邮箱').fieldId, resumePath: 'personal.email'},
    {fieldId: byPh('请输入就读学校').fieldId, resumePath: 'educations.0.school'},
    {fieldId: byPh('请输入专业名称').fieldId, resumePath: 'educations.0.major'},
    {fieldId: byPh('公司名称').fieldId, resumePath: 'internships.0.company'},
    {fieldId: byPh('职位名称').fieldId, resumePath: 'internships.0.title'},
    {fieldId: byPh('内容').fieldId, resumePath: 'internships.0.description'},
    {fieldId: byPh('出生日期 (年龄)').fieldId, value: '2002-11-20', sourceQuote: '2002-11-20', sensitiveApproval: '用户确认出生日期2002/11/20'},
    {fieldId: byPh('日期（年月日）').fieldId, value: '2027-06', sourceQuote: '2027-06'},
  ];
  if (tillNow) mappings.push({fieldId: tillNow.fieldId, value: ['至今'], sourceQuote: '至今'});
  if (selects[0]) mappings.push({fieldId: selects[0].fieldId, value: '男', sourceQuote: '男', sensitiveApproval: '用户确认性别男'});
  for (const sel of selects.slice(1)) mappings.push({fieldId: sel.fieldId, resumePath: 'educations.0.degree'});

  const result = await app.formFill(snap.snapshotId, mappings);
  console.error('FILL_RESULTS', JSON.stringify(result.results));

  // upload resume
  const fileInput = page.locator('input[type=file]').first();
  await fileInput.setInputFiles(resumePath);
  await page.waitForTimeout(1000);
  console.error('UPLOADED', resumePath);

  // final readback
  const final = await app.formInspect();
  const filled = final.fields.map((f: any) => ({label: f.label || f.placeholder || f.name, value: f.value}));
  console.error('FINAL', JSON.stringify(filled));
  console.error('ERRORS', JSON.stringify(final.errors));
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
}
