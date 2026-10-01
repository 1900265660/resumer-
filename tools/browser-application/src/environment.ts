import {mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const local = fileURLToPath(new URL('../.local/', import.meta.url));
const downloadTemp = path.join(local, 'downloads');
mkdirSync(downloadTemp, {recursive: true});
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(local, 'browsers');
process.env.TEMP = downloadTemp;
process.env.TMP = downloadTemp;
