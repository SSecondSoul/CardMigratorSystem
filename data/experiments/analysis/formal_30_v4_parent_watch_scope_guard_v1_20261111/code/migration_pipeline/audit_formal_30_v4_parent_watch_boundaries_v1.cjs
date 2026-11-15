/* Diagnostic only: run frozen source and frozen normal-flow candidate, never rewrite either. */
'use strict';
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');
const EPOCH=Date.UTC(2026,10,11,12);
const script=text=>/<script\b[^>]*>([\s\S]*?)<\/script>/.exec(text)[1];
const copy=value=>JSON.parse(JSON.stringify(value,(_key,v)=>typeof v==='undefined'?{$type:'undefined'}:
    typeof v==='function'?{$type:'function'}:typeof v==='number'&&!Number.isFinite(v)?{$type:String(v)}:v));
const nextTurn=()=>new Promise(resolve=>setImmediate(resolve));
function evaluate(code,env,requireFunction){
    env.context.__module={exports:{}};env.context.__require=requireFunction||(()=>{throw Error('Unexpected dependency');});
    vm.runInContext('(function(module,exports,require){\n'+code+'\n})(__module,__module.exports,__require)',env.context,{timeout:5000});
    const result=env.context.__module.exports;delete env.context.__module;delete env.context.__require;return result;
}
function sandbox(){
    let phase='construct',events=[],stored=null,nextInterval=0,nextTimeout=1000,failWrites=0;
    const intervals=new Map(),timeouts=new Map(),errors=[],warnings=[];
    const log=value=>events.push(copy({phase,...value}));
    class FixedDate extends Date{constructor(...args){super(...(args.length?args:[EPOCH]));}static now(){return EPOCH;}}
    const context=vm.createContext({Date:FixedDate,Promise,process:{env:{NODE_ENV:'development'}},
        console:{log(){},warn:(...args)=>warnings.push(args.join(' ')),error:(...args)=>warnings.push(args.map(String).join(' '))},
        localStorage:{getItem(key){log({kind:'storage-read',key});return stored;},setItem(key,text){
            const value=JSON.parse(text);log({kind:'storage-write-attempt',key,value});
            if(failWrites>0){failWrites--;log({kind:'storage-write-failure',key});throw new Error('BoundaryStorageWriteFailure');}
            stored=text;log({kind:'storage-write',key,value});}},
        setInterval(fn,delay){const id=++nextInterval;intervals.set(id,{fn,delay});log({kind:'interval-start',id,delay});return id;},
        clearInterval(id){const existed=intervals.delete(id);log({kind:'interval-clear',id,existed});},
        setTimeout(fn,delay){const id=++nextTimeout;timeouts.set(id,{fn,delay});return id;},clearTimeout(id){timeouts.delete(id);}});
    context.global=context;
    return {context,log,errors,warnings,
        initialize(value){stored=JSON.stringify(value);},phase(name){phase=name;events=[];},
        failNextWrite(){failWrites=1;},events:()=>copy(events),stored:()=>stored===null?null:JSON.parse(stored),
        timers:()=>[...intervals.values()].map(x=>x.delay).sort((a,b)=>a-b),
        pending:()=>[...timeouts.values()].filter(x=>x.delay===3000).length,
        error(channel,error,info){errors.push({phase,channel,message:error.message||String(error),info:info||null});}};
}
const traceNames=['updateSettings','updateStatistics','saveToLocalStorage','startAutoSync','updateSyncInterval','showNotification'];
function trace(object,env){for(const name of traceNames){const original=object[name];
    if(typeof original!=='function')throw Error('Missing method '+name);
    object[name]=function(...args){env.log({kind:'call',name,args});return original.apply(this,args);};}}
