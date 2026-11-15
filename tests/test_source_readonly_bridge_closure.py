"""Source-native private render copies; legacy loop recognition is not equivalence."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from migration_pipeline.utils.source_render_dependency_semantics import source_render_dependency_semantics
from migration_pipeline.utils.bounded_semantics import inspect_semantics
from migration_pipeline.utils.source_dom_semantics import source_dom_semantics
from migration_pipeline.utils.repair_scheduler import candidate_gate
from migration_pipeline.utils.repair_prompt import RepairPromptInput, build_repair_prompt
from migration_pipeline.stages.repair import RepairStage, RepairStageInput
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput
from migration_pipeline.repair_client import RepairResult

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/formal_30_v4_render_bridge_v1_input_20261114'
FILTER='function filter(items,predicate){const result=[];for(let i=0;i<items.length;i++){if(predicate(items[i],i,items)){result.push(items[i]);}}return result;}'
INDEX='function indexOf(arr,value){for(let i=0;i<arr.length;i++){if(arr[i]===value){return i;}}return -1;}'


def fixture():
    data="{items:[{kind:'a'}],ids:[1]}"
    source="count(kind){return this.items.filter(item=>item.kind===kind).length;},has(id){return this.selectedIds.indexOf(id)>=0;},hit(){}"
    target="count(kind){const items=this.data.get('items');return countValue(items,kind);},has(id){const ids=this.data.get('selectedIds');return hasValue(ids,id);},hit(){}"
    vue='<template><section><b>{{count(\'a\')}}</b><p :class="has(1) ? \'active\' : \'\'"><small v-if="has(1)">yes</small></p></section></template><script>module.exports={data(){return '+data+';},computed:{selectedIds(){return Array.from(new Set(this.ids));}},methods:{'+source+'}};</script>'
    code='<template><section><b>{{count(\'a\')}}</b><p class="{{has(1) ? \'active\' : \'\'}}"><small s-if="has(1)">yes</small></p></section></template><script>const san=require("san");'+FILTER+INDEX+'function countValue(items,kind){return filter(items,item=>item.kind===kind).length;}function hasValue(ids,id){return indexOf(ids,id)>=0;}module.exports=san.defineComponent({initData(){return '+data+';},computed:{selectedIds(){return Array.from(new Set(this.data.get(\'ids\')));}},'+target+'});</script><style>.active{color:red}</style>'
    return code,vue


def native_trip(code,vue):
    script=r'''
const fs=require('fs'),san=require('san'),{parse}=require('@vue/compiler-sfc');
const x=JSON.parse(fs.readFileSync(0,'utf8')),Vue=require(x.runtime),a={exports:{}},b={exports:{}};
Function('module',parse(x.vue).descriptor.script.content)(a);
Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(x.code)[1])(require,b);
b.exports.prototype.template=/<template\b[^>]*>([\s\S]*?)<\/template>/.exec(x.code)[1];
const source=new Vue(a.exports),target=new b.exports(),observations=[];
const privateCount=Object.keys(b.exports.prototype).find(k=>k.startsWith('__sourceDependency_dayCount'));
const privateHas=Object.keys(b.exports.prototype).find(k=>k.startsWith('__sourceDependency_isConflict'));
const expressions=[];function scan(n){if(n.textExpr)expressions.push(n.textExpr);
 for(const p of n.props||[])if(p.name==='class')expressions.push(p.expr);
 if(n.directives?.if)expressions.push(n.directives.if.value);
 for(const c of n.children||[])scan(c);}
scan(target.aNode);
const matching=expressions.filter(e=>JSON.stringify(e).includes('__sourceDependency_'));
const row=(day,id)=>({day:{id:day},item:{id}});
const evaluate=(day,id)=>matching.map(e=>san.evalExpr(e,new san.Data(row(day,id),target.data),target));
async function observe(label){await new Promise(resolve=>san.nextTick(resolve));
 const days=['d1','d2'],ids=[1,2,3,99];
 const expected={counts:days.map(d=>source.dayCount(d)),conflicts:ids.map(id=>source.isConflict(id))};
 const actual={counts:days.map(d=>target[privateCount](d,target.data.get('items'))),
 conflicts:ids.map(id=>target[privateHas](id,target.data.get('conflictIds')))};
 observations.push({label,source:expected,target:actual,expressions:evaluate('d1',1)});
}
(async()=>{await observe('initial');
 source.activeDayId='d2';target.data.set('activeDayId','d2');await observe('switch-day');
 const items=[{id:1,dayId:'d1',start:'08:00',end:'09:00',cost:1,place:'A'},
 {id:2,dayId:'d1',start:'10:00',end:'11:00',cost:2,place:'B'},
 {id:3,dayId:'d2',start:'12:00',end:'13:00',cost:3,place:'C'}];
 source.items=JSON.parse(JSON.stringify(items));target.data.set('items',JSON.parse(JSON.stringify(items)));
 source.activeDayId='d1';target.data.set('activeDayId','d1');await observe('no-conflict');
 items[1].start='08:30';source.items=JSON.parse(JSON.stringify(items));target.data.set('items',JSON.parse(JSON.stringify(items)));await observe('new-conflict');
 source.items=[];target.data.set('items',[]);await observe('empty');
 // San's Node MessageChannel keeps ports alive after nextTick; explicitly end
 // the test process only after flushing all five observations and disposing.
 source.$destroy();target.dispose();process.stdout.write(JSON.stringify(observations),()=>process.exit(0));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
'''
    p=subprocess.run(['node','-e',script],cwd=ROOT,text=True,encoding='utf-8',capture_output=True,timeout=30,
        input=json.dumps({'code':code,'vue':vue,'runtime':str(ROOT/'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/vendor/vue-2.7.16.js')}))
    if p.returncode:raise AssertionError(p.stderr)
    return json.loads(p.stdout)


class SourceReadonlyBridgeClosureTests(unittest.TestCase):
    def apply(self,p,repair=True):
        r=source_render_dependency_semantics(*p,repair=repair);self.assertNotIn('error',r,r);return r

    def state(self,p):return {'generated_code':p[0],'vue_source':p[1],'ssm':{},'validation_errors':self.apply(p,False)['findings']+inspect_semantics(*p)['findings']}

    def test_source_native_private_copies_cover_text_conditional_class_and_if(self):
        p=fixture();r=self.apply(p);self.assertEqual(len(r['proofs']),3)
        self.assertEqual({b for q in r['proofs'] for b in q['corrected_legacy_array_bridges']},{'filter','indexOf'})
        self.assertIn('__sourceDependency_has(1,selectedIds)',r['code'])
        self.assertIn('__sourceField_items.filter(',r['code']);self.assertIn('__sourceField_selectedIds.indexOf(',r['code'])
        again=self.apply((r['code'],p[1]));self.assertEqual(again['findings'],[]);self.assertEqual(again['code'],r['code'])
        self.assertTrue(all(p['explicit'] for p in again['proofs']))

    def test_existing_script_and_style_remain_exact_including_public_legacy_methods(self):
        p=fixture();r=self.apply(p)
        self.assertEqual(p[0].split('initData(){')[1],r['code'].split('initData(){')[1])
        self.assertEqual(p[0].split('<script>')[1].split('module.exports')[0],r['code'].split('<script>')[1].split('module.exports')[0])

    def test_external_helpers_rename_generically_without_name_allowlist(self):
        p=fixture()
        for old,new in [('filter','selectRecords'),('indexOf','lookup'),('countValue','measure'),('hasValue','containsValue'),('count','total')]:
            p=tuple(x.replace(old,new) if i==0 or old=='count' else x for i,x in enumerate(p))
        r=self.apply(p);self.assertEqual(len(r['proofs']),3)

    def test_changed_primitive_loop_or_unknown_effect_is_not_overwritten(self):
        c,v=fixture()
        for original,replacement in [('result.push(items[i]);','sideEffect();result.push(items[i]);'),
                ('arr[i]===value','arr[i]==value'),('return filter(items,item=>item.kind===kind).length','return external(items,kind)'),
                ('return indexOf(ids,id)>=0','return this.unknown(ids,id)')]:
            code=c.replace(original,replacement)
            r=self.apply((code,v));self.assertNotEqual(code,c);self.assertTrue(r['findings'])
            self.assertNotEqual(len(r['proofs']),3)

    def test_reassigned_escaped_or_shadowed_bridge_is_not_inlined(self):
        c,v=fixture()
        for prefix in ['filter=external;','sink(filter);','const Array=other;','const Set=other;','Array.prototype.filter=external;']:
            code=c.replace('module.exports=',prefix+'module.exports=');r=self.apply((code,v));self.assertNotEqual(len(r['proofs']),3)
        code=c.replace('return countValue(items,kind);','const countValue=other;return countValue(items,kind);')
        self.assertNotEqual(len(self.apply((code,v))['proofs']),3)

    def test_source_mutation_recursion_and_unknown_calls_remain_unproven(self):
        c,v=fixture()
        for old,new in [('return this.items.filter','this.items.push({});return this.items.filter'),
                ('return this.items.filter','return this.unknown(this.items).filter'),
                ('return this.items.filter','return this.count(kind).filter')]:
            self.assertNotEqual(len(self.apply((c,v.replace(old,new)))['proofs']),3)

    def test_computed_missing_collision_or_reserved_root_is_not_invented(self):
        c,v=fixture()
        for code,vue in [(c.replace('selectedIds(){','different(){'),v),
                (c.replace('ids:[1]','ids:[1],selectedIds:[]'),v),
                (c.replace('selectedIds','_selectedIds'),v.replace('selectedIds','_selectedIds'))]:
            r=self.apply((code,vue));self.assertNotEqual(len(r['proofs']),3)

    def test_loop_dependency_shadow_and_changed_adjacent_class_context_refused(self):
        c,v=fixture()
        pairs=[(c.replace('<p class=', '<p s-for="selectedIds in items" class='),v.replace('<p :class=','<p v-for="selectedIds in items" :class=')),
               (c.replace('<b>','<strong>'),v),(c.replace("'active'", "'wrong'"),v)]
        for p in pairs:self.assertNotEqual(len(self.apply(p)['proofs']),3)

    def test_private_graph_tamper_and_forged_pass_rejected_independently(self):
        p=fixture();fixed=self.apply(p)['code'];before=self.state(p);after=self.state((fixed,p[1]))
        self.assertFalse(candidate_gate(before,after)['should_stop'])
        for code in [p[0],fixed.replace('__sourceDependency_has(1,selectedIds)','__sourceDependency_has(1,ids)'),
                     fixed.replace('.indexOf(id)>=0','.indexOf(id)>0')]:
            self.assertNotEqual(code,fixed)
            forged={**self.state((code,p[1])),'validation_errors':[],'validation_passed':True}
            gate=candidate_gate(after,forged);self.assertTrue(gate['should_stop'])
            self.assertTrue(gate['waived_source_dependency_findings'] or gate['lost_source_dependency_proofs'])

    def test_proven_if_scope_keeps_dom_event_checks_not_waived(self):
        c,v=fixture()
        c=c.replace('>yes</small>', '><button on-click="hit">go</button></small>')
        v=v.replace('>yes</small>', '><button @click.stop="hit">go</button></small>')
        before=source_dom_semantics(c,v);fixed=self.apply((c,v))['code'];after=source_dom_semantics(fixed,v)
        self.assertEqual(before['mapped_nodes'],after['mapped_nodes'])
        self.assertEqual(before['findings'],after['findings']);self.assertTrue(after['findings'])
        wrong=fixed.replace('__sourceDependency_has(1,selectedIds)','__sourceDependency_has(1,ids)')
        self.assertNotEqual(source_dom_semantics(wrong,v)['mapped_nodes'],after['mapped_nodes'])

    def test_private_helper_name_avoids_template_loop_alias(self):
        c,v=fixture()
        c=c.replace('<p class=', '<p s-for="__sourceDependency_has in items" class=')
        v=v.replace('<p :class=', '<p v-for="__sourceDependency_has in items" :class=')
        r=self.apply((c,v));self.assertEqual(len(r['proofs']),3)
        self.assertIn('__sourceDependency_has_(1,selectedIds)',r['code'])
        self.assertEqual(self.apply((r['code'],v),False)['findings'],[])

    def test_existing_explicit_public_bridge_body_and_early_return_are_proven(self):
        source=ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'
        v=(source/'protocol/frozen/data/datasets/components/02_medium/SeatBookingMap/vue/SeatBookingMap.vue').read_text(encoding='utf-8')
        c=(source/'pipeline/medium/SeatBookingMap_repaired_repaired.san').read_text(encoding='utf-8')
        r=self.apply((c,v));self.assertEqual(r['code'],c);self.assertFalse(r['findings'])
        self.assertTrue(r['proofs'][0]['explicit']);self.assertTrue(r['proofs'][0]['preexisting_public_call'])
        changed=c.replace("if (seat.reserved) return 'reserved';", "if (seat.reserved) return 'wrong';")
        self.assertTrue(self.apply((changed,v),False)['findings'])

    def test_native_sparse_array_private_operation_uses_source_not_legacy_loop(self):
        c,v=fixture();fixed=self.apply((c,v))['code']
        js=r'''const fs=require('fs'),m={exports:{}};const x=JSON.parse(fs.readFileSync(0,'utf8'));
Function('require','module',/<script>([\s\S]*?)<\/script>/.exec(x)[1])(require,m);const c=new m.exports();
const rows=[];rows[2]={kind:'a'};let beforeError=false;try{c.data.set('items',rows);c.count('a');}catch(_){beforeError=true;}
const dense=c.__sourceDependency_count('a',rows);const ids=new Array(2);
process.stdout.write(JSON.stringify({beforeError,count:dense,sourceCount:rows.filter(x=>x.kind==='a').length,
sourceHas:ids.indexOf(undefined)>=0,privateHas:c.__sourceDependency_has(undefined,ids)}));c.dispose();'''
        proc=subprocess.run(['node','-e',js],input=json.dumps(fixed),cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(proc.returncode,0,proc.stderr);r=json.loads(proc.stdout)
        self.assertTrue(r['beforeError']);self.assertEqual(r['count'],r['sourceCount']);self.assertFalse(r['sourceHas']);self.assertEqual(r['privateHas'],r['sourceHas'])

    def test_prepass_and_stub_response_postprocessing_and_legacy_boundaries(self):
        p=fixture()
        class Client:
            def repair(self,request):return RepairResult(code=p[0],saved_file_path=request.output_file_path,source_file='',ssm={},provider='stub',model='stub',raw_response={})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a.vue';path.write_text(p[1],encoding='utf-8')
            errors=self.state(p)['validation_errors']
            fixed,steps=RepairStage._deterministic_repair_plan(p[0],errors,[],{},str(path),enable_residual_v2=True)
            expected=self.apply((inspect_semantics(*p,repair=True)['code'],p[1]))['code']
            self.assertEqual(fixed,expected);self.assertIn(('source_readonly_render_graph','explicit_source_readonly_render_dependency_graph'),steps)
            legacy,_=RepairStage._deterministic_repair_plan(p[0],errors,[],{},str(path))
            self.assertEqual(legacy,inspect_semantics(*p,repair=True)['code']);self.assertNotIn('__sourceDependency_',legacy)
            r=RepairStage(Client()).run(RepairStageInput(ssm={},generated_code=p[0],vue_file_path=str(path),output_file_path=str(Path(tmp)/'out.san'),metadata={'skip_deterministic_prepass':True,'semantic_rule_set':'residual_v2'}))
            self.assertEqual(r.repaired_code.rstrip(),fixed.rstrip())

    def test_prompt_states_private_copy_and_computed_and_loop_boundaries(self):
        text=build_repair_prompt(RepairPromptInput(ssm={},current_code='',validation_errors=[{'code':'source_render_dependency_not_landed'}]))
        for term in ['conditional class and if','computed value','sparse arrays','old public method']:self.assertIn(term,text)

    def test_frozen_trip_closes_three_bindings_not_move_or_dynamic_setter(self):
        b=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'));code=(ROOT/b['candidate_before']['path']).read_text(encoding='utf-8');vue=ROOT/b['source']['path']
        state=json.loads((ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821/repair_reports/complex/TripItineraryPlanner_repair_history.json').read_text(encoding='utf-8'))['state']
        def assess(c):return {'generated_code':c,'vue_file_path':str(vue),'ssm':state['ssm'],**ValidateStage().run(ValidateStageInput(generated_code=c,ssm=state['ssm'],vue_file_path=str(vue))).to_state_update()}
        before=assess(code);r=self.apply((code,vue.read_text(encoding='utf-8')));after=assess(r['code'])
        self.assertEqual(len(before['validation_errors']),14);self.assertEqual(len(after['validation_errors']),8)
        self.assertEqual({e['code'] for e in after['validation_errors']},{'nested_state_mutation','source_method_interface_not_landed','source_shared_record_projection_not_landed','source_parent_initialization_not_landed','source_computed_collection_not_landed','source_filter_method_not_landed'})
        self.assertFalse(after['validation_passed']);self.assertFalse(candidate_gate(before,after)['should_stop'])

    def test_actual_frozen_frameworks_counts_conflicts_and_compiled_expressions(self):
        b=json.loads((BASE/'baseline.json').read_text(encoding='utf-8'));c=(ROOT/b['candidate_before']['path']).read_text(encoding='utf-8');v=(ROOT/b['source']['path']).read_text(encoding='utf-8')
        values=native_trip(self.apply((c,v))['code'],v);self.assertEqual(len(values),5)
        for row in values:self.assertEqual(row['source'],row['target'],row['label'])
        self.assertEqual([r['source']['counts'] for r in values],[[2,1],[2,1],[2,1],[2,1],[0,0]])
        self.assertEqual([r['source']['conflicts'][:2] for r in values],[[True,True],[False,False],[False,False],[True,True],[False,False]])
        self.assertTrue(all(len(r['expressions'])==3 for r in values))
        for row in values:
            active=row['source']['conflicts'][0]
            self.assertEqual(row['expressions'],[str(row['source']['counts'][0])+' 项','conflict' if active else '',active])


if __name__=='__main__':unittest.main()
