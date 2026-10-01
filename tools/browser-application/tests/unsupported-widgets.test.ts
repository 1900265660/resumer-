import test from 'node:test';
import assert from 'node:assert/strict';
import {ApplicationRuntime} from '../src/runtime.js';
import {fixture, answers, approval} from './fixture.js';

test('reports and blocks a required custom widget with no fillable control', {timeout: 120000}, async t => {
  const f = await fixture();
  t.after(f.close);
  const app = new ApplicationRuntime(f.root);
  t.after(() => app.applicationClose());
  await app.applicationPrepare(f.approvedPath, answers, approval);
  let snapshot: any = await app.browserStart();

  await app.bridge!.page.evaluate(() => {
    const label = document.createElement('div');
    label.className = 'FormItem';
    label.textContent = '意向城市';
    const widget = document.createElement('div');
    widget.setAttribute('role', 'combobox');
    widget.setAttribute('aria-required', 'true');
    widget.textContent = '请选择';
    label.append(widget);
    document.querySelector('form')!.prepend(label);
  });

  snapshot = await app.formInspect();
  assert.equal(snapshot.unsupportedWidgets.length, 1);
  assert.equal(snapshot.unsupportedWidgets[0].role, 'combobox');
  await assert.rejects(
    app.formFill(snapshot.snapshotId, [{
      fieldId: snapshot.fields.find((field: any) => field.name === 'name').fieldId,
      resumePath: 'personal.name',
    }]),
    /unsupported_required_widget/
  );
});
