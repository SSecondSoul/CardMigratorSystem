import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import puppeteer from 'puppeteer-core'
import { pixels } from './metrics.mjs'
import { emptyClassPolicy } from './empty-class-policy.mjs'
import { inspectTarget } from './target-syntax.mjs'
import { inspectSourceContracts } from './source-contracts.mjs'
const input=JSON.parse(fs.readFileSync(0,'utf8')), require=createRequire(path.join(input.repository,'package.json'))
const {parse,compileStyle}=require('@vue/compiler-sfc'), babel=require('@babel/parser'), san=require('san')
const vueRuntime=fs.readFileSync(path.join(input.project,'frontend/node_modules/vue/dist/vue.global.js'),'utf8')
const sanRuntime=fs.readFileSync(require.resolve('san/dist/san.dev.js'),'utf8')

function sourceFailure(code, kind, errors, baseOffset=0){
  const diagnostics=errors.slice(0,16).map(error=>{
    const relative=error.loc?.start?.offset??error.pos,exact=Number.isInteger(relative)
    const offset=Math.max(0,Math.min(code.length,baseOffset+(exact?relative:0))),prefix=code.slice(0,offset)
    return {code:kind,message:String(error.message??error).slice(0,800),
      location:{offset,line:prefix.split('\n').length,column:offset-prefix.lastIndexOf('\n')},
      location_precision:exact?'exact':baseOffset?'block_start':'document_start',
      excerpt:code.slice(Math.max(0,offset-70),Math.min(code.length,offset+170))}
  })
  return Object.assign(new Error(kind),{sourceDiagnostics:diagnostics})
}

function blocks(code,source=false){
  if(source){
    const {descriptor,errors}=parse(code)
    if(errors.length){
      const template=descriptor.template
      const inTemplate=template&&errors.every(e=>Number.isInteger(e.loc?.start?.offset)&&
        e.loc.start.offset>=template.loc.start.offset&&e.loc.start.offset<=template.loc.end.offset)
      throw sourceFailure(code,inTemplate?'source_template_syntax_error':'source_sfc_syntax_error',errors)
    }
    if(descriptor.scriptSetup||descriptor.script?.lang)throw new Error('unsupported_source_sfc')
    const script=descriptor.script?.content??'export default {}'
    let ast
    try{ast=babel.parse(script,{sourceType:'module'})}
    catch(error){throw sourceFailure(code,'source_script_syntax_error',[error],descriptor.script?.loc.start.offset??0)}
    if(ast.program.body.some(n=>n.type==='ImportDeclaration'))throw new Error('external_source_dependencies_unsupported')
    const exports=ast.program.body.filter(n=>n.type==='ExportDefaultDeclaration')
    const commonjs=ast.program.body.filter(n=>n.type==='ExpressionStatement'&&n.expression.type==='AssignmentExpression'&&
      n.expression.operator==='='&&n.expression.left.type==='MemberExpression'&&!n.expression.left.computed&&
      n.expression.left.object.type==='Identifier'&&n.expression.left.object.name==='module'&&
      n.expression.left.property.type==='Identifier'&&n.expression.left.property.name==='exports')
    if(ast.program.body.some(n=>n.type==='ExportNamedDeclaration'||n.type==='ExportAllDeclaration')||
      exports.length+commonjs.length!==1)throw new Error('unsupported_source_sfc')
    let browserScript
    if(exports.length){
      const exported=exports[0]
      browserScript=script.slice(0,exported.start)+'window.__definition = '+script.slice(exported.declaration.start)
    }else{
      // Legacy dataset SFCs also use a CommonJS Options object. Keep the source
      // unchanged on disk; provide module scope only inside the isolated browser.
      // Do not evaluate source in Node or resolve external require() dependencies.
      if(commonjs[0].expression.right.type!=='ObjectExpression')throw new Error('unsupported_source_sfc')
      browserScript='window.__definition = (() => { const module = {exports:{}}; const exports = module.exports;\n'+script+'\nreturn module.exports; })();'
    }
    if(descriptor.styles.some(s=>s.lang&&s.lang!=='css'))throw new Error('source_style_preprocessor_unsupported')
    const scoped=descriptor.styles.some(s=>s.scoped)
    const styles=descriptor.styles.map(s=>{const result=compileStyle({source:s.content,id:'data-v-cardmig',scoped:s.scoped});if(result.errors.length)throw new Error('source_css_compile_failed');return result.code})
    return {template:descriptor.template?.content??'',templateOffset:descriptor.template?.loc.start.offset??0,
      script:browserScript,style:styles.join('\n'),scoped}
  }
  // Reuse the SFC parser for outer block boundaries. A regex would truncate
  // the outer template at a nested <template s-if> closing tag.
  const {descriptor,errors}=parse(code)
  if(errors.length||!descriptor.template||!descriptor.script||descriptor.scriptSetup||descriptor.customBlocks.length)throw new Error('invalid_target_sfc')
  const script=descriptor.script.content,template=descriptor.template.content
  babel.parse(script,{sourceType:'unambiguous'})
  // Target template really goes through San's parser; no target script executes in Node.
  san.parseTemplate(template)
  return {template,script,style:descriptor.styles.map(s=>s.content).join('\n')}
}

