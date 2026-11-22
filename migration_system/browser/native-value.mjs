// Reflect a source :value on ordinary inputs through the native defaultValue
// property, which San updates and the browser reflects to the actual value
// attribute. This changes the target DOM; it does NOT waive DOM differences.
// Nullable/unknown data, props, v-model, loops and arbitrary keys stay strict.
export function nonNullableRootState(source, field, require) {
  try {
    if (!/^[A-Za-z_$][\w$]*$/.test(field)) return false
    const {descriptor}=require('@vue/compiler-sfc').parse(source)
    if (!descriptor.script || /\bv-for\b/.test(descriptor.template?.content??'')) return false
    const t=require('@babel/types'),traverse=require('@babel/traverse').default
    const ast=require('@babel/parser').parse(descriptor.script.content,{sourceType:'unambiguous'})
    const key=p=>!p.computed&&(p.key?.name??p.key?.value), one=(o,k)=>{
      const ps=o?.properties?.filter(p=>key(p)===k)??[];return ps.length===1?ps[0]:null
    }
    const roots=ast.program.body.flatMap(n=>t.isExportDefaultDeclaration(n)?[n.declaration]:
      t.isExpressionStatement(n)&&t.isAssignmentExpression(n.expression,{operator:'='})&&
      t.isMemberExpression(n.expression.left)&&!n.expression.left.computed&&
      n.expression.left.object.name==='module'&&n.expression.left.property.name==='exports'?[n.expression.right]:[])
    const root=roots.length===1&&roots[0],data=one(root,'data'),methods=one(root,'methods')?.value
    if(!t.isObjectExpression(root)||root.properties.some(p=>!key(p))||one(root,'mixins')||one(root,'extends')||one(root,'setup')
        ||!t.isObjectMethod(data)||data.body.body.length!==1||!t.isReturnStatement(data.body.body[0]))return false
    const initial=one(data.body.body[0].argument,field)?.value
    if(!['StringLiteral','NumericLiteral','BooleanLiteral'].includes(initial?.type)||one(one(root,'props')?.value,field))return false
    const setters=new Set()
    for(const m of methods?.properties??[]){
      if(!t.isObjectMethod(m)||m.params.length!==2||!m.params.every(t.isIdentifier)||m.body.body.length!==1)continue
      const a=m.body.body[0].expression
      if(t.isAssignmentExpression(a,{operator:'='})&&t.isMemberExpression(a.left)&&a.left.computed&&t.isThisExpression(a.left.object)
          &&t.isIdentifier(a.left.property,{name:m.params[0].name})&&t.isIdentifier(a.right,{name:m.params[1].name}))setters.add(key(m))
    }
    let valid=true
    const eventMethods=new Set()
    const visit=n=>{
      if(n.type===1&&n.tag==='input'&&n.props.some(p=>p.type===7&&p.name==='bind'&&p.arg?.content==='value'&&p.exp?.content.trim()===field))
        for(const p of n.props)if(p.type===7&&p.name==='on'&&['input','change'].includes(p.arg?.content)
          &&/^[A-Za-z_$][\w$]*$/.test(p.exp?.content.trim()??''))eventMethods.add(p.exp.content.trim())
      for(const c of n.children??[])visit(c)
    }
    visit(require('@vue/compiler-dom').parse(descriptor.template.content))
    const nonnull=(n,path,seen=new Set())=>{
      if(!n)return false
      if(['StringLiteral','NumericLiteral','BooleanLiteral'].includes(n.type))return true
      if(t.isUnaryExpression(n)&&['+','-','!','~','typeof'].includes(n.operator))return true
      if(t.isBinaryExpression(n)&&!['in','instanceof'].includes(n.operator))return true
      if(t.isLogicalExpression(n))return nonnull(n.left,path,seen)&&nonnull(n.right,path,seen)
      if(t.isConditionalExpression(n))return nonnull(n.consequent,path,seen)&&nonnull(n.alternate,path,seen)
      if(t.isTemplateLiteral(n))return true
      if(t.isMemberExpression(n)&&!n.computed&&n.property.name==='value'&&t.isMemberExpression(n.object)
          &&!n.object.computed&&n.object.property.name==='target'&&t.isIdentifier(n.object.object)){
        const b=path.scope.getBinding(n.object.object.name),fn=b?.path.findParent(p=>p.isFunction())
        if(b?.kind==='param'&&t.isObjectMethod(fn?.node)&&methods?.properties.includes(fn.node)
            &&eventMethods.has(key(fn.node))&&fn.node.params.length===1&&fn.node.params[0]===b.path.node)return true
      }
      if(t.isCallExpression(n)&&t.isIdentifier(n.callee)&&['String','Number','Boolean'].includes(n.callee.name)
          &&!path.scope.getBinding(n.callee.name))return true
      if(t.isIdentifier(n)){
        const b=path.scope.getBinding(n.name),d=b?.path.node
        return !seen.has(n.name)&&b?.constant&&t.isVariableDeclarator(d)&&nonnull(d.init,b.path,new Set([...seen,n.name]))
      }
      return false
    }
    const owns=n=>t.isMemberExpression(n)&&t.isThisExpression(n.object)&&(!n.computed?n.property.name:n.property.value)===field
    traverse(ast,{
      ThisExpression(p){if(!p.parentPath.isMemberExpression()||p.parent.object!==p.node)valid=false},
      MemberExpression(p){const n=p.node;if(t.isThisExpression(n.object)&&!n.computed){
        if(['$data','$props','$options'].includes(n.property.name))valid=false
        if(setters.has(n.property.name)&&(!p.parentPath.isCallExpression()||p.parent.callee!==n))valid=false
      }},
      AssignmentExpression(p){const n=p.node,l=n.left;if(owns(l)&&!nonnull(n.right,p))valid=false
        if(t.isMemberExpression(l)&&t.isThisExpression(l.object)&&l.computed&&!t.isStringLiteral(l.property)){
          const fn=p.getFunctionParent();if(!setters.has(key(fn?.node)))valid=false
        }},
      CallExpression(p){const c=p.node.callee
        if(!t.isMemberExpression(c)||!t.isThisExpression(c.object))return
        if(c.computed||['$set','$delete'].includes(c.property.name)){valid=false;return}
        if(!setters.has(c.property.name))return
        const [k,v]=p.node.arguments
        if(p.node.arguments.length!==2||!t.isStringLiteral(k)){valid=false;return}
        if(k.value===field&&!nonnull(v,p))valid=false
      }
    })
    return valid
  } catch {return false}
}
