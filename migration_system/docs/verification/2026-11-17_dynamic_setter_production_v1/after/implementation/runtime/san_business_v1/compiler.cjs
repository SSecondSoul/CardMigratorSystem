/* Parse-only canonical Options-to-San business receiver emitter.
 * Does NOT evaluate source in Node, and does NOT load a Vue component runtime.
 */
'use strict';
const fs = require('node:fs'), path = require('node:path');
const {createRequire} = require('node:module'), {createHash} = require('node:crypto');
const {isDeepStrictEqual} = require('node:util');
const {compileTemplate,eventSource}=require('./template.cjs');
const project = path.resolve(__dirname, '../..');
const engineRequire = createRequire(path.join(project, 'engine/package.json'));
const {parse} = engineRequire('@vue/compiler-sfc'), parser = engineRequire('@babel/parser');
const traverse = engineRequire('@babel/traverse').default, san = engineRequire('san');
const hash = text => createHash('sha256').update(text).digest('hex');
const contract = 'san-business-instance-v1';
const publicNames = new Set(['$data', '$props', '$attrs', '$slots', '$refs', '$parent', '$root', '$el', '$options', '$emit', '$forceUpdate', '$nextTick', '$watch']);
const allowedOptions = new Set(['name', 'props', 'data', 'methods', 'computed', 'watch', 'emits', 'inheritAttrs',
  'components','template','errorCaptured','beforeCreate', 'created', 'beforeMount', 'mounted', 'beforeUpdate', 'updated', 'beforeUnmount', 'unmounted']);
