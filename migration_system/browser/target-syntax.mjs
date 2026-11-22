// Parse only: never execute uploaded/generated JavaScript. Edits are bounded and audited.
import {attributeDiagnostics, attributeEdits, templateRegions} from './attribute-syntax.mjs'
export const syntaxPolicy = 'target_syntax_first_v1'

function position(code, offset) {
  const prefix = code.slice(0, offset), line = prefix.split('\n').length
  return {offset, line, column: offset - prefix.lastIndexOf('\n')}
}
function finding(code, kind, message, offset = 0, precision = 'exact') {
  offset = Math.max(0, Math.min(code.length, offset))
  return {code: kind, message: String(message).slice(0, 800), location: position(code, offset), location_precision: precision,
    excerpt: code.slice(Math.max(0, offset - 100), Math.min(code.length, offset + 140))}
}

export function inspectTarget(code, require) {
  const {parse} = require('@vue/compiler-sfc'), babel = require('@babel/parser'), san = require('san')
  const errors = [], {descriptor, errors: outerErrors} = parse(code)
  for (const error of outerErrors) errors.push(finding(code, 'target_sfc_syntax_error', error.message ?? error,
    error.loc?.start?.offset ?? 0, error.loc?.start?.offset != null ? 'exact' : 'document_start'))
  if (!descriptor.template || !descriptor.script || descriptor.scriptSetup || descriptor.customBlocks.length)
    errors.push(finding(code, 'target_sfc_shape_error', 'Require template and ordinary script blocks; script setup/custom blocks are unsupported.',0,'document_start'))
  if (descriptor.script) {
    try {babel.parse(descriptor.script.content, {sourceType: 'unambiguous'})}
    catch (error) {errors.push(finding(code, 'target_script_syntax_error', error.message,
      descriptor.script.loc.start.offset + (error.pos ?? 0)))}
  }
  if (descriptor.template) {
    const attributes = attributeDiagnostics(code,require)
    for (const item of attributes) errors.push({...finding(code,'target_template_syntax_error',item.message,item.offset),attribute:item.attribute})
    for (const region of templateRegions(code,require)) try {san.parseTemplate(region.text)}
    catch (error) {
      if (!attributes.some(a=>a.offset>=region.offset && a.offset<region.offset+region.text.length))
        errors.push(finding(code,'target_template_syntax_error',error.message,region.offset,'template_block_start'))
    }
  }
  return {policy: syntaxPolicy, status: errors.length ? 'fail' : 'pass',
    diagnostics: errors.slice(0, 128), diagnostic_count: errors.length, diagnostic_limit:128, overflow: errors.length > 128}
}

function walk(node, visit) {
  if (!node || typeof node !== 'object') return
  if (node.type) visit(node)
  for (const [key, value] of Object.entries(node)) {
    if (['loc', 'tokens', 'comments', 'errors'].includes(key)) continue
    if (Array.isArray(value)) value.forEach(child => walk(child, visit))
    else if (value && typeof value === 'object') walk(value, visit)
  }
}

function elements(node, ancestors, visit) {
  if (!node || typeof node !== 'object') return
  if (node.type === 1) {visit(node, ancestors); ancestors = [...ancestors, node]}
  for (const child of node.children ?? []) elements(child, ancestors, visit)
}

