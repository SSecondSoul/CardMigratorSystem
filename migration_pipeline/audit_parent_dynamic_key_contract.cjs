/* Read-only source evidence. UI routes are NOT a closed public-method contract. */
'use strict';
const fs=require('fs'),parser=require('@babel/parser'),t=require('@babel/types');
const dom=require('@vue/compiler-dom'),{parse}=require('@vue/compiler-sfc');
const traverse=require('@babel/traverse').default;
const {key}=require('./utils/inline_identifier_recovery.cjs');
const {one,safe,print,sourceParent,registered}=require('./utils/source_render_call_semantics.cjs');
const own=n=>t.isMemberExpression(n)&&!n.computed&&t.isThisExpression(n.object);
const scalar=n=>t.isStringLiteral(n)||t.isNumericLiteral(n)||t.isBooleanLiteral(n)||t.isNullLiteral(n);
const tag=s=>s.replace(/([a-z0-9])([A-Z])/g,'$1-$2').toLowerCase();
function eachElement(node,fn){if(node.type===1)fn(node);for(const child of node.children||[])eachElement(child,fn);}
function run(input){
 const result={classification:'read_only_source_contract_evidence_not_proof_of_public_closure',writers:[],reviews:[],
  public_contract_closed:false,production_eligible:false,code_modified:false};
 const parsed=parse(input.vue);
 if(parsed.errors.length||!parsed.descriptor.script||parsed.descriptor.scriptSetup||!parsed.descriptor.template){
  result.reviews.push('unsupported_source_sfc');return result;
 }
 const content=parsed.descriptor.script.content,ast=parser.parse(content,{sourceType:'unambiguous'}),parent=sourceParent(ast);
 const methods=one(parent,'methods')?.value,data=one(parent,'data'),initial=data?.body?.body?.[0]?.argument;
 if(!safe(methods)||!safe(initial)){result.reviews.push('unsupported_parent_data_or_methods');return result;}
 const scriptStart=parsed.descriptor.script.loc.start.offset;
 const location=(node,extra=0)=>{
  const offset=scriptStart+node.start+extra;
  return {offset,offset_unit:'utf16_code_units',line:input.vue.slice(0,offset).split('\n').length};
 };
 const errors=[],template=dom.parse(parsed.descriptor.template.content,{onError:e=>errors.push(e.message)});
 if(errors.length){result.reviews.push('invalid_parent_template');return result;}
 for(const method of methods.properties){
  if(!t.isObjectMethod(method)||method.params.length!==2||!method.params.every(p=>t.isIdentifier(p)))continue;
  const assignment=method.body.body[0]?.expression,left=assignment?.left;
  if(!t.isAssignmentExpression(assignment,{operator:'='})||!t.isMemberExpression(left)||!left.computed||!own(left.object)
    ||!t.isIdentifier(left.property,{name:method.params[0].name}))continue;
  const name=key(method),field=left.object.property.name,shape=one(initial,field)?.value;
  const row={method:name,field,location:location(method),parameters:method.params.map(p=>p.name),
   entry_guard_before_write:false,source_write:print(assignment),public_domain_proven:false,
   initial_keys:safe(shape)?shape.properties.map(key):[],initial_flat_scalar:safe(shape)&&shape.properties.every(p=>scalar(p.value)),
   ui_routes:[],unresolved_ui_routes:[],internal_calls:[],root_replacements:[],root_uses:[],computed_root_reads:[]};
  traverse(ast,{ObjectMethod(p){
   // Only methods owned by the exported parent's own methods object.
   if(p.node===method||!methods.properties.includes(p.node))return;
   p.traverse({CallExpression(q){const c=q.node;if(own(c.callee)&&c.callee.property.name===name)
      row.internal_calls.push({caller:key(p.node),expression:print(c),location:location(c)});}});
  },MemberExpression(p){
   const n=p.node;if(!own(n)||n.property.name!==field)return;
   const parentMethod=p.findParent(v=>v.isObjectMethod()),owner=parentMethod?.node;
   if(!owner||!methods.properties.includes(owner)&&!one(parent,'computed')?.value?.properties.includes(owner))return;
   const container=p.parentPath;let role='borrowed_root_or_other_use';
   if(container.isAssignmentExpression()&&container.node.left===n){
    role='whole_root_replacement';const rhs=container.node.right;
    row.root_replacements.push({method:key(owner),expression:print(rhs),
      shape_proven:safe(rhs)&&rhs.properties.every(v=>scalar(v.value)),
      spreads:t.isObjectExpression(rhs)?rhs.properties.filter(t.isSpreadElement).map(v=>print(v.argument)):[],
      location:location(container.node)});
   }else if(container.isMemberExpression()&&container.node.object===n)role='property_access';
   else if(container.isSpreadElement())role='spread_read';
   else if(container.isVariableDeclarator()&&container.node.init===n)role='local_root_alias';
   else if(container.isObjectProperty())role='aggregate_root_alias';
   else if(container.isReturnStatement())role='returned_root_alias';
   else if(container.isCallExpression())role='call_argument_root_alias';
   row.root_uses.push({method:key(owner),role,expression:print(container.node),location:location(n)});
   if(one(parent,'computed')?.value?.properties.includes(owner))
    row.computed_root_reads.push({method:key(owner),role,location:location(n)});
  }});
  eachElement(template,node=>{
   const handlers=node.props.filter(p=>p.type===7&&p.name==='on'&&p.exp?.content===name&&p.arg?.isStatic);
   for(const handler of handlers){
    const registration=registered(ast,parent,tag(node.tag),false),value=registration&&one(registration.object,'template')?.value;
    if(!registration||!t.isTemplateLiteral(value)||value.expressions.length){
      row.unresolved_ui_routes.push({tag:node.tag,event:handler.arg.content,reason:'unresolved_inline_component'});continue;
    }
    const childErrors=[],childText=value.quasis[0].value.cooked;
    const childTemplate=dom.parse(childText,{onError:e=>childErrors.push(e.message)});
    if(childErrors.length){row.unresolved_ui_routes.push({tag:node.tag,reason:'invalid_inline_template'});continue;}
    const bindings=node.props.filter(p=>p.type===7&&p.name==='bind'&&p.exp?.content===field&&p.arg?.isStatic).map(p=>p.arg.content);
    eachElement(childTemplate,element=>{
     for(const directive of element.props.filter(p=>p.type===7&&p.name==='on'&&p.exp)){
      let expression;try{expression=parser.parseExpression(directive.exp.content);}catch(_){
       row.unresolved_ui_routes.push({tag:node.tag,reason:'unsupported_child_event_expression'});continue;}
      if(!t.isCallExpression(expression)||!t.isIdentifier(expression.callee,{name:'$emit'}))continue;
      const [event,eventKey,eventValue]=expression.arguments;
      if(!t.isStringLiteral(event)||event.value!==handler.arg.content)continue;
      const kind=t.isMemberExpression(eventValue)&&!eventValue.computed&&t.isMemberExpression(eventValue.object)
       &&!eventValue.object.computed&&t.isIdentifier(eventValue.object.object,{name:'$event'})
       &&t.isIdentifier(eventValue.object.property,{name:'target'})?eventValue.property.name:null;
      const options=[];eachElement(element,option=>{if(option.tag==='option'){
       const attr=option.props.find(p=>p.type===6&&p.name==='value');if(attr?.value)options.push(attr.value.content);
      }});
      row.ui_routes.push({component:registration.name,tag:node.tag,prop_bindings:bindings,event:event.value,
       key:t.isStringLiteral(eventKey)?eventKey.value:null,key_proven_literal:t.isStringLiteral(eventKey),
       value_kind:kind==='checked'?'native_checkbox_boolean':kind==='value'?'native_control_string':'unknown',
       native_option_values:options,expression:directive.exp.content,
       location:location(value,1+directive.exp.loc.start.offset)});
     }
    });
    // Imperative child emits are not silently assumed covered by template routes.
    const childMethods=one(registration.object,'methods')?.value;
    if(childMethods)row.unresolved_ui_routes.push({tag:node.tag,reason:'child_methods_require_separate_emit_and_alias_analysis'});
   }
  });
  row.observed_ui_keys=[...new Set(row.ui_routes.map(v=>v.key).filter(Boolean))].sort();
  row.ui_routes_finite_in_supported_templates=row.ui_routes.length>0&&!row.unresolved_ui_routes.length
   &&row.ui_routes.every(v=>v.key_proven_literal&&v.value_kind!=='unknown');
  row.review_reasons=['public_method_has_no_entry_domain_guard'];
  if(row.root_replacements.some(v=>!v.shape_proven))row.review_reasons.push('whole_root_replacement_shape_unproven');
  if(row.root_uses.some(v=>v.role.includes('alias')))row.review_reasons.push('root_borrowing_requires_consumer_analysis');
  if(row.computed_root_reads.length)row.review_reasons.push('computed_root_identity_notification_requires_runtime_proof');
  result.writers.push(row);
 }
 if(!result.writers.length)result.reviews.push('no_supported_direct_dynamic_writer');
 return result;
}
if(require.main===module){try{process.stdout.write(JSON.stringify(run(JSON.parse(fs.readFileSync(0,'utf8')))));}
 catch(error){process.stderr.write(error.stack);process.exitCode=1;}}
module.exports={run};
