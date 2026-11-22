// AST-backed, deliberately narrow repairs. No generated code is executed here.
const fs = require('fs');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const sourcePhaseRepairs = require('./source_phase_semantics.cjs');
const t = require('@babel/types');
const generate = require('@babel/generator').default;
const {parentOf} = require('./inline_identifier_recovery.cjs');
const {one,safe,sourceParent,declared,same} = require('./source_render_call_semantics.cjs');

const key = p => !p.computed && p.key && (p.key.name || p.key.value);
const escapeRE = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const member = (n, object, name) => n && n.type === 'MemberExpression' && !n.computed
  && n.object.type === object && n.property.name === name;
const isComponent = n => n && n.type === 'CallExpression' && n.callee.type === 'MemberExpression'
  && n.callee.object.name === 'san' && n.callee.property.name === 'defineComponent'
  && n.arguments.length === 1 && n.arguments[0].type === 'ObjectExpression';

function wrapperTarget(method) {
  if (method.type !== 'ObjectMethod' || method.async || method.generator || method.params.length !== 1
      || method.params[0].type !== 'Identifier' || method.body.body.length !== 1) return null;
  const param = method.params[0].name;
  const stmt = method.body.body[0];
  if (stmt.type !== 'IfStatement' || stmt.alternate) return null;
  let cond = stmt.test;
  if (cond.type === 'LogicalExpression' && cond.operator === '&&'
      && cond.left.type === 'Identifier' && cond.left.name === param) cond = cond.right;
  const field = (n, name) => n && n.type === 'MemberExpression' && !n.computed
    && n.object.type === 'Identifier' && n.object.name === param && n.property.name === name;
  if (cond.type !== 'BinaryExpression' || cond.operator !== '==='
      || !field(cond.left, 'target') || !field(cond.right, 'currentTarget')) return null;
  let consequent = stmt.consequent;
  if (consequent.type === 'BlockStatement' && consequent.body.length === 1) consequent = consequent.body[0];
  if (consequent.type !== 'ExpressionStatement') return null;
  const call = consequent.expression;
  if (call.type !== 'CallExpression' || call.arguments.length || call.callee.type !== 'MemberExpression'
      || call.callee.computed || call.callee.object.type !== 'ThisExpression') return null;
  return call.callee.property.name;
}

function pureArithmetic(n, params) {
  if (!n) return false;
  if (n.type === 'NumericLiteral') return true;
  if (n.type === 'Identifier') return params.includes(n.name);
  if (n.type === 'UnaryExpression' && ['+', '-'].includes(n.operator)) return pureArithmetic(n.argument, params);
  if (n.type === 'BinaryExpression' && ['+', '-', '*', '/', '%', '**'].includes(n.operator))
    return pureArithmetic(n.left, params) && pureArithmetic(n.right, params);
  return false;
}

// Copy only tiny source-backed handlers whose complete effects are understood:
// assigning a parameter to declared root state, and calls to existing methods
// with parameter/literal arguments. No loops, async, globals or nested mutation.
function sourceHandler(source, parent, dataNames) {
  if (!source || source.is_async || !Array.isArray(source.params) || source.params.length !== 1
      || !/^[A-Za-z_$][\w$]*$/.test(source.params[0])) return null;
  let method;
  try { method = parser.parseExpression(`({${source.name}(${source.params[0]}) ${source.body_full || source.body}})`).properties[0]; }
  catch (_) { return null; }
  const param = source.params[0], body = source.body_full || source.body;
  const safeArg = n => {
    if (!n) return false;
    if (['StringLiteral', 'NumericLiteral', 'BooleanLiteral', 'NullLiteral'].includes(n.type)) return true;
    if (n.type === 'Identifier') return n.name === param;
    if (n.type === 'MemberExpression' && !n.computed && n.object.type !== 'ThisExpression') return safeArg(n.object);
    if (n.type === 'TemplateLiteral') return n.expressions.every(safeArg);
    return false;
  };
  const statements = [];
  for (const stmt of method.body.body) {
    if (stmt.type !== 'ExpressionStatement') return null;
    const expr = stmt.expression;
    if (expr.type === 'AssignmentExpression' && expr.operator === '=' && expr.left.type === 'MemberExpression'
        && !expr.left.computed && expr.left.object.type === 'ThisExpression'
        && dataNames.has(expr.left.property.name) && safeArg(expr.right)) {
      const prefix = `({${source.name}(${param}) `;
      statements.push(`this.data.set('${expr.left.property.name}', ${(`${prefix}${body}})`).slice(expr.right.start, expr.right.end)});`);
    } else if (expr.type === 'CallExpression' && expr.callee.type === 'MemberExpression' && !expr.callee.computed
        && expr.callee.object.type === 'ThisExpression'
        && parent.properties.some(p => key(p) === expr.callee.property.name && p.type === 'ObjectMethod')
        && expr.arguments.every(safeArg)) {
      const sourceCode = `({${source.name}(${param}) ${body}})`;
      statements.push(sourceCode.slice(stmt.start, stmt.end));
    } else return null;
  }
  return statements.length ? `${source.name}(${param}) {\n    ${statements.join('\n    ')}\n  }` : null;
}