function scenarios(){
    const update=(key,value)=>({kind:'update',key,value});
    return [
        {name:'declared_same_value',first:update('autoSave',true),second:update('autoSave',true)},
        {name:'declared_changed_value',first:update('syncInterval','30'),second:update('syncInterval',30)},
        {name:'restored_extra_key',restoreExtra:true,first:update('customFlag','first'),second:update('customFlag','second')},
        {name:'new_key',initialInterval:30,first:update('customFlag','first'),second:update('customFlag','second')},
        {name:'new_undefined_key',first:{kind:'update',key:'extraUndefined',undefinedValue:true},
            second:{kind:'update',key:'extraUndefined',undefinedValue:true}},
        {name:'inherited_key',initialInterval:30,first:update('toString','first'),second:update('toString','second')},
        {name:'prototype_key',first:update('__proto__',{boundaryMarker:'first'}),second:update('__proto__',{boundaryMarker:'second'})},
        {name:'write_failure_captured',failure:true,errorPolicy:'capture',first:update('syncInterval',30),second:update('syncInterval',60)},
        {name:'write_failure_headless_default',failure:true,errorPolicy:'headless_default',first:update('syncInterval',30),second:update('syncInterval',60)}
    ];
}
async function runOne(input,variant,scenario,onActive){
    const env=sandbox();onActive(env);
    const task={id:10,title:'saved',description:'',completed:false,tags:[],priority:'medium',dueDate:''};
    const settings={autoSave:true,syncInterval:scenario.initialInterval||0,defaultView:'list',notifications:true};
    if(scenario.restoreExtra)settings.customFlag='restored';
    env.initialize({tasks:[task],settings});
    let instance,runtime,read,destroy;
    if(variant==='vue_source'){
        runtime=evaluate(input.vueRuntime,env);
        if(runtime.version!=='2.7.16'||runtime.config.async!==true)throw Error('Unexpected Vue scheduler');
        runtime.config.warnHandler=message=>env.warnings.push(message);
        if(scenario.errorPolicy!=='headless_default')runtime.config.errorHandler=(error,_component,info)=>env.error('vue.config.errorHandler',error,info);
        const options=evaluate(script(input.vue),env);trace(options.methods,env);
        options.render=h=>h('section');instance=new runtime(options);env.phase('mount_sync');instance.$mount();
        read=field=>instance[field];destroy=()=>instance.$destroy();
    }else{
        runtime=evaluate(input.sanRuntime,env);
        if(runtime.version!=='3.15.6')throw Error('Unexpected San runtime');
        const Parent=evaluate(script(input.code),env,name=>{if(name!=='san')throw Error('Unexpected require '+name);return runtime;});
        Parent.prototype.template=/<template\b[^>]*>([\s\S]*?)<\/template>/.exec(input.code)[1];
        trace(Parent.prototype,env);instance=new Parent();env.phase('mount_sync');instance.attached();
        read=field=>instance.data.get(field);destroy=()=>instance.dispose(true,true);
    }
    env.context.__instance=instance;
    const execute=action=>{
        env.context.__action=JSON.stringify(action);
        const body=variant==='vue_source'?"__instance.tasks[0].title=a.value;":"__instance.data.set('tasks[0].title',a.value);";
        vm.runInContext("(()=>{const a=JSON.parse(__action);if(a.kind==='title'){"+body+
            "}else{__instance.updateSettings(a.key,a.undefinedValue?undefined:a.value);}})()",env.context);
    };
    const phases=[];
    const capture=name=>{
        env.context.__settings=read('settings');
        const shape=vm.runInContext(`(()=>{const o=__settings,p=Object.getPrototypeOf(o);return {
            ownEnumerableKeys:Object.keys(o).sort(),ownUndefined:Object.keys(o).filter(k=>o[k]===undefined).sort(),
            hasOwnProto:Object.prototype.hasOwnProperty.call(o,'__proto__'),
            standardPrototype:p===Object.prototype,inheritedMarker:p&&p.boundaryMarker||null,
            realmObjectPrototypeClean:!Object.prototype.hasOwnProperty.call(Object.prototype,'boundaryMarker')};})()`,env.context);
        phases.push({name,events:env.events(),state:{tasks:copy(read('tasks')),settings:copy(read('settings')),
            settingsShape:copy(shape),statistics:copy(read('statistics')).map(s=>s.value),notification:copy(read('notification')),
            stored:env.stored(),activeIntervalDelays:env.timers(),pendingNotificationTimeouts:env.pending(),
            disposed:variant==='vue_source'?!!instance._isDestroyed:!!instance.lifeCycle.disposed}});
    };
    const drain=async()=>{await nextTurn();await nextTurn();}; // Let native framework Promise queues and rejection delivery finish.
    capture('mount_sync');env.phase('mount_tick');await drain();capture('mount_tick');
    const phase=async(name,action)=>{env.phase(name+'_sync');action();capture(name+'_sync');
        env.phase(name+'_tick');await drain();capture(name+'_tick');};
    await phase('primary',()=>{if(scenario.failure)env.failNextWrite();execute(scenario.first);
        if(scenario.failure)execute({kind:'title',value:'fault-turn'});});
    await phase('repeat',()=>execute(scenario.second));
    await phase('recovery',()=>{execute({kind:'update',key:'syncInterval',value:0});execute({kind:'title',value:'recovered'});});
    await phase('destroy',()=>destroy());
    return {scenario:scenario.name,variant,frameworkVersion:runtime.version,errorPolicy:scenario.errorPolicy||'capture',
        phases,errors:copy(env.errors),warnings:copy(env.warnings),
        boundary:{sourceDummyRender:variant==='vue_source',sanFullAttach:false,browser:false,realStorage:false,
            realApplicationTimers:false,nativePromiseQueues:true,hostImmediateUsedOnlyToObserve:true,
            sourceBusinessCodeChanged:false,sanCodeChanged:false,exceptionBridgeInstalledInSan:false}};
}
async function audit(input){
    const beforeHostClean=!Object.prototype.hasOwnProperty.call(Object.prototype,'boundaryMarker');
    let active;const listener=error=>{if(!active)throw error;active.error('process.unhandledRejection',error);};
    const listenersBefore=process.listenerCount('unhandledRejection');process.on('unhandledRejection',listener);
    const runs=[];
    try{for(const scenario of scenarios())for(const variant of ['vue_source','san_frozen_normal_flow'])
        runs.push(await runOne(input,variant,scenario,env=>{active=env;}));}
    finally{await nextTurn();process.removeListener('unhandledRejection',listener);active=null;}
    const pairs=[];
    for(const scenario of scenarios()){
        const a=runs.find(r=>r.scenario===scenario.name&&r.variant==='vue_source');
        const b=runs.find(r=>r.scenario===scenario.name&&r.variant==='san_frozen_normal_flow');
        for(let i=0;i<a.phases.length;i++){
            const left=a.phases[i],right=b.phases[i];if(left.name!==right.name)throw Error('Phase drift');
            pairs.push({scenario:scenario.name,phase:left.name,stateEqual:JSON.stringify(left.state)===JSON.stringify(right.state),
                businessEffectsEqual:JSON.stringify(left.events)===JSON.stringify(right.events)});
        }
    }
    return {runs,pairs,scenarios:scenarios().map(s=>s.name),nodeVersion:process.version,
        vueRuntimeSha256:crypto.createHash('sha256').update(input.vueRuntime).digest('hex'),
        sanRuntimeSha256:crypto.createHash('sha256').update(input.sanRuntime).digest('hex'),
        hostPrototypeCleanBefore:beforeHostClean,hostPrototypeCleanAfter:!Object.prototype.hasOwnProperty.call(Object.prototype,'boundaryMarker'),
        rejectionListenerCountRestored:process.listenerCount('unhandledRejection')===listenersBefore,
        modelRequests:0,productionRuleChanged:false,
        limitations:['Diagnosis of two explicitly unproven boundaries, not a repair or new 30-sample batch.',
            'Vue capture policy is test configuration, not a claim about the browser default error policy.',
            'Headless default policy intentionally observes Node Vue rethrows; no browser environment emulation.',
            'Host rejection listener observes errors without attaching catches to the tested Promise or modifying either scheduler.',
            'No real DOM attach/browser, real storage or real application timer execution.']};
}
if(require.main===module)audit(JSON.parse(fs.readFileSync(0,'utf8')))
    .then(x=>process.stdout.write(JSON.stringify(x))).catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
module.exports={audit};
