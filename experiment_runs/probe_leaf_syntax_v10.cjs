// Executes only this repository's trusted parser helpers, NEVER component JS.
const fs=require('fs'),path=require('path'),{createRequire}=require('module');
const req=createRequire(path.join(process.cwd(),'migration_system/engine/package.json'));
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const trusted=fs.readFileSync('migration_system/browser/target-syntax.mjs','utf8')
 .replace(/^import .*\r?\n/gm,'').replace(/^export /gm,'');
const helpers=new Function('require',trusted+'\nreturn {sourceOptions,leafReference,sourceLeafClosingEdits,applyEdits};')(req);
const source=helpers.sourceOptions(input.source,req),data=source.properties.find(p=>p.key.name==='data');
const methods=source.properties.find(p=>p.key.name==='methods').value.properties;
const fields=new Set(data.body.body[0].argument.properties.map(p=>p.key.name));
const refs=methods.map(m=>({name:m.key.name,reference:helpers.leafReference(m,fields)})).filter(r=>r.reference);
const edits=helpers.sourceLeafClosingEdits(input.source,input.code,req);
const partial=req('@vue/compiler-sfc').parse(helpers.applyEdits(input.code,edits)).descriptor.script.content;
let parsed;try{req('@babel/parser').parse(partial);parsed='pass'}catch(e){parsed={message:e.message,pos:e.pos,excerpt:partial.slice(e.pos-120,e.pos+140)}}
process.stdout.write(JSON.stringify({fields:[...fields],dataStatements:data.body.body.length,references:refs,edits,parsed}));
