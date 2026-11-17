// Capability check, not a source-code error or a finite-key contract waiver.
export function inspectSourceContracts(source,require){
  const {descriptor}=require('@vue/compiler-sfc').parse(source)
  const parser=require('@babel/parser'),traverse=require('@babel/traverse').default
  const inspect=require('./migration_pipeline/utils/method_interface_semantics.cjs').inspectDynamicAssignment
  const script=descriptor.script?.content??'',ast=parser.parse(script,{sourceType:'module'})
  const roots=ast.program.body.flatMap(n=>n.type==='ExportDefaultDeclaration'?[n.declaration]:
    n.type==='ExpressionStatement'&&n.expression.type==='AssignmentExpression'&&n.expression.operator==='='&&
    n.expression.left.type==='MemberExpression'&&!n.expression.left.computed&&
    n.expression.left.object.name==='module'&&n.expression.left.property.name==='exports'?[n.expression.right]:[])
  const name=n=>!n.computed&&(n.key?.name??n.key?.value)
  const fn=n=>n?.type==='ObjectMethod'&&n.kind==='method'?n:
    n?.type==='ObjectProperty'&&['FunctionExpression','ArrowFunctionExpression'].includes(n.value.type)?n.value:null
  const bindings=new Map()
  traverse(ast,{Program(p){for(const [key,binding] of Object.entries(p.scope.bindings)){
    if(!binding.constant)continue
    const node=binding.path.node
    bindings.set(key,node.type==='VariableDeclarator'?node.init:node)
  }p.stop()}})
  const root=roots.length===1?(roots[0].type==='Identifier'?bindings.get(roots[0].name):roots[0]):null
  const methods=root?.type==='ObjectExpression'&&root.properties.find(p=>name(p)==='methods')?.value
  const diagnostics=[]
  for(const method of methods?.type==='ObjectExpression'?methods.properties:[]){
    const body=fn(method)??(method.value?.type==='Identifier'?bindings.get(method.value.name):null)
    if(!inspect(body))continue
    const offset=(descriptor.script?.loc.start.offset??0)+body.start,prefix=source.slice(0,offset)
    diagnostics.push({code:'source_dynamic_key_contract_unsupported',
      message:`源方法 ${String(name(method))} 使用 this[key] = value。源代码合法，但当前迁移器尚未实现任意公开键契约（包括字面点号键、Symbol 和实例命名空间）；this.data.set(key, value) 不能直接视为等价。保留原契约，停止模型调用，不缩小为固定键白名单。`,
      location:{offset,line:prefix.split('\n').length,column:offset-prefix.lastIndexOf('\n')},
      location_precision:'exact',excerpt:source.slice(Math.max(0,offset-70),offset+170)})
  }
  return {version:'arbitrary_public_key_capability_v1',status:diagnostics.length?'blocked':'completed',diagnostics:diagnostics.slice(0,16),
    scope:'exact_dynamic_instance_setter_recognition_only_not_full_source_support_proof'}
}
