import test from 'node:test';
import assert from 'node:assert/strict';
import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import {moduleDir} from '../src/browser.js';
import path from 'node:path';
import {fixture} from './fixture.js';

test('MCP stdio handshake, tool discovery, strict input and lifecycle', {timeout: 20000}, async t => {
  const transport = new StdioClientTransport({command: process.execPath, args: [path.join(moduleDir, 'dist/server.js')], stderr: 'pipe'});
  const client = new Client({name: 'acceptance-client', version: '1.0.0'});
  t.after(() => client.close());
  await client.connect(transport);
  const list = await client.listTools();
  assert.equal(list.tools.length, 11);
  assert.ok(list.tools.some(t => t.name === 'attachment_upload'));
  assert.ok(!list.tools.some(t => /evaluate|execute|script/.test(t.name)));
  const status = await client.callTool({name: 'application_status', arguments: {}});
  assert.match(JSON.stringify(status), /idle/);
  const invalid = await client.callTool({name: 'submission_commit', arguments: {digest: 'bad'}});
  assert.equal(invalid.isError, true);
});

test('MCP can read the approved bundle through the real integration', {timeout: 20000}, async t => {
  const f = await fixture(); t.after(f.close);
  const transport = new StdioClientTransport({command: process.execPath, args: [path.join(moduleDir, 'dist/server.js')],
    env: {...process.env as Record<string,string>, CODEX_APPLICATION_ROOT: f.root}, stderr: 'pipe'});
  const client = new Client({name: 'material-client', version: '1'}); t.after(() => client.close());
  await client.connect(transport);
  const result: any = await client.callTool({name: 'application_prepare', arguments: {approvedPath: f.approvedPath}});
  assert.notEqual(result.isError, true, JSON.stringify(result));
  assert.equal(JSON.parse(result.content[0].text).company, '模拟公司');
});
