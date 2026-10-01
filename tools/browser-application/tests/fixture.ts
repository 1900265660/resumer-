import {mkdtemp, mkdir, writeFile, copyFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createServer} from 'node:http';
import {fileURLToPath} from 'node:url';
import {fileHash, json, type Answer} from '../src/materials.js';

export const approval = '用户明确批准向本地模拟招聘网站填写以下测试资料并上传测试附件。';
export const answers = [
  {resumePath: 'personal.name', value: '测试候选人', sourceQuote: '姓名：测试候选人'},
  {resumePath: 'personal.email', value: 'candidate@example.test', sourceQuote: '邮箱：candidate@example.test'},
  {resumePath: 'educations.0.school', value: '模拟大学', sourceQuote: '学校：模拟大学'},
  {resumePath: 'educations.0.degree', value: '本科', sourceQuote: '学历：本科'},
  {resumePath: 'educations.0.start', value: '2021-09', sourceQuote: '开始：2021-09'},
  {resumePath: 'preferences.cities', value: ['上海', '广州'], sourceQuote: '意向城市：上海、广州'},
  {resumePath: 'projects.0.name', value: '模拟项目', sourceQuote: '项目：模拟项目'},
  {resumePath: 'additional.intro', value: '这是已确认的模拟介绍。', sourceQuote: '介绍：这是已确认的模拟介绍。'},
].map(a => ({...a, source: 'answers' as const}));
export const html = `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>模拟公司 网申</title>
<style>body{font:18px system-ui;padding:25px;max-width:800px}label{display:block;margin:18px 0}input,select,textarea{margin-left:10px}button{padding:12px}</style>
<h1>模拟公司</h1><h2>AI产品经理</h2><main>
<form id="one"><label>姓名<input name="name" required></label><label>邮箱<input name="email" type="email" required></label>
<fieldset><legend>教育经历</legend><label>学校<input name="school" required></label><label>学历<select name="degree" required><option value="">请选择</option><option>本科</option></select></label><label>开始日期<input name="start" type="month" required></label></fieldset>
<fieldset><legend>意向工作城市</legend><label>城市<input id="cities" name="cities" role="combobox" aria-haspopup="listbox" aria-controls="city-options" aria-expanded="false" autocomplete="off"></label>
<div id="city-options" role="listbox" aria-multiselectable="true" hidden><button type="button" role="option" aria-selected="false">上海市</button><button type="button" role="option" aria-selected="false">广州市</button></div></fieldset>
<div id="projects"></div><button type="button" id="add">添加项目经历</button><button type="button" id="next">下一步</button></form>
<form id="two" hidden><label>自我介绍<textarea name="intro" required></textarea></label><label>简历<input name="resume" type="file" accept=".pdf" required></label><p id="upload"></p><p role="alert" id="error"></p><button id="submit" type="submit">提交申请</button></form>
<p id="receipt" hidden>投递成功</p></main><script>
window.submitCount=0;
document.querySelector('#cities').addEventListener('click',()=>{const list=document.querySelector('#city-options');list.hidden=false;document.querySelector('#cities').setAttribute('aria-expanded','true')});
document.querySelectorAll('#city-options [role=option]').forEach(option=>option.addEventListener('click',()=>option.setAttribute('aria-selected',option.getAttribute('aria-selected')==='true'?'false':'true')));
add.onclick=()=>{const label=document.createElement('label');label.textContent='项目名称';const input=document.createElement('input');input.name='project';input.required=true;label.append(input);projects.append(label)};
next.onclick=()=>{if(one.reportValidity()){one.hidden=true;two.hidden=false;history.pushState({},'', '/apply?step=2')}};
two.elements.resume.onchange=()=>{upload.textContent=two.elements.resume.files[0]?.name||''};
two.onsubmit=(e)=>{e.preventDefault();window.submitCount++; if(new URL(location.href).searchParams.has('unknown'))return;two.hidden=true;receipt.hidden=false};
</script></html>`;
export async function fixture() {
  const server = createServer((_req, res) => {res.setHeader('content-type', 'text/html; charset=utf-8'); res.end(html);});
  await new Promise<void>(r => server.listen(0, '127.0.0.1', r));
  const address = server.address() as {port: number};
  const url = `http://127.0.0.1:${address.port}/apply`;
  const root = await mkdtemp(path.join(tmpdir(), 'codex-网申测试-'));
  const dir = path.join(root, 'applications', '模拟公司_AI产品经理');
  await mkdir(dir, {recursive: true});
  await mkdir(path.join(root, 'jobs', 'approved'), {recursive: true});
  await mkdir(path.join(root, 'scripts'));
  await writeFile(path.join(root, 'AGENTS.md'), '# Mock workspace');
  const sourceRoot = fileURLToPath(new URL('../../../', import.meta.url));
  for (const name of ['approval_manifest_common.ps1', 'validate_approved_manifest.ps1', 'create_approved_manifest.ps1'])
    await copyFile(path.join(sourceRoot, 'scripts', name), path.join(root, 'scripts', name));
  await writeFile(path.join(dir, 'answers.md'), approval + '\n' + answers.map(a => a.sourceQuote).join('\n'));
  await writeFile(path.join(dir, 'jd.md'), '模拟公司 AI产品经理');
  await writeFile(path.join(dir, 'review.md'), '本地虚构样本，pdf_visual/pdf_text_layer/ats passed（仅测试）');
  await writeFile(path.join(dir, 'resume.pdf'), '%PDF-1.4\n% Synthetic test fixture only\n%%EOF');
  await writeFile(path.join(dir, 'manifest.json'), JSON.stringify({status: 'ready', company: '模拟公司', role: 'AI产品经理', application_url: url}));
  const draft: any = {status: 'ready_for_user_approval', company: '模拟公司', job_title: 'AI产品经理',
    application_url: url, normalized_url: url, mode: 'existing', content_pipeline: 'existing-material',
    review_checks: {pdf_visual: 'passed', pdf_text_layer: 'passed', ats: 'passed'}};
  for (const [key, name] of Object.entries({jd: 'jd.md', answers: 'answers.md', review: 'review.md', resume: 'resume.pdf'}))
    draft[key] = {path: name, sha256: await fileHash(path.join(dir, name))};
  const draftPath = path.join(dir, 'manifest-draft.json');
  await writeFile(draftPath, JSON.stringify(draft));
  const result = await promisify(execFile)('pwsh', ['-NoProfile', '-File', path.join(root, 'scripts', 'create_approved_manifest.ps1'),
    '-DraftPath', draftPath, '-ApprovalStatement', approval, '-Commit']);
  const approvedPath = JSON.parse(result.stdout.trim()).path;
  return {root, dir, url, approvedPath, server, close: () => new Promise<void>(r => {
    server.closeAllConnections?.();
    server.close(() => r());
  })};
}
