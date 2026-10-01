import {existsSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../', import.meta.url));
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(root, '.local', 'browsers');
const {chromium} = await import('playwright');
const checks = {
  node: Number(process.versions.node.split('.')[0]) >= 22,
  chromium: existsSync(chromium.executablePath()),
  compiled: existsSync(path.join(root, 'dist/server.js')),
  extension: existsSync(path.join(root, 'extension/codex-background.js')),
  powershell: spawnSync(process.env.CODEX_APPLICATION_PWSH || 'pwsh', ['-NoProfile', '-Command', '$PSVersionTable.PSVersion.Major'], {windowsHide: true}).status === 0,
};
console.log(JSON.stringify({checks, ready: Object.values(checks).every(Boolean), browser: chromium.executablePath()}, null, 2));
if (!Object.values(checks).every(Boolean)) process.exitCode = 1;
