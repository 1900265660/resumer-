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
  const birth = snap.fields.find((f: any) => f.placeholder === '出生日期 (年龄)');
  const mappings = [{fieldId: birth.fieldId, value: '2002-11-20', sourceQuote: '2002-11-20', sensitiveApproval: '用户确认出生日期2002/11/20'}];
  const result = await app.formFill(snap.snapshotId, mappings);
  const readback = result.snapshot.fields.find((f: any) => f.placeholder === '出生日期 (年龄)');
  console.error('DATE_RESULT', JSON.stringify({results: result.results, value: readback.value}));
} catch (e) {
  console.error('ERROR', e instanceof Error ? e.message : String(e));
} finally {
  await app.applicationClose();
}
