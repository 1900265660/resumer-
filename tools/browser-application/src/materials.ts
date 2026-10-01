import {readFile, realpath, readdir, writeFile, rename, mkdir} from 'node:fs/promises';
import path from 'node:path';
import {createHash, randomUUID} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {z} from 'zod';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const exec = promisify(execFile);
export const answerSchema = z.object({
  resumePath: z.string().regex(/^[a-zA-Z][\w]*(?:\.[\w]+)*$/),
  value: z.union([z.string().min(1), z.array(z.string().min(1)).min(1)]),
  sourceQuote: z.string().min(1),
  source: z.enum(['answers', 'resume']).default('answers'),
  sensitiveApproval: z.string().optional(),
});
export type Answer = z.infer<typeof answerSchema>;
export type Material = {
  approvedPath: string; approvedHash: string; root: string; dir: string;
  company: string; job: string; url: string; resume: string; resumeHash: string;
  answersText: string; resumeText: string; answers: Answer[]; resumeProfile?: Record<string, any>; packageHash: string; transferApproval: string;
};
export const sensitive = /身份证|证件|护照|健康|婚育|婚姻|家庭|亲属|薪资|薪酬|工资|竞业|协议|承诺|授权|同意|调动|到岗|出生|民族|政治面貌|性别|salary|gender|birth|consent|agree|authorization|identity|passport/i;
export const hash = (data: string | Buffer) => createHash('sha256').update(data).digest('hex');
export const fileHash = async (file: string) => hash(await readFile(file));
export async function json(file: string): Promise<any> {return JSON.parse((await readFile(file, 'utf8')).replace(/^\uFEFF/, ''));}
export async function exists(file: string) {try {await realpath(file); return true;} catch {return false;}}
export async function within(root: string, name: string) {
  const base = await realpath(root), resolved = await realpath(path.resolve(base, name));
  const rel = path.relative(base, resolved);
  if (!rel || rel === '..' || rel.startsWith('..' + path.sep) || path.isAbsolute(rel)) throw new Error('path_outside_workspace');
  return resolved;
}
export async function atomic(file: string, value: unknown) {
  await mkdir(path.dirname(file), {recursive: true});
  const tmp = file + '.' + randomUUID() + '.tmp';
  await writeFile(tmp, JSON.stringify(value, null, 2), {mode: 0o600});
  await rename(tmp, file);
}
export function canonicalUrl(raw: string) {
  const url = new URL(raw);
  const secret = /^(utm_.+|sessionid|session|sid|token|access_token|id_token|code|ticket|state|auth|key|jwt|signature|password|phone|email|name|locale)$/i;
  for (const key of [...url.searchParams.keys()]) if (secret.test(key)) url.searchParams.delete(key);
  const hashParts = url.hash.split('?');
  if (hashParts.length > 1) {
    const params = new URLSearchParams(hashParts.slice(1).join('?'));
    for (const key of [...params.keys()]) if (secret.test(key)) params.delete(key);
    url.hash = hashParts[0] + (params.size ? '?' + params.toString() : '');
  } else if (/(?:^#|&)(?:access_token|id_token|code|token)=/i.test(url.hash)) url.hash = '';
  url.searchParams.sort(); // Preserve SPA hash routes and job identity parameters.
  return url.toString();
}
export function getProfilePath(profile: Record<string, any> | undefined, resumePath: string): unknown {
  if (!profile || !resumePath) return undefined;
  let current: any = profile;
  for (const part of resumePath.split('.')) {
    if (current == null) return undefined;
    if (Array.isArray(current)) {
      const index = Number(part);
      if (!Number.isInteger(index) || index < 0 || index >= current.length) return undefined;
      current = current[index];
    } else if (typeof current === 'object') {
      if (!Object.prototype.hasOwnProperty.call(current, part)) return undefined;
      current = current[part];
    } else {
      return undefined;
    }
  }
  return current;
}
export async function loadResumeProfile(root: string, company: string): Promise<Record<string, any> | undefined> {
  const dir = path.join(root, 'outputs', 'ai-resume-imports');
  let entries: string[] = [];
  try { entries = await readdir(dir); } catch { return undefined; }
  const norm = (s: string) => String(s || '').replace(/[^\p{L}\p{N}]/gu, '').toLowerCase();
  const target = norm(company);
  const candidates = entries.filter(n => n.toLowerCase().endsWith('.json'));
  for (const name of candidates) {
    const data = await json(path.join(dir, name));
    const profile = data?.profile && typeof data.profile === 'object' ? data.profile : data;
    if (!profile || typeof profile !== 'object' || !profile.personal) continue;
    if (target && norm(name).includes(target)) return profile;
  }
  if (candidates.length === 1) {
    const data = await json(path.join(dir, candidates[0]));
    return data?.profile && typeof data.profile === 'object' ? data.profile : data;
  }
  return undefined;
}
export function validateAnswers(answers: Answer[], text: string, resumeText = '') {
  const seen = new Set<string>();
  for (const answer of answers) {
    answerSchema.parse(answer);
    if (seen.has(answer.resumePath)) throw new Error('duplicate_resume_path');
    seen.add(answer.resumePath);
    const source = answer.source === 'resume' ? resumeText : text;
    if (!source.includes(answer.sourceQuote)) throw new Error('answer_quote_not_in_approved_snapshot');
    if (/待确认|需确认|草拟|确认后|未确认|暂停|由 Codex|示例|仅供参考/.test(answer.sourceQuote)) throw new Error('answer_not_approved');
    for (const value of Array.isArray(answer.value) ? answer.value : [answer.value]) {
      if (!answer.sourceQuote.includes(value)) throw new Error('answer_value_not_in_quote');
    }
    if (answer.sensitiveApproval && (!text.includes(answer.sensitiveApproval) || answer.sensitiveApproval.length < 8 || !/用户.*(?:确认|同意|批准)/.test(answer.sensitiveApproval) || /需确认|待确认|未确认/.test(answer.sensitiveApproval))) throw new Error('sensitive_approval_not_in_snapshot');
  }
}
export async function extractResume(file: string): Promise<string> {
  if (path.extname(file).toLowerCase() !== '.pdf') return '';
  try {
    const require = createRequire(import.meta.url);
    const pdfjs = require(fileURLToPath(new URL('../extension/libs/pdfjs/pdf.min.js', import.meta.url)));
    const task = pdfjs.getDocument({data: new Uint8Array(await readFile(file)), isEvalSupported: false, disableFontFace: true, verbosity: 0});
    const pdf = await task.promise;
    try {
      const pages = [];
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i), content = await page.getTextContent();
        pages.push(content.items.map((item: any) => item.str || '').join(' '));
      }
      return pages.join('\n');
    } finally {await pdf.destroy();}
  } catch {return '';}
}
export async function rejectDuplicate(root: string, dir: string, company: string, job: string, url: string) {
  for (const entry of await readdir(path.join(root, 'applications'), {withFileTypes: true})) {
    if (!entry.isDirectory()) continue;
    const target = path.join(root, 'applications', entry.name);
    const mf = path.join(target, 'manifest.json');
    if (!await exists(mf)) continue;
    const m = await json(mf);
    const otherUrl = m.application_url || m.job_url || m.normalized_url;
    const same = target === dir || (m.company === company && (m.job_title || m.role) === job) || (otherUrl && canonicalUrl(otherUrl) === canonicalUrl(url));
    if (same && (m.status === 'submitted' || m.has_success_receipt === true || await exists(path.join(target, 'receipt.md')))) throw new Error('duplicate_or_existing_receipt_requires_review');
  }
}
export async function prepare(root: string, approvedPath: string, answers: Answer[] = [], transferApproval = '', resumeProfile?: Record<string, any>): Promise<Material> {
  root = await realpath(root);
  const approved = await within(path.join(root, 'jobs', 'approved'), approvedPath);
  await validateApproved(root, approved);
  const a = await json(approved), m = a.manifest;
  const draft = await within(path.join(root, 'applications'), path.relative(path.join(root, 'applications'), path.resolve(root, a.source_draft_path)));
  const dir = path.dirname(draft);
  const state = await json(path.join(dir, 'manifest.json'));
  if (!['ready', 'approved', 'filling', 'manual_required'].includes(state.status)) throw new Error('application_state_inconsistent: 需先核对岗位主状态');
  const resume = await within(dir, m.resume.path), answersFile = await within(dir, m.answers.path);
  const answersText = await readFile(answersFile, 'utf8');
  const resumeText = await extractResume(resume);
  validateAnswers(answers, answersText, resumeText);
  resumeProfile = resumeProfile || await loadResumeProfile(root, m.company);
  if (resumeProfile && !resumeProfile.personal) throw new Error('resume_profile_invalid: 缺少 personal 信息');
  if (answers.some(a => a.source === 'resume') && !/简历|材料/.test(transferApproval)) throw new Error('resume_field_transfer_authorization_required');
  if (transferApproval && !answersText.includes(transferApproval) && !String(a.approval_statement).includes(transferApproval)) throw new Error('transfer_approval_not_in_frozen_material');
  await rejectDuplicate(root, dir, m.company, m.job_title, m.application_url);
  return {root, dir, approvedPath: approved, approvedHash: await fileHash(approved), company: m.company,
    job: m.job_title, url: m.application_url, resume, resumeHash: await fileHash(resume), answersText, resumeText, answers, resumeProfile,
    packageHash: hash(JSON.stringify(answers)), transferApproval};
}
export async function validateApproved(root: string, approved: string) {
  try {
    const {stdout} = await exec(process.env.CODEX_APPLICATION_PWSH || 'pwsh', ['-NoProfile', '-NonInteractive', '-File',
      path.join(root, 'scripts', 'validate_approved_manifest.ps1'), '-ApprovedPath', approved], {timeout: 30000, maxBuffer: 2 * 1024 * 1024});
    if (JSON.parse(stdout.replace(/^\uFEFF/, '').trim()).status !== 'validation_pass') throw new Error('validation_failed');
  } catch {throw new Error('approved_manifest_validation_failed: 运行 scripts/validate_approved_manifest.ps1 查看本地校验原因');}
}
export async function revalidate(m: Material) {
  if (await fileHash(m.approvedPath) !== m.approvedHash || await fileHash(m.resume) !== m.resumeHash) throw new Error('approved_material_changed');
  await validateApproved(m.root, m.approvedPath);
  await rejectDuplicate(m.root, m.dir, m.company, m.job, m.url);
}
export async function updateMain(m: Material, next: 'filling' | 'manual_required' | 'submitted') {
  const file = path.join(m.dir, 'manifest.json'), data = await json(file);
  if (next === 'filling' && data.status === 'ready') { data.status = 'approved'; await atomic(file, data); }
  // Resume lives in a separate ledger: never roll manual_required backwards.
  if (next === 'filling' && data.status === 'manual_required') return;
  if (!['approved', 'filling', 'manual_required'].includes(data.status)) throw new Error('invalid_application_state_transition');
  data.status = next;
  if (next === 'submitted') data.has_success_receipt = true;
  await atomic(file, data);
}
