'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const {createHash} = require('node:crypto');
const project = path.resolve(__dirname, '../..');
const requireBrowser = createRequire(path.join(project, 'browser/package.json'));
const puppeteer = requireBrowser('puppeteer-core');

async function run(executable, version = 'v5') {
  assert.equal(version, 'v5');
  const runtimeFile = path.join(project, `research/public_instance_${version}/runtime.cjs`);
  const browser = await puppeteer.launch({executablePath: executable, headless: true,
    args: ['--disable-background-networking', '--disable-extensions', '--disable-sync']});
  const errors = [], observations = [];
  const previous = fs.readFileSync(path.join(project, 'research/public_instance_v1/runtime.cjs'), 'utf8');
  const implementation = fs.readFileSync(runtimeFile, 'utf8');
  const ownerImplementation = fs.readFileSync(path.join(__dirname, 'owner.cjs'), 'utf8');
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
            const old=(()=>{const module={exports:{}};${previous}\nreturn module.exports;})();
            const require=name=>{if(name!=='../public_instance_v1/runtime.cjs')throw Error('Unexpected dependency');return old;};
            const module={exports:{}};${implementation}\nwindow.publicPrototype=module.exports;
            window.ownerPrototype=(()=>{const module={exports:{}};${ownerImplementation}\nreturn module.exports;})();})();`});
        }
        const results = await page.evaluate(async kind => {
          function mount() {
            const seed = {count: 0};
            if (kind === 'source') {
              const app = Vue.createApp({data() {return seed;}, render() {return Vue.h('output', String(this.count));}});
              const vm = app.mount('#app'); return {vm, dispose: () => app.unmount()};
            }
            const Component = san.defineComponent({template: '<output>{{count}}</output>', initData() {return seed;}});
            const native = new Component();
            const handle = publicPrototype.createPublicInstance(native, {sourceData: seed, stateKeys: ['count'],
              reactivity: VueReactivity, parseNativeExpr: san.parseExpr, evaluateNativeExpr: san.evalExpr,
              nextRender: callback => san.nextTick(callback)});
            ownerPrototype.connectRootOwner(native, handle);
            native.attach(document.getElementById('app'));
            return {vm: handle.instance, dispose: () => handle.dispose()};
          }
          const dom = () => document.querySelector('output')?.textContent ?? null;
          const cases = [];
          async function scenario(name, operation) {
            const fixture = mount();
            const dispose = fixture.dispose; let closed = false;
            fixture.dispose = () => {if (!closed) {closed = true; dispose();}};
            try {cases.push({name, value: await operation(fixture)});}
            finally {
              fixture.dispose();
              // Explicitly separate fixtures; this wait is NOT used for verdicts.
              if (kind === 'target') await new Promise(resolve => san.nextTick(resolve));
              else await Vue.nextTick();
            }
          }
          await scenario('no-watcher-nextTick-observes-render', async ({vm}) => {
            vm.count = 1; await vm.$nextTick(); return {state: vm.count, dom: dom()};
          });
          await scenario('callback-receiver-and-result-after-render', async ({vm}) => {
            vm.count = 1;
            const value = await vm.$nextTick(function () {return {sameThis: this === vm, dom: dom(), result: 42};});
            return value;
          });
          await scenario('nextTick-promises-share-active-and-idle-flush', async ({vm}) => {
            const idleSame = vm.$nextTick() === vm.$nextTick();
            vm.count = 1;
            const first = vm.$nextTick(), second = vm.$nextTick();
            const activeSame = first === second;
            await first;
            return {idleSame, activeSame, dom: dom()};
          });
          await scenario('pre-only-watcher-before-render-nextTick-after-render', async ({vm}) => {
            const log = [];
            vm.$watch('count', value => log.push(['pre', value, dom()]));
            vm.count = 1; await vm.$nextTick(); log.push(['tick', vm.count, dom()]); return log;
          });
          await scenario('post-watcher-sidewrite-is-drained-before-nextTick', async ({vm}) => {
            const log = [];
            vm.$watch('count', value => log.push(['pre', value, dom()]));
            vm.$watch('count', value => {log.push(['post', value, dom()]); if (value === 1) vm.count = 2;}, {flush: 'post'});
            vm.count = 1; await vm.$nextTick(); log.push(['tick', vm.count, dom()]); return log;
          });
          await scenario('idle-nextTick-does-not-invent-a-render-turn', async ({vm}) => {
            const log = [];
            const promise = vm.$nextTick(() => log.push('tick'));
            Promise.resolve().then(() => log.push('microtask'));
            await promise; return log;
          });
          await scenario('unmount-cancels-watches-but-not-existing-tick-callback', async ({vm, dispose}) => {
            const log = [];
            vm.$watch('count', () => log.push('watch'));
            vm.count = 1;
            const tick = vm.$nextTick(function () {log.push(['tick', dom(), this === vm]);});
            dispose(); await tick; return log;
          });
          await scenario('render-already-settled-does-not-delay-idle-nextTick', async ({vm}) => {
            vm.count = 1;
            if (kind === 'target') await new Promise(resolve => san.nextTick(resolve)); else await Vue.nextTick();
            // Allow bridge's existing completion marker to settle too.
            await Promise.resolve(); await Promise.resolve();
            const log = [];
            const promise = vm.$nextTick(() => log.push(['tick', dom()]));
            Promise.resolve().then(() => log.push('microtask'));
            await promise; return log;
          });
          return {cases, runtime: {vue: typeof window.Vue !== 'undefined', kernel: typeof window.VueReactivity !== 'undefined'}};
        }, kind);
        observations.push({kind, ...results});
      } finally {await context.close();}
    }
    const cases = observations[0].cases.map((source, i) => {
      const target = observations[1].cases[i];
      assert.equal(source.name, target.name);
      let equal = true;
      try {assert.deepEqual(target.value, source.value);} catch {equal = false;}
      return {name: source.name, source: source.value, target: target.value, equal};
    });
    const fingerprints = Object.fromEntries([__filename, runtimeFile, path.join(__dirname, 'owner.cjs'),
      path.join(project, 'research/public_instance_v1/runtime.cjs'),
      path.join(project, 'frontend/node_modules/vue/dist/vue.global.js'),
      path.join(project, 'frontend/node_modules/@vue/reactivity/dist/reactivity.global.js'),
      path.join(project, 'engine/node_modules/san/dist/san.dev.js')]
      .map(file => [path.relative(project, file).replaceAll('\\', '/'), createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
    return {status: cases.every(item => item.equal) ? 'finite_render_schedule_cases_match' : 'render_schedule_difference_observed',
      runtime_version: version, cases, observations, errors, fingerprints, page_count: 2,
      browser_version: await browser.version(), matched_cases: cases.filter(item => item.equal).length,
      production_admission_eligible: false, arbitrary_public_key_contract_complete: false, model_calls: 0, live_database_writes: 0};
  } finally {await browser.close();}
}
if (require.main === module) {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  run(input.executable, input.version || 'v5').then(result => {
    if (input.output) {
      const output = path.resolve(input.output); assert.ok(output.startsWith(path.join(project, 'var') + path.sep));
      fs.mkdirSync(path.dirname(output), {recursive: true}); fs.writeFileSync(output, JSON.stringify(result, null, 2), {flag: 'wx'});
    }
    console.log(JSON.stringify(result));
  }).catch(error => {console.error(error.stack); process.exitCode = 1;});
}
module.exports = {run};
