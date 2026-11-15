// Offline counterexamples only; does not install a dynamic setter or patch startup.
// stdin: {vue, code, runtime}, where runtime is a local Vue2.7.16 module path.
const fs=require('fs'),{parse}=require('@vue/compiler-sfc');
const x=JSON.parse(fs.readFileSync(0,'utf8')),Vue=require(x.runtime),m={exports:{}},n={exports:{}};
Function('module',parse(x.vue).descriptor.script.content)(m);
Function('require','module',/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(x.code)[1])(require,n);
const source=new Vue(m.exports),naive=new n.exports();
const oldSourceStart=source.draft.start,oldSanStart=naive.data.get('draft').start;
source.setValue('draft.start','literal');source.setValue('lateField',7);
naive.data.set('draft.start','literal');naive.data.set('lateField',7);
const setter={source:{oldStart:oldSourceStart,literalInstanceKey:source['draft.start'],nestedStart:source.draft.start,
 lateInstanceField:source.lateField,lateDeclared:Object.prototype.hasOwnProperty.call(source.$data,'lateField')},
 naiveSan:{oldStart:oldSanStart,literalInstanceKeyPresent:Object.prototype.hasOwnProperty.call(naive,'draft.start'),
 nestedStart:naive.data.get('draft').start,lateStoreField:naive.data.get('lateField')},naiveImplementationInstalled:false};
source.$destroy();naive.dispose();
const rows=()=>[{id:1,dayId:'d1',start:'09:00',end:'10:00',place:'A',cost:1,meta:{tag:1}}];
const a=new Vue({...m.exports,propsData:{initialItems:rows()}}),b=new n.exports({data:{initialItems:rows()}});
const inspect=(state,props)=>({newArray:state!==props,newRecord:state[0]!==props[0],sameNested:state[0].meta===props[0].meta});
const startup={source:inspect(a.items,a.initialItems),target:inspect(b.data.get('items'),b.data.get('initialItems')),
 scope:'initialization counterexample only; not repaired in swap step'};
a.$destroy();b.dispose();
process.stdout.write(JSON.stringify({setter,startup}),()=>process.exit(0));
