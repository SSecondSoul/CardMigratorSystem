'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const {createHash} = require('node:crypto');
const project = path.resolve(__dirname, '../..');
const puppeteer = createRequire(path.join(project, 'browser/package.json'))('puppeteer-core');

async function run(executable, version = 'v5') {
  assert.ok(['v4', 'v5'].includes(version));
  const runtimeFile = path.join(project, `research/public_instance_${version}/runtime.cjs`);
  const browser = await puppeteer.launch({executablePath: executable, headless: true,
    args: ['--disable-background-networking', '--disable-extensions', '--disable-sync']});
  const observations = [], errors = [];
  const v1 = fs.readFileSync(path.join(project, 'research/public_instance_v1/runtime.cjs'), 'utf8');
  const runtime = fs.readFileSync(runtimeFile, 'utf8');
  const owner = fs.readFileSync(path.join(__dirname, 'owner.cjs'), 'utf8');
  try {
    for (const kind of ['source', 'target']) {
      const context = await browser.createBrowserContext(), page = await context.newPage();
      try {
        page.on('pageerror', error => errors.push({kind, message: error.message}));
        page.on('console', msg => {if (['warning', 'error'].includes(msg.type())) errors.push({kind, message: msg.text()});});
        await page.setRequestInterception(true); page.on('request', request => request.abort());
        await page.setContent('<!doctype html><main id="app"></main>');
        await page.addScriptTag({path: path.join(project, kind === 'source' ?
          'frontend/node_modules/vue/dist/vue.global.js' : 'engine/node_modules/san/dist/san.dev.js')});
        if (kind === 'target') {
          await page.addScriptTag({path: path.join(project, 'frontend/node_modules/@vue/reactivity/dist/reactivity.global.js')});
          await page.addScriptTag({content: `(()=>{
            const previous=(()=>{const module={exports:{}};${v1}\nreturn module.exports;})();
            const require=name=>{if(name!=='../public_instance_v1/runtime.cjs')throw Error('Unexpected dependency');return previous;};
            const prototype=(()=>{const module={exports:{}};${runtime}\nreturn module.exports;})();
            const owner=(()=>{const module={exports:{}};${owner}\nreturn module.exports;})();
            window.publicPrototype=prototype;window.ownerPrototype=owner;})();`});
        }
        const result = await page.evaluate(async ({kind, version}) => {
          const dom = () => document.querySelector('output')?.textContent ?? null;
          function mount(hooks = {}, log = [], errorLog = []) {
            const seed = {count: 0}, methods = {setValue(key, value) {this[key] = value;}};
            let vm, cleanup, nativeDispose, handle, app;
            if (kind === 'source') {
              app = Vue.createApp({data() {return seed;}, methods, ...hooks,
                render() {return Vue.h('output', String(this.count));}});
              app.config.errorHandler = (error, proxy, phase) => errorLog.push({message: error.message, phase, receiver: !!proxy});
              vm = app.mount('#app');
              cleanup = () => app.unmount(); nativeDispose = cleanup;
            } else {
              const Component = san.defineComponent({template: '<output>{{count}}</output>', initData() {return seed;}});
              const native = new Component();
              handle = publicPrototype.createPublicInstance(native, {sourceData: seed, stateKeys: ['count'], methods,
                reactivity: VueReactivity, parseNativeExpr: san.parseExpr, evaluateNativeExpr: san.evalExpr,
                nextRender: callback => san.nextTick(callback),
                onError: (error, proxy, phase) => errorLog.push({message: error.message, phase, receiver: !!proxy})});
              if (version === 'v5') ownerPrototype.connectRootOwner(native, handle, hooks);
              vm = handle.instance; native.attach(document.getElementById('app'));
              cleanup = () => handle.dispose(); nativeDispose = () => native.dispose();
            }
            let closed = false;
            return {vm, handle, dispose() {if (!closed) {closed = true; cleanup();}},
              nativeDispose() {if (!closed) {closed = true; nativeDispose();}},
              async settle() {await vm.$nextTick(); if (kind === 'target') await new Promise(resolve => san.nextTick(resolve)); else await Vue.nextTick();}};
          }
          const cases = [];
          const capture = function (name, log) {
            log.push({name, count: this.count, dom: dom(), elText: this.$el?.textContent ?? null,
              mounted: this.$.isMounted, unmounted: this.$.isUnmounted, scopeActive: this.$.scope.active,
              receiver: this.$.proxy === this});
          };
          {
            const log = [], hooks = {};
            for (const name of ['beforeMount','mounted','beforeUpdate','updated','beforeUnmount','unmounted']) {
              hooks[name] = function () {capture.call(this, name, log);};
            }
            const f = mount(hooks);
            f.vm.count = 1; await f.vm.$nextTick();
            f.vm.count = 2; await f.vm.$nextTick();
            f.nativeDispose(); await f.settle();
            cases.push({name: 'root-hook-order-receiver-dom-and-flags', value: {log,
              final: {mounted: f.vm.$.isMounted, unmounted: f.vm.$.isUnmounted, scopeActive: f.vm.$.scope.active}}});
          }
          {
            const log = [], f = mount();
            f.vm.$watch('count', (value, old, cleanup) => {log.push(['watch', value, old]); cleanup(() => log.push(['cleanup', value]));}, {flush: 'sync'});
            f.vm.count = 1; f.nativeDispose();
            f.vm.count = 2; await f.settle();
            cases.push({name: 'native-disposal-stops-owner-watch-and-cleans-once', value: {log, scopeActive: f.vm.$.scope.active, dom: dom()}});
          }
          {
            const log = [], f = mount({mounted() {
              this.$watch('count', value => log.push(value), {flush: 'sync'});
              this.count = 1;
            }});
            await f.vm.$nextTick(); f.vm.count = 2; await f.vm.$nextTick(); f.nativeDispose();
            f.vm.count = 3; await f.settle();
            cases.push({name: 'watch-created-in-mounted-belongs-to-owner', value: {log, dom: dom(), scopeActive: f.vm.$.scope.active}});
          }
          {
            const log = [], hooks = {beforeUnmount() {capture.call(this, 'beforeUnmount', log); this.count = 2;},
              unmounted() {capture.call(this, 'unmounted', log);}};
            const f = mount(hooks);
            f.vm.$watch('count', value => log.push(['sync', value]), {flush: 'sync'});
            f.vm.$watch('count', value => log.push(['pre', value]));
            f.vm.$watch('count', value => log.push(['post', value]), {flush: 'post'});
            f.vm.count = 1;
            const tick = f.vm.$nextTick(() => log.push(['tick', dom()]));
            f.nativeDispose(); await tick; await f.settle();
            cases.push({name: 'beforeUnmount-sidewrite-then-cancel-queued-work', value: log});
          }
          {
            const log = [], hookErrors = [];
            const f = mount({mounted: [function () {throw new Error('mounted-first');}, function () {log.push('mounted-later');}],
              beforeUnmount: [function () {throw new Error('before-unmount');}, function () {log.push('before-later');}],
              unmounted() {log.push('unmounted');}}, log, hookErrors);
            f.nativeDispose(); await f.settle();
            cases.push({name: 'explicit-error-policy-continues-hook-array-and-cleanup', value: {log, errors: hookErrors, scopeActive: f.vm.$.scope.active}});
          }
          {
            const log = [], f = mount({mounted() {log.push('mounted');}, beforeUnmount() {log.push('before');}, unmounted() {log.push('after');}});
            f.vm.setValue('dispose', null); f.vm.setValue('attach', 42); f.vm.setValue('data', null);
            f.nativeDispose(); await f.settle();
            cases.push({name: 'business-native-name-collisions-do-not-break-owner', value: {log, scopeActive: f.vm.$.scope.active, dom: dom()}});
          }
          return {cases, runtime: {vue: typeof window.Vue !== 'undefined', kernel: typeof window.VueReactivity !== 'undefined'}};
        }, {kind, version});
        observations.push({kind, ...result});
      } finally {await context.close();}
    }
    const cases = observations[0].cases.map((source, index) => {
      const target = observations[1].cases[index]; let equal = true;
      try {assert.deepEqual(target, source);} catch {equal = false;}
      return {name: source.name, source: source.value, target: target.value, equal};
    });
    const fingerprints = Object.fromEntries([__filename, runtimeFile, path.join(__dirname, 'owner.cjs'),
      path.join(project, 'research/public_instance_v1/runtime.cjs'),
      path.join(project, 'frontend/node_modules/vue/dist/vue.global.js'),
      path.join(project, 'frontend/node_modules/@vue/reactivity/dist/reactivity.global.js'),
      path.join(project, 'engine/node_modules/san/dist/san.dev.js')].map(file => [path.relative(project, file).replaceAll('\\', '/'),
      createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
    return {status: cases.every(item => item.equal) ? 'finite_root_owner_cases_match' : 'root_owner_difference_observed',
      runtime_version: version, owner_connection_available: version === 'v5', cases, observations, errors, fingerprints,
      page_count: 2, matched_cases: cases.filter(item => item.equal).length, browser_version: await browser.version(),
      production_admission_eligible: false, arbitrary_public_key_contract_complete: false, model_calls: 0, live_database_writes: 0};
  } finally {await browser.close();}
}
if (require.main === module) {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  run(input.executable, input.version || 'v5').then(report => {
    if (input.output) {
      const output = path.resolve(input.output); assert.ok(output.startsWith(path.join(project, 'var') + path.sep));
      fs.mkdirSync(path.dirname(output), {recursive: true}); fs.writeFileSync(output, JSON.stringify(report, null, 2), {flag: 'wx'});
    }
    console.log(JSON.stringify(report));
  }).catch(error => {console.error(error.stack); process.exitCode = 1;});
}
module.exports = {run};
