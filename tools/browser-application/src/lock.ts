import {mkdir, open, readFile, unlink} from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {hash} from './materials.js';
import {moduleDir} from './browser.js';

export async function acquireWorkspace(root: string) {
  const directory = path.join(moduleDir, '.local');
  await mkdir(directory, {recursive: true});
  const file = path.join(directory, `workspace-${hash(path.resolve(root).toLowerCase())}.lock`);
  const owner = {pid: process.pid, nonce: randomUUID()};
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const fd = await open(file, 'wx', 0o600);
      try {await fd.writeFile(JSON.stringify(owner));} finally {await fd.close();}
      return async () => {
        const current = JSON.parse(await readFile(file, 'utf8'));
        if (current.nonce === owner.nonce) await unlink(file);
      };
    } catch (e: any) {
      if (e.code !== 'EEXIST') throw e;
      const old = JSON.parse(await readFile(file, 'utf8'));
      if (!Number.isInteger(old.pid) || old.pid < 1) throw new Error('workspace_lock_needs_review');
      let alive = true;
      try {process.kill(old.pid, 0);} catch (err: any) {if (err.code === 'ESRCH') alive = false;}
      if (alive) throw new Error('workspace_session_already_running');
      await unlink(file); // Exact lock file, only when its owning process is gone.
    }
  }
  throw new Error('workspace_lock_busy');
}