function normalizeOptionShape(code) {
  const block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
  if(!block)return {code,changes:[]};
  const script=block[1],offset=block.index+block[0].indexOf('>')+1,edits=[];
  const ast=parser.parse(script,{sourceType:'unambiguous'});
  const reserved=new Set(['initData','data','computed','components','template','watch','fire','attach','detach','dispose',
    'inited','created','attached','detached','disposed','updated','compiled','dataTypes','filters','constructor','__proto__']);
  traverse(ast,{CallExpression(path){
    if(!isComponent(path.node))return;
    const object=path.node.arguments[0],wrappers=object.properties.filter(p=>key(p)==='methods');
    if(wrappers.length!==1||wrappers[0].type!=='ObjectProperty'||wrappers[0].value.type!=='ObjectExpression')return;
    const wrapper=wrappers[0],methods=wrapper.value.properties,names=methods.map(key);
    if(!methods.length||new Set(names).size!==names.length||methods.some(p=>!key(p)||p.computed
        ||!(p.type==='ObjectMethod'&&p.kind==='method'||p.type==='ObjectProperty'&&['FunctionExpression','ArrowFunctionExpression'].includes(p.value.type)))
        ||names.some(n=>reserved.has(n)||object.properties.some(p=>p!==wrapper&&key(p)===n)))return;
    edits.push({start:offset+wrapper.start,end:offset+wrapper.end,text:script.slice(wrapper.value.start+1,wrapper.value.end-1)});
  }});
  edits.sort((a,b)=>b.start-a.start);
  if(edits.some((e,i)=>i&&e.end>edits[i-1].start))return {code,changes:[]};
  let next=code;for(const e of edits)next=next.slice(0,e.start)+e.text+next.slice(e.end);
  if(edits.length)parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(next)[1],{sourceType:'unambiguous'});
  return {code:next,changes:edits.length?['flattened_parsed_component_method_options']:[]};
}

