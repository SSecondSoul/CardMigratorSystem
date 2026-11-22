// Prove only fresh array + fresh shallow records, direct scalar writes, then
// one explicit commit. Unknown syntax, escape, depth or control flow fails closed.
// Parsing only: generated component code is never executed.
const fs = require('fs'), parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const t = require('@babel/types');
const forbiddenKeys = new Set(['__proto__', 'constructor', 'prototype']);
function fieldCall(n, action, field) {
  return t.isCallExpression(n) && !n.optional && n.arguments.length === (action === 'get' ? 1 : 2)
    && t.isMemberExpression(n.callee) && !n.callee.computed && n.callee.property.name === action
    && t.isMemberExpression(n.callee.object) && !n.callee.object.computed
    && t.isThisExpression(n.callee.object.object) && n.callee.object.property.name === 'data'
    && t.isStringLiteral(n.arguments[0]) && (!field || n.arguments[0].value === field);
}
function recordProperty(n, name) {
  return t.isMemberExpression(n) && !n.computed && t.isIdentifier(n.property)
    && !forbiddenKeys.has(n.property.name) && t.isMemberExpression(n.object)
    && n.object.computed && t.isNumericLiteral(n.object.property)
    && Number.isInteger(n.object.property.value) && n.object.property.value >= 0
    && t.isIdentifier(n.object.object, {name});
}
function scalar(n, name, scope) {
  if (t.isNumericLiteral(n) || t.isBooleanLiteral(n) || t.isStringLiteral(n) || t.isNullLiteral(n)) return true;
  if (recordProperty(n, name)) return true;
  if (t.isBinaryExpression(n) || t.isLogicalExpression(n)) return scalar(n.left, name, scope) && scalar(n.right, name, scope);
  if (t.isUnaryExpression(n) && ['+', '-', '!', '~'].includes(n.operator)) return scalar(n.argument, name, scope);
  if (t.isConditionalExpression(n)) return [n.test, n.consequent, n.alternate].every(x => scalar(x, name, scope));
  return t.isCallExpression(n) && t.isMemberExpression(n.callee) && !n.callee.computed
    && t.isIdentifier(n.callee.object, {name: 'Math'}) && !scope.getBinding('Math')
    && ['max', 'min', 'random', 'round', 'floor', 'ceil', 'abs'].includes(n.callee.property.name)
    && n.arguments.every(x => scalar(x, name, scope));
}
// Different proof from fresh records: only detach the ARRAY CONTAINER, remove
// one element and reinsert it unchanged, then commit immediately. A shallow
// array copy never authorizes record/deep writes. No source code is rewritten.
function containerCopies(fn, ast) {
  if(!fn.isObjectMethod()||fn.node.kind!=='method'||fn.node.params.some(p=>!t.isIdentifier(p)))return [];
  const properties=fn.parentPath.node.properties;
  if(!Array.isArray(properties))return [];
  const nameOf=p=>!p.computed&&(p.key?.name??p.key?.value);
  const factories=properties.filter(p=>nameOf(p)==='initData');
  const factory=factories[0],returned=factory?.body?.body;
  if(factories.length!==1||!t.isObjectMethod(factory)||returned?.length!==1
      ||!t.isReturnStatement(returned[0])||!t.isObjectExpression(returned[0].argument))return [];
  let changedIntrinsic=false;
  traverse(ast,{
    BindingIdentifier(p){if(['Array','eval'].includes(p.node.name))changedIntrinsic=true;},
    AssignmentExpression(p){let root=p.node.left;while(t.isMemberExpression(root))root=root.object;
      if(t.isIdentifier(root,{name:'Array'}))changedIntrinsic=true;},
    CallExpression(p){if(t.isIdentifier(p.node.callee,{name:'eval'}))changedIntrinsic=true;
      if(t.isMemberExpression(p.node.callee)&&t.isIdentifier(p.node.callee.object,{name:'Object'})
          &&['defineProperty','defineProperties','setPrototypeOf','assign'].includes(p.node.callee.property.name)
          &&p.node.arguments.some(n=>t.isIdentifier(n,{name:'Array'})||t.isMemberExpression(n)&&t.isIdentifier(n.object,{name:'Array'})))changedIntrinsic=true;}
  });
  if(changedIntrinsic)return [];
  const statements=fn.get('body.body'),params=new Set(fn.node.params.map(p=>p.name)),proofs=[];
  const index=n=>t.isNumericLiteral(n)||(t.isIdentifier(n)&&params.has(n.name))
    ||t.isUnaryExpression(n)&&['+','-'].includes(n.operator)&&index(n.argument)
    ||t.isBinaryExpression(n)&&['+','-','*','/','%'].includes(n.operator)&&index(n.left)&&index(n.right);
  const call=(n,name,method)=>t.isCallExpression(n)&&!n.optional&&t.isMemberExpression(n.callee)&&!n.callee.computed
    &&t.isIdentifier(n.callee.object,{name})&&t.isIdentifier(n.callee.property,{name:method});
  for(let i=0;i<statements.length-3;i++){
    const declaration=statements[i],d=declaration.node.declarations?.[0];
    if(!declaration.isVariableDeclaration({kind:'const'})||declaration.node.declarations.length!==1||!t.isIdentifier(d.id))continue;
    let read;
    if(t.isCallExpression(d.init)&&!d.init.optional&&!d.init.arguments.length&&t.isMemberExpression(d.init.callee)
        &&!d.init.callee.computed&&t.isIdentifier(d.init.callee.property,{name:'slice'}))read=d.init.callee.object;
    if(t.isArrayExpression(d.init)&&d.init.elements.length===1&&t.isSpreadElement(d.init.elements[0]))read=d.init.elements[0].argument;
    if(!fieldCall(read,'get'))continue;
    const field=read.arguments[0].value,initial=returned[0].argument.properties.filter(p=>nameOf(p)===field);
    if(initial.length!==1||!t.isObjectProperty(initial[0])||!t.isArrayExpression(initial[0].value))continue;
    const name=d.id.name,binding=declaration.scope.getBinding(name);
    if(!binding?.constant||binding.constantViolations.length)continue;
    const take=statements[i+1],item=take.node.declarations?.[0],access=item?.init,remove=access?.object;
    if(!take.isVariableDeclaration({kind:'const'})||take.node.declarations.length!==1||!t.isIdentifier(item?.id)
        ||!t.isMemberExpression(access)||!access.computed||!t.isNumericLiteral(access.property,{value:0})
        ||!call(remove,name,'splice')||remove.arguments.length!==2||!index(remove.arguments[0])
        ||!t.isNumericLiteral(remove.arguments[1],{value:1}))continue;
    const put=statements[i+2].node.expression,commit=statements[i+3].node.expression;
    if(!statements[i+2].isExpressionStatement()||!call(put,name,'splice')||put.arguments.length!==3
        ||!index(put.arguments[0])||!t.isNumericLiteral(put.arguments[1],{value:0})
        ||!t.isIdentifier(put.arguments[2],{name:item.id.name})||!statements[i+3].isExpressionStatement()
        ||!fieldCall(commit,'set',field)||!t.isIdentifier(commit.arguments[1],{name}))continue;
    const itemBinding=take.scope.getBinding(item.id.name);
    if(!itemBinding?.constant||itemBinding.constantViolations.length||itemBinding.referencePaths.length!==1
        ||itemBinding.referencePaths[0].node!==put.arguments[2])continue;
    let safe=true;
    fn.traverse({Identifier(p){
      if(p.node.name===name&&p.scope.getBinding(name)!==binding)safe=false;
      if(p.node.name===item.id.name&&p.scope.getBinding(item.id.name)!==itemBinding)safe=false;
    }});
    for(const ref of binding.referencePaths){
      if(ref.getFunctionParent()!==fn){safe=false;break;}
      if([remove.callee.object,put.callee.object,commit.arguments[1]].includes(ref.node))continue;
      const member=ref.parentPath,c=member.parentPath,fire=c.parentPath,statement=fire.parentPath;
      if(!member.isMemberExpression()||member.node.object!==ref.node||!call(c.node,name,'slice')||c.node.arguments.length
          ||!fire.isCallExpression()||!t.isMemberExpression(fire.node.callee)||fire.node.callee.computed
          ||!t.isThisExpression(fire.node.callee.object)||!t.isIdentifier(fire.node.callee.property,{name:'fire'})
          ||fire.node.arguments.length!==2||!t.isStringLiteral(fire.node.arguments[0])||fire.node.arguments[1]!==c.node
          ||!statement.isExpressionStatement()||statement.parentPath!==fn.get('body')||fire.node.start<commit.end)safe=false;
    }
    if(safe)proofs.push(name);
  }
  return proofs;
}
function prove({body, script}) {
  const ast = parser.parse(script, {sourceType: 'unambiguous'});
  const matches = [];
  traverse(ast, {Function(p) {
    if (t.isBlockStatement(p.node.body) && script.slice(p.node.body.start + 1, p.node.body.end - 1) === body)
      matches.push(p);
  }});
  if (matches.length !== 1 || matches[0].node.async || matches[0].node.generator) return {aliases: []};
  const fn = matches[0];
  const aliases = containerCopies(fn,ast);
  for (const statement of fn.get('body.body')) {
    if (!statement.isVariableDeclaration({kind: 'const'}) || statement.node.declarations.length !== 1) continue;
    const declaration = statement.get('declarations.0'), n = declaration.node, map = n.init;
    if (!t.isIdentifier(n.id) || !t.isCallExpression(map) || map.arguments.length !== 1
        || !t.isMemberExpression(map.callee) || map.callee.computed || map.callee.property.name !== 'map'
        || !fieldCall(map.callee.object, 'get')) continue;
    const cb = map.arguments[0], obj = cb?.body;
    if (!t.isArrowFunctionExpression(cb) || cb.async || cb.params.length !== 1 || !t.isIdentifier(cb.params[0])
        || !t.isObjectExpression(obj) || obj.properties.length !== 1 || !t.isSpreadElement(obj.properties[0])
        || !t.isIdentifier(obj.properties[0].argument, {name: cb.params[0].name})) continue;
    const name = n.id.name, field = map.callee.object.arguments[0].value;
    const binding = declaration.scope.getBinding(name);
    if (!binding || binding.constantViolations.length) continue;
    let unsafe = false, commit, writes = [];
    // Textual fallback validator cannot distinguish shadowed names: in that
    // situation retain its diagnostics rather than hiding an unrelated mutation.
    fn.traverse({Identifier(p) {
      if (p.node.name === name && p.scope.getBinding(name) !== binding) unsafe = true;
    }});
    for (const ref of binding.referencePaths) {
      if (ref.getFunctionParent() !== fn) {unsafe = true; break;}
      const parent = ref.parentPath;
      if (parent.isCallExpression() && fieldCall(parent.node, 'set', field)
          && parent.node.arguments[1] === ref.node && parent.parentPath.isExpressionStatement()
          && parent.parentPath.parentPath === fn.get('body')) {
        if (commit) unsafe = true;
        commit = parent.node; continue;
      }
      let root = ref;
      while (root.parentPath.isMemberExpression() && root.parentPath.node.object === root.node) root = root.parentPath;
      if (!recordProperty(root.node, name)) {unsafe = true; break;}
      if (root.parentPath.isAssignmentExpression() && root.parentPath.node.left === root.node) {
        const assignment = root.parentPath;
        if (assignment.node.operator !== '=' || !assignment.parentPath.isExpressionStatement()
            || assignment.parentPath.parentPath !== fn.get('body')
            || !scalar(assignment.node.right, name, assignment.scope)) unsafe = true;
        writes.push(assignment.node);
      } else {
        // A record read is allowed only inside an already bounded scalar write.
        const assignment = root.findParent(p => p.isAssignmentExpression());
        if (!assignment || !recordProperty(assignment.node.left, name)
            || !scalar(assignment.node.right, name, assignment.scope)) unsafe = true;
      }
    }
    if (!unsafe && commit && writes.length && writes.every(w => w.start > n.end && w.end < commit.start)) {
      // Abrupt flow can skip the commit. Unknown loops/try/closures in the
      // enclosing method are conservatively refused even without alias escape.
      fn.traverse({enter(p) {
        if (p.isReturnStatement() || p.isThrowStatement() || p.isTryStatement()
            || p.isAwaitExpression() || p.isYieldExpression() || p.isLoop()
            || p.isWithStatement() || p.isSwitchStatement()
            || (p.isCallExpression() && t.isIdentifier(p.node.callee, {name: 'eval'}))) unsafe = true;
      }});
      if (!unsafe) aliases.push(name);
    }
  }
  return {aliases, boundary: 'shallow fresh records; complete local use chain; direct scalar writes then commit'};
}
try {process.stdout.write(JSON.stringify(prove(JSON.parse(fs.readFileSync(0, 'utf8')))));}
catch (_) {process.stdout.write(JSON.stringify({aliases: [], status: 'unproven'}));}
