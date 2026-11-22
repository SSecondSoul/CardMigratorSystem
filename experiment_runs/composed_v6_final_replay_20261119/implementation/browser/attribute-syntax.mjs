// Parser-only, source-bound attribute repair. Never execute either component.
// Offsets refer to the original SFC, including static inline component templates.
import {nonNullableRootState} from './native-value.mjs'
function walk(n, fn) {
  if (!n || typeof n !== 'object') return
  if (Array.isArray(n)) {n.forEach(x => walk(x, fn)); return}
  if (n.type) fn(n)
  for (const [k,v] of Object.entries(n)) if (!['loc','extra','comments','tokens'].includes(k)) walk(v, fn)
}
const key = p => !p.computed && (p.key?.name ?? p.key?.value)
export function templateRegions(code, require, source=false) {
  const {descriptor} = require('@vue/compiler-sfc').parse(code), regions = []
  if (descriptor.template) regions.push({text:descriptor.template.content, offset:descriptor.template.loc.start.offset, outer:true,scope:'@outer'})
  if (!descriptor.script) return regions
  const base = descriptor.script.loc.start.offset
  try {
    const ast = require('@babel/parser').parse(descriptor.script.content, {sourceType:'unambiguous'})
    const parents = [], components = new Set(), identities=new Map()
    walk(ast,n=>{
      if (n.type==='CallExpression' && n.callee.type==='MemberExpression' && !n.callee.computed &&
          n.callee.object.name==='san' && n.callee.property.name==='defineComponent' && n.arguments[0]?.type==='ObjectExpression') components.add(n.arguments[0])
      if (n.type==='VariableDeclarator' && n.id.type==='Identifier') {
        const object=n.init?.type==='ObjectExpression'?n.init:n.init?.type==='CallExpression'?n.init.arguments[0]:null
        if (object?.type==='ObjectExpression') identities.set(object,n.id.name)
      }
    })
    walk(ast, n => {
      if (n.type === 'AssignmentExpression' && n.operator === '=' && n.left.type === 'MemberExpression' &&
          !n.left.computed && n.left.object.name === 'module' && n.left.property.name === 'exports' &&
          n.right.type === 'CallExpression' && n.right.callee.type === 'MemberExpression' &&
          !n.right.callee.computed && n.right.callee.object.name === 'san' && n.right.callee.property.name === 'defineComponent' &&
          n.right.arguments.length === 1 && n.right.arguments[0].type === 'ObjectExpression') parents.push(n.right.arguments[0])
      if (n.type !== 'ObjectExpression') return
      if (!source && !components.has(n)) return
      const p = n.properties.filter(p => key(p) === 'template')
      if (p.length !== 1 || p[0].type !== 'ObjectProperty') return
      const v = p[0].value, name=n.properties.filter(p=>key(p)==='name'),
        scope=name.length===1&&name[0].value?.type==='StringLiteral'?name[0].value.value:identities.get(n)
      if (!scope) return
      // Editing escaped string literals would need a separate byte-offset map.
      if (v.type === 'TemplateLiteral' && !v.expressions.length && v.quasis[0].value.raw === v.quasis[0].value.cooked)
        regions.push({text:v.quasis[0].value.raw, offset:base+v.start+1, owner:n, scriptOffset:base,scope})
      else if (v.type === 'StringLiteral' && code.slice(base+v.start+1,base+v.end-1) === v.value)
        regions.push({text:v.value,offset:base+v.start+1,owner:n,scriptOffset:base,scope})
    })
    if (parents.length === 1 && regions[0]?.outer) Object.assign(regions[0],{owner:parents[0],scriptOffset:base})
  } catch { /* Keep outer template diagnostics even when the script is broken. */ }
  return regions
}
function nodes(region, require) {
  const result = []
  function visit(n, path) {
    let i = 0
    for (const child of n.children ?? []) if (child.type === 1) {
      const p = path+'/'+child.tag+'['+i+++']'
      result.push({node:child,path:p}); visit(child,p)
    }
  }
  visit(require('@vue/compiler-dom').parse(region.text,{onError(){}}),'')
  return result
}
export function attributeDiagnostics(code, require) {
  const result = [], san = require('san')
  for (const region of templateRegions(code,require)) for (const {node} of nodes(region,require)) {
    for (const p of node.props) {
      if (p.type===7) {
        result.push({message:'Vue directive '+p.loc.source+' remains in a San component template.',offset:region.offset+p.loc.start.offset,attribute:p.loc.source.split(/[=\s]/)[0]})
        continue
      }
      if (p.type !== 6 || !/^(on-|s-(for|if|elif)$)/.test(p.name)) continue
      try {san.parseTemplate((p.name==='s-elif'?'<div s-if="true"></div>':'')+'<div '+p.loc.source+'></div>')}
      catch (e) {result.push({message:String(e.message),offset:region.offset+p.loc.start.offset,attribute:p.name})}
    }
    for (const p of node.props) if (p.type===6 && p.value && !p.name.startsWith('on-') && !p.name.startsWith('s-'))
      try {san.parseTemplate('<div '+p.loc.source+'></div>')}
      catch (e) {result.push({message:String(e.message),offset:region.offset+p.loc.start.offset,attribute:p.name})}
    for (const c of node.children??[]) if (c.type===5)
      try {san.parseTemplate('<div>'+c.loc.source+'</div>')}
      catch (e) {result.push({message:String(e.message),offset:region.offset+c.loc.start.offset,attribute:'#interpolation'})}
  }
  return result
}
function expression(text, require, target=false) {
  const babel = require('@babel/parser'), t = require('@babel/types'), generate = require('@babel/generator').default
  let n = babel.parseExpression(text)
  function convert(v) {
    if (!v || typeof v !== 'object') return v
    if (Array.isArray(v)) return v.map(convert)
    if (target && v.type === 'CallExpression' && !v.optional && v.arguments.length === 1 &&
        v.arguments[0].type === 'StringLiteral' && /^[A-Za-z_$][\w$]*$/.test(v.arguments[0].value) &&
        v.callee.type === 'MemberExpression' && !v.callee.computed && v.callee.property.name === 'get' &&
        v.callee.object.type === 'MemberExpression' && !v.callee.object.computed &&
        v.callee.object.property.name === 'data' && v.callee.object.object.type === 'ThisExpression')
      return t.identifier(v.arguments[0].value)
    const out = {...v}
    delete out.extra
    for (const [k,x] of Object.entries(v)) if (x && typeof x === 'object' && !['loc','extra'].includes(k)) out[k] = convert(x)
    return out
  }
  n=convert(n)
  return generate(n,{compact:true,comments:false,jsescOption:{quotes:'single',minimal:true}}).code
}
const rawAttr = (node,name) => node.props.filter(p => p.type===6 && p.name===name)
const sourceAttr = (node,name,arg) => node.props.filter(p => p.type===7 && p.name===name && (arg===undefined || p.arg?.content===arg))
function classExpr(p,require) {
  const e = require('@babel/parser').parseExpression(p.exp.content), t = require('@babel/types')
  if (e.type === 'ObjectExpression' && e.properties.length === 1) {
    const v=e.properties[0], name=key(v)
    if (v.type === 'ObjectProperty' && typeof name === 'string' && /^[-\w]+$/.test(name))
      return expression(require('@babel/generator').default(t.conditionalExpression(v.value,t.stringLiteral(name),t.stringLiteral(''))).code,require)
  }
  return expression(p.exp.content,require)
}
export function attributeEdits(source,code,require) {
  const expected = templateRegions(source,require,true).flatMap(region => nodes(region,require).map(n=>({...n,scope:region.scope}))), edits=[], noops=new Map()
  const match = (region,path,node) => expected.filter(s => s.scope===region.scope && s.path===path && s.node.tag===node.tag)
  for (const region of templateRegions(code,require)) for (const {node,path} of nodes(region,require)) {
    const choices=match(region,path,node)
    if (choices.length !== 1) continue
    const src=choices[0].node, base=region.offset
    const add=(p,replacement,rule)=>edits.push({start:base+p.loc.start.offset,end:base+p.loc.end.offset,replacement,rule})
    const classes=rawAttr(node,'class'), binding=sourceAttr(src,'bind','class')
    // San skips className='' when the property is already empty, leaving the
    // class attribute absent. The native className setter preserves Vue's
    // observable class="" without changing comparison/CSS observer policy.
    if(src.ns===0&&classes.length===1&&binding.length===1&&!binding[0].modifiers.length
        &&!rawAttr(src,'class').length&&!node.props.some(p=>p.type===6&&p.name.toLowerCase()==='classname'))try{
      const p=classes[0],m=/^\s*{{([\s\S]+)}}\s*$/.exec(p.value?.content??'')
      const exp=m&&require('@babel/parser').parseExpression(m[1]),t=require('@babel/types')
      if(exp&&t.isConditionalExpression(exp)&&t.isStringLiteral(exp.consequent)&&t.isStringLiteral(exp.alternate)
          &&expression(m[1],require)===classExpr(binding[0],require)){
        const q=p.value.loc.source[0],at=base+p.loc.end.offset
        if(['"',"'"].includes(q)&&!p.value.content.includes('&'))edits.push({start:at,end:at,
          replacement:' className='+q+p.value.content+q,rule:'source_string_class_native_attribute_reflection_v1'})
      }
    }catch{/* Unknown class values are not forced to strings. */}
    // A native defaultValue property reflects the *real* HTML value attribute.
    // Only source :value (not v-model) and proven non-null internal state; no
    // nullable props, file/checkbox/radio, unknown loops or duplicate bindings.
    if(region.outer&&node.tag==='input'&&!sourceAttr(src,'model').length
        &&!src.props.some(p=>p.type===7&&p.name==='bind'&&p.arg?.content==='type')
        &&!node.props.some(p=>p.type===6&&p.name.toLowerCase()==='defaultvalue'))try{
      const wanted=sourceAttr(src,'bind','value'),actual=rawAttr(node,'value'),type=rawAttr(src,'type')
      const field=wanted[0]?.exp?.content.trim(),value=actual[0]?.value?.content
      if(wanted.length===1&&!wanted[0].modifiers.length&&actual.length===1&&type.length<=1
          &&['text','number','range','search','email','url','tel','password','hidden'].includes(type[0]?.value?.content??'text')
          &&value?.trim()==='{{'+field+'}}'&&nonNullableRootState(source,field,require)){
        const at=base+actual[0].loc.end.offset,q=actual[0].value.loc.source[0]
        if(['"',"'"].includes(q))edits.push({start:at,end:at,replacement:' defaultValue='+q+'{{'+field+'}}'+q,
          rule:'source_nonnullable_native_value_attribute_reflection_v1'})
      }
    }catch{/* No proof means no native attribute change. */}
    if (classes.length===2 && binding.length===1) try {
      const fixed=classes.filter(p=>p.value && !p.value.content.includes('{{')), dynamic=classes.filter(p=>/^\s*{{([\s\S]+)}}\s*$/.test(p.value?.content??''))
      if (fixed.length===1 && dynamic.length===1 && rawAttr(src,'class').length===1 &&
          rawAttr(src,'class')[0].value?.content===fixed[0].value.content && !/[&\\]/.test(fixed[0].value.content) &&
          expression(dynamic[0].value.content.trim().slice(2,-2),require,true)===classExpr(binding[0],require)) {
        const value=dynamic[0].value.loc.source, q=value[0]
        if (['"',"'"].includes(q) && !fixed[0].value.content.includes(q)) {
          add(fixed[0],'','source_proven_duplicate_class_merge_v1')
          add(dynamic[0],'class='+q+fixed[0].value.content+' '+value.slice(1,-1)+q,'source_proven_duplicate_class_merge_v1')
        }
      }
    } catch { /* Unknown class maps stay blocked. */ }
    for (const p of node.props) {
      if (p.type!==6 || !p.value) continue
      const v=p.value.content, q=p.value.loc.source[0]
      if (!['"',"'"].includes(q) || p.value.loc.source.slice(1,-1)!==v) continue
      if (!p.name.startsWith('on-') && p.name!=='s-for') try {
        const wrapped=/^\s*{{([\s\S]+)}}\s*$/.exec(v)
        const directive=['s-if','s-elif'].includes(p.name), bindings=directive?
          sourceAttr(src,p.name==='s-if'?'if':'else-if'):sourceAttr(src,'bind',p.name)
        if (bindings.length===1 && wrapped && (directive || v.includes('this.data')) && expression(wrapped[1],require,true)===expression(bindings[0].exp.content,require)) {
          const exp=bindings[0].exp.content.trim(), next=directive?exp:'{{'+exp+'}}'
          if (!next.includes(q) && next!==v) {
            const replacement=p.name+'='+q+next+q
            require('san').parseTemplate('<div '+replacement+'></div>')
            add(p,replacement,'source_matched_template_data_path_v1')
          }
        }
      } catch {}
      if (p.name==='s-for') try {
        const loops=sourceAttr(src,'for'), m=/^\s*\(?\s*([\w$]+)(?:\s*,\s*([\w$]+))?\s*\)?\s+in\s+([\s\S]+?)(?:\s+trackby\s+([\s\S]+))?\s*$/.exec(v)
        if (loops.length!==1 || !m) continue
        const s=/^\s*\(?\s*([\w$]+)(?:\s*,\s*([\w$]+))?\s*\)?\s+in\s+([\s\S]+)$/.exec(loops[0].exp?.content??''), keys=sourceAttr(src,'bind','key')
        if (!s || m[1]!==s[1] || m[2]!==s[2] || expression(m[3],require,true)!==expression(s[3],require) ||
            m[4] && (keys.length!==1 || expression(m[4],require,true)!==expression(keys[0].exp.content,require))) continue
        const collection=s[3].trim(), aliases=[s[1],s[2]].filter(Boolean).join(', ')
        // Restrict collections to San data paths; do not infer JS calls/filters.
        if (!/^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$/.test(collection)) continue
        const next=aliases+' in '+collection+(m[4]?' trackby '+m[4].trim():'')
        if (next!==v) add(p,'s-for='+q+next+q,'source_matched_san_loop_alias_and_collection_v1')
      } catch {}
      if (p.name.startsWith('on-') && region.owner) {
        const parts=p.name.slice(3).split('.')
        let sourceEvents=sourceAttr(src,'on',parts[0])
        if (!sourceEvents.length && require('@vue/shared').isHTMLTag(node.tag) &&
            ['dragstart','dragend','dragover','dragenter','dragleave','drop'].includes(parts[0].replaceAll('-',''))) {
          parts[0]=parts[0].replaceAll('-','');sourceEvents=sourceAttr(src,'on',parts[0])
        }
        if (sourceEvents.length!==1) continue
        const modifiers=sourceEvents[0].modifiers.map(m=>typeof m==='string'?m:m.content)
        const srcExpr=sourceEvents[0].exp?.content?.trim()
        if (v.trim()) {
          // Ordinary method/call grammar only. Assignments, .self and event
          // payload adapters belong to the existing bounded semantic repair.
          if (!srcExpr || modifiers.some(m=>!['stop','prevent','enter'].includes(m)) ||
              modifiers.includes('enter') && !['keyup','keydown','keypress'].includes(parts[0])) continue
          try {
            const canonical=expression(v,require,true), e=require('@babel/parser').parseExpression(srcExpr)
            if (canonical!==expression(srcExpr,require) || !['Identifier','CallExpression'].includes(e.type) ||
                !/^[A-Za-z_$][\w$]*(?:\([\s\S]*\))?$/.test(srcExpr)) continue
            const next=modifiers.map(m=>m+':').join('')+srcExpr
            if (!next.includes(q) && (p.name!=='on-'+parts[0] || next!==v))
              add(p,'on-'+parts[0]+'='+q+next+q,'source_proven_event_modifier_and_operand_v1')
          } catch {}
          continue
        }
        if (srcExpr || !modifiers.length || modifiers.some(m=>!['stop','prevent'].includes(m))) continue
        const identity=region.scriptOffset+region.owner.start
        let plan=noops.get(identity)
        if (!plan) {
          let name='__migrationNoopEvent', i=0
          while (code.includes(name)) name='__migrationNoopEvent'+(++i)
          plan={region,name}; noops.set(identity,plan)
        }
        add(p,'on-'+parts[0]+'='+q+modifiers.map(m=>m+':').join('')+plan.name+'($event)'+q,'source_proven_empty_modifier_event_v1')
      }
    }
    const sText=(src.children??[]).filter(n=>n.type===5), nText=(node.children??[]).filter(n=>n.type===5)
    if (sText.length===nText.length) for(let i=0;i<sText.length;i++) try {
      const wanted=sText[i].content.content, actual=nText[i].content.content
      if (actual.includes('this.data') && wanted!==actual && expression(actual,require,true)===expression(wanted,require)) {
        const replacement='{{'+wanted+'}}'
        require('san').parseTemplate('<div>'+replacement+'</div>')
        edits.push({start:base+nText[i].loc.start.offset,end:base+nText[i].loc.end.offset,replacement,rule:'source_matched_template_data_path_v1'})
      }
    } catch {}
  }
  for (const {region,name} of noops.values()) {
    const at=region.scriptOffset+region.owner.start+1
    edits.push({start:at,end:at,replacement:'\n'+name+'() {},\n',rule:'source_proven_empty_modifier_event_v1'})
  }
  return edits
}

