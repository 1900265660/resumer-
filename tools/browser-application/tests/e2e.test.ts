import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {readFile} from 'node:fs/promises';
import {ApplicationRuntime} from '../src/runtime.js';
import {fixture, answers, approval} from './fixture.js';
import {moduleDir} from '../src/browser.js';

test('real visible Chromium extension: dynamic form, stale snapshot, pause, upload, human confirmation, receipt', {timeout: 180000}, async t => {
  const f = await fixture(); t.after(f.close);
  const app = new ApplicationRuntime(f.root); t.after(() => app.applicationClose());
  await app.applicationPrepare(f.approvedPath, answers, approval);
  let s: any = await app.browserStart();
  assert.equal(s.fields.length, 6, JSON.stringify(s.fields));
  const cityField = s.fields.find((f: any) => f.name === 'cities');
  assert.equal(cityField.widget.role, 'combobox');
  assert.equal(cityField.widget.multiSelect, true);
  s = (await app.formFill(s.snapshotId, [{fieldId: cityField.fieldId, resumePath: 'preferences.cities'}])).snapshot;
  assert.deepEqual(s.fields.find((f: any) => f.name === 'cities').value, ['上海市', '广州市']);
  await assert.rejects(app.formFill(s.snapshotId, [{fieldId: cityField.fieldId, resumePath: 'educations.0.school'}]), /existing_value_conflict/);
  await app.bridge!.page.evaluate(() => {
    const label = document.createElement('label'); label.id = 'sensitive-test'; label.textContent = '期望薪资';
    const input = document.createElement('input'); input.name = 'salary'; label.append(input); document.querySelector('form')!.append(label);
  });
  s = await app.formInspect();
  await assert.rejects(app.formFill(s.snapshotId, [{fieldId: s.fields.find((f: any) => f.name === 'salary').fieldId, resumePath: 'personal.name'}]), /sensitive_answer/);
  await app.bridge!.page.locator('#sensitive-test').evaluate(el => el.remove());
  await app.bridge!.page.evaluate(() => {const input = document.createElement('input'); input.type = 'password'; input.id = 'login-test'; document.body.append(input);});
  s = await app.formInspect(); assert.equal(s.loginRequired, true);
  await assert.rejects(app.formFill(s.snapshotId, [{fieldId: s.fields[0].fieldId, resumePath: 'personal.name'}]), /login_or_captcha/);
  await app.bridge!.page.locator('#login-test').evaluate(el => el.remove());
  s = await app.applicationResume();
  await app.bridge!.page.evaluate(() => {const button = document.createElement('button'); button.type = 'button'; button.id = 'noop'; button.textContent = '添加教育经历'; document.body.append(button);});
  s = await app.formInspect();
  s = await app.formAdvance(s.snapshotId, s.actions.find((a: any) => a.label === '添加教育经历').actionId);
  await assert.rejects(app.formAdvance(s.snapshotId, s.actions.find((a: any) => a.label === '添加教育经历').actionId), /repeated_failure/);
  await app.bridge!.page.locator('#noop').evaluate(el => el.remove());
  s = await app.applicationResume();
  const field = (name: string) => s.fields.find((x: any) => x.name === name).fieldId;
  const old = s.snapshotId;
  await app.bridge!.page.locator('[name=name]').fill('手动修改');
  await assert.rejects(app.formFill(old, [{fieldId: field('name'), resumePath: 'personal.name'}]), /stale_snapshot/);
  s = await app.formInspect();
  await assert.rejects(app.formFill(s.snapshotId, [{fieldId: field('name'), resumePath: 'personal.name'}]), /existing_value_conflict/);
  await app.bridge!.page.locator('[name=name]').fill('');
  s = await app.formInspect();
  s = (await app.formFill(s.snapshotId, [
    ['name', 'personal.name'], ['email', 'personal.email'], ['school', 'educations.0.school'], ['degree', 'educations.0.degree'], ['start', 'educations.0.start'],
  ].map(([n, p]) => ({fieldId: field(n), resumePath: p})))).snapshot;
  s = await app.formAdvance(s.snapshotId, s.actions.find((a: any) => a.kind === 'add').actionId);
  s = (await app.formFill(s.snapshotId, [{fieldId: field('project'), resumePath: 'projects.0.name'}])).snapshot;
  // Mimics a human pausing in the extension UI; not a production MCP capability.
  await app.bridge!.showPanel();
  await app.bridge!.panel!.locator('#pause').click();
  await assert.rejects(app.formAdvance(s.snapshotId, s.actions.find((a: any) => a.kind === 'next').actionId), /user_paused/);
  s = await app.applicationResume();
  s = await app.formAdvance(s.snapshotId, s.actions.find((a: any) => a.kind === 'next').actionId);
  assert.equal(s.fields.length, 2);
  await assert.rejects(app.formAdvance(s.snapshotId, s.actions.find((a: any) => a.kind === 'submit').actionId), /not_a_navigation/);
  s = (await app.formFill(s.snapshotId, [{fieldId: field('intro'), resumePath: 'additional.intro'}])).snapshot;
  s = (await app.attachmentUpload(s.snapshotId, field('resume'))).snapshot;
  let pending = await app.submissionPrepare(s.snapshotId, s.actions.find((a: any) => a.kind === 'submit').actionId);
  await app.bridge!.panel!.screenshot({path: path.join(moduleDir, '.local', 'acceptance-review.png'), fullPage: true});
  await assert.rejects(app.submissionCommit(pending.digest), /confirmation_required/);
  // Browser input is the test's synthetic user, exercising the real consent UI.
  await app.bridge!.panel!.locator('#confirm').click();
  await app.bridge!.page.locator('[name=intro]').fill('变更');
  await assert.rejects(app.submissionCommit(pending.digest), /changed_reconfirm/);
  await app.bridge!.page.locator('[name=intro]').fill('这是已确认的模拟介绍。');
  s = await app.formInspect();
  pending = await app.submissionPrepare(s.snapshotId, s.actions.find((a: any) => a.kind === 'submit').actionId);
  await app.bridge!.panel!.locator('#confirm').click();
  const result = await app.submissionCommit(pending.digest);
  assert.equal(result.status, 'submitted');
  assert.equal(await app.bridge!.page.evaluate(() => (window as any).submitCount), 1);
  await assert.rejects(app.submissionCommit(pending.digest), /already_attempted/);
  const receipt = await readFile(path.join(f.dir, 'receipt.md'), 'utf8');
  assert.match(receipt, /投递成功/);
  assert.doesNotMatch(receipt, /candidate@example/);
  const checkpoint = await readFile(path.join(f.dir, 'browser-application/checkpoint.json'), 'utf8');
  assert.doesNotMatch(checkpoint, /测试候选人|candidate@example/);
});

