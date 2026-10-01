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
  console.error('DETAIL_FRAMES', JSON.stringify(snap.unsupportedFrames));
  try {
    console.error('IFRAME_DETAIL', JSON.stringify(await (app as any).bridge.page.evaluate(`Array.from(document.querySelectorAll('iframe')).map((f) => ({src: f.getAttribute('src') || '(inline)', visible: !!(f.getClientRects().length), w: f.offsetWidth, h: f.offsetHeight, title: f.title, name: f.name, id: f.id}))`)));
  } catch {}
  const apply = snap.actions.find((a: any) => a.kind === 'expand');
  if (apply) snap = await app.formAdvance(snap.snapshotId, apply.actionId);
  console.error('AFTER_APPLY_ACTIONS', JSON.stringify({url: snap.url, fieldCount: snap.fields.length, actions: snap.actions.filter((a: any) => a.label).map((a: any) => ({label: a.label, kind: a.kind}))}));
  const consent = snap.actions.find((a: any) => a.kind === 'consent');
  if (consent) snap = await app.formAdvance(snap.snapshotId, consent.actionId);
  for (let i = 0; i < 30 && snap.fields.length <= 1; i++) {
    await new Promise(r => setTimeout(r, 1000));
    try { snap = await app.formInspect(); } catch { continue; }
  }
  console.error('FORM_STATE', JSON.stringify({url: snap.url, fieldCount: snap.fields.length, fields: snap.fields.slice(0, 35).map((f: any) => ({id: f.fieldId, label: f.label, ph: f.placeholder, kind: f.kind, value: f.value}))}));
  const byPlaceholder = (ph: string) => snap.fields.find((f: any) => f.placeholder === ph || f.label === ph);
  const mappings: any[] = [];
  const map = (ph: string, resumePath: string) => {
    const f = byPlaceholder(ph);
    if (f && f.kind !== 'file') mappings.push({fieldId: f.fieldId, resumePath});
  };
  map('姓名', 'personal.fullName');
  map('邮箱', 'personal.email');
  map('请输入就读学校', 'educations.0.school');
  map('请输入专业名称', 'educations.0.major');
  map('公司名称', 'internships.0.company');
  map('职位名称', 'internships.0.title');
  map('内容', 'internships.0.description');
  const tillNow = snap.fields.find((f: any) => f.kind === 'checkbox_group' && (f.options || []).includes('至今'));
  if (tillNow) mappings.push({fieldId: tillNow.fieldId, value: ['至今'], sourceQuote: '至今'});
  // The three "请选择" selects are 性别 / 学历 / 学历. Fill the two 学历 with 本科.
  const selects = snap.fields.filter((f: any) => f.placeholder === '请选择');
  if (selects[0]) mappings.push({fieldId: selects[0].fieldId, value: '男', sourceQuote: '男', sensitiveApproval: '用户明确确认性别男'});
  for (const sel of selects.slice(1)) mappings.push({fieldId: sel.fieldId, resumePath: 'educations.0.degree'});
  console.error('MAPPING', JSON.stringify(mappings.map(m => ({fieldId: m.fieldId, resumePath: m.resumePath, value: m.value}))));
  if (!mappings.length) { console.error('NO_MAPPINGS'); } else {
    const result = await app.formFill(snap.snapshotId, mappings);
    const readback = result.snapshot.fields.filter((f: any) => !['', '输入职位关键字', '推荐码', '请选择'].includes(f.placeholder || f.label) && f.value !== '' && f.value !== undefined);
    console.error('FILLED', JSON.stringify(readback.map((f: any) => ({label: f.label, placeholder: f.placeholder, value: f.value}))));
    console.error('RESULTS', JSON.stringify(result.results));
  }
  const remaining = snap.fields.filter((f: any) => !mappings.some(m => m.fieldId === f.fieldId) && f.placeholder && f.placeholder !== '输入职位关键字' && f.placeholder !== '推荐码' && f.value === '').map((f: any) => ({fieldId: f.fieldId, label: f.label, placeholder: f.placeholder, kind: f.kind, required: f.required}));
  console.error('REMAINING', JSON.stringify(remaining));
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
}
