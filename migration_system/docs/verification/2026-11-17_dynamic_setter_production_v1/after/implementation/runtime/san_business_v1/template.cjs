/* Node-only source template compiler; no Vue component/render runtime emitted. */
'use strict';
const path=require('node:path'),{createRequire}=require('node:module'),{createHash}=require('node:crypto');
const load=createRequire(path.join(__dirname,'../../engine/package.json'));
const dom=load('@vue/compiler-dom'),parser=load('@babel/parser'),traverse=load('@babel/traverse').default,generate=load('@babel/generator').default;
const shared=load('@vue/shared');
const escape=value=>String(value).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;');
function eventHandler(expression,locals,resolveOnly=false){
  let ast,invoke=false;
  try{
    const value=parser.parseExpression(expression);
    if(resolveOnly&&!['Identifier','MemberExpression','OptionalMemberExpression'].includes(value.type))return null;
    invoke=['Identifier','MemberExpression','OptionalMemberExpression','ArrowFunctionExpression','FunctionExpression'].includes(value.type);
    ast={type:'File',program:{type:'Program',sourceType:'script',body:[{type:'ExpressionStatement',expression:value}]}};
  }catch{if(resolveOnly)return null;ast=parser.parse(expression,{sourceType:'script'});}
  const localNames=new Set(locals);
  traverse(ast,{
    AssignmentExpression(p){if(!['Identifier','MemberExpression'].includes(p.node.left.type))throw Error('business_event_assignment_shape_unsupported');},
    ThisExpression(p){p.replaceWith({type:'Identifier',name:'__vm'});p.skip();},
    Identifier(p){
      const assignment=p.parentPath.isAssignmentExpression()&&p.parentPath.node.left===p.node||p.parentPath.isUpdateExpression();
      if((!p.isReferencedIdentifier()&&!assignment)||p.scope.getBinding(p.node.name))return;
      const name=p.node.name;
      if(name==='$event')p.replaceWith({type:'MemberExpression',computed:true,object:{type:'Identifier',name:'__args'},property:{type:'NumericLiteral',value:0}});
      else if(shared.isGloballyAllowed(name))return;
      else p.replaceWith({type:'MemberExpression',computed:true,object:{type:'Identifier',name:localNames.has(name)?'__locals':'__vm'},property:{type:'StringLiteral',value:name}});
      p.skip();
    }
  });
  const body=resolveOnly?'return ('+generate(ast.program.body[0].expression).code+');':invoke?'return ('+generate(ast.program.body[0].expression).code+')(...__args);':generate(ast).code;
  return 'function(__vm,__locals,__args){'+body+'}';
}
function compileTemplate(template,{componentNames=[],reservedMethods=[],reactiveExpressions=false}={}){
  const ast=dom.parse(template),events={},entries=[],references=[],policies=[],expressions={};
  const componentTags=new Set(componentNames.flatMap(name=>[name,name.replace(/\B([A-Z])/g,'-$1').toLowerCase(),name[0].toLowerCase()+name.slice(1)]));
  const prefix='__businessEvent_'+createHash('sha256').update(template).digest('hex').slice(0,12)+'_';
  function expression(text,locals){
    if(!reactiveExpressions)return text;
    const value=parser.parseExpression(text);let calls=false;
    const scan=node=>{if(!node||typeof node!=='object')return;if(['CallExpression','OptionalCallExpression'].includes(node.type))calls=true;
      for(const child of Object.values(node))if(Array.isArray(child))child.forEach(scan);else if(child&&typeof child==='object')scan(child);};
    scan(value);if(!calls)return text;
    let name=prefix+'expression_'+Object.keys(expressions).length;while(reservedMethods.includes(name))name+='_';
    expressions[name]={locals:[...locals],invoke:eventHandler('()=>('+text+')',locals)};
    return name+'(0'+locals.map(name=>', '+name).join('')+')';
  }
  const voids=new Set(['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr']);
  function visit(node,context=[]){
    if(node.type===2)return node.content;
    if(node.type===3)return '<!--'+node.content+'-->';
    if(node.type===5)return '{{ '+expression(node.content.content,context)+' }}';
    if(node.type!==1)return (node.children||[]).map(child=>visit(child,context)).join('');
    const attributes=[],bound=[],inputNames={},loop=node.props.find(prop=>prop.type===7&&prop.name==='for');
    let locals=[...context],loopText,key;
    if(loop){
      const match=loop.exp?.content.match(/^\s*(.*?)\s+(?:in|of)\s+([\s\S]+)$/);
      if(!match)throw Error('business_invalid_source_loop');
      const names=match[1].replace(/^\(|\)$/g,'').split(',').map(name=>name.trim());
      if(names.length>2||names.some(name=>!/^[$\w]+$/.test(name)))throw Error('business_source_loop_layout_unsupported');
      locals.push(...names);loopText=names.join(',')+' in '+expression(match[2],context);
    }
    const component=componentTags.has(node.tag),eventRecords=[];
    for(const prop of node.props){
      if(prop.type===6){
        const name=prop.name==='ref'?'s-ref':prop.name;
        if(prop.name==='ref')references.push(prop.value?.content||'');
        if(component&&prop.name!=='ref')inputNames[shared.camelize(prop.name)]=prop.name;
        attributes.push(name+(prop.value?'="'+escape(prop.value.content)+'"':''));continue;
      }
      const expression=prop.exp?.content;
      if(prop.name==='for')continue;
      if(prop.name==='bind'){
        if(!prop.arg?.isStatic)throw Error('business_dynamic_attribute_unsupported');
        const name=prop.arg.content;
        if(name==='key'){key=expression;continue;}
        if(name==='ref')throw Error('business_dynamic_ref_unsupported');
        if(component)inputNames[shared.camelize(name)]=name;
        if(['class','value','checked','selected'].includes(name))bound.push(name);
        const filter=name==='class'?' | __businessClass':name==='style'?' | __businessStyle':'';
        attributes.push(name+'="'+escape('{{ '+compileBinding(expression,locals)+filter+' }}')+'"');continue;
      }
      if(prop.name==='on'){
        if(!prop.arg?.isStatic)throw Error('business_dynamic_event_unsupported');
        let name=prefix+entries.length;while(reservedMethods.includes(name))name+='_';
        const modifiers=prop.modifiers.map(value=>typeof value==='string'?value:value.content);
        for(const modifier of modifiers)if(!['once','stop','prevent','self','capture'].includes(modifier))throw Error('business_event_modifier_unsupported:'+modifier);
        if(component&&modifiers.some(value=>value!=='once'))throw Error('business_component_event_modifier_unsupported');
        events[name]={locals:[...locals],once:modifiers.includes('once'),modifiers,invoke:eventHandler(expression||'()=>{}',locals),resolve:eventHandler(expression||'()=>{}',locals,true)};
        const record={name,event:prop.arg.content,modifiers,locals:[...locals],component};entries.push(record);eventRecords.push(record);
        const modifierText=modifiers.includes('capture')?'capture:':'';
        attributes.push('on-'+prop.arg.content+'="'+modifierText+name+'($event'+locals.map(value=>', '+value).join('')+')"');
        continue;
      }
      if(prop.name==='if'||prop.name==='else-if')attributes.push((prop.name==='if'?'s-if':'s-elif')+'="'+escape(compileBinding(expression,locals))+'"');
      else if(prop.name==='else')attributes.push('s-else');
      else if(prop.name==='show')attributes.push('s-show="'+escape(compileBinding(expression,locals))+'"');
      else if(prop.name==='html')attributes.push('s-html="'+escape(compileBinding(expression,locals))+'"');
      else throw Error('business_source_directive_not_implemented:'+prop.name);
    }
    if(loopText)attributes.push('s-for="'+escape(loopText+(key?' trackBy '+key:''))+'"');
    else if(key)throw Error('business_non_loop_key_unsupported');
    const implicitOptionValue=node.tag==='option'&&!node.props.some(prop=>prop.type===6&&prop.name==='value'||prop.type===7&&prop.name==='bind'&&prop.arg?.content==='value');
    policies.push({tag:node.tag,attributes:bound,loop:!!loop,...(key?{key:key.replace(/\s+/g,'')}:{}),events:eventRecords,inputNames,...(implicitOptionValue?{implicitOptionValue:true}:{})});
    const head='<'+node.tag+(attributes.length?' '+attributes.join(' '):'')+'>';
    return head+(voids.has(node.tag)?'':node.children.map(child=>visit(child,locals)).join('')+'</'+node.tag+'>');
  }
  const compileBinding=expression;
  const output=visit(ast);
  return {template:output,eventHandlers:events,expressionHandlers:expressions,refs:references,elementPolicies:policies,events:entries};
}
function eventSource(entries){return '{'+Object.entries(entries).map(([name,entry])=>JSON.stringify(name)+':{locals:'+JSON.stringify(entry.locals)+',once:'+!!entry.once+',modifiers:'+JSON.stringify(entry.modifiers)+',invoke:'+entry.invoke+',resolve:'+(entry.resolve||'null')+'}').join(',')+'}';}
module.exports={compileTemplate,eventHandler,eventSource};
