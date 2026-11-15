"""Static source/interface review only; never requests browser permissions."""

import argparse
import json
import subprocess
from pathlib import Path

from migration_pipeline.analyze_formal_30_v4_full_regression import digest, verify_snapshot


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/experiments/snapshots/formal_30_v4_semantic_closure_v4_results_20261103_204227'
OFFLINE = ROOT / 'data/experiments/analysis/formal_30_v4_startup_phase_closure_v1_20261103'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_notification_method_audit_v1_20261103'

AUDIT_JS = r'''
const fs=require('fs'),parser=require('@babel/parser');
const {parse:parseSFC}=require('@vue/compiler-sfc');
const {parse:parseTemplate}=require('@vue/compiler-dom');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const key=p=>!p.computed&&(p.key?.name||p.key?.value);
const one=(obj,name)=>{
 const rows=obj?.properties?.filter(p=>key(p)===name)||[];
 if(rows.length>1)throw Error('Ambiguous option: '+name);
 return rows[0];
};
function read(code,source){
 // San's frozen initial template may contain known invalid/duplicate attrs.
 // Isolate its script audit and mark template coverage unknown instead of
 // confusing a template parse failure with a missing method definition.
 const sfc=source?parseSFC(code):null;
 const block=!source&&/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(code);
 if(source&&(sfc.errors.length||!sfc.descriptor.script||sfc.descriptor.scriptSetup))throw Error('Invalid source SFC');
 if(!source&&!block)throw Error('Missing San script');
 const script=source?sfc.descriptor.script.content:block[1],ast=parser.parse(script,{sourceType:'unambiguous'});
 const roots=ast.program.body.flatMap(n=>{
  if(source&&n.type==='ExportDefaultDeclaration')return [n.declaration];
  const e=n.type==='ExpressionStatement'&&n.expression;
  if(e?.type==='AssignmentExpression'&&e.operator==='='&&e.left.type==='MemberExpression'
    &&!e.left.computed&&e.left.object.name==='module'&&e.left.property.name==='exports'){
   if(source)return [e.right];
   if(e.right.type==='CallExpression'&&e.right.callee.type==='MemberExpression'&&!e.right.callee.computed
     &&e.right.callee.object.name==='san'&&e.right.callee.property.name==='defineComponent')return e.right.arguments;
  }return [];
 });
 if(roots.length!==1||roots[0].type!=='ObjectExpression')throw Error('Ambiguous parent');
 const template=source?sfc.descriptor.template?.content||'':(/<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(code)?.[1]||'');
 return {parent:roots[0],script,template,source};
}
function walk(node,visit,parent=null){
 if(!node||typeof node!=='object')return;
 if(Array.isArray(node)){node.forEach(n=>walk(n,visit,parent));return;}
 visit(node,parent);
 for(const [k,v]of Object.entries(node))if(!['loc','extra','comments','tokens'].includes(k))walk(v,visit,node);
}
function inspect(ctx,name){
 const methods=ctx.source?one(ctx.parent,'methods')?.value:ctx.parent;
 const definition=one(methods,name);
 const legacyDefinition=!ctx.source&&one(one(ctx.parent,'methods')?.value,name);
 const methodNames=(methods?.properties||[]).filter(p=>p.type==='ObjectMethod').map(key).filter(Boolean);
 const references=[],uncertain=[],notificationSites=[];
 // Inspect only this exported parent's options, not separately defined inline children.
 walk(ctx.parent,(n,p)=>{
  if(['MemberExpression','OptionalMemberExpression'].includes(n.type)&&n.object.type==='ThisExpression'){
   if(n.computed&&n.property.type!=='StringLiteral')uncertain.push({kind:'dynamic_this_member',text:ctx.script.slice(n.start,n.end)});
   if((!n.computed&&n.property.name===name)||(n.computed&&n.property.value===name))
    references.push({kind:p&&['CallExpression','OptionalCallExpression'].includes(p.type)&&p.callee===n?'call':'reference',
     text:ctx.script.slice(n.start,n.end),line_in_script:n.loc.start.line});
  }
  if(n.type==='ThisExpression'&&!(p&&['MemberExpression','OptionalMemberExpression'].includes(p.type)&&p.object===n))
   uncertain.push({kind:'this_escape_or_alias',line_in_script:n.loc.start.line});
  if(n.type==='CallExpression'&&n.callee.type==='MemberExpression'&&!n.callee.computed
    &&n.callee.object.name==='Notification'&&n.callee.property.name==='requestPermission')
   notificationSites.push({kind:'permission_request',text:ctx.script.slice(n.start,n.end),line_in_script:n.loc.start.line});
  if(n.type==='NewExpression'&&n.callee.name==='Notification')
   notificationSites.push({kind:'notification_construction',text:ctx.script.slice(n.start,n.end),line_in_script:n.loc.start.line});
 });
 const templateReferences=[];let template;
 try{template=parseTemplate(ctx.template);}catch(e){
  if(ctx.source)throw e;
  uncertain.push({kind:'unparsed_target_template',reason:e.message});
 }
 const expression=(text,kind)=>{
  let ast;
  try{ast=parser.parseExpression(text);}catch(_){uncertain.push({kind:'unparsed_template_expression',text});return;}
  walk(ast,n=>{
   if(n.type==='Identifier'&&n.name===name)templateReferences.push({kind,text});
   if(n.type==='StringLiteral'&&n.value===name)uncertain.push({kind:'string_method_name_in_template',text});
  });
 };
 const visit=n=>{
  if(n.type===1)for(const p of n.props){
   if(ctx.source&&p.type===7&&p.exp)expression(p.exp.content,'vue_'+p.name);
   if(!ctx.source&&p.type===6&&p.name.startsWith('on-')&&p.value)expression(p.value.content,'san_'+p.name);
  }
  if(n.type===5)expression(n.content.content,'interpolation');
  for(const c of n.children||[])visit(c);
 };
 if(template)visit(template);
 return {method_exists:!!definition,method_is_callable:definition?.type==='ObjectMethod',
  legacy_vue_methods_wrapper_definition_exists:!!legacyDefinition,method_names:methodNames,
  definition:definition?ctx.script.slice(definition.start,definition.end):null,
  parent_script_references:references,template_references:templateReferences,
  uncertain_reference_sites:uncertain,notification_sites:notificationSites};
}
const source=read(input.vue,true),target=read(input.code,false);
const a=inspect(source,input.name),b=inspect(target,input.name);
const missing=a.method_names.filter(n=>!b.method_names.includes(n));
process.stdout.write(JSON.stringify({method:input.name,source:a,target:b,source_method_names_missing_by_name:missing,
 conclusion:a.method_exists&&!b.method_exists?'source_method_interface_removed':'review_other_shape',
 internal_invocation_found:a.parent_script_references.length>0||a.template_references.length>0,
 boundary:'Name/reference audit is not full behavioral equivalence or proof that no external consumer can call the method. '
  +'Method renaming, inherited/mixin methods, dynamic dispatch and parent refs require separate proof. No component is executed.'}));
'''


