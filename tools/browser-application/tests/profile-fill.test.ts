import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {mkdir, writeFile} from 'node:fs/promises';
import {ApplicationRuntime} from '../src/runtime.js';
import {fixture, answers, approval} from './fixture.js';

test('fills a page from a full structured resume profile, including a textbox multi-select city widget', {timeout: 120000}, async t => {
  const f = await fixture();
  t.after(f.close);
  await mkdir(path.join(f.root, 'outputs', 'ai-resume-imports'), {recursive: true});
  await writeFile(path.join(f.root, 'outputs', 'ai-resume-imports', '模拟公司_AI产品经理.json'), JSON.stringify({
    profile: {
      personal: {fullName: '测试候选人', email: 'candidate@example.test', phoneNumber: '13800138000', currentCity: '上海'},
      educations: [{school: '模拟大学', degree: '本科', major: '计算机科学', startDate: '2021-09', endDate: '2025-06'}],
      projects: [{name: '模拟项目', role: '负责人'}],
    },
  }));

  const app = new ApplicationRuntime(f.root);
  t.after(() => app.applicationClose());
  const prepared = await app.applicationPrepare(f.approvedPath, answers, approval);
  assert.equal(prepared.resumeProfileLoaded, true);

  let s: any = await app.browserStart();
  const tOpen = Date.now();
  await app.bridge!.page.evaluate(() => {
    const input = document.createElement('input');
    input.id = 'city'; input.name = 'city';
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-haspopup', 'listbox');
    input.setAttribute('aria-controls', 'city-list');
    input.setAttribute('aria-expanded', 'false');
    input.addEventListener('click', () => {
      const expanded = input.getAttribute('aria-expanded') === 'true';
      input.setAttribute('aria-expanded', expanded ? 'false' : 'true');
    });
    const list = document.createElement('ul');
    list.id = 'city-list'; list.setAttribute('role', 'listbox'); list.setAttribute('aria-multiselectable', 'true');
    list.style.margin = '0'; list.style.padding = '0';
    for (const name of ['上海', '广州', '北京']) {
      const li = document.createElement('li');
      li.setAttribute('role', 'option'); li.setAttribute('aria-selected', 'false');
      li.style.listStyle = 'none'; li.textContent = name;
      li.addEventListener('click', () => li.setAttribute('aria-selected', li.getAttribute('aria-selected') === 'true' ? 'false' : 'true'));
      list.append(li);
    }
    const label = document.createElement('label'); label.textContent = '意向城市';
    label.append(input, list);
    document.querySelector('form')!.prepend(label);

    const mokaWrapper = document.createElement('div');
    mokaWrapper.className = 'sd-Select-container-hash';
    const mokaInput = document.createElement('input');
    mokaInput.id = 'moka-school'; mokaInput.name = 'mokaSchool';
    mokaInput.placeholder = '院校检索';
    const display = document.createElement('span');
    display.className = 'sd-Input-display-value-hash';
    const mokaOptions = document.createElement('div');
    mokaOptions.hidden = true;
    for (const name of ['模拟大学', '另一所大学']) {
      const option = document.createElement('button');
      option.type = 'button'; option.className = 'sd-Select-common-item-hash'; option.textContent = name;
      option.addEventListener('click', () => { display.textContent = name; mokaOptions.hidden = true; });
      mokaOptions.append(option);
    }
    mokaInput.addEventListener('click', () => { mokaOptions.hidden = false; });
    mokaWrapper.append(mokaInput, display, mokaOptions);
    const mokaLabel = document.createElement('label'); mokaLabel.textContent = 'Moka 学校'; mokaLabel.append(mokaWrapper);
    document.querySelector('form')!.prepend(mokaLabel);
  });

  s = await app.formInspect();
  const city = s.fields.find((f: any) => f.name === 'city');
  const mokaSchool = s.fields.find((f: any) => f.name === 'mokaSchool');
  assert.equal(city.widget.role, 'combobox');
  assert.equal(city.widget.multiSelect, true);

  const byName = (name: string) => s.fields.find((f: any) => f.name === name).fieldId;
  const result = await app.formFill(s.snapshotId, [
    {fieldId: byName('name'), resumePath: 'personal.fullName'},
    {fieldId: byName('email'), resumePath: 'personal.email'},
    {fieldId: byName('school'), resumePath: 'educations.0.school'},
    {fieldId: city.fieldId, value: ['上海', '广州'], sourceQuote: '意向城市：上海、广州'},
    {fieldId: mokaSchool.fieldId, value: '模拟大学', sourceQuote: '学校：模拟大学'},
  ]);
  console.error('TIMING open-page-to-fill-ms=' + (Date.now() - tOpen));
  const after = result.snapshot;
  assert.equal(after.fields.find((f: any) => f.name === 'name').value, '测试候选人');
  assert.equal(after.fields.find((f: any) => f.name === 'email').value, 'candidate@example.test');
  assert.equal(after.fields.find((f: any) => f.name === 'school').value, '模拟大学');
  const cityAfter = after.fields.find((f: any) => f.name === 'city');
  assert.deepEqual([...cityAfter.value].sort(), ['上海', '广州']);
  assert.equal(after.fields.find((f: any) => f.name === 'mokaSchool').value, '模拟大学');

  const existing = await app.formFill(after.snapshotId, [{fieldId: byName('name'), resumePath: 'personal.fullName'}]);
  assert.equal(existing.results[0].status, 'existing');
  assert.equal(existing.results[0].verified, true);
});
