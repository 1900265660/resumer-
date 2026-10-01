import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {writeFile} from 'node:fs/promises';
import {prepare, validateAnswers, canonicalUrl, within, revalidate} from '../src/materials.js';
import {fixture, answers, approval} from './fixture.js';
import {acquireWorkspace} from '../src/lock.js';

test('approved answers cannot invent facts, draft open questions or sensitive consent', () => {
  validateAnswers(answers, answers.map(a => a.sourceQuote).join('\n'));
  assert.throws(() => validateAnswers([{...answers[0], value: '不存在'}], answers[0].sourceQuote), /value_not_in_quote/);
  assert.throws(() => validateAnswers([{...answers[0], sourceQuote: '由 Codex 草拟', value: '草拟'}], '由 Codex 草拟'), /not_approved/);
  assert.throws(() => validateAnswers([{...answers[0], sensitiveApproval: '姓名'}], answers[0].sourceQuote), /sensitive_approval/);
  assert.throws(() => validateAnswers([answers[0], answers[0]], answers[0].sourceQuote), /duplicate/);
});
test('URL normalization preserves actual job identity including SPA routes', () => {
  assert.equal(canonicalUrl('https://a.test/?sessionid=secret#/job/123'), 'https://a.test/#/job/123');
  assert.notEqual(canonicalUrl('https://a.test/#/job/123'), canonicalUrl('https://a.test/#/job/456'));
});
test('real PowerShell approval validation, path boundary, stale attachment and duplicate receipt', async t => {
  const f = await fixture(); t.after(f.close);
  const m = await prepare(f.root, f.approvedPath, answers, approval);
  const release = await acquireWorkspace(f.root);
  await assert.rejects(acquireWorkspace(f.root), /already_running/);
  await release();
  assert.equal(m.company, '模拟公司');
  await assert.rejects(within(path.join(f.root, 'jobs'), '../AGENTS.md'), /outside/);
  await writeFile(path.join(f.dir, 'receipt.md'), '已成功');
  await assert.rejects(prepare(f.root, f.approvedPath, answers, approval), /receipt/);
  await writeFile(m.resume, 'changed');
  await assert.rejects(revalidate(m), /changed/);
});