function canonicalTemplate(template,source,templateOffset=0){
  const compiler=require('@vue/compiler-dom')
  let ast
  try{ast=source?compiler.parse(template):san.parseTemplate(template)}
  catch(error){if(source)throw sourceFailure(input.source,'source_template_syntax_error',[error],templateOffset);throw error}
  // Preserve separators until adjacent text/interpolation segments are merged.
  function textNode(t){return {label:'#text:'+String(t),children:[]}}
  function mergeText(children){
    const result=[]
    for(const child of children){if(result.length&&child.label.startsWith('#text:')&&result.at(-1).label.startsWith('#text:'))result.at(-1).label+=child.label.slice(6);else result.push(child)}
    return result.map(child=>child.label.startsWith('#text:')?{...child,label:'#text:'+child.label.slice(6).replace(/\s+/g,' ').trim()}:child).filter(child=>child.label!=='#text:')
  }
  // San sometimes unwraps a single interpolation into its actual expression
  // (including TERTIARY=10). Only TEXT=7 is a list of literal/interpolation parts;
  // traversing arbitrary .segs would mislabel ternary branch strings as text.
  function sanText(expr){
    if(expr.type===1)return String(expr.value)
    if(expr.type===7)return expr.segs.map(part=>part.type===1?part.value:'@binding').join('')
    return '@binding'
  }
  const tokens=value=>String(value).trim().split(/\s+/).filter(Boolean)
  function staticClass(expr){
    if(expr.type===1)return tokens(expr.value)
    if(expr.type===5)return staticClass(expr.expr)
    if(expr.type===7)return expr.segs.flatMap(part=>part.type===1?tokens(part.value):staticClass(part))
    if(expr.type===8&&expr.operator===43)return expr.segs.flatMap(staticClass)
    if(expr.type===10){const left=staticClass(expr.segs[1]),right=new Set(staticClass(expr.segs[2]));return left.filter(token=>right.has(token))}
    return []
  }
  const classValue=value=>[...new Set(tokens(value))].sort().join(' ')
  function visit(node){
    if(source){
      if(node.type===2)return textNode(node.content)
      if(node.type===5)return {label:'#text:@binding',children:[]}
      if(node.type!==0&&node.type!==1)return null
      const attrs=(node.props??[]).map(p=>p.type===6?p.name+'='+(p.name==='class'?classValue(p.value?.content??''):String(p.value?.content??'')):p.name==='on'?'event:'+p.arg?.content:p.name==='bind'?'binding:'+p.arg?.content:p.name==='model'?'binding:value':'directive:'+p.name).sort()
      return {label:node.type===0?'#root':node.tag+'|'+attrs.join('|'),children:mergeText((node.children??[]).map(visit).filter(Boolean))}
    }
    if(node.textExpr)return textNode(sanText(node.textExpr))
    const attrs=(node.props??[]).flatMap(p=>{
      if(p.expr?.type===1)return [p.name+'='+(p.name==='class'?classValue(p.expr.value):String(p.expr.value))]
      const result=['binding:'+p.name]
      if(p.name==='class'){const fixed=[...new Set(staticClass(p.expr))].sort().join(' ');if(fixed)result.push('class='+fixed)}
      return result
    })
    for(const event of node.events??[])attrs.push('event:'+event.name)
    for(const [name] of Object.entries(node.directives??{}))attrs.push('directive:'+name)
    return {label:node.tagName?node.tagName+'|'+attrs.sort().join('|'):'#root',children:mergeText((node.children??[]).map(visit).filter(Boolean))}
  }
  return {tree:visit(ast),normalization:'template_projection_v2_san_expression_kinds_and_static_class_tokens',
    ...(source?{source_parser:'vue_compiler_dom_html_v1'}:{}),
    limitations:['binding_expression_equivalence_and_class_token_boundaries_are_checked_separately','component_expansion_not_in_template_ted']}
}

