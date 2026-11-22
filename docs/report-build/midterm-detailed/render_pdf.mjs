import fs from 'node:fs/promises';import {createRequire} from 'node:module';import {pathToFileURL} from 'node:url';
const r=createRequire(import.meta.url);const m=await import(pathToFileURL(r.resolve('@oai/artifact-tool',{paths:['C:/Users/soul/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules']})));
const input=process.argv[2],output=process.argv[3];
const d=await m.DocumentFile.importDocx(await fs.readFile(input));
const pdf=await d.export({format:'pdf'});await fs.writeFile(output,new Uint8Array(await pdf.arrayBuffer()));
const layout=await d.export({format:'layout'});await fs.writeFile(output+'.layout.json',new Uint8Array(await layout.arrayBuffer()));
console.log('exported',output);
