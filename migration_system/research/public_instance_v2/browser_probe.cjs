/* Two disposable native pages. Prototype loader only; never production approval. */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const {createHash} = require('node:crypto');
const project = path.resolve(__dirname, '../..');
const requireBrowser = createRequire(path.join(project, 'browser/package.json'));
const puppeteer = requireBrowser('puppeteer-core');

async function run(executable) {
  const browser = await puppeteer.launch({executablePath: executable, headless: true,
    args: ['--disable-background-networking', '--disable-extensions', '--disable-sync']});
  const errors = [], pages = [], observations = [];
  const prototype = fs.readFileSync(path.join(__dirname, 'runtime.cjs'), 'utf8');
  const v1 = fs.readFileSync(path.join(project, 'research/public_instance_v1/runtime.cjs'), 'utf8');
  try {
    for (const scenario of ['plain', 'ref']) for (const kind of ['source', 'target']) {
      const context = await browser.createBrowserContext(), page = await context.newPage();
      pages.push({kind, scenario, context, page});
      page.on('pageerror', error => errors.push({kind, message: error.message}));
      page.on('console', msg => {if (['warning', 'error'].includes(msg.type())) errors.push({kind, message: msg.text()});});
      await page.setRequestInterception(true);
      page.on('request', request => request.abort());
      await page.setViewport({width: 800, height: 600});
      await page.setContent('<!doctype html><html><body><main id="app"></main></body></html>');
      await page.addScriptTag({path: path.join(project, kind === 'source' ?
        'frontend/node_modules/vue/dist/vue.global.js' : 'engine/node_modules/san/dist/san.dev.js')});
      if (kind === 'target') {
        await page.addScriptTag({path: path.join(project, 'frontend/node_modules/@vue/reactivity/dist/reactivity.global.js')});
        await page.addScriptTag({content: `(() => {
          const previous=(()=>{const module={exports:{}};${v1}\nreturn module.exports;})();
          const require=name=>{if(name!=='../public_instance_v1/runtime.cjs')throw Error('Unexpected dependency');return previous;};
          const module={exports:{}};${prototype}\nwindow.publicPrototype=module.exports;})();`});
      }
      await page.evaluate(({kind, scenario}) => {
        const seed = {count: scenario === 'ref' ? (kind === 'source' ? Vue.ref(0) : VueReactivity.ref(0)) : 0,
          objectValue: {nested: {x: 0}}};
        const methods = {setValue(key, value) {this[key] = value;}, increment() {this.count++;}};
        if (kind === 'source') {
          const app = Vue.createApp({data() {return seed;}, methods,
            render() {return Vue.h('div', [Vue.h('button', {onClick: this.increment}, String(this.count)),
              Vue.h('output', String(this.objectValue.nested.x))]);}});
          window.instance = app.mount('#app');
          const store = instance.$data;
          window.intact = () => instance.$data === store;
          window.cleanup = () => app.unmount();
        } else {
          let handle;
          const Component = san.defineComponent({template: '<div><button on-click="increment">{{count}}</button><output>{{objectValue.nested.x}}</output></div>',
            initData() {return seed;}, increment() {handle.invoke('increment');}});
          const runtime = new Component(), store = runtime.data;
          handle = publicPrototype.createPublicInstance(runtime, {stateKeys: Object.keys(seed), methods,
            sourceData: seed, reactivity: VueReactivity, nextRender: callback => san.nextTick(callback)});
          window.instance = handle.instance;
          window.intact = () => runtime.data === store;
          window.cleanup = () => handle.dispose();
          runtime.attach(document.getElementById('app'));
        }
        window.watchCalls = [];
        instance.$watch('count', value => watchCalls.push(['pre', value, document.querySelector('button').textContent]));
        instance.$watch('count', value => watchCalls.push(['post', value, document.querySelector('button').textContent]), {flush: 'post'});
        window.mutateEscapedRef = () => {seed.count.value = 21;};
      }, {kind, scenario});
    }
    for (const {kind, scenario, page} of pages) {
      const states = [];
      const observe = async () => page.evaluate(() => ({text: document.querySelector('button').textContent,
        count: instance.count, intact: intact(), publicData: instance.data,
        publicWatch: instance.watch, vuePresent: typeof window.Vue !== 'undefined',
        standaloneKernelPresent: typeof window.VueReactivity !== 'undefined'}));
      states.push(await observe());
      await page.evaluate(() => {instance.setValue('data', null); instance.setValue('watch', 42);});
      await page.click('button');
      await page.waitForFunction(() => document.querySelector('button').textContent === '1');
      states.push(await observe());
      await page.evaluate(() => instance.setValue('count', 10));
      await page.waitForFunction(() => document.querySelector('button').textContent === '10');
      await page.click('button');
      await page.waitForFunction(() => document.querySelector('button').textContent === '11');
      states.push(await observe());
      let escapedRef = null;
      if (scenario === 'ref') {
        await page.evaluate(() => mutateEscapedRef());
        await page.waitForFunction(() => document.querySelector('button').textContent === '21');
        escapedRef = await observe();
      }
      await page.evaluate(() => instance.$nextTick());
      const watches = await page.evaluate(() => watchCalls);
      const nested = await page.evaluate(async () => {
        instance.objectValue.nested.x = 9;
        await instance.$nextTick();
        if (typeof window.san !== 'undefined') await new Promise(resolve => san.nextTick(resolve));
        return {publicValue: instance.objectValue.nested.x, dom: document.querySelector('output').textContent};
      });
      await page.evaluate(() => {instance.setValue('dispose', null); cleanup();});
      assert.equal(await page.$('button'), null, `${kind} disposal`);
      observations.push({kind, scenario, states, nested, watches, escapedRef, disposal_succeeded: true});
    }
    assert.deepEqual(errors, [], 'Warnings/errors must not be hidden');
    const projected = item => item.states.map(({vuePresent, standaloneKernelPresent, ...state}) => state);
    for (const scenario of ['plain', 'ref']) {
      const source = observations.find(item => item.kind === 'source' && item.scenario === scenario);
      const target = observations.find(item => item.kind === 'target' && item.scenario === scenario);
      assert.deepEqual(projected(target), projected(source));
      assert.ok(target.states.every(state => !state.vuePresent), 'Target page must not load Vue');
      assert.ok(target.states.every(state => state.standaloneKernelPresent), 'Reactive kernel dependency must be explicit');
      assert.deepEqual(target.watches, source.watches);
      assert.equal(source.watches.length, scenario === 'ref' ? 8 : 6, 'Actual pre/post callbacks required');
      assert.deepEqual(target.nested, source.nested, 'Nested alias mutation must reach the actual DOM');
      if (scenario === 'ref') {
        const strip = ({vuePresent, standaloneKernelPresent, ...rest}) => rest;
        assert.deepEqual(strip(target.escapedRef), strip(source.escapedRef));
      }
    }
    const fingerprints = Object.fromEntries([
      __filename, path.join(__dirname, 'runtime.cjs'),
      path.join(project, 'frontend/node_modules/vue/dist/vue.global.js'),
      path.join(project, 'frontend/node_modules/@vue/reactivity/dist/reactivity.global.js'),
      path.join(project, 'research/public_instance_v1/runtime.cjs'),
      path.join(project, 'engine/node_modules/san/dist/san.dev.js')
    ].map(file => [path.relative(project, file).replaceAll('\\', '/'),
      createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
    return {status: 'reactive_prototype_root_watch_and_nested_render_verified', observations, errors, fingerprints,
      browser_version: await browser.version(),
      rendered_texts: observations[1].states.map(state => state.text),
      target_has_no_vue_component_runtime: true, standalone_reactivity_kernel_loaded: true,
      native_clicks_per_page: 2, page_count: 4, escaped_ref_render_verified: true,
      nested_alias_render_verified: true,
      full_visual_evaluation_performed: false, generated_SFC_loaders_changed: false,
      model_calls: 0, live_database_writes: 0, production_admission_eligible: false};
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  const value = JSON.parse(fs.readFileSync(0, 'utf8'));
  run(value.executable).then(result => {
    if (value.output) {
      const output = path.resolve(value.output);
      assert.ok(output.startsWith(path.join(project, 'var') + path.sep), 'Evidence must stay inside project/var');
      fs.mkdirSync(path.dirname(output), {recursive: true});
      fs.writeFileSync(output, JSON.stringify(result, null, 2), {flag: 'wx'});
    }
    console.log(JSON.stringify(result));
  }, error => {
    console.error(error.stack); process.exitCode = 1;
  });
}
module.exports = {run};
