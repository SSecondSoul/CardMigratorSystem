// Symmetric, bounded abstract interpretation; never execute binding expressions.
// Unknown fragments may join neighbouring text, so 'base'+suffix is NOT 'base'.
const UNKNOWN='\u0000'
const tokens=s=>String(s).split(/[\t\n\f\r ]+/).filter(Boolean)
const intersection=sets=>sets.length?[...sets[0]].filter(x=>sets.every(s=>s.has(x))):[]
function strings(n){
  if(n.kind==='literal')return [String(n.value)]
  if(n.kind==='choice'){const result=[...new Set(n.items.flatMap(strings))];return result.length>32?[UNKNOWN]:result}
  if(n.kind==='concat'){
    let result=['']
    for(const item of n.items){
      const next=strings(item)
      if(result.length*next.length>32)return [UNKNOWN]
      result=result.flatMap(a=>next.map(b=>a+b))
    }
    return result
  }
  return [UNKNOWN]
}
function guaranteed(n){
  if(n.kind==='list')return n.items.flatMap(guaranteed)
  if(n.kind==='choice')return intersection(n.items.map(x=>new Set(guaranteed(x))))
  return intersection(strings(n).map(s=>new Set(tokens(s).filter(x=>!x.includes(UNKNOWN)))))
}
const unknown=()=>({kind:'unknown'})
const literal=value=>({kind:'literal',value})
function vue(n){
  if(n.type==='StringLiteral')return literal(n.value)
  if(n.type==='ConditionalExpression')return {kind:'choice',items:[vue(n.consequent),vue(n.alternate)]}
  if(n.type==='BinaryExpression'&&n.operator==='+')return {kind:'concat',items:[vue(n.left),vue(n.right)]}
  if(n.type==='TemplateLiteral')return {kind:'concat',items:n.quasis.flatMap((q,i)=>[literal(q.value.cooked??''),...(i<n.expressions.length?[vue(n.expressions[i])]:[])])}
  return unknown()
}
function vueClass(n){
  if(n.type==='ArrayExpression')return {kind:'list',items:n.elements.map(x=>x?vueClass(x):unknown())}
  if(n.type==='ObjectExpression')return {kind:'list',items:n.properties.flatMap(p=>
    p.type==='ObjectProperty'&&!p.computed&&(p.key.name??p.key.value)!=='__proto__'&&p.value.type==='BooleanLiteral'&&p.value.value
      ?[literal(p.key.name??p.key.value)]:[])}
  if(n.type==='ConditionalExpression')return {kind:'choice',items:[vueClass(n.consequent),vueClass(n.alternate)]}
  return vue(n)
}
function sanString(n){
  if(n?.type===1)return literal(n.value)
  if(n?.type===8&&n.operator===43)return {kind:'concat',items:n.segs.map(sanString)}
  if(n?.type===10)return {kind:'choice',items:n.segs.slice(1).map(sanString)}
  return unknown()
}
function sanClass(n){
  // Only San's renderer-owned class normalization filter is transparent.
  if(n?.type===5&&n.filters.every(f=>f.name?.paths?.length===1&&f.name.paths[0].value==='_class'))return sanClass(n.expr)
  if(n?.type===7)return {kind:'concat',items:n.segs.map(x=>x.type===5?sanClass(x):sanString(x))}
  if(n?.type===12)return {kind:'list',items:n.items.map(x=>sanClass(x.expr))}
  if(n?.type===11)return {kind:'list',items:n.items.flatMap(x=>x.name.type===1&&x.name.value!=='__proto__'&&x.expr.type===3&&x.expr.value?[literal(x.name.value)]:[])}
  if(n?.type===10)return {kind:'choice',items:n.segs.slice(1).map(sanClass)}
  return sanString(n)
}
export function sourceClassTokens(expression,parser){
  try{return [...new Set(guaranteed(vueClass(parser.parseExpression(expression))))].sort()}catch(_){return []}
}
export function targetClassTokens(expression){return [...new Set(guaranteed(sanClass(expression)))].sort()}
