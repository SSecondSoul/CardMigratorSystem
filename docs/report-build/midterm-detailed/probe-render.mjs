import {createRequire} from 'node:module';import {pathToFileURL} from 'node:url';
const r=createRequire(import.meta.url);const m=await import(pathToFileURL(r.resolve('@oai/artifact-tool',{paths:['C:/Users/soul/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules']})));
for(const n of ['DocumentFile','DocumentModel','layoutDocumentPages','renderRenderedDocumentPage'])console.log(n,typeof m[n],Object.getOwnPropertyNames(m[n]),String(m[n]).slice(0,n==='DocumentFile'?5500:600));
console.log('MODEL PROTO',Object.getOwnPropertyNames(m.DocumentModel.prototype));
console.log('draw',String(m.drawDocumentToCtx).slice(0,2600));
console.log('paint',String(m.paintRenderedDocumentPage).slice(0,1800));
console.log('FONT',Object.keys(m).filter(x=>/font|canvas/i.test(x)).slice(0,90));
console.log('EXPORT',String(m.DocumentModel.prototype.export).slice(0,4500));
