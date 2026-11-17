'use strict';
const fs=require('node:fs'),path=require('node:path'),{createRequire}=require('node:module');
const project=path.resolve(__dirname,'..'),request=JSON.parse(fs.readFileSync(0,'utf8'));
const puppeteer=createRequire(path.join(project,'browser/package.json'))('puppeteer-core');
(async()=>{
  const browser=await puppeteer.launch({executablePath:request.executable,headless:true});
  const observations=[];
  try{for(const kind of ['vue','san']){
    const context=await browser.createBrowserContext(),page=await context.newPage();
    await page.setRequestInterception(true);page.on('request',r=>r.abort());
    await page.setContent('<main id="app"></main>');
    await page.addScriptTag({path:path.join(project,kind==='vue'?'frontend/node_modules/vue/dist/vue.global.js':'engine/node_modules/san/dist/san.dev.js')});
    const code=kind==='vue'?request.source:request.code;
    await page.evaluate(({kind,code})=>{
      const template=code.match(/<template>([\s\S]*?)<\/template>/)[1],script=code.match(/<script>([\s\S]*)<\/script>/)[1],module={exports:{}};
      new Function('require','module','exports',script.replace('export default','module.exports='))(()=>san,module,module.exports);
      if(kind==='vue')globalThis.vm=Vue.createApp({...module.exports,template}).mount('#app');
      else{const C=module.exports,native=new C();globalThis.native=native;globalThis.vm=C.business(native).instance;native.attach(document.getElementById('app'));}
    },{kind,code});
    const states=[];
    for(const action of request.actions){
      if(action.type==='click')await page.click(action.selector);else await page.select(action.selector,action.value);
      await new Promise(resolve=>setTimeout(resolve,100));
      states.push(await page.evaluate(()=>({selected:vm.selectedWorkId,cycle:vm.cycle,
        buttons:Array.from(document.querySelectorAll('aside>button'),el=>({text:el.textContent,class:el.className})),
        options:Array.from(document.querySelectorAll('.capacity-summary option'),el=>el.outerHTML)})));
    }
    const publicKeys=await page.evaluate(()=>{
      const payload={value:7},symbol=Symbol('external caller'),literal='literal.dot[bracket]',checks={};
      vm.setValue(literal,payload);checks.literal=vm[literal]===payload;
      vm.setValue(symbol,payload);checks.symbol=vm[symbol]===payload;
      for(const key of ['data','watch','dispose','attach']){vm.setValue(key,payload);checks[key]=vm[key]===payload;}
      let conversions=0;const key={[Symbol.toPrimitive](){conversions++;return 'converted.key'}};
      vm.setValue(key,payload);checks.coercionOnce=conversions===1&&vm['converted.key']===payload;
      const error=Error('coercion rejected');let caught;
      try{vm.setValue({[Symbol.toPrimitive](){throw error}},payload);}catch(value){caught=value;}
      checks.coercionErrorIdentity=caught===error;
      checks.nativeNamespaceIntact=!globalThis.native||typeof native.data.get==='function'&&typeof native.attach==='function';
      return checks;
    });
    observations.push({kind,states,publicKeys});await context.close();
  }}finally{await browser.close();}
  process.stdout.write(JSON.stringify(observations));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
