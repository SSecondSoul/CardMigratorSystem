"""Reproducible tiny development demonstrations; not trained models or test-set answers."""
from hashlib import sha256
import json
from pathlib import Path
import sys
PROJECT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(PROJECT/'src'))
from card_migration_system.adapters.ssm import SSMExtractor
from card_migration_system.application.storage import Storage
from card_migration_system.reporting.identity import digest

PAIRS=[
    ('builtin-info','BuiltinInfo',
     '<template><article class="card"><h2>{{title}}</h2><p>Migration example</p></article></template><script>export default {name:"BuiltinInfo",data(){return {title:"Example"}}}</script><style>.card{padding:16px;color:#243934}</style>',
     '<template><article class="card"><h2>{{title}}</h2><p>Migration example</p></article></template><script>const san=require("san");const DataTypes=san.DataTypes;module.exports=san.defineComponent({name:"BuiltinInfo",dataTypes:{},initData(){return {title:"Example"}}});</script><style>.card{padding:16px;color:#243934}</style>'),
    ('builtin-counter','CounterCard',
     '<template><button class="card" @click="increment">{{count}}</button></template><script>export default {name:"CounterCard",data(){return {count:0}},methods:{increment(){this.count++}}}</script><style>.card{color:rgb(20,40,60)}</style>',
     '<template><button class="card" on-click="increment">{{count}}</button></template><script>const san=require("san");const DataTypes=san.DataTypes;module.exports=san.defineComponent({name:"CounterCard",dataTypes:{},initData(){return {count:0}},increment(){this.data.set("count",this.data.get("count")+1)}});</script><style>.card{color:rgb(20,40,60)}</style>')]

def main():
    rows=[]
    for key,group,source,target in PAIRS:
        source_hash=sha256(source.encode()).hexdigest()
        ssm=SSMExtractor(PROJECT.parent).extract(source.encode(),group+'.vue',source_hash)['ssm']
        rows.append({'id':key,'group':group,'split':'train','source_sha256':source_hash,'ssm':ssm,'ssm_sha256':digest(ssm),
            'san':target,'san_sha256':sha256(target.encode()).hexdigest(),'provenance':'synthetic_development_demonstration_not_dataset_test_answer'})
    storage=Storage(PROJECT/'configs')
    fingerprint=storage.put('few-shot-builtin-v1.json',json.dumps({'schema_version':1,'examples':rows},ensure_ascii=True,sort_keys=True,indent=2).encode())
    print(json.dumps({'examples':len(rows),'sha256':fingerprint,'model_calls':0}))

if __name__=='__main__':main()
