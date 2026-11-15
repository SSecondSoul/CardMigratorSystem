"""Isolated candidate evidence, deliberately NOT a production repair acceptance test."""
import json
from pathlib import Path
import subprocess
import unittest

from migration_pipeline.audit_formal_30_v4_parent_watch_boundaries_v1 import (
    SAN, VUE, VUE_RUNTIME, SAN_RUNTIME, OUTPUT as DIAGNOSTIC,
)
from migration_pipeline.utils.source_parent_watch_semantics import source_parent_watch_semantics
from migration_pipeline.utils.repair_scheduler import PARENT_WATCH_REVIEW_CODES, candidate_gate
from test_parent_watch_scope_guard import fixture

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT/'migration_pipeline/probe_parent_dynamic_key_adapter.cjs'


def node(script, payload):
    args = ['node', '-e', script] if isinstance(script, str) else ['node', str(script)]
    proc = subprocess.run(args, input=json.dumps(payload), text=True, encoding='utf-8',
                          capture_output=True, check=True, cwd=ROOT, timeout=40)
    if proc.stderr.strip():
        raise AssertionError(proc.stderr)
    return json.loads(proc.stdout)


def adapt(code, vue, **kwargs):
    return node(ADAPTER, {'code':code, 'vue':vue, 'experimental':True, **kwargs})


def generic_pair():
    code, vue = fixture()
    code = source_parent_watch_semantics(code, vue, repair=True)['code']
    vue = vue.replace('methods:{', 'methods:{assign(key,value){this.settings[key]=value;},')
    code = code.replace("load(){this.data.set", "assign(key,value){const o=this.data.get('settings');const v=value;"
                        "const c={...o,[key]:v};if(!Object.is(o[key],v)){this.data.set('settings',c);}},load(){this.data.set")
    return code, vue


# Uses actual pinned frameworks, not a simulated Data/watch implementation.
# New fixture source is unmodified except its export syntax for VM execution.
EXTENDED = r"""
const fs=require('fs'),vm=require('vm');const input=JSON.parse(fs.readFileSync(0,'utf8'));
const script=s=>/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(s)[1];
async function run(variant){
 const context=vm.createContext({console,Promise,process:{env:{NODE_ENV:'development'}}});
 context.global=context;context.module={exports:{}};context.exports=context.module.exports;
 vm.runInContext(variant==='vue'?input.vueRuntime:input.sanRuntime,context);
 const runtime=context.module.exports;const errors=[];
 if(variant==='vue'){runtime.config.errorHandler=e=>errors.push(e.message);runtime.config.warnHandler=()=>{};}
 context.module={exports:{}};context.exports=context.module.exports;
 context.require=name=>{if(name!=='san')throw Error(name);return runtime;};
 vm.runInContext(script(variant==='vue'?input.vue:input.code).replace('export default','module.exports='),context);
 let Options=context.module.exports,events=[];
 const target=variant==='vue'?Options.methods:Options.prototype,original=target.recount;
 target.recount=function(){events.push('recount');return original.call(this);};
 if(variant==='vue')Options.render=h=>h('main');else Options.prototype.template='<main></main>';
 const create=()=>{const i=variant==='vue'?new runtime(Options):new Options();
  variant==='vue'?i.$mount():i.attached();return i;};
 const instance=create(),second=create();context.instance=instance;
 const read=(i,k)=>variant==='vue'?i[k]:i.data.get(k);
 const setRoot=value=>variant==='vue'?instance.settings=value:instance.data.set('settings',value);
 const originalRoot=read(instance,'settings');
 const drain=async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));};
 const snapshots=[];
 const save=(name)=>{context.root=read(instance,'settings');context.secondRoot=read(second,'settings');
  const shape=vm.runInContext(`o=>({keys:Object.keys(o).sort(),values:Object.keys(o).sort().map(k=>[k,
     o[k]===undefined?'undefined':typeof o[k]==='number'&&Number.isNaN(o[k])?'NaN':
     Object.is(o[k],-0)?'-0':o[k]]),prototypeMarker:Object.getPrototypeOf(o)?.marker||null,
     standardPrototype:Object.getPrototypeOf(o)===Object.prototype})`,context);
  snapshots.push({name,shape:shape(context.root),second:shape(context.secondRoot),
    events:events.slice(),count:read(instance,'count')});};
 await drain();events=[];save('mount');
 const action=async(name,fn)=>{events=[];fn();save(name+'_sync');await drain();save(name+'_tick');};
 // All created values live in the framework realm, including the local prototype.
 const update=(key,expression)=>vm.runInContext('instance.assign('+JSON.stringify(key)+','+expression+')',context);
 await action('changed',()=>update('enabled','true'));
 await action('same',()=>update('enabled','true'));
 await action('new_undefined',()=>update('newFlag','undefined'));
 await action('new_repeated',()=>update('newFlag','1'));
 await action('negative_zero',()=>update('enabled','-0'));
 await action('positive_zero',()=>update('enabled','0'));
 await action('nan',()=>update('enabled','NaN'));
 await action('nan_same',()=>update('enabled','NaN'));
 await action('inherited',()=>update('toString',"'x'"));
 await action('prototype',()=>update('__proto__',"({marker:'local'})"));
 await action('new_root',()=>setRoot(vm.runInContext("({enabled:false,newFlag:'restored'})",context)));
 await action('restored_key',()=>update('newFlag',"'changed'"));
 await action('old_identity',()=>setRoot(originalRoot));
 await action('old_nonreactive',()=>update('newFlag','2'));
 await action('destroy_pending',()=>{update('enabled','false');
    variant==='vue'?instance.$destroy():instance.dispose(true,true);});
 variant==='vue'?second.$destroy():second.dispose(true,true);
 return {snapshots,errors};
}
(async()=>{const vue=await run('vue'),san=await run('san');
 process.stdout.write(JSON.stringify({vue,san,equal:JSON.stringify(vue)===JSON.stringify(san)}));})()
 .catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
"""

