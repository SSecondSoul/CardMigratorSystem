import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const r=createRequire(import.meta.url);
const sharp=r(r.resolve('sharp',{paths:['C:/Users/soul/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules']}));
await sharp(await fs.readFile(new URL('./section16-backend-mysql.svg',import.meta.url)),{density:220}).png().toFile(fileURLToPath(new URL('./section16-backend-mysql.png',import.meta.url)));