class BusinessCompileError extends Error {
  constructor(code, details) {super(code);this.code=code;this.details=details;}
}
const decline = (code, details) => {throw new BusinessCompileError(code, details);};
const property = node => !node.computed ? node.key?.name ?? node.key?.value : undefined;
function inspectSource(source) {
  const {descriptor,errors} = parse(source);
  if(errors.length || descriptor.scriptSetup || !descriptor.script || descriptor.script.lang) decline('business_source_shape_unsupported');
  const script = descriptor.script.content;
  const ast = parser.parse(script,{sourceType:'module'});
  const exports = ast.program.body.filter(node => node.type==='ExportDefaultDeclaration');
  const common = ast.program.body.filter(node=>node.type==='ExpressionStatement'&&node.expression.type==='AssignmentExpression'&&node.expression.operator==='='&&
    node.expression.left.type==='MemberExpression'&&!node.expression.left.computed&&node.expression.left.object.name==='module'&&node.expression.left.property.name==='exports');
  if(exports.length+common.length!==1 || ast.program.body.some(node=>['ImportDeclaration','ExportNamedDeclaration','ExportAllDeclaration'].includes(node.type))) decline('business_source_module_unsupported');
  const root = exports[0]?.declaration ?? common[0]?.expression.right;
  if(root.type!=='ObjectExpression' || root.properties.some(node=>node.type==='SpreadElement'||property(node)===undefined)) decline('business_options_shape_unsupported');
  for(const option of root.properties) if(!allowedOptions.has(property(option))) decline('business_public_option_not_implemented',property(option));
  const methods = root.properties.find(node=>property(node)==='methods')?.value;
  if(methods && (methods.type!=='ObjectExpression'||methods.properties.some(node=>property(node)===undefined||node.type==='SpreadElement'))) decline('business_method_layout_unsupported');
  const methodNames = methods ? methods.properties.map(property) : [];
  traverse(ast,{
    ThisExpression(p) {
      const member=p.parentPath.node;
      if(member.type==='BinaryExpression'&&['===','!=='].includes(member.operator))return;
      if(!['MemberExpression','OptionalMemberExpression'].includes(member.type)||member.object!==p.node) decline('business_this_escape_unsupported');
      const name=!member.computed?member.property.name:member.property.type==='StringLiteral'?member.property.value:undefined;
      if(name===undefined) {
        const assignment=p.parentPath.parentPath.node;
        if(assignment.type!=='AssignmentExpression'||assignment.operator!=='='||assignment.left!==member) decline('business_unknown_dynamic_read_unsupported');
      } else if(name==='$'||name==='_') decline('source_private_runtime_dependency_unsupported',name);
      else if(name.startsWith('$')&&!publicNames.has(name)) decline('business_public_api_not_implemented',name);
    },
    Identifier(p) {
      if(['Vue','eval'].includes(p.node.name)&&p.isReferencedIdentifier()&&!p.scope.getBinding(p.node.name)) decline('business_source_runtime_dependency_unsupported',p.node.name);
    },
    CallExpression(p) {if(p.node.callee.type==='Identifier'&&['require','Function'].includes(p.node.callee.name)&&!p.scope.getBinding(p.node.callee.name)) decline('business_source_module_unsupported');},
    NewExpression(p) {if(p.node.callee.type==='Identifier'&&p.node.callee.name==='Function'&&!p.scope.getBinding('Function'))decline('business_source_runtime_dependency_unsupported','Function');}
  });
  const scriptText=exports.length ? script.slice(0,exports[0].start)+'module.exports = '+script.slice(exports[0].declaration.start) : script;
  const refs=[],elementPolicies=[];
  const template=descriptor.template?.content||'';
  const compiler=engineRequire('@vue/compiler-dom');
  const sourceTemplate=compiler.parse(template);
  function findRefs(node){
    if(node.type===1){
      const attributes=[];let key;
      for(const attr of node.props||[]){
        if(attr.type===6&&attr.name==='ref')refs.push(attr.value?.content||'');
        if(attr.type===7&&attr.name==='bind'){
          if(!attr.arg?.isStatic)decline('business_dynamic_attribute_unsupported');
          const name=attr.arg.content;
          if(name==='ref')decline('business_dynamic_ref_unsupported');
          if(['class','value','checked','selected'].includes(name))attributes.push(name);
          if(name==='key')key=attr.exp?.content;
        }
      }
      if(key&&!node.props.some(attr=>attr.type===7&&attr.name==='for'))decline('business_non_loop_key_unsupported');
      const implicitOptionValue=node.tag==='option'&&!node.props.some(prop=>prop.type===6&&prop.name==='value'||prop.type===7&&prop.name==='bind'&&prop.arg?.content==='value');
      elementPolicies.push({tag:node.tag,attributes,loop:node.props.some(attr=>attr.type===7&&attr.name==='for'),...(key?{key:key.replace(/\s+/g,'')}: {}),...(implicitOptionValue?{implicitOptionValue:true}:{})});
    }
    for(const child of node.children||[])findRefs(child);
  }
  findRefs(sourceTemplate);
  const constants=new Map(ast.program.body.filter(node=>node.type==='VariableDeclaration'&&node.kind==='const')
    .flatMap(node=>node.declarations).filter(node=>node.id.type==='Identifier').map(node=>[node.id.name,node.init]));
  function childDefinitions(options,seen=new Set()){
    const declaration=options.properties.find(node=>property(node)==='components')?.value;
    if(!declaration)return {};
    if(declaration.type!=='ObjectExpression')decline('business_component_registry_not_static');
    const result={};
    for(const entry of declaration.properties){
      const name=property(entry);let value=entry.value;
      if(!name||!value)decline('business_component_registry_not_static');
      if(value.type==='Identifier')value=constants.get(value.name);
      if(!value||value.type!=='ObjectExpression'||seen.has(value))decline('business_component_definition_not_static',name);
      const next=new Set(seen);next.add(value);
      for(const option of value.properties)if(!allowedOptions.has(property(option)))decline('business_public_option_not_implemented',property(option));
      const rawTemplate=value.properties.find(node=>property(node)==='template')?.value;
      const text=rawTemplate?.type==='StringLiteral'?rawTemplate.value:
        rawTemplate?.type==='TemplateLiteral'&&!rawTemplate.expressions.length?rawTemplate.quasis[0].value.cooked:undefined;
      if(text===undefined)decline('business_inline_component_template_required',name);
      const methods=value.properties.find(node=>property(node)==='methods')?.value;
      if(methods&&(methods.type!=='ObjectExpression'||methods.properties.some(node=>property(node)===undefined)))decline('business_method_layout_unsupported');
      result[name]={sourceTemplate:text,methodNames:methods?methods.properties.map(property):[],components:childDefinitions(value,next)};
    }
    return result;
  }
  return {script:scriptText,template,methodNames,refs,elementPolicies,components:childDefinitions(root,new Set([root]))};
}
function bundle() {
  const files=['errors.cjs','runtime.cjs','owner.cjs','component.cjs','dom.cjs','registry.cjs','events.cjs','tree.cjs','expressions.cjs'];
  const modules=files.map(name=>JSON.stringify('./'+name)+':function(require,module,exports){\n'+fs.readFileSync(path.join(__dirname,name),'utf8')+'\n}').join(',\n');
  const kernelPath=path.join(project,'frontend/node_modules/@vue/reactivity/dist/reactivity.global.js');
  const kernel=fs.readFileSync(kernelPath,'utf8');
  const sharedPath=path.join(project,'frontend/node_modules/@vue/shared/dist/shared.cjs.js');
  const shared=fs.readFileSync(sharedPath,'utf8');
  const R='(()=>{\n'+kernel+'\nreturn VueReactivity;})()';
  return {text:`const __businessR=${R};\nconst __businessShared=(()=>{const module={exports:{}},exports=module.exports;\n${shared}\nreturn module.exports;})();\nconst __businessModules={${modules}};\nconst __businessCache=Object.create(null);\nfunction __businessRequire(name){if(!Object.prototype.hasOwnProperty.call(__businessModules,name))throw Error('business_dependency_not_bundled:'+name);if(__businessCache[name])return __businessCache[name].exports;const module={exports:{}};__businessCache[name]=module;__businessModules[name](__businessRequire,module,module.exports);return module.exports;}\n`,
    fingerprints:Object.fromEntries([...files.map(name=>path.join(__dirname,name)),__filename,path.join(__dirname,'template.cjs'),kernelPath,sharedPath,
      engineRequire.resolve('san/dist/san.dev.js'),engineRequire.resolve('san/package.json')].map(file=>[path.relative(project,file).replaceAll('\\','/'),hash(fs.readFileSync(file))]))};
}
function displayTemplate(template){
  const ast=engineRequire('@vue/compiler-dom').parse(template),edits=[];
  function visit(node){
    if(node.type===5){
      const expression=san.parseTemplate('<b>'+node.loc.source+'</b>').children[0].children[0].textExpr;
      if(!(expression.filters||[]).some(filter=>filter.name?.paths?.[0]?.value==='__businessDisplay')) {
        edits.push({start:node.loc.start.offset,end:node.loc.end.offset,text:'{{ '+node.content.content+' | __businessDisplay }}'});
      }
    }
    for(const child of node.children||[])visit(child);
  }
  visit(ast);
  for(const edit of edits.sort((a,b)=>b.start-a.start))template=template.slice(0,edit.start)+edit.text+template.slice(edit.end);
  return template;
}
function compile(source, target, mode) {
  const metadata=inspectSource(source);
  const production=mode==='dynamic-setter-single-component-v1';
  if(mode&&!production)decline('business_compile_mode_unsupported');
  if(production&&Object.keys(metadata.components).length)decline('business_component_tree_production_not_released');
  const {descriptor,errors}=parse(target);
  if(errors.length||!descriptor.template||!descriptor.script||descriptor.scriptSetup||descriptor.customBlocks.length)decline('business_target_shape_unsupported');
  const hasTree=Object.keys(metadata.components).length>0;
  const compiledTemplate=hasTree||production;
  const treeSpec=(function build(node){
    if(!compiledTemplate)return null;
    const generated=compileTemplate(node.sourceTemplate||node.template,{componentNames:Object.keys(node.components),reservedMethods:node.methodNames,reactiveExpressions:production});
    return {...generated,template:displayTemplate(generated.template),sourceTemplate:node.sourceTemplate||node.template,
      components:Object.fromEntries(Object.entries(node.components).map(([name,child])=>[name,build(child)]))};
  })(metadata);
  const template=compiledTemplate?treeSpec.template:displayTemplate(descriptor.template.content);
  const parsed=san.parseTemplate(template);
  const eventMethods=new Set(),elements=[];
  function visit(node){
    if(node.tagName)elements.push(node);
    for(const event of node.events||[]){const expr=event.expr;const name=expr?.name?.paths?.map(part=>part.value).join('.');if(name)eventMethods.add(name);}
    for(const child of node.children||[])visit(child);
    for(const child of node.elses||[])visit(child);
  }
  visit(parsed);
  if(elements.length!==metadata.elementPolicies.length)decline('business_template_shape_mismatch');
  for(let index=0;index<elements.length;index++){
    const node=elements[index],policy=metadata.elementPolicies[index];
    if(node.tagName!==policy.tag)decline('business_template_tag_mismatch',policy.tag);
    if(!!node.directives?.for!==policy.loop)decline('business_template_loop_mismatch',policy.tag);
    if(!policy.key&&node.directives?.for?.trackBy)decline('business_loop_key_invented');
    for(const attr of policy.attributes)if(!node.props?.some(prop=>prop.name===attr))decline('business_template_bound_attribute_missing',attr);
    if(policy.key){
      const key=node.directives?.for?.trackBy;
      const expression=key?.type===4?key.paths.map(part=>part.value).join('.'):undefined;
      if(expression!==policy.key)decline('business_loop_key_mismatch',policy.key);
    }
  }
  for(const name of eventMethods)if(!metadata.methodNames.includes(name)&&!treeSpec?.eventHandlers[name]&&!['$emit','$forceUpdate','$nextTick','$watch'].includes(name))decline('business_target_unknown_event_handler',name);
  // Template-method hidden dependencies require a separate emitter. Never silently
  // bind an untracked source helper and call that equivalent computed behavior.
  const collect=node=>{
    if(!node||typeof node!=='object')return;
    if(node.type===6&&node.name){const name=node.name.paths?.map(part=>part.value).join('.');if(metadata.methodNames.includes(name))decline('business_template_method_dependency_unsupported',name);}
    for(const [key,value]of Object.entries(node)){if(key==='events')continue;if(Array.isArray(value))value.forEach(collect);else if(value&&typeof value==='object')collect(value);}
  };
  collect(parsed);
  const built=bundle();
  const sourceScript='(()=>{const module={exports:{}};const exports=module.exports;\n'+metadata.script+'\nreturn module.exports;})()';
  const kernelHash=built.fingerprints['frontend/node_modules/@vue/reactivity/dist/reactivity.global.js'];
  const common=`{reactivityHash:${JSON.stringify(kernelHash)},toDisplayString:__businessShared.toDisplayString,normalizeClass:__businessShared.normalizeClass,stringifyStyle:value=>__businessShared.stringifyStyle(__businessShared.normalizeStyle(value))}`;
  function specSource(node){return '{template:'+JSON.stringify(node.template)+',sourceTemplate:'+JSON.stringify(node.sourceTemplate)+
    ',refs:'+JSON.stringify(node.refs)+',elementPolicies:'+JSON.stringify(node.elementPolicies)+',eventHandlers:'+eventSource(node.eventHandlers)+
    ',expressionHandlers:'+eventSource(node.expressionHandlers||{})+
    ',components:{'+Object.entries(node.components).map(([name,child])=>JSON.stringify(name)+':'+specSource(child)).join(',')+'}}';}
  const construction=compiledTemplate?`__businessRequire('./tree.cjs').defineBusinessTree(require('san'),__businessR,__businessSource,${specSource(treeSpec)},${common})`:
    `__businessRequire('./component.cjs').defineBusinessComponent(require('san'),__businessR,__businessSource,${JSON.stringify(template)},{...${common},refs:${JSON.stringify(metadata.refs)},sourceTemplate:${JSON.stringify(metadata.template)},domPolicy:${JSON.stringify(metadata.elementPolicies)}})`;
  const script=built.text+`\nconst __businessSource=${sourceScript};\nmodule.exports=${construction};\n`;
  let code=target;
  for(const edit of [{start:descriptor.script.loc.start.offset,end:descriptor.script.loc.end.offset,text:script},
    {start:descriptor.template.loc.start.offset,end:descriptor.template.loc.end.offset,text:template}].sort((a,b)=>b.start-a.start)) {
    code=code.slice(0,edit.start)+edit.text+code.slice(edit.end);
  }
  const manifest={contract_id:contract,source_sha256:hash(source),template_sha256:hash(template),runtime_fingerprints:built.fingerprints,
    code_sha256:hash(code),vue_component_runtime_used:false,vue_renderer_used:false,standalone_reactivity_kernel_used:true,
    metadata_origin:'source_ast_and_options_no_user_key_whitelist',element_policies:metadata.elementPolicies,
    source_component_tree_compiled:hasTree,old_full_contract_complete:false,production_admission_eligible:false};
  if(production)manifest.production_profile=mode;
  return {code,manifest};
}
function verify(source,code,manifest) {
  const canonical=compile(source,code,manifest.production_profile);
  return canonical.code===code&&isDeepStrictEqual(canonical.manifest,manifest);
}
module.exports={compile,inspectSource,verify,bundle,BusinessCompileError};