async function capture(browser,code,kind,actions){
  const context=await browser.createBrowserContext(),page=await context.newPage()
  const errors=[],warnings=[],blocked=[];let overflow=false
  const remember=(array,value)=>{if(array.length<100)array.push(String(value).slice(0,1000));else overflow=true}
  page.on('pageerror',e=>remember(errors,e.message));page.on('console',msg=>{if(msg.type()==='warning'||msg.type()==='error')remember(warnings,msg.text())})
  page.on('dialog',dialog=>dialog.dismiss());page.setDefaultTimeout(5000)
  await page.setViewport({width:input.browser.width,height:input.browser.height,deviceScaleFactor:1})
  await page.setRequestInterception(true)
  page.on('request',req=>{
    if(req.isInterceptResolutionHandled())return
    if(req.url()==='http://component.invalid/'&&req.isNavigationRequest()&&req.method()==='GET')return req.respond({status:200,contentType:'text/html',body:'<!doctype html><html><head><link rel="icon" href="data:,"></head><body><div id="mount"></div></body></html>'})
    remember(blocked,req.url());return req.abort()
  })
  await page.evaluateOnNewDocument(()=>{
    window.__events=[];window.WebSocket=class{constructor(){throw Error('network_disabled')}}
    window.EventSource=class{constructor(){throw Error('network_disabled')}}
    Object.defineProperty(navigator,'serviceWorker',{value:undefined})
  })
  const begin=performance.now();await page.goto('http://component.invalid/',{waitUntil:'domcontentloaded'})
  const parts=blocks(code,kind==='vue')
  await page.addStyleTag({content:parts.style+'\n*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}body{margin:8px;} '})
  await page.addScriptTag({content:kind==='vue'?vueRuntime:sanRuntime})
  try { if(kind==='vue'){
    await page.addScriptTag({content:parts.script})
    await page.evaluate(({template,props,scoped})=>{const definition={...window.__definition,template};if(scoped)definition.__scopeId='data-v-cardmig';const app=Vue.createApp(definition,props);window.__app=app;window.__instance=app.mount('#mount')},{template:parts.template,props:input.props,scoped:parts.scoped})
  } else {
    await page.evaluate(({script,template,props})=>{const module={exports:{}},exports=module.exports;const onlySan=(name)=>{if(name!=='san')throw Error('unsupported_require:'+name);return window.san};new Function('require','module','exports',script)(onlySan,module,exports);const Definition=module.exports.default??module.exports;const C=typeof Definition==='function'?Definition:san.defineComponent({...Definition,template});C.template=template;C.prototype.template=template;window.__instance=new C({data:props});window.__instance.attach(document.getElementById('mount'))},{...parts,props:input.props})
  }} catch(e){remember(errors,kind+'_render_failed:'+e.message)}
  await new Promise(r=>setTimeout(r,input.browser.settle_ms))
  await page.evaluate(()=>document.fonts.ready)
  const snapshots=[]
  async function snapshot(name){return {name,...await page.evaluate(()=>{
    let count=0;const styles=[]
    function walk(n,p){if(++count>3000)throw Error('dom_node_limit');if(n.nodeType===3){const text=n.textContent.replace(/\s+/g,' ').trim();return text?{label:'#text:'+text,children:[]}:null}if(n.nodeType!==1)return null
      if(styles.length>=300)throw Error('style_capacity_exceeded')
      const css=getComputedStyle(n);styles.push({path:p,tag:n.tagName.toLowerCase(),text:n.textContent.slice(0,200),value:n.value??null,checked:n.checked??null,
        selected_values:n.tagName==='SELECT'&&n.multiple?Array.from(n.selectedOptions,o=>o.value):null,
        styles:Object.fromEntries(['color','backgroundColor','fontSize','fontFamily','fontWeight','marginTop','marginLeft','paddingTop','paddingLeft','width','height','display','position'].map(k=>[k,css[k]]))})
      const attributes=Object.fromEntries(Array.from(n.attributes).filter(a=>!a.name.startsWith('data-v-')&&!['id'].includes(a.name)).map(a=>[a.name,a.value]))
      const attrs=Object.entries(attributes).map(([name,value])=>name+'='+value).sort()
      // Style paths identify ELEMENT siblings, not indentation text/comments.
      // Nonempty text is still retained in the DOM tree and compared normally.
      let elementIndex=0
      return {label:n.tagName.toLowerCase()+'|'+attrs.join('|'),tag:n.tagName.toLowerCase(),attributes,children:Array.from(n.childNodes).map(c=>walk(c,c.nodeType===1?p+'.'+elementIndex++:p+'.text')).filter(Boolean)}
    }
    return {dom:walk(document.getElementById('mount'),'root'),styles}
  })}}
  snapshots.push(await snapshot('initial'))
  for(const action of actions){try{
    if(action.type==='click')await page.click(action.selector)
    else if(action.type==='input'){await page.$eval(action.selector,(el,value)=>{el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}))},action.value)}
    else if(action.type==='select')await page.select(action.selector,action.value)
    else if(action.type==='key'){await page.focus(action.selector);await page.keyboard.press(action.value)}
    else if(action.type==='drag'){const from=await page.$(action.selector),to=await page.$(action.target);if(!from||!to)throw Error('drag_element_missing');await from.dragAndDrop(to)}
    else throw Error('unsupported_interaction')
    await new Promise(r=>setTimeout(r,100))
    }catch(e){remember(errors,kind+'_interaction_failed:'+action.name+':'+e.message)}
    snapshots.push(await snapshot(action.name))
  }
  const png=await page.screenshot({type:'png',fullPage:false})
  const result={snapshots,png:Buffer.from(png).toString('base64'),errors,warnings,blocked_requests:blocked,evidence_overflow:overflow,render_ms:performance.now()-begin,url:'http://component.invalid/',storage:'fresh_context'}
  await context.close();return result
}

