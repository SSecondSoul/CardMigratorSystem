// Read-only method-body inventory. This is not a migration/repair recognizer.
const parser = require('@babel/parser');
const generate = require('@babel/generator').default;
const key = p => !p.computed && (p.key?.name || p.key?.value);
const member = (n, object, property) => n?.type === 'MemberExpression' && !n.computed
  && n.object.type === 'Identifier' && n.object.name === object && n.property.name === property;
function options(code, target) {
  const block = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
  if (!block) throw Error('missing_script');
  const ast = parser.parse(block[1], {sourceType:'unambiguous'}), candidates=[];
  for (const statement of ast.program.body) {
    let value;
    if (statement.type === 'ExportDefaultDeclaration' && !target) value=statement.declaration;
    if (statement.type === 'ExpressionStatement' && statement.expression.type === 'AssignmentExpression'
        && statement.expression.operator === '=' && member(statement.expression.left,'module','exports')) value=statement.expression.right;
    if (!value) continue;
    if (target) {
      if (value.type !== 'CallExpression' || value.optional || !member(value.callee,'san','defineComponent')
          || value.arguments.length !== 1) throw Error('unsupported_export');
      value=value.arguments[0];
    }
    candidates.push(value);
  }
  if (candidates.length !== 1 || candidates[0].type !== 'ObjectExpression') throw Error('ambiguous_export');
  return candidates[0];
}
function unique(object, name) {
  if (!object || object.type !== 'ObjectExpression' || object.properties.some(p => !key(p))) throw Error('ambiguous_options');
  const matches=object.properties.filter(p=>key(p)===name);
  if(matches.length>1) throw Error('duplicate_method');
  return matches[0];
}
function shape(method) {
  if (!method) return {shape:'missing', code:null};
  const fn=method.type==='ObjectMethod'&&method.kind==='method'?method:
    method.type==='ObjectProperty'&&method.value.type==='FunctionExpression'?method.value:null;
  const text=generate(method,{compact:true,comments:false}).code;
  if(!fn||fn.async||fn.generator||fn.params.length!==2||fn.params.some(p=>p.type!=='Identifier')
      ||fn.params[0].name===fn.params[1].name||fn.body.directives?.length||fn.body.body.length!==1)
    return {shape:'unassessed',code:text};
  const [a,b]=fn.params.map(p=>p.name), s=fn.body.body[0], e=s.type==='ExpressionStatement'&&s.expression;
  if(e?.type==='AssignmentExpression'&&e.operator==='='&&e.left.type==='MemberExpression'
      &&e.left.computed&&e.left.object.type==='ThisExpression'&&e.left.property.type==='Identifier'
      &&e.left.property.name===a&&e.right.type==='Identifier'&&e.right.name===b)
    return {shape:'dynamic_instance_assignment',code:text};
  if(e?.type==='CallExpression'&&!e.optional&&e.arguments.length===2
      &&e.arguments[0].type==='Identifier'&&e.arguments[0].name===a
      &&e.arguments[1].type==='Identifier'&&e.arguments[1].name===b
      &&e.callee.type==='MemberExpression'&&!e.callee.computed&&e.callee.property.name==='set'
      &&e.callee.object.type==='MemberExpression'&&!e.callee.object.computed
      &&e.callee.object.object.type==='ThisExpression'&&e.callee.object.property.name==='data')
    return {shape:'dynamic_san_data_path_write',code:text};
  return {shape:'unassessed',code:text};
}
function inspect({vue,san,names}) {
  try {
    const source=options(vue,false), target=options(san,true), methods=unique(source,'methods')?.value;
    return {scope:'exported_parent_method_body_only_not_whole_component', rows:names.map(name=>({name,
      source:shape(unique(methods,name)),target:shape(unique(target,name))}))};
  } catch(e) {return {scope:'unassessed',reason:e.message,rows:[]};}
}
module.exports={inspect,shape};
if(require.main===module){let input='';process.stdin.on('data',c=>input+=c);
  process.stdin.on('end',()=>process.stdout.write(JSON.stringify(inspect(JSON.parse(input)))));}
