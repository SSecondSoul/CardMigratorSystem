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
// call/return expression using literals, parameters, declared state reads and
// member/call chains qualifies. No writes, closures, computed access or control flow.
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
    if (n.type === 'CallExpression' && !n.optional) return expression(n.callee) + '(' + n.arguments.map(expression).join(',') + ')'
    throw Error('unsupported')
  }
  try {
    const body = stmt.type === 'ExpressionStatement' ? expression(stmt.expression) :
      stmt.type === 'ReturnStatement' ? 'return ' + expression(stmt.argument) : null
    return body === null ? null : method.key.name + '(' + method.params.map(p => p.name).join(',') + '){' + body + '}'
  } catch {return null}
}

// Lex only the tiny leaf method span above. Any regex/template/operator or
// unknown token refuses repair. String values use Babel decoding, never eval.
function leafTokens(text, babel) {
  const tokens = []; let at = 0
  while (at < text.length) {
    const rest = text.slice(at), space = /^\s+/.exec(rest)
    if (space) {at += space[0].length; continue}
    const match = /^(?:"(?:[^"\\\r\n]|\\.)*"|'(?:[^'\\\r\n]|\\.)*'|[A-Za-z_$][\w$]*|\d+(?:\.\d+)?|[(){},.;])/.exec(rest)
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
  let options
  try {options = sourceOptions(source, require)} catch {return []}
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
        method:method.key.name,reference,rule:'source_proven_leaf_closing_tokens_v1'})
    }
    if (actual[i]?.value === ';') i++
    if (!insertions || i !== actual.length || !insertions.length || insertions.length > 3) continue
    edits.push(...insertions)
  }
  return edits
}

function applyEdits(code, edits) {
  // Reverse index for coincident insertion positions preserves token order.
  for (const {edit} of edits.map((edit,index) => ({edit,index})).sort((a,b) => b.edit.start-a.edit.start || b.index-a.index))
    code = code.slice(0,edit.start) + edit.replacement + code.slice(edit.end)
  return code
}

function scriptEdits(source, code, require) {
  const leaves = sourceLeafClosingEdits(source,code,require)
  leaves.push(...sourceExactMethodClosingEdits(source,code,require).filter(e => !leaves.some(l => l.method === e.method)))
  const partial = applyEdits(code,leaves), commas = commaEdits(partial,require)
  const candidate = applyEdits(partial,commas)
  if (!leaves.length) return {code:candidate,edits:commas}
  const babel = require('@babel/parser'), descriptor = require('@vue/compiler-sfc').parse(candidate).descriptor
  let ast
  try {ast = babel.parse(descriptor.script.content,{sourceType:'unambiguous'})} catch {return {code,edits:[]}}
  const parents = []
  walk(ast,n => {
    if (n.type === 'AssignmentExpression' && n.operator === '=' && n.left.type === 'MemberExpression' &&
        !n.left.computed && n.left.object.name === 'module' && n.left.property.name === 'exports' &&
        n.right.type === 'CallExpression' && n.right.callee.type === 'MemberExpression' && !n.right.callee.computed &&
        n.right.callee.object.name === 'san' && n.right.callee.property.name === 'defineComponent' &&
        n.right.arguments.length === 1 && n.right.arguments[0].type === 'ObjectExpression') parents.push(n.right.arguments[0])
  })
  if (parents.length !== 1) return {code,edits:[]}
  // Exclude matches inside comments/strings or child components. Every repaired
  // span must be the unique ordinary method on the exported parent.
  for (const name of new Set(leaves.map(e => e.method))) {
    const methods = parents[0].properties.filter(p => p.type === 'ObjectMethod' && !p.computed && p.key.name === name)
    if (methods.length !== 1) return {code,edits:[]}
    const reference = babel.parseExpression('({' + leaves.find(e => e.method === name).reference + '})').properties[0]
    if (canonicalAst(methods[0]) !== canonicalAst(reference)) return {code,edits:[]}
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
