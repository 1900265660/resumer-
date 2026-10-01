import {spawnSync} from 'node:child_process';
import {existsSync, mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../', import.meta.url));
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(root, '.local', 'browsers');
process.env.TEMP = process.env.TMP = path.join(root, '.local', 'downloads');
mkdirSync(process.env.TEMP, {recursive: true});
const run = (args) => {
  const p = spawnSync(process.execPath, args, {cwd: root, stdio: 'inherit', windowsHide: true});
  if (p.status !== 0) process.exit(p.status || 1);
};
if (!existsSync(path.join(root, 'node_modules/playwright/cli.js'))) {
  console.error('请先在本目录运行 pnpm install --frozen-lockfile'); process.exit(1);
}
run(['node_modules/typescript/bin/tsc']);
run(['node_modules/playwright/cli.js', 'install', 'chromium', '--no-shell', '--no-remove']);
run(['scripts/doctor.mjs']);
