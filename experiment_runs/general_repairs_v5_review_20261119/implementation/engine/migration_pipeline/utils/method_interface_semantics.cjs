// Preserve the exported parent's callable surface; never execute a source body.
const parser = require('@babel/parser');
const t = require('@babel/types');
const generate = require('@babel/generator').default;
const traverse = require('@babel/traverse').default;
const {parse} = require('@vue/compiler-dom');
const key = n => !n.computed && (n.key?.name ?? (n.key?.value===undefined?undefined:String(n.key.value)));
const one = (o, n) => o?.properties?.find(p => key(p) === n);
const callable = p => (p?.type === 'ObjectMethod' && p.kind === 'method')
  || (p?.type === 'ObjectProperty' && ['FunctionExpression','ArrowFunctionExpression'].includes(p.value.type));
const functionOf = p => p.type === 'ObjectMethod' ? p : p.value;
function functionBindings(ast) {
  const result=new Map();traverse(ast,{Program(path){
    for(const [name,binding] of Object.entries(path.scope.bindings)){
      if(!binding.constant)continue;
      const n=binding.path.node,fn=n.type==='FunctionDeclaration'?n:
        n.type==='VariableDeclarator'&&['FunctionExpression','ArrowFunctionExpression'].includes(n.init?.type)?n.init:null;
      if(fn)result.set(name,fn);
    }path.stop();
  }});return result;
}
const resolvedFunction = (p, bindings) => callable(p)?functionOf(p):
  p?.type==='ObjectProperty'&&p.value.type==='Identifier'?bindings.get(p.value.name):null;
const plain = o => o?.type === 'ObjectExpression' && o.properties.every(p => key(p))
  && new Set(o.properties.map(key)).size === o.properties.length;
const reserved = new Set(['initData','inited','compiled','created','attached','updated','detached','disposed',
  'watch','fire','ref','slot','attach','detach','dispose','data','el','constructor','prototype','__proto__',
  'template','components','computed','dataTypes','filters','messages','tagName']);
const globals = new Set(['window','Notification','Math','JSON','String','Number','Boolean','undefined','NaN','Infinity']);
const dangerous = new Set(['constructor','prototype','__proto__']);
const pureCalls = new Set(['Math.abs','Math.round','Math.floor','Math.ceil','Math.min','Math.max',
  'Math.pow','Math.sqrt','JSON.stringify','JSON.parse','String','Number','Boolean']);
const escape = s => s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');

