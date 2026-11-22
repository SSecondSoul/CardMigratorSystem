"""Calibrate native HTML attribute setters; not installed in production yet."""
from pathlib import Path
import json
import sys
from analyze_coverage import write_once,hashed,RUNS
from replay_composed_v6 import raw_evidence

ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT/'migration_system'
sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.adapters.browser import BrowserEvaluator
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile
from card_migration_system.stages.structure import tree_distance


def main():
    out=RUNS/'native_attribute_calibration_v7_20261119'
    if out.exists():raise ValueError('new_output_required')
    settings=load_settings(project_root=PROJECT,environ={});runtime=profile(settings);rows=[]
    for tag in ('input','select','textarea'):
        choices='<option value="a">A</option><option value="b">B</option>' if tag=='select' else ''
        source_element='<input :value="value"/>' if tag=='input' else f'<{tag} :value="value">{choices}</{tag}>'
        target_element='<input value="{{value}}" VALUE="{{value}}"/>' if tag=='input' else f'<{tag} value="{{{{value}}}}" VALUE="{{{{value}}}}">{choices}</{tag}>'
        source='<template><div>'+source_element+'<button @click="change">next</button><button @click="clear">clear</button></div></template><script>export default {data(){return {value:null}},methods:{change(){this.value="b"},clear(){this.value=null}}}</script>'
        code='<template><div>'+target_element+'<button on-click="change">next</button><button on-click="clear">clear</button></div></template><script>const san=require("san");module.exports=san.defineComponent({initData(){return {value:null}},change(){this.data.set("value","b")},clear(){this.data.set("value",null)}})</script>'
        raw=BrowserEvaluator(settings,runtime).evaluate(source,code,{},[
            {'name':'next','type':'click','selector':'button'},{'name':'clear','type':'click','selector':'button:last-child'}])
        row={'tag':tag,'model_calls':0,'source_errors':raw['vue']['errors'],'target_errors':raw['san']['errors'],
             'raw_dom_distances':[tree_distance(a['dom'],b['dom'])['distance'] for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots'])],
             'live_control_values_equal':[[x['value'] for x in a['styles']]==[x['value'] for x in b['styles']]
                for a,b in zip(raw['vue']['snapshots'],raw['san']['snapshots'])],
             'production_rule_installed':False,'not_a_migration_quality_pass':True}
        write_once(out/tag/'source.vue',source);write_once(out/tag/'target.san',code)
        raw_evidence(out/tag,'probe',raw);write_once(out/tag/'result.json',row);rows.append(row)
    write_once(out/'results.json',rows)
    write_once(out/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in sorted(out.rglob('*')) if p.is_file()))
    print(json.dumps(rows,ensure_ascii=True))


if __name__=='__main__':main()