// Source computed values must not silently become ordinary San methods. Move
// only an existing exact source-body translation with no script/event callers,
// unknown captures, writes or ambiguous option shapes. Never invent a getter.
function computedOptions(code,vue,repair) {
  const result={code,changes:[],findings:[]},src=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(vue||''),
    block=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
  if(!src||!block)return result;
  const original=sourceParent(parser.parse(src[1],{sourceType:'unambiguous'})),script=block[1],
    ast=parser.parse(script,{sourceType:'unambiguous'}),parent=parentOf(ast),computed=one(original,'computed')?.value;
  if(!safe(original)||!safe(parent)||!safe(computed)||['mixins','extends'].some(k=>one(original,k)||one(parent,k)))return result;
  const fn=p=>t.isObjectMethod(p)&&p.kind==='method'?p:t.isObjectProperty(p)&&t.isFunctionExpression(p.value)?p.value:null;
  const targetComputed=one(parent,'computed')?.value,fields=declared(original,true),names=new Set(computed.properties.map(key));
  const globals=new Set(['undefined','NaN','Infinity','Math','Date','String','Number','Boolean','Array','Object','JSON']);
  const readonly=new Set(['filter','map','find','findIndex','some','every','includes','indexOf','lastIndexOf','slice','concat','join','reduce',
    'split','trim','toLowerCase','toUpperCase','toFixed','toString','getTime','getHours','getMinutes','getSeconds','getDate','getMonth','getFullYear',
    'toLocaleTimeString','toLocaleDateString','abs','min','max','floor','ceil','round','pow','sqrt','isArray','keys','values','entries','stringify']);
  const moved=new Map(), uses=new Map(), blocked=new Set();let trusted=false;
  traverse(ast,{Program(p){const b=p.scope.getBinding('san'),n=b?.path.node;
    trusted=!!b?.constant&&t.isVariableDeclarator(n)&&t.isCallExpression(n.init)&&t.isIdentifier(n.init.callee,{name:'require'})
      &&!b.path.scope.getBinding('require')&&n.init.arguments.length===1&&t.isStringLiteral(n.init.arguments[0],{value:'san'});}});
  // A Vue computed value is not callable. Some generated code converts both
  // the getter and its consumers into methods. Relocation must repair the
  // complete dependency group atomically, or San computed callbacks crash.
  const lifecycle={inited:'created',attached:'mounted',disposed:'beforeDestroy'};
  traverse(ast,{MemberExpression(p){
    const n=p.node,name=!n.computed&&t.isThisExpression(n.object)&&n.property.name;
    if(!names.has(name))return;
    let owner=p.getFunctionParent();while(owner?.isArrowFunctionExpression())owner=owner.getFunctionParent();
    let option=owner?.node;
    if(t.isFunctionExpression(option)&&owner.parentPath.isObjectProperty())option=owner.parentPath.node;
    const rootOption=option&&(parent.properties.includes(option)||targetComputed?.properties?.includes(option)),ownerName=rootOption&&key(option);
    const originalOwner=ownerName&&(one(computed,ownerName)||one(one(original,'methods')?.value,ownerName)
      ||one(original,lifecycle[ownerName]||ownerName));
    const call=p.parentPath.isCallExpression()&&p.parent.callee===n;
    const invalid=!originalOwner||!rootOption||!call||p.parent.arguments.length||p.parent.optional;
    if(invalid){blocked.add(name);return;}
    // Source methods calling a computed value as a function are not a valid
    // value-read proof. Never reinterpret their public call contract.
    let sourceCall=false;
    const inspect=node=>{if(!node||typeof node!=='object')return;
      if(t.isCallExpression(node)&&t.isMemberExpression(node.callee)&&t.isThisExpression(node.callee.object)
          &&(!node.callee.computed&&node.callee.property.name===name||node.callee.computed&&node.callee.property.value===name))sourceCall=true;
      for(const [k,v] of Object.entries(node))if(!['loc','extra','comments'].includes(k)){
        if(Array.isArray(v))v.forEach(inspect);else if(v&&typeof v==='object')inspect(v);}};
    inspect(originalOwner);
    if(sourceCall){blocked.add(name);return;}
    if(!uses.has(name))uses.set(name,[]);uses.get(name).push(p.parent);
  }});
  const valueReads=node=>{
    const file=t.file(t.program([t.expressionStatement(t.functionExpression(null,[],t.cloneNode(node,true)))]));
    traverse(file,{CallExpression(p){const c=p.node.callee;
      if(t.isMemberExpression(c)&&!c.computed&&t.isThisExpression(c.object)&&names.has(c.property.name)
          &&!blocked.has(c.property.name)&&!p.node.arguments.length&&!p.node.optional)
        p.replaceWith(parser.parseExpression('this.data.get('+JSON.stringify(c.property.name)+')'));
    }});return file.program.body[0].expression.body;
  };
  const writableLocal=p=>{
    let root=p.node.left||p.node.argument;while(t.isMemberExpression(root))root=root.object;
    if(!t.isIdentifier(root))return false;
    const binding=p.scope.getBinding(root.name);
    if(!binding)return false;
    const fresh=n=>t.isObjectExpression(n)&&n.properties.every(p=>t.isObjectProperty(p)&&!p.computed
      &&['StringLiteral','NumericLiteral','BooleanLiteral','NullLiteral'].includes(p.value.type));
    if(binding.path.isVariableDeclarator())return binding.constant&&fresh(binding.path.node.init);
    // reduce's accumulator may be mutated only when allocated by this call,
    // never when it is a state object, callback item or arbitrary parameter.
    const callback=binding.path.findParent(p=>p.isFunction());
    const call=callback?.parentPath;
    return binding.kind==='param'&&callback?.isArrowFunctionExpression()&&callback.node.params[0]===binding.path.node
      &&call?.isCallExpression()&&call.node.arguments[0]===callback.node&&call.node.arguments.length===2
      &&t.isMemberExpression(call.node.callee)&&!call.node.callee.computed&&call.node.callee.property.name==='reduce'
      &&fresh(call.node.arguments[1]);
  };
  for(const prop of computed.properties){
    const name=key(prop),source=fn(prop),existing=one(targetComputed,name),candidate=one(parent,name),target=fn(candidate);
    if(!source||source.async||source.generator||source.params.length||fn(existing))continue;
    let eligible=!!target&&!target.async&&!target.generator&&!target.params.length&&trusted
      &&/^[A-Za-z_$][\w$]*$/.test(name)&&!['data','watch','fire','initData','inited','attached','disposed','constructor','prototype','__proto__'].includes(name)
      &&!existing&&(!targetComputed||safe(targetComputed))&&!fields.has(name)&&!one(one(original,'methods')?.value,name)&&!blocked.has(name);
    const tree=t.file(t.program([t.expressionStatement(t.functionExpression(null,[],t.cloneNode(source.body,true)))]));
    const root=tree.program.body[0].expression;
    traverse(tree,{
      ReferencedIdentifier(p){if(!p.scope.getBinding(p.node.name)&&!globals.has(p.node.name))eligible=false;},
      ThisExpression(p){const n=p.parent;if(!t.isMemberExpression(n)||n.object!==p.node||n.computed
        ||!fields.has(n.property.name)&&!names.has(n.property.name))eligible=false;
        let owner=p.getFunctionParent();while(owner?.isArrowFunctionExpression())owner=owner.getFunctionParent();
        if(owner?.node!==root)eligible=false;},
      AssignmentExpression(p){if(!writableLocal(p))eligible=false;},UpdateExpression(p){if(!writableLocal(p))eligible=false;},AwaitExpression(){eligible=false;},YieldExpression(){eligible=false;},
      Super(){eligible=false;},TaggedTemplateExpression(){eligible=false;},
      UnaryExpression(p){if(p.node.operator==='delete')eligible=false;},
      NewExpression(p){if(!t.isIdentifier(p.node.callee,{name:'Date'})||p.scope.getBinding('Date'))eligible=false;},
      CallExpression(p){const c=p.node.callee;if(!t.isMemberExpression(c)||c.computed||!readonly.has(c.property.name)
        ||t.isThisExpression(c.object)||p.node.optional||p.node.arguments.some(a=>t.isSpreadElement(a)))eligible=false;},
      MemberExpression:{exit(p){const n=p.node;if(t.isThisExpression(n.object)&&!n.computed&&(fields.has(n.property.name)||names.has(n.property.name))){
        p.replaceWith(t.callExpression(t.memberExpression(t.memberExpression(t.thisExpression(),t.identifier('data')),t.identifier('get')),[t.stringLiteral(n.property.name)]));p.skip();}}}
    });
    if(!target||!same(root.body,valueReads(target.body)))eligible=false;
    traverse(ast,{MemberExpression(p){const n=p.node;if(t.isThisExpression(n.object)&&n.computed&&n.property.value===name)eligible=false;},
      AssignmentExpression(p){let n=p.node.left;while(t.isMemberExpression(n))n=n.object;if(t.isIdentifier(n,{name:'san'}))eligible=false;}});
    const template=/<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(code)?.[1]||'',escaped=escapeRE(name);
    if(new RegExp('\\b'+escaped+'\\s*\\(').test(template)||new RegExp('on-[\\w-]+\\s*=\\s*["\\\']\\s*'+escaped+'(?:\\s*["\\\']|\\b)').test(template))eligible=false;
    result.findings.push({code:'source_computed_option_not_landed',location:'script.computed.'+name,
      message:'Source computed value '+name+' is missing from San computed options; an ordinary method does not supply a reactive template value.',
      details:{contract:'source_computed_option_shape_v1',name,source_matched_relocation_eligible:!!eligible}});
    if(repair&&eligible)moved.set(name,candidate);
  }
  // Do not strand a getter depending on another ordinary method that could
  // not itself be proven and relocated. Existing computed values are retained.
  let removed=true;while(removed){removed=false;for(const [name,prop] of moved){
    const text=generate(valueReads(fn(prop).body),{compact:true}).code;
    if([...names].some(dep=>new RegExp('this\\.data\\.get\\(["\\\']'+escapeRE(dep)+'["\\\']\\)').test(text)
        &&!fn(one(targetComputed,dep))&&!moved.has(dep))){moved.delete(name);removed=true;}
  }}
  if(moved.size){
    const render=prop=>{
      let text=script.slice(prop.start,prop.end),edits=[];
      for(const name of moved.keys())for(const use of uses.get(name)||[])if(use.start>=prop.start&&use.end<=prop.end)
        edits.push({start:use.start-prop.start,end:use.end-prop.start,text:'this.data.get('+JSON.stringify(name)+')'});
      for(const e of edits.sort((a,b)=>b.start-a.start))text=text.slice(0,e.start)+e.text+text.slice(e.end);
      return text;
    };
    const properties=parent.properties.filter(p=>!moved.has(key(p))&&key(p)!=='computed').map(render);
    const getters=[...(targetComputed?.properties||[]),...moved.values()].map(render);
    properties.push('computed:{'+getters.join(',')+'}');
    const offset=block.index+block[0].indexOf('>')+1;
    result.code=code.slice(0,offset+parent.start)+'{'+properties.join(',')+'}'+code.slice(offset+parent.end);
    parser.parse(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(result.code)[1],{sourceType:'unambiguous'});
    result.changes.push('restored_source_matched_computed_option_shape');
  }
  return result;
}