def inspect_method(vue, code, name='requestNotificationPermission'):
    result = subprocess.run(['node','-e',AUDIT_JS],cwd=ROOT,
        input=json.dumps({'vue':vue,'code':code,'name':name}),capture_output=True,
        text=True,encoding='utf-8',timeout=20)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def audit():
    counts = {'raw':verify_snapshot(SOURCE),'startup_offline':verify_snapshot(OFFLINE)}
    report_path = SOURCE/'repair_reports/complex/MonitoringDashboard_repair_history.json'
    state = json.loads(report_path.read_text(encoding='utf-8'))['state']
    vue_path = SOURCE/'protocol/frozen/data/datasets/components/03_complex/MonitoringDashboard/vue/MonitoringDashboard.vue'
    vue = vue_path.read_text(encoding='utf-8')
    outputs = {}
    cases = [('initial_generation',state['generate_result']['generation_code']),
             ('first_repair',state['repair_history'][0]['repair_result']['repaired_code']),
             ('final_repair',state['generated_code']),
             ('startup_offline_final',(OFFLINE/'final_automatic_pass_offline.san').read_text(encoding='utf-8'))]
    for name,code in cases:
        outputs[name] = inspect_method(vue,code)
    final = outputs['final_repair']
    if (counts!={'raw':342,'startup_offline':24}
            or not (outputs['initial_generation']['target']['method_exists']
                    or outputs['initial_generation']['target']['legacy_vue_methods_wrapper_definition_exists'])
            or not outputs['first_repair']['target']['method_exists']
            or final['target']['method_exists'] or outputs['startup_offline_final']['target']['method_exists']
            or final['internal_invocation_found'] or final['source']['uncertain_reference_sites']):
        raise RuntimeError('Audit conclusion changed; do not reuse narrative')
    methods = state['ssm']['script']['options']['methods']
    source_method = [m for m in methods if m.get('name')=='requestNotificationPermission']
    if len(source_method)!=1:
        raise RuntimeError('SSM method contract missing/ambiguous')
    data = {'classification':'readonly_source_notification_interface_and_callsite_review',
        'source_snapshot':SOURCE.name,'source_verified_files':counts,
        'source_vue_sha256':digest(vue_path),'source_history_sha256':digest(report_path),
        'ssm_method_contract':source_method[0], 'cases':outputs,
        'second_repair_prompt_contains_method': 'requestNotificationPermission' in state['repair_history'][1]['repair_result']['repair_prompt'],
        'method_lost_at':'second_llm_repair','visible_settings_permission_trigger_missing_already_in_source':True,
        'external_interface_equivalence_proven':False,
        'model_requests':0,'browser_or_permission_request_performed':False,
        'production_code_modified':False,'original_score_modified':False,
        'recommendation':'Preserve the source callable interface without inventing new UI/lifecycle permission triggers. '
                         'Do not dismiss the lost API solely because internal call sites are absent. '
                         'A general method-preservation contract and safe restoration require a separately approved implementation step.'}
    verify_snapshot(SOURCE)
    verify_snapshot(OFFLINE)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-report',action='store_true')
    args = parser.parse_args()
    data = audit()
    if args.write_report:
        if OUTPUT.exists():
            raise FileExistsError('Do not overwrite existing review')
        OUTPUT.mkdir(parents=True)
        (OUTPUT/'summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'method_lost_at':data['method_lost_at'],
        'source_internal_references':len(data['cases']['final_repair']['source']['parent_script_references']),
        'source_template_references':len(data['cases']['final_repair']['source']['template_references']),
        'external_interface_equivalence_proven':False,'model_requests':0,'report_written':args.write_report}))


if __name__=='__main__':
    main()