UNSUPPORTED = r"""
const fs=require('fs'),vm=require('vm');const input=JSON.parse(fs.readFileSync(0,'utf8'));
const context=vm.createContext({console,Promise,process:{env:{NODE_ENV:'development'}}});context.global=context;
context.module={exports:{}};context.exports=context.module.exports;vm.runInContext(input.sanRuntime,context);
const san=context.module.exports;context.require=()=>san;context.module={exports:{}};context.exports=context.module.exports;
vm.runInContext(/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(input.code)[1],context);
const Parent=context.module.exports;Parent.prototype.template='<main></main>';
context.instance=new Parent();context.instance.attached();
const rows=[];for(const expr of ['[Symbol("x"),1]','[{},1]','["__ob__",1]','["enabled",{}]',
  '["__proto__",Object.defineProperty({},"bad",{get(){throw Error("getter must not run");}})]']){
  const before=JSON.stringify(context.instance.data.get('settings'));let error;
  try{vm.runInContext('instance.assign(...'+expr+')',context);}catch(e){error=e.message;}
  rows.push({error,unchanged:before===JSON.stringify(context.instance.data.get('settings'))});
}
context.instance.dispose(true,true);process.stdout.write(JSON.stringify(rows));
"""


class ParentDynamicKeyAdapterProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code=SAN.read_text(encoding='utf-8');cls.vue=VUE.read_text(encoding='utf-8')
        cls.adapted=adapt(cls.code,cls.vue)
        cls.payload={'code':cls.adapted['code'],'vue':cls.vue,
            'vueRuntime':VUE_RUNTIME.read_bytes().decode('utf-8'),
            'sanRuntime':SAN_RUNTIME.read_bytes().decode('utf-8')}
        cls.oracle=DIAGNOSTIC/'code/migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs'
        cls.result=node(cls.oracle,cls.payload)
        cls.prior=json.loads((DIAGNOSTIC/'audit.json').read_text(encoding='utf-8'))['observations']

    def test_explicit_opt_in_and_no_production_eligibility(self):
        self.assertFalse(self.adapted['production_eligible']);self.assertTrue(self.adapted['changes'])
        no=adapt(self.code,self.vue,experimental=False)
        self.assertEqual(no['code'],self.code);self.assertFalse(no['changes'])

    def test_seven_normal_key_scenarios_all_seventy_phase_pairs_match(self):
        pairs=[p for p in self.result['pairs'] if not p['scenario'].startswith('write_failure')]
        self.assertEqual(len(pairs),70)
        self.assertTrue(all(p['stateEqual'] and p['businessEffectsEqual'] for p in pairs))

    def test_native_oracle_unchanged_source_runs_and_prototype_safety(self):
        self.assertEqual([r for r in self.result['runs'] if r['variant']=='vue_source'],
                         [r for r in self.prior['runs'] if r['variant']=='vue_source'])
        self.assertTrue(all(self.result[k] for k in ['hostPrototypeCleanBefore','hostPrototypeCleanAfter','rejectionListenerCountRestored']))

    def test_two_exception_scenarios_still_fail_and_observations_are_not_filtered(self):
        for name in ['write_failure_captured','write_failure_headless_default']:
            pairs=[p for p in self.result['pairs'] if p['scenario']==name]
            self.assertTrue(any(not(p['stateEqual'] and p['businessEffectsEqual']) for p in pairs))
            self.assertEqual([r for r in self.result['runs'] if r['scenario']==name],
                             [r for r in self.prior['runs'] if r['scenario']==name])

    def test_both_production_boundaries_remain_and_forged_pass_is_rejected(self):
        for code in [self.code,self.adapted['code']]:
            r=source_parent_watch_semantics(code,self.vue)
            self.assertEqual({b['code'] for b in r['blocked_boundaries']},PARENT_WATCH_REVIEW_CODES)
        before={'generated_code':self.code,'vue_source':self.vue,
                'validation_errors':source_parent_watch_semantics(self.code,self.vue)['findings']}
        after={**before,'generated_code':self.adapted['code'],'validation_errors':[],'validation_passed':True}
        gate=candidate_gate(before,after)
        self.assertTrue(gate['should_stop']);self.assertEqual(len(gate['waived_source_parent_watch_boundaries']),2)

    def test_missing_or_corrupt_queue_or_writer_is_not_repaired(self):
        for code in [self.code.replace('queue.sort((a,b)=>a-b);','queue.reverse();'),
                     self.code.replace('updateSettings(key,value){','wrongWriter(key,value){')]:
            self.assertTrue(code!=self.code,'Corruption fixture must change the input')
            r=adapt(code,self.vue);self.assertEqual(r['code'],code);self.assertFalse(r['changes'])

    def test_repeat_probe_refuses_existing_marker_without_rewriting(self):
        r=adapt(self.adapted['code'],self.vue)
        self.assertEqual(r['code'],self.adapted['code']);self.assertFalse(r['changes'])

    def test_generic_source_and_renaming_not_component_name_special_case(self):
        pair=generic_pair()
        for code,vue in [pair,tuple(s.replace('settings','options').replace('assign','change') for s in pair)]:
            r=adapt(code,vue);self.assertEqual(r['changes'],self.adapted['changes'])
            self.assertNotIn('TaskManager',r['code'])

    def test_shadowed_weakmap_is_declined(self):
        code,vue=generic_pair();code=code.replace("const san=",'const WeakMap=class {};const san=')
        r=adapt(code,vue);self.assertEqual(r['code'],code);self.assertIn('shadowed_adapter_global',r['reviews'])

    def test_other_nested_source_mutation_is_not_treated_as_root_observation(self):
        code,vue=generic_pair()
        vue=vue.replace('methods:{','methods:{other(value){this.settings.enabled=value;},')
        code=code.replace("load(){this.data.set","other(value){this.data.set('settings.enabled',value);},load(){this.data.set")
        r=adapt(code,vue);self.assertEqual(r['code'],code)
        self.assertIn('other_nested_source_mutation',r['reviews'])

    def test_actual_framework_extended_root_identity_signed_zero_and_instance_isolation(self):
        code,vue=generic_pair();r=adapt(code,vue)
        result=node(EXTENDED,{**self.payload,'code':r['code'],'vue':vue})
        self.assertTrue(result['equal'],result)
        self.assertEqual(len(result['vue']['snapshots']),31)
        self.assertEqual(result['vue']['errors'],[]);self.assertEqual(result['san']['errors'],[])
        phases={p['name']:p for p in result['san']['snapshots']}
        self.assertEqual(phases['old_nonreactive_tick']['events'],[])
        self.assertEqual(phases['restored_key_tick']['events'],['recount'])
        self.assertEqual(phases['positive_zero_tick']['events'],['recount'])
        self.assertEqual(phases['nan_same_tick']['events'],[])
        self.assertEqual(phases['destroy_pending_tick']['events'],[])

    def test_unsupported_runtime_keys_and_values_are_explicit_probe_refusals(self):
        code,vue=generic_pair();r=adapt(code,vue)
        result=node(UNSUPPORTED,{**self.payload,'code':r['code']})
        self.assertEqual(len(result),5)
        self.assertTrue(all(row['unchanged'] and row['error']=='Dynamic-key probe: unsupported key or value' for row in result))

    def test_no_production_stage_imports_experimental_adapter(self):
        for directory in ['migration_pipeline/stages','migration_pipeline/utils','local_server']:
            for path in (ROOT/directory).rglob('*'):
                if path.suffix in {'.py','.cjs','.js'}:
                    self.assertNotIn('probe_parent_dynamic_key_adapter',path.read_text(encoding='utf-8'),str(path))


if __name__=='__main__':unittest.main()
