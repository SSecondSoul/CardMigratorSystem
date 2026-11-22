import {createRequire} from 'node:module';import{pathToFileURL}from'node:url';import fs from'node:fs/promises';
const r=createRequire(import.meta.url),base='C:/Users/soul/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
for(const n of ['@napi-rs/canvas','canvas','skia-canvas','pdfkit','sharp']){try{console.log(n,r.resolve(n,{paths:[base]}))}catch{}}
const m=await import(pathToFileURL(r.resolve('@oai/artifact-tool',{paths:[base]})));
console.log('canvasfunc',String(m.createWhiteboardExportCanvas).slice(0,2200));
console.log('imagesfunc',String(m.preloadDocumentImageBitmaps).slice(0,1300));
const d=await m.DocumentFile.importDocx(await fs.readFile('output/reports/中期报告_论文研究进度_详细版_20261119.docx'));
const l=await d.export({format:'layout'});await fs.writeFile('docs/report-build/midterm-detailed/layout.json',new Uint8Array(await l.arrayBuffer()));console.log('LAYOUT');