// Only move a malformed loop wrapper onto its sole child when Vue declares
// exactly that loop, key and element. No guessed divs, body rewrites or scope changes.
function loopEdits(source, code, require) {
  const {parse} = require('@vue/compiler-sfc'), compiler = require('@vue/compiler-dom')
  const sourceParts = parse(source), targetParts = parse(code)
  if (sourceParts.errors.length || !sourceParts.descriptor.template || !targetParts.descriptor.template) return []
  const expected = []
  try {
    const ast = compiler.baseParse(sourceParts.descriptor.template.content)
    elements(ast, [], (node, ancestors) => {
      const loop = node.props.find(p => p.type === 7 && p.name === 'for')
      const key = node.props.find(p => p.type === 7 && p.name === 'bind' && p.arg?.content === 'key')
      if (loop?.exp && key?.exp) {
        const value = node.props.find(p => p.type === 7 && p.name === 'bind' && p.arg?.content === 'value')
        const model = ancestors.at(-1)?.props.find(p => p.type === 7 && p.name === 'model')
        // Restore a lost option only for this completely source-described leaf.
        // No labels, disabled state, events, conditional/outer loop scopes or extra attributes are inferred.
        const leaf = node.tag === 'option' && ancestors.at(-1)?.tag === 'select' && node.props.length === 3 &&
          [loop,key,value].every(p => p && !p.modifiers?.length) && value?.exp?.content.trim() === key.exp.content.trim() &&
          node.children.length === 1 && node.children[0].type === 5 &&
          node.children[0].content.content.trim() === key.exp.content.trim() &&
          (!model || (!model.arg && !model.modifiers?.length && /^[A-Za-z_$][\w$]*$/.test(model.exp?.content.trim() ?? ''))) &&
          !ancestors.some(a => a.props.some(p => p.type === 7 && !['bind','model'].includes(p.name)))
        expected.push({tag: node.tag, loop: loop.exp.content.trim(), key: key.exp.content.trim(),
          leaf, model:model?.exp?.content.trim(), path: ancestors.map(a => a.tag).join('/')})
      }
    })
  } catch {return []}
  const template = targetParts.descriptor.template, body = template.content, edits = []
  const elementStarts = new Map()
  // Recover only to identify real markup starts. This AST is NEVER accepted as
  // a successful syntax check. Literal strings in attributes/comments/interpolations
  // must not be mistaken for malformed loop elements.
  try {elements(compiler.baseParse(body, {onError() {}}), [], (node, ancestors) => {
    elementStarts.set(node.loc.start.offset, {node, ancestors})
  })} catch {return []}
  const pattern = /<s-for\s*=\s*(["'])([^"'<>]+)\1\s*>([\s\S]*?)<\/s-for\s*>/g
  for (const match of body.matchAll(pattern)) {
    if (!elementStarts.has(match.index)) continue
    if (/<\/?s-for\b/.test(match[3])) continue
    const expr = /^([A-Za-z_$][\w$]*)\s+in\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s+trackby\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)$/.exec(match[2].trim())
    if (!expr) continue
    let children
    try {children = compiler.baseParse(match[3]).children.filter(n => n.type !== 2 || n.content.trim())} catch {continue}
    if (children.length === 1 && children[0].type === 5 && children[0].content.content.trim() === expr[1]) {
      const context = elementStarts.get(match.index)
      const value = context.ancestors.at(-1)?.props.find(p => p.type === 6 && p.name === 'value')?.value?.content
      const matches = expected.filter(e => e.leaf && e.loop === `${expr[1]} in ${expr[2]}` && e.key === expr[3] &&
        e.key === expr[1] && e.path === context.ancestors.map(a => a.tag).join('/') &&
        (e.model ? new RegExp('^\\{=\\s*'+e.model.replace(/[$]/g,'\\$')+'\\s*=\\}$').test(value ?? '') : value === undefined))
      if (matches.length !== 1 || context.ancestors.at(-1)?.tag !== 'select' ||
          context.ancestors.some(a => a.props.some(p => p.name === 's-for' || p.name === 's-if'))) continue
      edits.push({start: template.loc.start.offset + match.index, end: template.loc.start.offset + match.index + match[0].length,
        replacement: `<option s-for=${match[1]}${match[2]}${match[1]} value="{{${expr[1]}}}">${match[3]}</option>`,
        rule: 'source_proven_missing_option_leaf_v1'})
      continue
    }
    if (children.length !== 1 || children[0].type !== 1) continue
    const child = children[0]
    if (child.tag === 'template' || child.props.some(p => p.name === 's-for' || p.name === 'for')) continue
    const matches = expected.filter(e => e.tag === child.tag && e.loop === `${expr[1]} in ${expr[2]}` && e.key === expr[3])
    if (matches.length !== 1) continue
    const start = child.loc.start.offset, insertion = start + 1 + child.tag.length
    const inner = match[3].slice(0, insertion) + ` s-for=${match[1]}${match[2]}${match[1]}` + match[3].slice(insertion)
    edits.push({start: template.loc.start.offset + match.index, end: template.loc.start.offset + match.index + match[0].length,
      replacement: inner, rule: 'source_matched_single_child_loop_attribute_v1'})
  }
  return edits
}

function commaEdits(code, require) {
  const {descriptor} = require('@vue/compiler-sfc').parse(code), babel = require('@babel/parser')
  if (!descriptor.script) return []
  const script = descriptor.script.content, positions = []
  let changed = script, ast
  for (let count = 0; count <= 4; count++) {
    try {ast = babel.parse(changed, {sourceType: 'unambiguous'}); break}
    catch (error) {
      const at = error.pos
      if (count === 4 || !/expected ","/.test(error.message) || !Number.isInteger(at) ||
          !/^[A-Za-z_$][\w$]*\s*\(/.test(changed.slice(at)) || (positions.length && at <= positions.at(-1))) return []
      positions.push(at); changed = changed.slice(0, at) + ',' + changed.slice(at)
    }
  }
  if (!ast || !positions.length) return []
  for (const at of positions) {
    let confirmed = false
    walk(ast, node => {
      if (node.type !== 'ObjectExpression') return
      for (let i = 1; i < node.properties.length; i++) {
        const previous = node.properties[i - 1], next = node.properties[i]
        if (previous.type === 'ObjectMethod' && next.type === 'ObjectMethod' && next.start === at + 1 &&
            /^\s*$/.test(changed.slice(previous.end, at))) confirmed = true
      }
    })
    if (!confirmed) return []
  }
  return positions.map((at,i) => ({start:descriptor.script.loc.start.offset + at - i,
    end:descriptor.script.loc.start.offset + at - i,replacement:',',rule:'parsed_adjacent_object_methods_comma_v1'}))
}

function sourceOptions(source, require) {
  const parts = require('@vue/compiler-sfc').parse(source)
  if (parts.errors.length || !parts.descriptor.script || parts.descriptor.scriptSetup) return null
  const ast = require('@babel/parser').parse(parts.descriptor.script.content, {sourceType:'unambiguous'})
  const values = ast.program.body.flatMap(n => n.type === 'ExportDefaultDeclaration' ? [n.declaration] :
    n.type === 'ExpressionStatement' && n.expression.type === 'AssignmentExpression' && n.expression.operator === '=' &&
    n.expression.left.type === 'MemberExpression' && !n.expression.left.computed &&
    n.expression.left.object.name === 'module' && n.expression.left.property.name === 'exports' ? [n.expression.right] : [])
  let shadowedModule=false
  require('@babel/traverse').default(ast,{Program(p){shadowedModule=p.scope.hasOwnBinding('module');p.stop()}})
  if(shadowedModule&&ast.program.body.some(n=>n.type==='ExpressionStatement'&&n.expression.type==='AssignmentExpression'
      &&n.expression.left?.object?.name==='module'))return null
  return values.length === 1 && values[0].type === 'ObjectExpression' ? values[0] : null
}

function canonicalAst(node) {
  return JSON.stringify(node,(key,value) =>
    ['start','end','loc','extra','leadingComments','trailingComments','innerComments'].includes(key) ? undefined : value)
}

// No translation for complex bodies: only an unchanged source method may get
// one lost final brace. All this.* accesses must be calls to source methods,
// never raw Vue state reads. Babel proves the entire body/parameters identical.
function sourceExactMethodClosingEdits(source, code, require) {
  const babel = require('@babel/parser'), sourceParts = require('@vue/compiler-sfc').parse(source)
  const targetParts = require('@vue/compiler-sfc').parse(code)
  let options
  try {options = sourceOptions(source,require)} catch {return []}
  if (!options || !targetParts.descriptor.script) return []
  const entries = options.properties.filter(p => !p.computed && p.key?.name === 'methods')
  if (entries.length !== 1 || entries[0].value?.type !== 'ObjectExpression') return []
  const methods = entries[0].value.properties, names = new Set(methods.filter(m => m.type === 'ObjectMethod').map(m => m.key.name))
  const script = targetParts.descriptor.script.content, edits = []
  for (const method of methods) {
    if (method.type !== 'ObjectMethod' || method.kind !== 'method' || method.computed || method.async || method.generator ||
        method.key.type !== 'Identifier' || method.params.some(p => p.type !== 'Identifier') ||
        methods.filter(m => m.key?.name === method.key.name).length !== 1) continue
    let unsafe = false
    walk(method,n => {
      if (n.type === 'MemberExpression' && n.object.type === 'ThisExpression' && (n.computed || !names.has(n.property.name))) unsafe = true
    })
    if (unsafe) continue
    const starts = [...script.matchAll(new RegExp('\\b'+method.key.name.replace(/[$]/g,'\\$')+'\\s*\\([^()]*\\)\\s*\\{','g'))]
    if (starts.length !== 1) continue
    const start = starts[0].index, tail = script.slice(start)
    const boundary = /,\s*[A-Za-z_$][\w$]*\s*\([^()]*\)\s*\{/.exec(tail.slice(starts[0][0].length))
    if (!boundary) continue
    const end = start + starts[0][0].length + boundary.index, span = script.slice(start,end)
    try {babel.parseExpression('({'+span+'})');continue} catch {}
    let restored
    try {
      const object = babel.parseExpression('({'+span+'}'+'})')
      if (object.type !== 'ObjectExpression' || object.properties.length !== 1) continue
      restored = object.properties[0]
    } catch {continue}
    if (canonicalAst(restored) !== canonicalAst(method)) continue
    edits.push({start:targetParts.descriptor.script.loc.start.offset+end,end:targetParts.descriptor.script.loc.start.offset+end,
      replacement:'}',method:method.key.name,reference:sourceParts.descriptor.script.content.slice(method.start,method.end),
      rule:'source_exact_method_closing_brace_v1'})
  }
  return edits
}

// A tiny expression emitter, NOT a general Vue-to-San translator. Only a single
// call/return or direct declared-state '=' statement is eligible. Arithmetic,
// literals, parameters and read/call chains are compared in full afterwards.
// No compound/nested writes, closures, computed keys or control flow.
function leafReference(method, fields) {
  if (method.type !== 'ObjectMethod' || method.kind !== 'method' || method.computed || method.async || method.generator ||
      method.key.type !== 'Identifier' || method.params.some(p => p.type !== 'Identifier') || method.body.body.length !== 1) return null
  const stmt = method.body.body[0], params = new Set(method.params.map(p => p.name))
  const globals = new Set(['localStorage','sessionStorage','JSON','Math','Number','String','Boolean'])
  function expression(n) {
    if (!n) throw Error('unsupported')
    if (['StringLiteral','NumericLiteral','BooleanLiteral'].includes(n.type)) return JSON.stringify(n.value)
    if (n.type === 'NullLiteral') return 'null'
    if (n.type === 'Identifier' && (params.has(n.name) || globals.has(n.name))) return n.name
    if (n.type === 'MemberExpression' && !n.computed && n.property.type === 'Identifier') {
      if (n.object.type === 'ThisExpression') {
        if (!fields.has(n.property.name)) throw Error('unknown state')
        return `this.data.get(${JSON.stringify(n.property.name)})`
      }
      return expression(n.object) + '.' + n.property.name
    }
    if(n.type==='BinaryExpression'&&['+','-','*','/','%','**'].includes(n.operator))
      return '('+expression(n.left)+n.operator+expression(n.right)+')'
    if (n.type === 'CallExpression' && !n.optional) return expression(n.callee) + '(' + n.arguments.map(expression).join(',') + ')'
    throw Error('unsupported')
  }
  try {
    const assignment=stmt.type==='ExpressionStatement'&&stmt.expression
    const direct=assignment?.type==='AssignmentExpression'&&assignment.operator==='='
      &&assignment.left.type==='MemberExpression'&&!assignment.left.computed&&assignment.left.object.type==='ThisExpression'
      &&fields.has(assignment.left.property.name)
    const body = direct?'this.data.set('+JSON.stringify(assignment.left.property.name)+','+expression(assignment.right)+')':
      stmt.type === 'ExpressionStatement' ? expression(stmt.expression) :
      stmt.type === 'ReturnStatement' ? 'return ' + expression(stmt.argument) : null
    return body === null ? null : method.key.name + '(' + method.params.map(p => p.name).join(',') + '){' + body + '}'
  } catch {return null}
}

// Lex only the tiny leaf method span above. Any regex/template/unknown operator or
// unknown token refuses repair. String values use Babel decoding, never eval.
function leafTokens(text, babel) {
  const tokens = []; let at = 0
  while (at < text.length) {
    const rest = text.slice(at), space = /^\s+/.exec(rest)
    if (space) {at += space[0].length; continue}
    const match = /^(?:"(?:[^"\\\r\n]|\\.)*"|'(?:[^'\\\r\n]|\\.)*'|[A-Za-z_$][\w$]*|\d+(?:\.\d+)?|\*\*|[(){},.;+*/%\-])/.exec(rest)
    if (!match) return null
    const raw = match[0]
    let value = raw
    if (/^["']/.test(raw)) {try {value = 'string:' + JSON.stringify(babel.parseExpression(raw).value)} catch {return null}}
    tokens.push({value,start:at,end:at+raw.length}); at += raw.length
  }
  return tokens
}

function sourceLeafClosingEdits(source, code, require) {
  const babel = require('@babel/parser'), descriptor = require('@vue/compiler-sfc').parse(code).descriptor
  if (!descriptor.script) return []
  let options,sourceAst
  try {options = sourceOptions(source, require);sourceAst=babel.parse(require('@vue/compiler-sfc').parse(source).descriptor.script.content,{sourceType:'unambiguous'})} catch {return []}
  if (!options) return []
  const named = name => options.properties.filter(p => !p.computed && p.key?.name === name)
  const data = named('data'), methods = named('methods'), fields = new Set()
  if (data.length !== 1 || data[0].type !== 'ObjectMethod' || data[0].body.body.length !== 1 ||
      data[0].body.body[0].type !== 'ReturnStatement' || data[0].body.body[0].argument?.type !== 'ObjectExpression' ||
      methods.length !== 1 || methods[0].value?.type !== 'ObjectExpression') return []
  for (const p of data[0].body.body[0].argument.properties) {
    if (p.type !== 'ObjectProperty' || p.computed || p.key.type !== 'Identifier') return []
    fields.add(p.key.name)
  }
  const script = descriptor.script.content, edits = []
  for (const method of methods[0].value.properties) {
    const reference = leafReference(method, fields)
    if (!reference || methods[0].value.properties.filter(p => p.key?.name === method.key.name).length !== 1) continue
    const natives=new Set();let closed=true
    require('@babel/traverse').default(sourceAst,{ReferencedIdentifier(p){
      if(p.node.start<method.start||p.node.end>method.end)return
      const binding=p.scope.getBinding(p.node.name)
      if(binding&&binding.path.node.start>=method.start&&binding.path.node.end<=method.end)return
      if(binding)closed=false;else natives.add(p.node.name)
    }})
    if(!closed)continue
    const name = method.key.name.replace(/[$]/g,'\\$')
    const starts = [...script.matchAll(new RegExp('\\b'+name+'\\s*\\([^()]*\\)\\s*\\{','g'))]
    if (starts.length !== 1) continue
    const start = starts[0].index
    // Stop at the next object method delimiter; only the final closing tokens
    // may be missing. The entire repaired program and exported-parent scope
    // must subsequently pass Babel validation below.
    const tail = script.slice(start)
    const boundary = /,\s*[A-Za-z_$][\w$]*\s*\([^()]*\)\s*\{/.exec(tail.slice(starts[0][0].length))
    if (!boundary) continue
    const end = start + starts[0][0].length + boundary.index
    const actual = leafTokens(script.slice(start,end),babel), wanted = leafTokens(reference,babel)
    if (!actual || !wanted) continue
    let i = 0, insertions = []
    for (const expected of wanted) {
      if (actual[i]?.value === ';') i++
      if (actual[i]?.value === expected.value) {i++; continue}
      if (![')', '}'].includes(expected.value)) {insertions = null; break}
      insertions.push({start:descriptor.script.loc.start.offset + start + (actual[i]?.start ?? end-start),
        end:descriptor.script.loc.start.offset + start + (actual[i]?.start ?? end-start),replacement:expected.value,
        method:method.key.name,reference,native_globals:[...natives],rule:'source_proven_leaf_closing_tokens_v1'})
    }
    if (actual[i]?.value === ';') i++
    if (!insertions || i !== actual.length || !insertions.length || insertions.length > 3) continue
    edits.push(...insertions)
  }
  return edits
}

// A second syntax witness covers a complete multi-statement source method.
// It is a REFERENCE for AST equality, never a generated replacement body: the
// only edits emitted are at most three missing closing delimiters. Full-script
// parent ownership and unshadowed native globals are checked before commit.
function sourceCompleteMethodClosingEdits(source,code,require) {
  const babel=require('@babel/parser'),t=require('@babel/types'),traverse=require('@babel/traverse').default
  const sfc=require('@vue/compiler-sfc'),a=sfc.parse(source),b=sfc.parse(code)
  let options,sourceAst
  try{options=sourceOptions(source,require);sourceAst=babel.parse(a.descriptor.script.content,{sourceType:'unambiguous'})}catch{return []}
  if(!options||!b.descriptor.script)return []
  const key=p=>!p.computed&&(p.key?.name??p.key?.value)
  const one=(o,k)=>o?.properties?.filter(p=>key(p)===k).length===1?o.properties.find(p=>key(p)===k):null
  const data=one(options,'data'),methods=one(options,'methods')?.value,fields=new Set(),reads=new Set()
  if(!t.isObjectMethod(data)||data.body.body.length!==1||!t.isReturnStatement(data.body.body[0])
      ||!t.isObjectExpression(data.body.body[0].argument)||!t.isObjectExpression(methods))return []
  for(const p of data.body.body[0].argument.properties){
    if(!t.isObjectProperty(p)||p.computed||typeof key(p)!=='string')return []
    fields.add(key(p));reads.add(key(p))
  }
  for(const option of ['props','computed'])for(const p of one(options,option)?.value?.properties??[])if(typeof key(p)==='string')reads.add(key(p))
  const names=new Set(methods.properties.map(key)),globals=new Set(['Math','Number','String','Boolean','JSON','Object','Array','Date','undefined','NaN','Infinity'])
  const script=b.descriptor.script.content,edits=[]
  for(const method of methods.properties){
    const name=key(method)
    if(!t.isObjectMethod(method)||method.kind!=='method'||method.computed||method.async||method.generator
        ||typeof name!=='string'||method.params.some(p=>!t.isIdentifier(p))
        ||methods.properties.filter(p=>key(p)===name).length!==1)continue
    const natives=new Set();let closed=true
    traverse(sourceAst,{ReferencedIdentifier(p){
      if(p.node.start<method.start||p.node.end>method.end)return
      const binding=p.scope.getBinding(p.node.name)
      if(binding&&binding.path.node.start>=method.start&&binding.path.node.end<=method.end)return
      if(binding||!globals.has(p.node.name))closed=false;else natives.add(p.node.name)
    }})
    if(!closed)continue
    function lower(n,lexical=true,parent=null){
      if(!n||typeof n!=='object')return n
      if(Array.isArray(n))return n.map(x=>lower(x,lexical,parent))
      if(t.isFunction(n)&&!t.isArrowFunctionExpression(n))lexical=false
      if(lexical&&t.isAssignmentExpression(n)&&t.isMemberExpression(n.left)&&t.isThisExpression(n.left.object)){
        if(n.operator!=='='||n.left.computed||!fields.has(n.left.property.name)||!t.isExpressionStatement(parent))throw Error('unproven_assignment_value')
        return t.callExpression(babel.parseExpression('this.data.set'),[t.stringLiteral(n.left.property.name),lower(n.right,lexical,n)])
      }
      if(lexical&&t.isUpdateExpression(n)&&t.isMemberExpression(n.argument)&&t.isThisExpression(n.argument.object))throw Error('unproven_update_value')
      if(lexical&&t.isCallExpression(n)&&t.isMemberExpression(n.callee)&&!n.callee.computed
          &&t.isThisExpression(n.callee.object)&&n.callee.property.name==='$emit')
        return t.callExpression(babel.parseExpression('this.fire'),n.arguments.map(x=>lower(x,lexical,n)))
      if(lexical&&t.isMemberExpression(n)&&t.isThisExpression(n.object)){
        if(n.computed)throw Error('dynamic_instance_key')
        if(t.isCallExpression(parent)&&parent.callee===n){
          if(!names.has(n.property.name))throw Error('unknown_instance_call')
          return t.cloneNode(n,true)
        }
        if(!reads.has(n.property.name))throw Error('unknown_instance_read')
        return t.callExpression(babel.parseExpression('this.data.get'),[t.stringLiteral(n.property.name)])
      }
      if(lexical&&t.isThisExpression(n))throw Error('instance_escape')
      const out={...n};for(const [k,v] of Object.entries(n))if(v&&typeof v==='object'&&!['loc','extra','comments'].includes(k))out[k]=lower(v,lexical,n)
      return out
    }
    let reference,expected
    try{const copy=t.cloneNode(method,true);copy.body=lower(method.body);reference=require('@babel/generator').default(copy,{compact:true,comments:false}).code
      expected=babel.parseExpression('({'+reference+'})').properties[0]}catch{continue}
    const starts=[...script.matchAll(new RegExp('\\b'+name.replace(/[$]/g,'\\$')+'\\s*\\([^()]*\\)\\s*\\{','g'))]
    if(starts.length!==1)continue
    const start=starts[0].index,tail=script.slice(start)
    const boundary=/,\s*[A-Za-z_$][\w$]*\s*\([^()]*\)\s*\{/.exec(tail.slice(starts[0][0].length))
    if(!boundary)continue
    const end=start+starts[0][0].length+boundary.index,original=script.slice(start,end)
    try{babel.parseExpression('({'+original+'})');continue}catch{}
    const queue=[{text:original,mapping:Array.from({length:original.length+1},(_,i)=>i),insertions:[]}],seen=new Set(),matches=new Map()
    while(queue.length){
      const item=queue.shift();if(seen.has(item.text))continue;seen.add(item.text)
      try{
        const object=babel.parseExpression('({'+item.text+'})')
        if(object.properties.length===1&&canonicalAst(object.properties[0])===canonicalAst(expected))matches.set(item.text,item.insertions)
      }catch(e){
        const at=e.pos-2
        if(item.insertions.length>=3||at<0||at>item.text.length)continue
        for(const token of [')',']','}'])queue.push({text:item.text.slice(0,at)+token+item.text.slice(at),
          mapping:[...item.mapping.slice(0,at),item.mapping[at],...item.mapping.slice(at)],
          insertions:[...item.insertions,{at:item.mapping[at],token}]})
      }
    }
    if(matches.size!==1)continue
    const insertions=[...matches.values()][0];if(!insertions.length)continue
    for(const insertion of insertions)edits.push({start:b.descriptor.script.loc.start.offset+start+insertion.at,
      end:b.descriptor.script.loc.start.offset+start+insertion.at,replacement:insertion.token,
      method:name,reference,native_globals:[...natives],rule:'source_complete_method_closing_tokens_v1'})
  }
  return edits
}

function applyEdits(code, edits) {
  // Reverse index for coincident insertion positions preserves token order.
  for (const {edit} of edits.map((edit,index) => ({edit,index})).sort((a,b) => b.edit.start-a.edit.start || b.index-a.index))
    code = code.slice(0,edit.start) + edit.replacement + code.slice(edit.end)
  return code
}

// A single excess object close may move a computed/methods option or an inline
// component method outside its option object. Recover only a source-paired
// component boundary, never by deleting a token inside a business function.
// Each candidate must parse as a COMPLETE program and exactly one candidate
// byte string must satisfy the component graph/adjacent option-role proof.
function sourceOptionBoundaryClose(source,code,require) {
  const babel=require('@babel/parser'),traverse=require('@babel/traverse').default,t=require('@babel/types')
  const sfc=require('@vue/compiler-sfc'),a=sfc.parse(source),b=sfc.parse(code)
  if(a.errors.length||!a.descriptor.script||a.descriptor.scriptSetup||!b.descriptor.script)return {code,edits:[]}
  const script=b.descriptor.script.content
  let sourceAst,errorAt
  try{sourceAst=babel.parse(a.descriptor.script.content,{sourceType:'unambiguous'})}catch{return {code,edits:[]}}
  try{babel.parse(script,{sourceType:'unambiguous'});return {code,edits:[]}}catch(e){errorAt=e.pos}
  if(!Number.isInteger(errorAt))return {code,edits:[]}
  const key=p=>!p.computed&&(p.key?.name??p.key?.value)
  const plain=o=>t.isObjectExpression(o)&&o.properties.every(p=>typeof key(p)==='string')
    &&new Set(o.properties.map(key)).size===o.properties.length
  const one=(o,k)=>plain(o)?o.properties.find(p=>key(p)===k):null
  const fn=p=>t.isObjectMethod(p)&&p.kind==='method'||t.isObjectProperty(p)&&t.isFunctionExpression(p.value)
  const tag=name=>name.replace(/([A-Z])([A-Z][a-z])/g,'$1-$2').replace(/([a-z0-9])([A-Z])/g,'$1-$2').toLowerCase()
  function graph(ast,target){
    let program;traverse(ast,{Program(p){program=p;p.stop()}})
    const roots=[]
    for(const statement of ast.program.body){
      if(!target&&t.isExportDefaultDeclaration(statement))roots.push(statement.declaration)
      const n=t.isExpressionStatement(statement)&&statement.expression
      if(t.isAssignmentExpression(n,{operator:'='})&&t.isMemberExpression(n.left)&&!n.left.computed
          &&t.isIdentifier(n.left.object,{name:'module'})&&t.isIdentifier(n.left.property,{name:'exports'})
          &&!program.scope.getBinding('module'))roots.push(n.right)
    }
    const resolve=(node,seen=new Set())=>{
      if(t.isIdentifier(node)){
        if(seen.has(node.name))return null
        const bind=program.scope.getBinding(node.name),d=bind?.path.node
        return bind?.constant&&bind.path.isVariableDeclarator()&&bind.path.parent.kind==='const'
          ?resolve(d.init,new Set([...seen,node.name])):null
      }
      if(target){
        if(!t.isCallExpression(node)||node.arguments.length!==1||!t.isMemberExpression(node.callee)||node.callee.computed
            ||!t.isIdentifier(node.callee.object,{name:'san'})||!t.isIdentifier(node.callee.property,{name:'defineComponent'}))return null
        const bind=program.scope.getBinding('san'),init=bind?.path.node.init
        if(!bind?.constant||!bind.path.isVariableDeclarator()||bind.path.parent.kind!=='const'
            ||!t.isCallExpression(init)||!t.isIdentifier(init.callee,{name:'require'})||program.scope.getBinding('require')
            ||init.arguments.length!==1||!t.isStringLiteral(init.arguments[0],{value:'san'}))return null
        node=node.arguments[0]
      }
      return plain(node)&&!one(node,'mixins')&&!one(node,'extends')?node:null
    }
    return {root:roots.length===1?resolve(roots[0]):null,resolve}
  }
  const sg=graph(sourceAst,false);if(!sg.root)return {code,edits:[]}
  function pairedOptions(ast){
    const tg=graph(ast,true),pairs=[],seen=new Set()
    if(!tg.root)return pairs
    const pair=(s,d)=>{
      if(seen.has(d))return;seen.add(d);pairs.push([s,d])
      const sourceComponents=one(s,'components')?.value,targetComponents=one(d,'components')?.value
      if(!plain(sourceComponents)||!plain(targetComponents))return
      for(const x of sourceComponents.properties){
        const matches=targetComponents.properties.filter(y=>tag(key(y))===tag(key(x)))
        if(matches.length!==1)continue
        const childSource=sg.resolve(x.value),childTarget=tg.resolve(matches[0].value)
        if(childSource&&childTarget)pair(childSource,childTarget)
      }
    };pair(sg.root,tg.root);return pairs
  }
  const sameKeys=(x,y)=>plain(x)&&plain(y)&&x.properties.every(fn)&&y.properties.every(fn)
    &&JSON.stringify(x.properties.map(key).sort())===JSON.stringify(y.properties.map(key).sort())
  const matches=new Map(),positions=[]
  for(let at=Math.max(0,errorAt-512);at<=errorAt&&at<script.length;at++)if(script[at]==='}')positions.push(at)
  if(positions.length>64)return {code,edits:[]}
  for(const at of positions){
    const proposed=script.slice(0,at)+script.slice(at+1);let ast
    try{ast=babel.parse(proposed,{sourceType:'unambiguous'})}catch{continue}
    let insideFunction=false
    walk(ast,n=>{if(t.isFunction(n)&&n.start<at&&at<n.end)insideFunction=true})
    if(insideFunction)continue
    let proved=false
    for(const [src,dst] of pairedOptions(ast)){
      for(let i=0;i<dst.properties.length-1;i++){
        const prev=dst.properties[i],next=dst.properties[i+1],name=key(prev),following=key(next)
        if(prev.end!==at||!/^\s*,\s*$/.test(proposed.slice(prev.end,next.start)))continue
        const sourceKey=name==='initData'?'data':name
        const sourcePrevious=one(src,sourceKey)
        const sourceFollowing=one(src,following)||one(one(src,'methods')?.value,following)
        if(!sourceFollowing)continue
        if(name==='initData'&&fn(prev)&&sourcePrevious&&fn(sourcePrevious))proved=true
        if(['computed','methods'].includes(name)&&t.isObjectProperty(prev)&&sourcePrevious
            &&sameKeys(sourcePrevious.value,prev.value))proved=true
      }
    }
    if(proved&&!matches.has(proposed))matches.set(proposed,at)
  }
  if(matches.size!==1)return {code,edits:[]}
  const [proposed,at]=[...matches][0],start=b.descriptor.script.loc.start.offset+at
  return {code:code.slice(0,b.descriptor.script.loc.start.offset)+proposed+code.slice(b.descriptor.script.loc.end.offset),
    edits:[{start,end:start+1,replacement:'',rule:'source_component_option_boundary_extra_brace_v1'}]}
}

function scriptEdits(source, code, require) {
  const boundary=sourceOptionBoundaryClose(source,code,require)
  if(boundary.edits.length)return boundary
  const leaves = sourceLeafClosingEdits(source,code,require)
  leaves.push(...sourceExactMethodClosingEdits(source,code,require).filter(e => !leaves.some(l => l.method === e.method)))
  leaves.push(...sourceCompleteMethodClosingEdits(source,code,require).filter(e=>!leaves.some(l=>l.method===e.method)))
  const partial = applyEdits(code,leaves), commas = commaEdits(partial,require)
  const candidate = applyEdits(partial,commas)
  if (!leaves.length) return {code:candidate,edits:commas}
  const babel = require('@babel/parser'), descriptor = require('@vue/compiler-sfc').parse(candidate).descriptor
  let ast
  try {ast = babel.parse(descriptor.script.content,{sourceType:'unambiguous'})} catch {return {code,edits:[]}}
  const parents = []
  require('@babel/traverse').default(ast,{AssignmentExpression(p){
    const n=p.node
    if (n.type === 'AssignmentExpression' && n.operator === '=' && n.left.type === 'MemberExpression' &&
        !n.left.computed && n.left.object.name === 'module' && n.left.property.name === 'exports' &&
        n.right.type === 'CallExpression' && n.right.callee.type === 'MemberExpression' && !n.right.callee.computed &&
        n.right.callee.object.name === 'san' && n.right.callee.property.name === 'defineComponent' &&
        n.right.arguments.length === 1 && n.right.arguments[0].type === 'ObjectExpression'
        &&p.parentPath.isExpressionStatement()&&p.parentPath.parentPath.isProgram()
        &&!p.scope.getBinding('module')&&!p.scope.getBinding('require')){
      const binding=p.scope.getBinding('san'),decl=binding?.path?.node
      if(binding?.kind==='const'&&decl?.type==='VariableDeclarator'&&decl.init?.type==='CallExpression'
          &&decl.init.callee?.name==='require'&&decl.init.arguments.length===1&&decl.init.arguments[0].value==='san'
          &&binding.constant)parents.push(n.right.arguments[0])
    }
  }})
  if (parents.length !== 1) return {code,edits:[]}
  // Exclude matches inside comments/strings or child components. Every repaired
  // span must be the unique ordinary method on the exported parent.
  for (const name of new Set(leaves.map(e => e.method))) {
    const methods = parents[0].properties.filter(p => p.type === 'ObjectMethod' && !p.computed && p.key.name === name)
    if (methods.length !== 1) return {code,edits:[]}
    const reference = babel.parseExpression('({' + leaves.find(e => e.method === name).reference + '})').properties[0]
    if (canonicalAst(methods[0]) !== canonicalAst(reference)) return {code,edits:[]}
    const globals=leaves.find(e=>e.method===name).native_globals??[]
    if(globals.length){
      let scoped;require('@babel/traverse').default(ast,{ObjectMethod(p){if(p.node===methods[0]){scoped=p;p.stop()}}})
      if(!scoped||globals.some(n=>scoped.scope.getBinding(n)))return {code,edits:[]}
    }
    const start = descriptor.script.loc.start.offset + methods[0].start, end = descriptor.script.loc.start.offset + methods[0].end
    let mapped = leaves.find(e => e.method === name).start
    for (const edit of leaves) if (edit.start <= mapped) mapped += edit.replacement.length
    for (const edit of commas) if (edit.start <= mapped) mapped += edit.replacement.length
    if (mapped < start || mapped > end) return {code,edits:[]}
  }
  return {code:candidate,edits:[...leaves,...commas]}
}

export function normalizeTarget(source, code, require) {
  const before = inspectTarget(code, require), edits = []
  // San accepts some prefixes (for example this.data.get in render bindings)
  // that are semantically wrong. Source-matched attribute repairs must also
  // run on parseable templates, rather than only after a fatal parse error.
  // Each edit is relative to the current bytes; apply right to left.
  const attributes=attributeEdits(source,code,require)
  code=applyEdits(code,attributes); edits.push(...attributes)
  if(before.status!=='pass'){
    const loops = loopEdits(source, code, require)
    for (const edit of [...loops].sort((a,b) => b.start-a.start)) code = code.slice(0, edit.start) + edit.replacement + code.slice(edit.end)
    edits.push(...loops)
    const script = scriptEdits(source,code,require)
    code = script.code; edits.push(...script.edits)
  }
  // Repairing an outer loop/script can expose previously unparsed ordinary
  // attributes. Complete those source-matched edits in this same proposal.
  for(let pass=0;pass<2;pass++){
    const following=attributeEdits(source,code,require)
    if(!following.length)break
    code=applyEdits(code,following);edits.push(...following)
  }
  const after = inspectTarget(code, require)
  return {code, changes: edits.map(({rule,start,end,replacement}) => ({rule,start,end,replacement})), before, after}
}
