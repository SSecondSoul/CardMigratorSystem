/* Interaction evidence packaging: adds passive declared root-event and trusted DOM observations.
 * Bounded build adapter for trusted frozen CommonJS Options-API SFCs.
 * Packaging only: never rewrite business bodies, inline component templates,
 * defaults, event handlers or CSS to make source/target appear equivalent.
 */
'use strict';
const crypto=require('crypto');
const {parse,compileStyle}=require('@vue/compiler-sfc');
const {parse:parseJS}=require('@babel/parser');
const postcss=require('postcss');
const sha=s=>crypto.createHash('sha256').update(s).digest('hex');
function walk(node,visit){if(!node||typeof node!=='object')return;visit(node);for(const [k,v] of Object.entries(node))if(k!=='loc'){
  if(Array.isArray(v))v.forEach(n=>walk(n,visit));else if(v&&typeof v==='object')walk(v,visit);
}}
function prepareModules(spec){
  if(!['vue','san'].includes(spec.framework)||!Array.isArray(spec.modules)||!spec.modules.length)throw Error('Explicit framework/module graph required');
  const modules={},styles=[],manifest=[];
  for(const file of spec.modules){
    if(typeof file.id!=='string'||!/^[-a-zA-Z0-9_/.]+$/.test(file.id)||file.id.split('/').includes('..')||Object.hasOwn(modules,file.id))throw Error('Invalid/duplicate module id');
    if(typeof file.source!=='string'||!file.source.trim()||file.source.length>1500000)throw Error('Invalid module source');
    const deps=file.dependencies||{};if(typeof deps!=='object'||Array.isArray(deps))throw Error('Explicit dependency map required');
    let script,template=null,scopeId=null,css=[];
    if(file.id.endsWith('.js'))script=file.source;
    else{
      if(!file.id.endsWith(spec.framework==='vue'?'.vue':'.san'))throw Error('Framework module extension mismatch');
      const parsed=parse(file.source,{filename:file.id});if(parsed.errors.length)throw Error('SFC parse failed '+String(parsed.errors[0]));
      const d=parsed.descriptor;
      if(d.scriptSetup||!d.script||!d.template||d.customBlocks.length||d.cssVars.length||d.slotted)throw Error('Unsupported SFC feature; no silent fallback');
      for(const block of [d.script,d.template,...d.styles])if(block.src||block.lang&&block.lang!==(block===d.script?'js':block===d.template?'html':'css'))throw Error('External block/preprocessor not supported');
      if(d.styles.some(s=>s.module))throw Error('CSS modules unsupported');
      if(spec.framework==='san'&&d.styles.some(s=>s.scoped))throw Error('Scoped San CSS needs explicit compiler support');
      script=d.script.content;template=d.template.content;
      if(d.styles.some(s=>s.scoped))scopeId='data-v-'+sha(file.id+'\n'+file.source).slice(0,12);
      for(const block of d.styles){
        // Only ordinary selectors in v1. Do not approximate Vue-version-specific deep/slot rules.
        if(/::?v-deep|:deep\(|:slotted\(|:global\(|>>>|\/deep\//.test(block.content))throw Error('Deep/slot/global scoped CSS unsupported');
        const tree=postcss.parse(block.content);tree.walkAtRules('import',()=>{throw Error('External CSS import unsupported');});
        tree.walkDecls(decl=>{if(/url\s*\(/i.test(decl.value)){
          const urls=[...decl.value.matchAll(/url\s*\(\s*(['"]?)(.*?)\1\s*\)/gi)];
          if(!urls.length||urls.some(m=>!m[2].startsWith('data:')))throw Error('External CSS URL unsupported');
        }});
        const result=compileStyle({source:block.content,filename:file.id,id:scopeId||'data-v-unused',scoped:!!block.scoped,trim:false});
        if(result.errors.length)throw Error('CSS compile failed '+String(result.errors[0]));
        css.push(result.code);styles.push({module:file.id,scoped:!!block.scoped,scopeId: block.scoped?scopeId:null,originalSha256:sha(block.content),compiledSha256:sha(result.code),css:result.code});
      }
    }
    const ast=parseJS(script,{sourceType:'script'}),requires=new Set();
    walk(ast,node=>{
      if(node.type==='CallExpression'&&node.callee?.type==='Identifier'&&node.callee.name==='require'){
        if(node.arguments.length!==1||node.arguments[0].type!=='StringLiteral')throw Error('Dynamic require unsupported');
        const request=node.arguments[0].value;if(request==='san'&&spec.framework==='san')return;
        if(!request.startsWith('./')&&!request.startsWith('../'))throw Error('External package unsupported: '+request);
        if(!Object.hasOwn(deps,request))throw Error('Missing declared dependency: '+request);requires.add(request);
      }
    });
    if(Object.keys(deps).some(k=>!requires.has(k)))throw Error('Unused dependency mapping');
    modules[file.id]={script,template,scopeId,dependencies:deps};
    manifest.push({id:file.id,sha256:sha(file.source),scriptSha256:sha(script),templateSha256:template===null?null:sha(template),scopeId,styleBlocks:css.length,requires:[...requires],scriptTransformed:false});
  }
  if(!Object.hasOwn(modules,spec.main)||modules[spec.main].template===null)throw Error('Main SFC missing');
  const visited=new Set(),visiting=new Set();
  function check(id){if(!Object.hasOwn(modules,id))throw Error('Dependency source missing: '+id);if(visiting.has(id))throw Error('Cyclic module graph unsupported');if(visited.has(id))return;
    visiting.add(id);Object.values(modules[id].dependencies).forEach(check);visiting.delete(id);visited.add(id);}
  check(spec.main);if(visited.size!==Object.keys(modules).length)throw Error('Unreachable extra module source');
  return {modules,styles,manifest};
}
function buildPage(spec,runtime){
  if(!Array.isArray(spec.events)||!spec.events.length||spec.events.length>10||new Set(spec.events).size!==spec.events.length||spec.events.some(n=>typeof n!=='string'||!/^[-a-zA-Z0-9_:]{1,60}$/.test(n)))throw Error('Explicit declared root event names required');
  const prepared=prepareModules(spec);
  if(!spec.ready||!Array.isArray(spec.ready.fields)||!spec.ready.equals||!spec.ready.minLengths)throw Error('Explicit ready and observation fields required');
  if(typeof runtime!=='string'||runtime.length<1000)throw Error('Full local framework runtime required');
  const data={framework:spec.framework,main:spec.main,modules:prepared.modules,props:spec.props||{},ready:spec.ready,events:spec.events};
  // JSON text is consumed by a script element; escape closing tags without rewriting code semantics.
  const escapeScript=s=>s.replace(/<\//g,'<\\/');
  const bootstrap=`(()=>{'use strict';const config=${JSON.stringify(data)};
    const framework=config.framework==='vue'?window.Vue:window.san;
    if(!framework||framework.version!==(config.framework==='vue'?'2.7.16':'3.15.6'))throw Error('Pinned full runtime missing');
    const cache=Object.create(null);
    function load(id){if(Object.hasOwn(cache,id))return cache[id];const file=config.modules[id],module={exports:{}};
      if(!file)throw Error('Module absent '+id);
      const require=request=>{if(request==='san'&&config.framework==='san')return framework;
        if(!Object.hasOwn(file.dependencies,request))throw Error('Undeclared dependency '+request);return load(file.dependencies[request]);};
      new Function('module','exports','require',file.script)(module,module.exports,require);const exported=module.exports;
      if(file.template!==null){
        if(config.framework==='vue'){
          if(!exported||typeof exported!=='object'||exported.render||exported.template)throw Error('Conflicting/unsupported Vue export');
          exported.template=file.template;if(file.scopeId)exported._scopeId=file.scopeId;
        }else{
          if(typeof exported!=='function'||!exported.prototype)throw Error('San constructor missing');
          if(exported.prototype.template&&exported.prototype.template.trim()!==file.template.trim())throw Error('Conflicting San root template');
          exported.prototype.template=file.template;
        }
      }cache[id]=exported;return exported;
    }
    if(config.framework==='vue'){
      framework.config.errorHandler=(error,_vm,info)=>console.error('Vue component error',info,error.stack||String(error));
      framework.config.warnHandler=(message,_vm,trace)=>console.error('Vue component warning',message,trace);
    }
    const Component=load(config.main),host=document.getElementById('component-host');let instance;
    if(config.framework==='vue'){
      const C=framework.extend(Component);instance=new C({propsData:config.props});instance.$mount();host.append(instance.$el);
    }else{instance=new Component({data:config.props});instance.attach(host);}
    const emittedEvents=[],nativeDOMEvents=[];
    const clone=value=>JSON.parse(JSON.stringify(value));
    for(const name of config.events){
      const listener=payload=>{try{emittedEvents.push({name,payload:clone(payload),serializable:true});}catch(_error){emittedEvents.push({name,payload:null,serializable:false});}};
      config.framework==='vue'?instance.$on(name,listener):instance.on(name,listener);
    }
    for(const type of ['input','change','click','keydown','keyup'])document.addEventListener(type,event=>{
      nativeDOMEvents.push({type,trusted:event.isTrusted,tag:event.target.tagName,key:event.key||null,value:event.target.value??null});
    },true);
    const get=name=>config.framework==='vue'?instance[name]:instance.data.get(name);
    const countSan=node=>(node.children||[]).reduce((n,child)=>n+(child.nodeType===5?1:0)+countSan(child),0);
    const countVue=node=>node.$children.reduce((n,child)=>n+1+countVue(child),0);
    const observe=()=>({framework:config.framework,rootTag:(config.framework==='vue'?instance.$el:instance.el)?.tagName||null,
      childComponentCount:config.framework==='vue'?countVue(instance):countSan(instance),
      fields:Object.fromEntries(config.ready.fields.map(name=>[name,get(name)])),emittedEvents:clone(emittedEvents),nativeDOMEvents:clone(nativeDOMEvents)});
    window.__componentEvidence=observe;window.__visualReady=false;
    const inspect=()=>{try{
      if(!Object.entries(config.ready.equals).every(([key,value])=>get(key)===value))return;
      if(!Object.entries(config.ready.minLengths).every(([key,value])=>Array.isArray(get(key))&&get(key).length>=value))return;
      framework.nextTick(()=>{window.__componentInitialEvidence=observe();window.__visualReady=true;clearInterval(poll);});
    }catch(error){clearInterval(poll);console.error('Component readiness failed',error.stack||String(error));}};
    const poll=setInterval(inspect,20);inspect();
    window.addEventListener('pagehide',()=>{clearInterval(poll);config.framework==='vue'?instance.$destroy():instance.dispose();},{once:true});
  })();`;
  const css=prepared.styles.map(s=>s.css).join('\n');
  if(/<\/style/i.test(css))throw Error('Unsafe closing style token unsupported');
  const html='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><link rel="icon" href="data:,">'+
    '<style data-component-styles>'+css+'</style></head><body><div id="component-host"></div><script>'+escapeScript(runtime)+'</script><script>'+escapeScript(bootstrap)+'</script></body></html>';
  return {html,manifest:prepared.manifest,styles:prepared.styles.map(({css,...record})=>record),
    boundary:{fullRootTemplate:true,inlineChildDefinitionsUnmodified:true,businessBodiesUnmodified:true,defaultPropsNotInjected:true,
      scopedCSSCompiled:true,framework:spec.framework,vueScopedRuntime:'Vue2 _scopeId; ordinary selector transform via compiler-sfc3',
      arbitraryFrameworkBuildSupported:false,runtimeInterop:false,productionPass:false,passiveDeclaredEventObservation:true,initializationEventsBeforeListenerNotCovered:true}};
}
module.exports={prepareModules,buildPage};
if(require.main===module){const fs=require('fs');const input=JSON.parse(fs.readFileSync(0,'utf8'));
  try{process.stdout.write(JSON.stringify(buildPage(input.spec,input.runtime)));}catch(e){process.stderr.write(e.stack);process.exitCode=2;}}