test('submit timeout survives a process-level restart without a second click', {timeout: 180000}, async t => {
  const f = await fixture(); t.after(f.close);
  const app = new ApplicationRuntime(f.root); t.after(() => app.applicationClose());
  await app.applicationPrepare(f.approvedPath, answers, approval);
  let s: any = await app.browserStart();
  s = (await app.formFill(s.snapshotId, [
    ['name', 'personal.name'], ['email', 'personal.email'], ['school', 'educations.0.school'], ['degree', 'educations.0.degree'], ['start', 'educations.0.start'],
  ].map(([name, resumePath]) => ({fieldId: s.fields.find((f: any) => f.name === name).fieldId, resumePath})))).snapshot;
  s = await app.formAdvance(s.snapshotId, s.actions.find((a: any) => a.kind === 'next').actionId);
  s = (await app.formFill(s.snapshotId, [{fieldId: s.fields.find((f: any) => f.name === 'intro').fieldId, resumePath: 'additional.intro'}])).snapshot;
  s = (await app.attachmentUpload(s.snapshotId, s.fields.find((f: any) => f.kind === 'file').fieldId)).snapshot;
  await app.bridge!.page.evaluate(() => history.replaceState({}, '', '/apply?step=2&unknown=1'));
  s = await app.formInspect();
  const pending = await app.submissionPrepare(s.snapshotId, s.actions.find((a: any) => a.kind === 'submit').actionId);
  await app.bridge!.panel!.locator('#confirm').click();
  assert.equal((await app.submissionCommit(pending.digest)).status, 'submission_unknown');
  assert.equal(await app.bridge!.page.evaluate(() => (window as any).submitCount), 1);
  await app.applicationClose();
  const resumed = new ApplicationRuntime(f.root); t.after(() => resumed.applicationClose());
  assert.equal((await resumed.applicationPrepare(f.approvedPath, answers, approval)).status, 'resume_required');
  assert.equal((await resumed.applicationResume()).status, 'submission_unknown');
  assert.equal(await resumed.bridge!.page.evaluate(() => (window as any).submitCount), 0, 'restoration never clicks');
  await assert.rejects(resumed.submissionCommit(pending.digest), /already_attempted/);
});
