// Prove this follow-up changes only parent method metadata, not render/rules.
const fs=require('fs'),path=require('path'),{createRequire}=require('module');
const req=createRequire(path.join(process.cwd(),'migration_system/engine/package.json'));
const parser=req('@babel/parser'),crypto=require('crypto');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
function inspect(file){
 const text=fs.readFileSync(file,'utf8'),ast=parser.parse(text,{sourceType:'unambiguous'});
 const fns=ast.program.body.filter(n=>n.type==='FunctionDeclaration'&&n.id.name==='parentMethodMetadata');
 if(fns.length!==1)throw Error('unique_parent_metadata_required');
 const target=fns[0],body=hash(text.slice(target.start,target.end));
 target.body={type:'BlockStatement',body:[]};
 const clean=n=>Array.isArray(n)?n.map(clean):n&&typeof n==='object'?
   Object.fromEntries(Object.entries(n).filter(([k])=>!['start','end','loc','extra','leadingComments','trailingComments','innerComments','comments','tokens'].includes(k)).map(([k,v])=>[k,clean(v)])):n;
 return {file_sha256:hash(text),function_sha256:body,rest:JSON.stringify(clean(ast.program))};
}
const old=inspect(input.old),current=inspect(input.new);
process.stdout.write(JSON.stringify({changed_function:'parentMethodMetadata',
 all_other_program_nodes_unchanged:old.rest===current.rest,old_file_sha256:old.file_sha256,
 new_file_sha256:current.file_sha256,old_function_sha256:old.function_sha256,new_function_sha256:current.function_sha256}));