let browser
try{
  const sourceParts=blocks(input.source,true)
  const source=canonicalTemplate(sourceParts.template,true,sourceParts.templateOffset)
  if(input.action==='source-preflight'){process.stdout.write(JSON.stringify({status:'completed',source}));process.exit(0)}
  if(input.action==='source-contracts'){
    const result=inspectSourceContracts(input.source,require)
    process.stdout.write(JSON.stringify({...result,...(result.status==='blocked'?{error:'source_dynamic_key_contract_unsupported'}:{})}))
    process.exit(result.status==='blocked'?2:0)
  }
  if(input.action==='comparison-policy'){process.stdout.write(JSON.stringify({status:'completed',policy:emptyClassPolicy(input.source,input.code,require)}));process.exit(0)}
  const syntax=inspectTarget(input.code,require)
  if(syntax.status==='fail'){process.stdout.write(JSON.stringify({status:'target_compile_failed',diagnostic:'Target syntax checks failed; see structured locations.',syntax}));process.exit(0)}
  let target
  try{target=canonicalTemplate(blocks(input.code).template,false)}catch(e){process.stdout.write(JSON.stringify({status:'target_compile_failed',diagnostic:String(e.message).slice(0,250)}));process.exit(0)}
  if(input.action==='parse'){process.stdout.write(JSON.stringify({source,target}));process.exit(0)}
  browser=await puppeteer.launch({executablePath:input.executable,headless:true,args:['--disable-background-networking','--disable-extensions','--disable-sync']})
  const vue=await capture(browser,input.source,'vue',input.actions),sanResult=await capture(browser,input.code,'san',input.actions)
  const image=pixels(Buffer.from(vue.png,'base64'),Buffer.from(sanResult.png,'base64'))
  process.stdout.write(JSON.stringify({status:'completed',source_ast:source,target_ast:target,vue,san:sanResult,image,
    comparison_policy:emptyClassPolicy(input.source,input.code,require),browser_version:await browser.version(),puppeteer_version:JSON.parse(fs.readFileSync(new URL('./node_modules/puppeteer-core/package.json',import.meta.url))).version}))
}catch(e){process.stdout.write(JSON.stringify({status:'blocked',error:String(e.message).slice(0,250),
  ...(e.sourceDiagnostics?{diagnostics:e.sourceDiagnostics}:{})}));process.exitCode=2}
finally{if(browser)await browser.close()}