function processInput(input) {
  const prepass=input.repair?normalizeOptionShape(input.code):{code:input.code,changes:[]};
  const values=computedOptions(prepass.code,input.vue,input.repair);
  const code = values.code;
  input={...input,code};
  const block = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
  if (!block) return {code, changes: [], wrappers: {}};
  const script = block[1], offset = block.index + block[0].indexOf('>') + 1;
  const ast = parser.parse(script, {sourceType: 'unambiguous'});
  const edits = [], changes = [...prepass.changes,...values.changes], wrappers = {}, findings = [...values.findings], startup_contracts = [], method_contracts = [], watcher_contracts = [];
  const record_update_contracts = [];
  const shared_record_contracts = [];
  const parent_initialization_contracts = [];
  const computed_collection_contracts = [];
  const filter_method_contracts = [];
  let parent = null;
  const children = [];
  const definitions=[];
  traverse(ast, {
    CallExpression(path) {if(isComponent(path.node))definitions.push({path,object:path.node.arguments[0]});},
    AssignmentExpression(path) {
      const n = path.node;
      if (member(n.left, 'Identifier', 'exports') && n.left.object.name === 'module' && isComponent(n.right)) {
        if (parent) throw new Error('Ambiguous exports');
        parent = n.right.arguments[0];
      }
    },
    VariableDeclarator(path) {
      if (path.node.id.type === 'Identifier' && isComponent(path.node.init)) children.push(path.node.init.arguments[0]);
    }
  });
  const edit = (start, end, text) => edits.push({start, end, text});
  // San computed callbacks are not an instance namespace. Diagnose all known
  // component scopes; repair only source-declared root computed VALUE reads.
  // No component/method names are hard-coded; no source or target is executed.
  let sourceRoot = null;
  try {
    const sourceScript=/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(input.vue||'')?.[1];
    if(sourceScript)traverse(parser.parse(sourceScript,{sourceType:'unambiguous'}),{
      ExportDefaultDeclaration(p){if(p.node.declaration.type==='ObjectExpression')sourceRoot=p.node.declaration;},
      AssignmentExpression(p){const n=p.node;
        if(member(n.left,'Identifier','exports')&&n.left.object.name==='module'&&n.right.type==='ObjectExpression')sourceRoot=n.right;}
    });
  } catch (_) { /* No proof means no automatic repair. */ }
  const unique=(object,name)=>object?.properties.filter(p=>key(p)===name).length===1
    ?object.properties.find(p=>key(p)===name):null;
  const sourceComputed=unique(sourceRoot,'computed')?.value;
  const sourceNames=new Set(sourceComputed?.type==='ObjectExpression'?sourceComputed.properties.filter(p=>
    p.type==='ObjectMethod'&&p.kind==='method'&&!p.params.length&&!p.async&&!p.generator
    &&unique(sourceComputed,key(p))===p).map(key):[]);
  const components=[...new Set([parent,...children,...definitions.map(d=>d.object)].filter(Boolean))];
  const init_data_store_access=[],init_data_analysis_errors=[];
  for(const definition of definitions){
    const fields=definition.object.properties.filter(p=>key(p)==='initData');
    if(!fields.length)continue;
    const item=fields[0];let fn=item.type==='ObjectMethod'?item:item.value;
    if(fields.length!==1){init_data_analysis_errors.push('duplicate_initData');continue;}
    if(fn?.type==='Identifier'){
      const binding=definition.path.scope.getBinding(fn.name),n=binding?.path.node;
      fn=binding?.constant?(n?.type==='FunctionDeclaration'?n:n?.type==='VariableDeclarator'?n.init:null):null;
    }
    if(!fn||!['ObjectMethod','FunctionExpression','ArrowFunctionExpression','FunctionDeclaration'].includes(fn.type)){
      init_data_analysis_errors.push('unresolved_initData_factory');continue;
    }
    if(fn.params.length||fn.async||fn.generator){init_data_analysis_errors.push('initData_signature_unassessed');continue;}
    const component=definition.object===parent?'exported component':'inline component at '+definition.object.loc.start.line;
    // Use Babel nodes, never text searching: strings, comments and template
    // literal text are data. A nested ordinary function has another this.
    traverse(ast,{MemberExpression:inspect,OptionalMemberExpression:inspect});
    function inspect(path){
      const n=path.node;
      if(n.start<fn.body.start||n.end>fn.body.end)return;
      const name=n.computed?n.property.value:n.property.name;
      if(name!=='data')return;
      let owner=path.getFunctionParent();while(owner?.isArrowFunctionExpression()&&owner.node!==fn)owner=owner.getFunctionParent();
      if(owner?.node!==fn)return;
      let receiver=n.object,seen=new Set();
      while(receiver?.type==='Identifier'&&!seen.has(receiver.name)){
        seen.add(receiver.name);const binding=path.scope.getBinding(receiver.name),decl=binding?.path.node;
        if(!binding?.constant||decl?.type!=='VariableDeclarator'||!decl.init
            ||decl.start<fn.start||decl.end>fn.end)break;
        receiver=decl.init;
      }
      if(receiver?.type==='ThisExpression')init_data_store_access.push({component,line:n.loc.start.line,column:n.loc.start.column});
    }
  }
  const unsafeStores=new Set();
  traverse(ast,{
    AssignmentExpression(p){let n=p.node.left;
      while(n?.type==='MemberExpression'&&n.object.type==='MemberExpression')n=n.object;
      if(member(n,'ThisExpression','data'))for(const c of components)
        if(c.start<p.node.start&&c.end>p.node.end)unsafeStores.add(c);},
    UpdateExpression(p){if(member(p.node.argument,'ThisExpression','data'))for(const c of components)
      if(c.start<p.node.start&&c.end>p.node.end)unsafeStores.add(c);}
  });
  traverse(ast,{
    MemberExpression(path){
      const n=path.node, namespace=n.object;
      if(!member(namespace,'ThisExpression','computed'))return;
      const component=components.filter(c=>c.start<n.start&&c.end>n.end).sort((a,b)=>(a.end-a.start)-(b.end-b.start))[0];
      const computed=unique(component,'computed')?.value;
      if(computed?.type!=='ObjectExpression')return;
      let owner=path.getFunctionParent();while(owner?.isArrowFunctionExpression())owner=owner.getFunctionParent();
      const direct=owner?.node.type==='ObjectMethod'?owner.parent:owner?.parentPath?.parent;
      if(direct!==component&&direct!==computed)return; // Nested ordinary function has a different this.
      const name=!n.computed&&n.property.type==='Identifier'?n.property.name:
        n.computed&&n.property.type==='StringLiteral'?n.property.value:null;
      let context=path;
      while(context.parentPath?.isMemberExpression()&&context.parent.object===context.node)context=context.parentPath;
      const use=context.parent;
      const unsafe=use?.type==='AssignmentExpression'&&use.left===context.node
        ||use?.type==='UpdateExpression'||use?.type==='UnaryExpression'&&use.operator==='delete'
        ||['CallExpression','NewExpression','OptionalCallExpression','TaggedTemplateExpression'].includes(use?.type);
      const entry=name&&unique(computed,name);
      const safe=component===parent&&sourceNames.has(name)&&entry?.type==='ObjectMethod'&&entry.kind==='method'
        &&!entry.params.length&&!entry.async&&!entry.generator&&!unsafe
        &&!['data','mixins','extends'].some(k=>component.properties.some(p=>key(p)===k))
        &&!unsafeStores.has(component)
        &&!component.properties.some(p=>key(p)===name);
      findings.push({code:'invalid_san_computed_namespace_access',location:'script',
        message:'Read San computed values through this.data.get(name), not this.computed: '+(name||'<dynamic>'),
        details:{contract:'computed_namespace_v1',component:component===parent?'root':'inline_child',
          name,line:n.loc.start.line,column:n.loc.start.column,source_declared_read_repairable:!!safe}});
      if(input.repair&&safe){edit(offset+n.start,offset+n.end,'this.data.get('+JSON.stringify(name)+')');
        changes.push('source_declared_computed_namespace_value_read');}
    }
  });
  if (parent) {
    for (const method of parent.properties) {
      const name = key(method), target = wrapperTarget(method);
      if (name && target && parent.properties.filter(p => key(p) === name).length === 1
          && parent.properties.some(p => key(p) === target && p.type === 'ObjectMethod' && !p.params.length))
        wrappers[name] = target;
    }
    sourcePhaseRepairs({input, parent, script, ast, offset, edit, changes, sourceHandler, findings, startup_contracts, method_contracts, watcher_contracts, record_update_contracts, shared_record_contracts, parent_initialization_contracts, computed_collection_contracts, filter_method_contracts});
    if (input.repair) {
      const outer = /<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(code);
      // A diagnosed source .self contract is required, not just a suggestive name.
      const selfTargets = new Set(Array.from((input.vue || '').matchAll(/@click\.self\s*=\s*(["'])([\w$]+)\1/g), m => m[2]));
      if (outer) {
        const start = outer.index + outer[0].indexOf('>') + 1;
        for (const [name, target] of Object.entries(wrappers)) {
          if (!selfTargets.has(target)) continue;
          const pattern = new RegExp('on-click\\s*=\\s*(["\'])' + escapeRE(name) + '\\1', 'g');
          for (const match of outer[1].matchAll(pattern)) {
            edit(start + match.index, start + match.index + match[0].length, `on-click=${match[1]}${name}($event)${match[1]}`);
            changes.push('explicit_self_wrapper_event');
          }
        }
      }
      const options = input.ssm?.script?.options || {};
      const bindings = input.ssm?.template?.event_bindings || [];
      const dataNames = new Set((options.data || []).map(p => p.name));
      for (const method of parent.properties) {
        const name = key(method);
        if (!name || method.type !== 'ObjectMethod' || method.params.length
            || parent.properties.filter(p => key(p) === name).length !== 1
            || !/\bthis\.event\b/.test(script.slice(method.body.start, method.body.end))) continue;
        const expected = bindings.filter(b => b.handler_name === name || b.handler_expression?.startsWith(name + '('));
        const expressions = [...new Set(expected.map(b => b.handler_expression))];
        if (expressions.length !== 1 || !new RegExp('^' + escapeRE(name) + '\\([A-Za-z_$][\\w$]*(?:\\.[A-Za-z_$][\\w$]*)*\\)$').test(expressions[0])) continue;
        const sources = (options.methods || []).filter(m => m.name === name);
        if (sources.length !== 1 || !outer) continue;
        const restored = sourceHandler(sources[0], parent, dataNames);
        if (!restored) continue;
        const currentCalls = Array.from(outer[1].matchAll(/\bon-[\w-]+\s*=\s*(["'])(.*?)\1/g), m => m[2]);
        if (currentCalls.some(expr => expr.startsWith(name + '(') && expr !== expressions[0])) continue;
        const start = outer.index + outer[0].indexOf('>') + 1;
        const bindingsToFix = [];
        for (const match of outer[1].matchAll(/<([A-Za-z][\w-]*)\b[^>]*>/g)) {
          for (const event of expected) {
            if (match[1] !== event.element_tag) continue;
            const pattern = new RegExp('\\bon-' + escapeRE(event.event_name) + '\\s*=\\s*(["\'])' + escapeRE(name) + '\\1', 'g');
            for (const attr of match[0].matchAll(pattern)) bindingsToFix.push({start: start + match.index + attr.index,
              end: start + match.index + attr.index + attr[0].length, text: `on-${event.event_name}=${attr[1]}${expressions[0]}${attr[1]}`});
          }
        }
        const unique = [...new Map(bindingsToFix.map(e => [e.start, e])).values()];
        if (!unique.length) continue;
        edits.push(...unique);
        edit(offset + method.start, offset + method.end, restored);
        changes.push('restored_source_parameterized_event_handler');
      }
    }
  }
  if (input.repair) for (const child of children) {
    const template = child.properties.find(p => key(p) === 'template');
    const computed = child.properties.find(p => key(p) === 'computed');
    if (!template || template.type !== 'ObjectProperty' || template.value.type !== 'TemplateLiteral'
        || template.value.expressions.length || !computed || computed.value?.type !== 'ObjectExpression') continue;
    const text = template.value.quasis[0].value.raw;
    const moved = [];
    for (const method of computed.value.properties) {
      const name = key(method);
      if (!name || method.type !== 'ObjectMethod' || method.params.length || method.body.body.length !== 1
          || method.async || method.generator || child.properties.some(p => key(p) === name)) continue;
      const ret = method.body.body[0];
      const fn = ret.type === 'ReturnStatement' && ret.argument;
      if (!fn || fn.type !== 'ArrowFunctionExpression' || fn.async || fn.params.length === 0
          || fn.params.some(p => p.type !== 'Identifier') || !pureArithmetic(fn.body, fn.params.map(p => p.name))) continue;
      // All template references must be calls, and there must be no script-side
      // reference (including computed dependencies or this.data.get('name')).
      if (template.end > method.start) continue;
      const refs = Array.from(text.matchAll(new RegExp('\\b' + escapeRE(name) + '\\b', 'g')));
      if (!refs.length || refs.some(m => !/^\s*\(/.test(text.slice(m.index + name.length)))) continue;
      const remainder = script.slice(child.start, template.start) + script.slice(template.end, method.start)
        + script.slice(method.end, child.end);
      if (new RegExp('\\b' + escapeRE(name) + '\\b').test(remainder)) continue;
      let end = method.end;
      while (/\s/.test(script[end] || '') && end < script.length) end++;
      // Leave an empty computed object if needed. Remove a following comma,
      // or the preceding separator when this is the last computed property.
      let start = method.start;
      if (script[end] === ',') end++;
      else { let pos = start - 1; while (/\s/.test(script[pos] || '') && pos > 0) pos--; if (script[pos] === ',') start = pos; }
      edit(offset + start, offset + end, '');
      moved.push(`${name}(${fn.params.map(p => p.name).join(', ')}) { return ${script.slice(fn.body.start, fn.body.end)}; }`);
      changes.push('parameterized_computed_to_pure_method');
    }
    if (moved.length) edit(offset + child.start + 1, offset + child.start + 1, '\n  ' + moved.join(',\n  ') + ',\n');
  }
  // Non-overlapping edits only; adjacent method removals are deliberately
  // rejected rather than risking an ambiguous rewrite.
  edits.sort((a, b) => b.start - a.start);
  for (let i = 1; i < edits.length; i++) if (edits[i].end > edits[i - 1].start) throw new Error('Overlapping edits');
  let result = code;
  for (const e of edits) result = result.slice(0, e.start) + e.text + result.slice(e.end);
  if (edits.length) {
    const next = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(result);
    parser.parse(next[1], {sourceType: 'unambiguous'});
  }
  return {code: result, changes: [...new Set(changes)], wrappers, findings, startup_contracts, method_contracts, watcher_contracts, record_update_contracts, shared_record_contracts, parent_initialization_contracts, computed_collection_contracts, filter_method_contracts,init_data_store_access,init_data_analysis_errors};
}

try { process.stdout.write(JSON.stringify(processInput(JSON.parse(fs.readFileSync(0, 'utf8'))))); }
catch (error) { process.stdout.write(JSON.stringify({error: String(error.message)})); }