function walk(node, visit, parent=null) {
  if (!node || typeof node !== 'object') return;
  if (Array.isArray(node)) {node.forEach(n=>walk(n,visit,parent));return;}
  visit(node,parent);
  for (const [k,v] of Object.entries(node)) if (!['loc','extra','comments','tokens'].includes(k)) walk(v,visit,node);
}
function references(parent, template, source, name) {
  let count=0, uncertain=false;
  walk(parent,(n,p)=>{
    if (['MemberExpression','OptionalMemberExpression'].includes(n.type) && n.object.type==='ThisExpression') {
      if (n.computed) uncertain=true;
      if ((!n.computed && n.property.name===name) || (n.computed && n.property.value===name)) count++;
    }
    if (n.type==='ThisExpression' && !(p && ['MemberExpression','OptionalMemberExpression'].includes(p.type) && p.object===n)) uncertain=true;
    if (n.type==='StringLiteral' && n.value===name && !(p && p.key===n && !p.computed)) uncertain=true;
  });
  try {
    const root=parse(template), pattern=new RegExp('(^|[^A-Za-z0-9_$])'+escape(name)+'(?![A-Za-z0-9_$])');
    const visit=n=>{
      if(n.type===1)for(const p of n.props){
        const text=source?(p.type===7&&p.exp?.content):
          (p.type===6&&p.value&&(p.name.startsWith('on-')||p.name.startsWith('s-')||/[{][{=]/.test(p.value.content))&&p.value.content);
        if(text&&pattern.test(text))count++;
      }
      if(n.type===5&&pattern.test(n.content.content))count++;
      for(const c of n.children||[])visit(c);
    };visit(root);
  } catch (_) {uncertain=true;}
  return {count,uncertain};
}
function fieldNames(parent, source) {
  const names=new Set(), factory=one(parent,source?'data':'initData');
  const fn=factory&&callable(factory)&&functionOf(factory);
  for(const s of fn?.body?.body||[])if(s.type==='ReturnStatement'&&plain(s.argument))
    for(const p of s.argument.properties)names.add(key(p));
  const schema=one(parent,source?'props':'dataTypes')?.value;
  if(plain(schema))for(const p of schema.properties)names.add(key(p));
  if(source&&schema?.type==='ArrayExpression')for(const p of schema.elements||[])if(p?.type==='StringLiteral')names.add(p.value);
  const computed=one(parent,'computed')?.value;
  if(plain(computed))for(const p of computed.properties)names.add(key(p));
  return names;
}
function programBindings(ast) {
  let names=new Set();traverse(ast,{Program(path){names=new Set(Object.keys(path.scope.bindings));path.stop();}});return names;
}
// A callable alone cannot prove this dynamic Vue instance write landed in San.
// Do not invent a path setter, finite-key restriction or compatibility layer.
function dynamicAssignment(fn) {
  if(!fn||fn.type==='ArrowFunctionExpression'||fn.async||fn.generator
      ||fn.params.length!==2||fn.params.some(p=>p.type!=='Identifier')
      ||fn.params[0].name===fn.params[1].name||fn.body?.type!=='BlockStatement'
      ||fn.body.directives?.length||fn.body.body.length!==1)return null;
  const statement=fn.body.body[0],assignment=statement.type==='ExpressionStatement'&&statement.expression;
  if(assignment?.type!=='AssignmentExpression'||assignment.operator!=='='
      ||assignment.left.type!=='MemberExpression'||!assignment.left.computed
      ||assignment.left.object.type!=='ThisExpression'
      ||assignment.left.property.type!=='Identifier'||assignment.left.property.name!==fn.params[0].name
      ||assignment.right.type!=='Identifier'||assignment.right.name!==fn.params[1].name)return null;
  return {key_parameter:fn.params[0].name,value_parameter:fn.params[1].name,
    source_shape:'exact_this_computed_key_assignment',arbitrary_key_semantics_proven:false,
    automatic_restore:false};
}
// The supported production contract is explicitly SOURCE-INTERNAL calls, not
// arbitrary public keys. Prove the setter transfer, not its surrounding program.
function declaredStateAssignment(ctx,src,methods,name,target) {
  const reasons=new Set(),fail=s=>reasons.add(s),calls={source:[],target:[]},sourceOwners=new Map();
  if(reserved.has(name)||name.startsWith('_')||name.startsWith('$'))fail('setter_name_conflicts_with_runtime');
  const factory=(object,label)=>{
    const fn=resolvedFunction(one(object,label),label==='data'?ctx.source_function_bindings:ctx.target_function_bindings);
    const body=fn?.body?.body;
    const result=body?.length===1&&body[0].type==='ReturnStatement'?body[0].argument:null;
    return plain(result)&&result.properties.every(p=>p.type==='ObjectProperty')?result:null;
  };
  const a=factory(src.object,'data'),b=factory(ctx.parent,'initData');
  if(!a||!b)fail('ordinary_state_factory_not_proven');
  const allowed=new Set((a?.properties||[]).map(key).filter(k=>
    typeof k==='string'&&/^[A-Za-z][A-Za-z0-9_]*$/.test(k)&&!reserved.has(k)
    &&!one(methods,k)&&!one(one(src.object,'computed')?.value,k)
    &&!one(one(src.object,'props')?.value,k)
    &&!one(src.object,'props')?.value?.elements?.some(p=>p?.value===k)
    &&!resolvedFunction(one(ctx.parent,k),ctx.target_function_bindings)&&!!one(b,k)));
  if(one(src.object,'mixins')||one(src.object,'extends')||one(src.object,'setup')
    ||one(ctx.parent,'mixins')||one(ctx.parent,'extends'))fail('runtime_extension');
  const fn=resolvedFunction(target,ctx.target_function_bindings);
  const statement=fn?.body?.body?.length===1&&fn.body.body[0];
  const call=statement?.type==='ExpressionStatement'&&statement.expression;
  const data=call?.callee?.object;
  const exact=fn&&fn.type!=='ArrowFunctionExpression'&&!fn.async&&!fn.generator&&!fn.body.directives?.length
    &&fn.params.length===2&&fn.params.every(p=>p.type==='Identifier')&&fn.params[0].name!==fn.params[1].name
    &&call?.type==='CallExpression'&&!call.optional&&call.arguments.length===2
    &&call.callee.type==='MemberExpression'&&!call.callee.computed&&call.callee.property.name==='set'
    &&data?.type==='MemberExpression'&&!data.computed&&data.object.type==='ThisExpression'&&data.property.name==='data'
    &&call.arguments.every((p,i)=>p.type==='Identifier'&&p.name===fn.params[i].name);
  if(!exact)fail('target_not_exact_single_data_set_statement');
  const constantKey=path=>{
    if(path?.node?.type==='StringLiteral')return path.node.value;
    if(path?.node?.type!=='Identifier')return null;
    const binding=path.scope.getBinding(path.node.name),n=binding?.path.node;
    return binding?.constant&&n?.type==='VariableDeclarator'&&binding.path.parent.kind==='const'
      &&n.init?.type==='StringLiteral'?n.init.value:null;
  };
  for(const [side,ast,root,definition,template] of [
    ['source',src.ast,src.object,resolvedFunction(one(methods,name),ctx.source_function_bindings),src.template],
    ['target',ctx.ast,ctx.parent,fn,ctx.event_forwarder_template]]){
    if(new RegExp('(^|[^A-Za-z0-9_$])'+escape(name)+'(?![A-Za-z0-9_$])').test(template))fail(side+':template_reference_unassessed');
    traverse(ast,{
      ThisExpression(path){
        if(path.node.start<root.start||path.node.end>root.end)return;
        if(path.node.start>=definition?.start&&path.node.end<=definition?.end)return;
        const p=path.parent;
        if(p.type!=='MemberExpression'||p.object!==path.node){fail(side+':instance_escape');return;}
        if(p.computed){fail(side+':dynamic_instance_member');return;}
        if(side==='target'&&p.property.name==='data'){
          const api=path.parentPath.parentPath,invoke=api.parentPath;
          if(api.node.type!=='MemberExpression'||api.node.computed
            ||!['get','set','push','pop','shift','unshift','splice','remove','removeAt'].includes(api.node.property.name)
            ||invoke.node.type!=='CallExpression'||invoke.node.callee!==api.node)fail('target:runtime_store_escape');
        }
        if(p.property.name!==name)return;
        const member=path.parentPath,invocation=member.parentPath;
        if(invocation.node.type!=='CallExpression'||invocation.node.callee!==p||invocation.node.optional){fail(side+':setter_reference_escape');return;}
        let owner=invocation.getFunctionParent();
        while(owner?.isArrowFunctionExpression())owner=owner.getFunctionParent();
        if(!owner||!(owner.node.type==='ObjectMethod'||owner.node.type==='FunctionExpression')
            ||(owner.node.type==='ObjectMethod'&&owner.parent!==root&&owner.parent!==methods)){
          fail(side+':unknown_this_owner');return;
        }
        let ownerName=owner.node.type==='ObjectMethod'?key(owner.node):key(owner.parent);
        if(!ownerName){fail(side+':unknown_caller');return;}
        if(side==='source'&&(owner.parent===root||owner.parentPath.parent===root))
          ownerName=({created:'inited',mounted:'attached',beforeUnmount:'detached',unmounted:'disposed'})[ownerName]||ownerName;
        if(side==='source')sourceOwners.set(ownerName,owner.node);
        const args=invocation.get('arguments'),field=constantKey(args[0]);
        if(args.length!==2||args.some(p=>p.isSpreadElement()))fail(side+':invalid_call_arguments');
        if(!allowed.has(field))fail(side+':key_not_ordinary_declared_state');
        calls[side].push({caller:ownerName,key:field,line:invocation.node.loc?.start.line});
      },
      CallExpression(path){
        const n=path.node,c=n.callee;
        if(side!=='target'||n.start<root.start||n.end>root.end||n.start>=fn?.start&&n.end<=fn?.end)return;
        if(c.type!=='MemberExpression'||c.computed||c.property.name!=='set'
          ||c.object.type!=='MemberExpression'||c.object.computed||c.object.property.name!=='data'
          ||c.object.object.type!=='ThisExpression')return;
        const field=constantKey(path.get('arguments.0'));
        if(field===null)fail('target:unresolved_state_write');
        if(!allowed.has(field))return;
        let owner=path.getFunctionParent();while(owner?.isArrowFunctionExpression())owner=owner.getFunctionParent();
        const caller=owner?.node.type==='ObjectMethod'?key(owner.node):key(owner?.parent);
        if(!caller){fail('target:unknown_state_write_owner');return;}
        calls.target.push({caller,key:field,line:n.loc?.start.line,form:'inlined_data_set'});
      },
      AssignmentExpression(path){
        if(path.node.start<root.start||path.node.end>root.end)return;
        let l=path.node.left;
        while(l?.type==='MemberExpression'&&l.object.type==='MemberExpression')l=l.object;
        if(l?.type==='MemberExpression'&&l.object.type==='ThisExpression'&&!l.computed
            &&[name,'data'].includes(l.property.name))fail(side+':setter_or_store_reassigned');
      },
    });
  }
  const identities=side=>calls[side].map(c=>c.caller+':'+c.key).sort();
  if(!calls.source.length)fail('no_proven_internal_calls');
  if(JSON.stringify(identities('source'))!==JSON.stringify(identities('target')))fail('caller_key_multiplicity_mismatch');
  const state=fieldNames(src.object,true),callerMappings=[];
  const clean=n=>{
    if(Array.isArray(n))return n.map(clean);
    if(!n||typeof n!=='object')return n;
    const out=Object.fromEntries(Object.entries(n).filter(([k])=>!['extra','loc','start','end','leadingComments','trailingComments','innerComments'].includes(k)).map(([k,v])=>[k,clean(v)]));
    // Only ordinary object EXPRESSION properties. Never sort, fold computed
    // keys, change patterns/accessors/methods, or erase evaluation order.
    if(out.type==='ObjectExpression')for(const p of out.properties){
      if(p.type!=='ObjectProperty'||p.computed||!['Identifier','StringLiteral'].includes(p.key.type))continue;
      const name=p.key.type==='Identifier'?p.key.name:p.key.value;
      // {__proto__} is an own data property, unlike {__proto__: value}.
      if(name==='__proto__'&&p.shorthand)continue;
      p.key={type:'StringLiteral',value:name};p.shorthand=false;
    }
    return out;
  };
  const compact=n=>generate(clean(n),{compact:true,comments:false}).code;
  // Compare COMPLETE caller bodies, not just field names/counts. The two
  // accepted forms preserve the helper or inline its one supported write.
  const forwarding=eventForwarders(ctx,src,methods), repairs=[];
  function translate(node,inline,inlineEvents=false,lexicalThis=true,parent=null){
    if(!node||typeof node!=='object')return node;
    if(Array.isArray(node))return node.map(n=>translate(n,inline,inlineEvents,lexicalThis,parent));
    if(['FunctionExpression','FunctionDeclaration','ObjectMethod'].includes(node.type)&&parent)lexicalThis=false;
    if(node.type==='CallExpression'&&node.callee.type==='MemberExpression'&&!node.callee.computed
        &&node.callee.object.type==='ThisExpression'&&node.callee.property.name===name&&inline){
      if(!lexicalThis)throw Error('unknown_this_owner');
      return t.callExpression(parser.parseExpression('this.data.set'),node.arguments.map(n=>translate(n,inline,inlineEvents,lexicalThis,node)));
    }
    if(inlineEvents&&lexicalThis&&node.type==='CallExpression'&&!node.optional
        &&parent?.type==='ExpressionStatement'&&node.callee.type==='MemberExpression'&&!node.callee.computed
        &&node.callee.object.type==='ThisExpression'){
      const plan=forwarding.get(node.callee.property.name), fn=plan?.node;
      const call=fn?.body.body[0]?.expression;
      // Only a one-level, exact argument-order passthrough. No return-value,
      // dropped/duplicated/reordered argument or nested forwarding assumption.
      if(fn&&call?.callee?.property?.name==='fire'&&node.arguments.length===fn.params.length
          &&!node.arguments.some(a=>a.type==='SpreadElement')&&call.arguments.length===fn.params.length
          &&call.arguments.every((a,i)=>a.type==='Identifier'&&a.name===fn.params[i].name))
        return t.callExpression(parser.parseExpression('this.fire'),node.arguments.map(n=>translate(n,inline,inlineEvents,lexicalThis,node)));
    }
    if(node.type==='MemberExpression'&&!node.computed&&node.object.type==='ThisExpression'){
      if(!lexicalThis)throw Error('unknown_this_owner');
      const k=node.property.name;
      if(parent?.type==='CallExpression'&&parent.callee===node&&one(methods,k)
          &&resolvedFunction(one(ctx.parent,k),ctx.target_function_bindings))return t.cloneNode(node,true);
      if(!state.has(k)||parent?.type==='AssignmentExpression'&&parent.left===node||parent?.type==='UpdateExpression')throw Error('unsupported_instance_access');
      return parser.parseExpression('this.data.get('+JSON.stringify(k)+')');
    }
    if(node.type==='ThisExpression')throw Error('instance_escape');
    const out={...node};
    for(const [k,v] of Object.entries(node))if(v&&typeof v==='object'&&!['loc','extra','comments'].includes(k))out[k]=translate(v,inline,inlineEvents,lexicalThis,node);
    return out;
  }
  for(const [caller,sourceFn] of sourceOwners){
    const targetFn=resolvedFunction(one(ctx.parent,caller),ctx.target_function_bindings);
    let mapping=null;
    if(targetFn&&!sourceFn.async&&!sourceFn.generator&&!targetFn.async&&!targetFn.generator&&targetFn.type!=='ArrowFunctionExpression'
        &&sourceFn.params.map(compact).join(',')===targetFn.params.map(compact).join(',')){
      for(const inline of [false,true])for(const events of [false,true])try{
        if(mapping)continue;
        if(compact(translate(sourceFn.body,inline,events))===compact(targetFn.body))
          mapping=(inline?'complete_caller_with_inlined_write':'complete_caller_with_preserved_helper')+(events?'_and_verified_emit_passthrough':'');
      }catch(_){}
      if(!mapping)try{
        // A repair restores a COMPLETE, translatable source body, never just
        // its key counts. Forbid unknown captured bindings/global shadowing.
        let closed=true;
        traverse(src.ast,{ReferencedIdentifier(path){
          if(path.node.start<sourceFn.start||path.node.end>sourceFn.end)return;
          const binding=path.scope.getBinding(path.node.name);
          if(binding&&binding.path.node.start>=sourceFn.start&&binding.path.node.end<=sourceFn.end)return;
          if(!globals.has(path.node.name)||binding||ctx.target_function_bindings.has(path.node.name)
              ||programBindings(ctx.ast).has(path.node.name))closed=false;
        }});
        if(closed)repairs.push({caller,start:targetFn.body.start,end:targetFn.body.end,
          text:generate(translate(sourceFn.body,false),{comments:false}).code});
      }catch(_){}
    }
    if(!mapping)fail('caller_body_not_source_matched:'+caller);
    callerMappings.push({caller,status:mapping||'unproven'});
  }
  // Do not repair an unknown key/owner/escape, or a mismatched write count.
  // The resulting candidate still goes through validation and rollback gates.
  if(ctx.input.repair&&repairs.length&&calls.target.every(c=>sourceOwners.has(c.caller))
      &&[...reasons].every(r=>r.startsWith('caller_body_not_source_matched:')||r==='caller_key_multiplicity_mismatch')){
    for(const repair of repairs)ctx.edit(ctx.offset+repair.start,ctx.offset+repair.end,repair.text);
    ctx.changes.push('restored_source_internal_setter_caller_bodies');
  }
  // Deliberate exclusion: namespace mutations, literal dotted keys, Symbols,
  // props/computed and unknown/escaped calls NEVER acquire a finite-key waiver.
  return {contract:'source_internal_declared_state_assignment_v1',
    status:reasons.size?'unproven':'proven_for_source_internal_calls',
    arbitrary_key_semantics_proven:false,source_keys:[...new Set(calls.source.map(c=>c.key))],
    calls,caller_mappings:callerMappings,refusals:[...reasons].sort(),
    limitations:['not_arbitrary_external_public_key_equivalence','surrounding_call_timing_values_and_other_methods_checked_separately']};
}
function restore(source, ctx, src, methods) {
  const fn=resolvedFunction(source,ctx.source_function_bindings), name=key(source);
  if(fn.async||fn.generator||fn.body.type!=='BlockStatement'||!/^[$A-Z_a-z][$\w]*$/.test(name)
      || fn.type==='ArrowFunctionExpression'
      || reserved.has(name)||name.startsWith('_')
      || fn.params.some(p=>p.type!=='Identifier'||globals.has(p.name))
      || new Set(fn.params.map(p=>p.name)).size!==fn.params.length)throw Error('Unsupported signature');
  const params=new Set(fn.params.map(p=>p.name));
  const a=fieldNames(src.object,true), b=fieldNames(ctx.parent,false);
  const shadowed=new Set([...programBindings(src.ast),...programBindings(ctx.ast)]);
  const global=n=>{if(!globals.has(n)||shadowed.has(n)||params.has(n))throw Error('Unknown or shadowed global');};
  const expr=(n, context='value')=>{
    if(!n)throw Error('Missing expression');
    if(['StringLiteral','NumericLiteral','BooleanLiteral','NullLiteral'].includes(n.type))return t.cloneNode(n,true);
    if(n.type==='Identifier'){
      if(params.has(n.name))return t.cloneNode(n);
      global(n.name);
      if(['undefined','NaN','Infinity'].includes(n.name)||context==='global_receiver')return t.cloneNode(n);
      throw Error('Bare global value');
    }
    if(n.type==='MemberExpression'&&!n.computed){
      const field=n.property.name;if(dangerous.has(field))throw Error('Unsafe member');
      if(n.object.type==='ThisExpression'){
        if(!a.has(field)||!b.has(field))throw Error('Unknown source/target state');
        return parser.parseExpression(`this.data.get(${JSON.stringify(field)})`);
      }
      if(n.object.type==='Identifier'&&globals.has(n.object.name)){
        global(n.object.name);
        if(n.object.name!=='Notification'||field!=='permission')throw Error('Unsupported global read');
      }
      return t.memberExpression(expr(n.object,n.object.name==='Notification'?'global_receiver':'value'),t.cloneNode(n.property));
    }
    if(n.type==='CallExpression'&&!n.optional){
      if(n.arguments.some(x=>x.type==='SpreadElement'))throw Error('Spread arguments');
      let callee;
      if(n.callee.type==='MemberExpression'&&!n.callee.computed&&n.callee.object.type==='ThisExpression'){
        const called=n.callee.property.name;
        if(reserved.has(called)||!resolvedFunction(one(methods,called),ctx.source_function_bindings)
            ||!resolvedFunction(one(ctx.parent,called),ctx.target_function_bindings))throw Error('Unknown method dependency');
        callee=t.cloneNode(n.callee,true);
      }else{
        const c=n.callee, root=c.type==='Identifier'?c.name:c.type==='MemberExpression'&&!c.computed&&c.object.type==='Identifier'?c.object.name:null;
        if(!root)throw Error('Unknown callee');global(root);
        const path=c.type==='Identifier'?root:`${root}.${c.property.name}`;
        if(!pureCalls.has(path)&&!(path==='Notification.requestPermission'&&!n.arguments.length))throw Error('Unsupported external call');
        callee=t.cloneNode(c,true);
      }
      return t.callExpression(callee,n.arguments.map(x=>expr(x)));
    }
    if(n.type==='BinaryExpression'){
      if(n.operator==='instanceof')throw Error('Unknown class');
      if(n.operator==='in'&&n.right.type==='Identifier'&&n.right.name==='window'){
        global('window');if(n.left.type!=='StringLiteral'||n.left.value!=='Notification')throw Error('Unknown capability');
        return t.cloneNode(n,true);
      }
      return t.binaryExpression(n.operator,expr(n.left),expr(n.right));
    }
    if(n.type==='LogicalExpression')return t.logicalExpression(n.operator,expr(n.left),expr(n.right));
    if(n.type==='ConditionalExpression')return t.conditionalExpression(expr(n.test),expr(n.consequent),expr(n.alternate));
    if(n.type==='UnaryExpression'&&['!','+','-','~','void','typeof'].includes(n.operator)){
      const value=n.operator==='typeof'&&n.argument.type==='Identifier'&&globals.has(n.argument.name)
        ?expr(n.argument,'global_receiver'):expr(n.argument);
      return t.unaryExpression(n.operator,value,true);
    }
    if(n.type==='TemplateLiteral')return t.templateLiteral(n.quasis.map(x=>t.cloneNode(x,true)),n.expressions.map(x=>expr(x)));
    if(n.type==='ArrayExpression'&&n.elements.every(x=>x&&x.type!=='SpreadElement'))return t.arrayExpression(n.elements.map(x=>expr(x)));
    if(plain(n))return t.objectExpression(n.properties.map(p=>{
      if(p.type!=='ObjectProperty'||dangerous.has(key(p)))throw Error('Unsupported object');
      return t.objectProperty(t.cloneNode(p.key),expr(p.value));
    }));
    throw Error('Unsupported expression');
  };
  const stmt=n=>{
    if(n.type==='BlockStatement')return t.blockStatement(n.body.map(stmt));
    if(n.type==='IfStatement')return t.ifStatement(expr(n.test),stmt(n.consequent),n.alternate?stmt(n.alternate):null);
    if(n.type==='ExpressionStatement'&&n.expression.type==='CallExpression')return t.expressionStatement(expr(n.expression));
    if(n.type==='ReturnStatement')return t.returnStatement(n.argument?expr(n.argument):null);
    throw Error('Unsupported statement or write');
  };
  return generate(t.objectMethod('method',t.identifier(name),fn.params.map(p=>t.cloneNode(p)),stmt(fn.body)),{comments:false}).code;
}

// Closed event-only forwarding graphs may be restored even when the source
// uses them internally. No target call site is added or rewritten. Each leaf
// is exactly this.$emit(name, payload), not an arbitrary missing method body.
function eventForwarders(ctx,src,methods) {
  const plans=new Map(), active=new Set();
  let binding;
  traverse(ctx.ast,{Program(p){binding=p.scope.getBinding('san');p.stop();}});
  if(!binding?.constant||binding.path.node.type!=='VariableDeclarator'
    ||binding.path.node.init?.type!=='CallExpression'||binding.path.node.init.optional
    ||binding.path.node.init.callee.type!=='Identifier'||binding.path.node.init.callee.name!=='require'
    ||binding.path.node.init.arguments.length!==1||binding.path.node.init.arguments[0]?.value!=='san'
    ||binding.path.scope.getBinding('require')||one(ctx.parent,'fire')
    ||one(methods,'$emit')||one(src.object,'$emit')||fieldNames(src.object,true).has('$emit'))return plans;
  let patched=false;
  walk(ctx.ast,n=>{if(n.type==='AssignmentExpression'||n.type==='UpdateExpression'){
    let root=n.type==='AssignmentExpression'?n.left:n.argument;
    while(root?.type==='MemberExpression')root=root.object;
    if(root?.type==='Identifier'&&root.name==='san')patched=true;
  }});
  if(patched)return plans;
  const compact=n=>generate(n,{compact:true,comments:false}).code;
  const shape=(name,fn)=>t.objectMethod('method',t.identifier(name),
    fn.params.map(p=>t.cloneNode(p,true)),t.cloneNode(fn.body,true));
  const visit=name=>{
    if(plans.has(name))return plans.get(name);
    if(typeof name!=='string'||!/^[$A-Z_a-z][$\w]*$/.test(name)
      ||active.has(name)||reserved.has(name)||name.startsWith('_'))return null;
    const source=one(methods,name),fn=source&&resolvedFunction(source,ctx.source_function_bindings);
    if(!fn||fn.type==='ArrowFunctionExpression'||fn.async||fn.generator
      ||fn.body.type!=='BlockStatement'||fn.body.directives?.length||fn.body.body.length!==1
      ||fn.params.some(p=>p.type!=='Identifier')
      ||new Set(fn.params.map(p=>p.name)).size!==fn.params.length)return null;
    const statement=fn.body.body[0],call=statement.type==='ExpressionStatement'&&statement.expression;
    if(call?.type!=='CallExpression'||call.optional||call.callee.type!=='MemberExpression'
      ||call.callee.computed||call.callee.object.type!=='ThisExpression')return null;
    const params=new Set(fn.params.map(p=>p.name));
    if(!call.arguments.every(a=>(a.type==='Identifier'&&params.has(a.name))
      ||['StringLiteral','NumericLiteral','BooleanLiteral','NullLiteral'].includes(a.type)))return null;
    const called=call.callee.property.name,copy=shape(name,fn);
    active.add(name);
    if(called==='$emit'){
      if(call.arguments.length!==2){active.delete(name);return null;}
      copy.body.body[0].expression.callee.property=t.identifier('fire');
    }else{
      const dependency=visit(called);
      if(!dependency||call.arguments.length!==dependency.node.params.length){active.delete(name);return null;}
    }
    active.delete(name);
    const target=one(ctx.parent,name),existing=target&&resolvedFunction(target,ctx.target_function_bindings);
    if(target){
      if(!existing||existing.async||existing.generator||existing.type==='ArrowFunctionExpression'
        ||compact(shape(name,existing))!==compact(copy))return null;
    }else{
      const refs=references(ctx.parent,ctx.event_forwarder_template,false,name);
      if(refs.count||refs.uncertain)return null;
    }
    const plan={node:copy,text:generate(copy,{comments:false}).code,missing:!target};
    plans.set(name,plan);return plan;
  };
  for(const source of methods.properties)visit(key(source));
  return plans;
}

module.exports=function preserveMethods(ctx,src,methods){
  const contracts=ctx.method_contracts;
  if(!plain(methods)||!plain(src.object)||!plain(ctx.parent)||one(ctx.parent,'mixins')||one(ctx.parent,'extends')){
    contracts?.push({status:'unassessed',reason:'ambiguous_options'});return;
  }
  const legacy=!!one(ctx.parent,'methods');
  const outer=/<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(ctx.input.code);
  ctx.source_function_bindings=functionBindings(src.ast);
  ctx.target_function_bindings=functionBindings(ctx.ast);
  ctx.event_forwarder_template=outer?.[1]||'';
  const forwarding=eventForwarders(ctx,src,methods);
  // Other source-proven rewrites can atomically depend only on additions
  // actually scheduled in this transaction, not arbitrary proposed methods.
  ctx.pending_event_forwarders=new Map();
  const additions=[];
  let eventAdditions=0,ordinaryAdditions=0;
  for(const source of methods.properties){
    if(!resolvedFunction(source,ctx.source_function_bindings))continue;
    const name=key(source), target=one(ctx.parent,name), exists=!!resolvedFunction(target,ctx.target_function_bindings);
    // Existing reserved-name normalization owns this unavoidable San factory
    // collision; an interface check must not overwrite initData with business logic.
    if(name==='initData'){contracts?.push({name,status:'reserved_factory_mapping_delegated'});continue;}
    const a=references(src.object,src.template,true,name), b=references(ctx.parent,outer?.[1]||'',false,name);
    const contract={name,status:exists?'callable_present':target?'noncallable_or_unproven':'missing',legacy_wrapper:legacy,
      source_references:a,target_references:b,restore_eligible:false};contracts?.push(contract);
    if(!a.uncertain&&!a.count&&b.count){
      ctx.findings.push({code:'source_method_trigger_added',location:`script.methods.${name}`,
        message:`Source method ${name} has no internal source references, but target adds ${b.count} explicit reference(s); do not invent UI or lifecycle triggers.`});
    }
    const assignment=dynamicAssignment(resolvedFunction(source,ctx.source_function_bindings));
    if(assignment){
      contract.dynamic_assignment={...assignment,target_status:exists?'callable_unproven':'missing'};
      if(exists){
        let proof;
        try{proof=declaredStateAssignment(ctx,src,methods,name,target);}
        catch(_){proof={contract:'source_internal_declared_state_assignment_v1',status:'unproven',
          arbitrary_key_semantics_proven:false,refusals:['scoped_assignment_analysis_unavailable']};}
        contract.dynamic_assignment.scoped_proof=proof;
        if(proof.status==='proven_for_source_internal_calls'){
          contract.dynamic_assignment.target_status=proof.status;
          contract.status=proof.status;
          continue;
        }
        contract.status='callable_semantics_unproven';
        ctx.findings.push({code:'source_dynamic_assignment_unproven',location:`script.methods.${name}`,
          message:'Dynamic setter is unproven even under the source-internal declared-state contract: '+proof.refusals.join(', ')+'. Do not waive unknown calls or claim arbitrary public-key equivalence.',
          details:proof});
        continue;
      }
    }
    if(exists)continue;
    ctx.findings.push({code:'source_method_interface_not_landed',location:`script.methods.${name}`,
      message:`Source method ${name} has no proven callable method on the exported San parent.`});
    const event=forwarding.get(name);
    if(!legacy&&!target&&event?.missing){
      contract.restore_eligible=true;
      contract.proof='closed_two_argument_source_emit_forwarding_graph_no_target_triggers';
      if(ctx.input.repair){additions.push(event.text);eventAdditions++;ctx.pending_event_forwarders.set(name,event.node);}
      continue;
    }
    // Never overwrite an existing option or restore an internally used method
    // whose new call timing/effects cannot be established here.
    if(legacy||target||a.count||b.count||a.uncertain||b.uncertain||reserved.has(name))continue;
    let text;try{text=restore(source,ctx,src,methods);}catch(e){contract.refusal=e.message;continue;}
    contract.restore_eligible=true;
    if(ctx.input.repair){additions.push(text);ordinaryAdditions++;}
  }
  if(additions.length){
    const last=ctx.parent.properties.at(-1),position=last?last.end:ctx.parent.start+1;
    ctx.edit(ctx.offset+position,ctx.offset+position,(last?',':'')+'\n'+additions.join(',\n')+'\n');
    if(ordinaryAdditions)ctx.changes.push('restored_source_unreferenced_method_interfaces');
    if(eventAdditions)ctx.changes.push('restored_source_event_forwarding_interfaces');
  }
};

// Shared recognition only, not an implementation of arbitrary instance writes.
module.exports.inspectDynamicAssignment = dynamicAssignment;
