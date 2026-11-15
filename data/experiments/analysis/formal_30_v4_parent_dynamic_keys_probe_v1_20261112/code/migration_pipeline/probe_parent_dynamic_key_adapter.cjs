/* Experimental only. Not imported by generate/repair/validate or the scheduler.
 * Proves a bounded writer candidate against the frozen native-framework oracle;
 * does NOT discharge the production dynamic-key or exception-policy findings.
 */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const traverse=require('@babel/traverse').default,{parse}=require('@vue/compiler-sfc');
const {parentOf,key}=require('./utils/inline_identifier_recovery.cjs');
const {one,print,walk,sourceParent}=require('./utils/source_render_call_semantics.cjs');
const {run:assess}=require('./utils/source_parent_watch_semantics.cjs');
const PREFIX='__dynamicKeyProbe_v1_';
const own=n=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object);
const method=(o,name)=>{const p=one(o,name);return t.isObjectMethod(p)?p:null;};
function run(input){
    const result={code:input.code,changes:[],reviews:[],production_eligible:false,
        contract:'experimental_flat_scalar_root_string_key_writer_v1',writers:[],
        limitations:['No production registration or diagnostic waiver.',
            'String keys excluding Vue observer metadata; flat scalar observed roots.',
            'Only scalar values, or plain scalar-valued local __proto__ replacements.',
            'No descriptor/ref/Proxy/Symbol keys, external aliases, nested mutation or browser-render proof.',
            'Unsupported probe inputs throw before mutation; this is NOT a source-compatible public API for arbitrary inputs.',
            'Existing async queue and exception propagation are unchanged.']};
    const decline=reason=>{result.reviews.push(reason);return result;};
    if(input.experimental!==true)return decline('explicit_experimental_opt_in_required');
    if(input.code.includes(PREFIX)||input.vue.includes(PREFIX))return decline('probe_marker_present_or_collision');
    const before=assess({code:input.code,vue:input.vue});
    if(before.error||before.proofs.length!==1||!before.proofs[0].landed)
        return decline('requires_exact_source_matched_frozen_normal_flow_queue');
    const entries=before.proofs[0].source_nested_clone_writers;
    if(!entries.length||entries.some(w=>!w.same_value_guard))return decline('no_exact_guarded_clone_writer');
    const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.code);
    const source=parse(input.vue),srcAst=parser.parse(source.descriptor.script.content,{sourceType:'unambiguous'});
    const ast=parser.parse(block[1],{sourceType:'unambiguous'}),parent=parentOf(ast),src=sourceParent(srcAst);
    let shadowed=false;
    for(const tree of [ast,srcAst])traverse(tree,{Scope(p){
        if(['WeakMap','TypeError'].some(name=>p.scope.hasOwnBinding(name)))shadowed=true;
    }});
    if(shadowed)return decline('shadowed_adapter_global');
    const init=method(parent,'inited'),sourceMethods=one(src,'methods').value;
    const declarations=[],edits=[];
    for(let slot=0;slot<entries.length;slot++){
        const row=entries[slot],sm=method(sourceMethods,row.method),tm=method(parent,row.method);
        const assignment=sm?.body.body[0]?.expression,lhs=assignment?.left;
        if(!t.isAssignmentExpression(assignment,{operator:'='})||!t.isMemberExpression(lhs)||!lhs.computed||!own(lhs.object)
            ||sm.params.length!==2||!sm.params.every(t.isIdentifier)||!t.isIdentifier(lhs.property,{name:sm.params[0].name}))
            return decline('unrecognized_source_writer');
        // Reject other source mutations of this root, rather than infer that an
        // immutable clone was a genuine Vue observation boundary.
        let extraMutation=false;
        for(const m of sourceMethods.properties)walk(m,n=>{
            const left=t.isAssignmentExpression(n)?n.left:t.isUpdateExpression(n)?n.argument:
                t.isUnaryExpression(n,{operator:'delete'})?n.argument:null;
            if(!left||n===assignment)return;
            let root=left;while(t.isMemberExpression(root)&&!t.isThisExpression(root.object))root=root.object;
            if(own(root)&&root.property.name===row.field&&left!==root)extraMutation=true;
        });
        if(extraMutation)return decline('other_nested_source_mutation');
        const queueIndex=before.proofs[0].fields.indexOf(row.field),prefix=PREFIX+slot;
        const helper=parser.parse(`
const ${prefix}Seen=new WeakMap();
const ${prefix}Scalar=value=>value===null||['undefined','boolean','number','string'].indexOf(typeof value)>=0;
const ${prefix}Plain=value=>{
    if(value===null||typeof value!=='object'||Object.getPrototypeOf(value)!==Object.prototype)return false;
    return Object.getOwnPropertyNames(value).every(name=>{
        const d=Object.getOwnPropertyDescriptor(value,name);
        return name!=='__ob__'&&d.enumerable&&d.configurable&&d.writable&&'value' in d&&${prefix}Scalar(d.value);
    })&&Object.getOwnPropertySymbols(value).length===0;
};
const ${prefix}Remember=object=>{
    if(!${prefix}Seen.has(object)){
        if(!${prefix}Plain(object))throw new TypeError('Dynamic-key probe: unsupported observed root');
        ${prefix}Seen.set(object,Object.keys(object));
    }
    return ${prefix}Seen.get(object);
};
${prefix}Remember(this.data.get(${JSON.stringify(row.field)}));
this.watch(${JSON.stringify(row.field)},value=>{${prefix}Remember(value);});
this.${prefix}Write=(key,value)=>{
    if(typeof key!=='string'||key==='__ob__'||(!${prefix}Scalar(value)&&!(key==='__proto__'&&${prefix}Plain(value))))
        throw new TypeError('Dynamic-key probe: unsupported key or value');
    const object=this.data.get(${JSON.stringify(row.field)});
    const reactive=${prefix}Remember(object).indexOf(key)>=0;
    const previous=object[key];
    object[key]=value;
    if(reactive&&!Object.is(previous,value)){
        this.data.set(${JSON.stringify(row.field)},object,{force:true});
        enqueue(${queueIndex});
    }
};`).program.body;
        declarations.push(...helper);
        const fixed=t.cloneNode(tm,true);
        fixed.body.body=[t.expressionStatement(t.callExpression(t.memberExpression(t.thisExpression(),t.identifier(prefix+'Write')),
            [t.cloneNode(sm.params[0]),t.cloneNode(assignment.right,true)])),...tm.body.body.slice(4)];
        edits.push({start:tm.start,end:tm.end,text:print(fixed)});
        result.writers.push({method:row.method,field:row.field,queue_index:queueIndex});
    }
    // Keep the original queue, callbacks, timers and disposal exactly intact.
    // Bookkeeping is registered before attached() can restore an observed root.
    const fixedInit=t.cloneNode(init,true);fixedInit.body.body.push(...declarations);
    edits.push({start:init.start,end:init.end,text:print(fixedInit)});
    let script=block[1];for(const edit of edits.sort((a,b)=>b.start-a.start))
        script=script.slice(0,edit.start)+edit.text+script.slice(edit.end);
    parser.parse(script,{sourceType:'unambiguous'});
    const offset=block.index+block[0].indexOf('>')+1;
    result.code=input.code.slice(0,offset)+script+input.code.slice(offset+block[1].length);
    result.changes=['experimental_source_dynamic_key_writer_adapter'];return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
    catch(error){process.stderr.write(error.stack);process.exitCode=1;}}
module.exports={run,PREFIX};
