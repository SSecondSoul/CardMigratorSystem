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
  try {
    for (const kind of ['source', 'target']) {
      const context = await browser.createBrowserContext(), page = await context.newPage();
      pages.push({kind, context, page});
      page.on('pageerror', error => errors.push({kind, message: error.message}));
      page.on('console', msg => {if (['warning', 'error'].includes(msg.type())) errors.push({kind, message: msg.text()});});
      await page.setRequestInterception(true);
      page.on('request', request => request.abort());
      await page.setViewport({width: 800, height: 600});
      await page.setContent('<!doctype html><html><body><main id="app"></main></body></html>');
      await page.addScriptTag({path: path.join(project, kind === 'source' ?
        'frontend/node_modules/vue/dist/vue.global.js' : 'engine/node_modules/san/dist/san.dev.js')});
      if (kind === 'target') await page.addScriptTag({content:
        `(() => {const module={exports:{}};${prototype}\nwindow.publicPrototype=module.exports;})();`});
      await page.evaluate(kind => {
        const methods = {setValue(key, value) {this[key] = value;}, increment() {this.count++;}};
        if (kind === 'source') {
          const app = Vue.createApp({data() {return {count: 0};}, methods,
            render() {return Vue.h('button', {onClick: this.increment}, String(this.count));}});
          window.instance = app.mount('#app');
          const store = instance.$data;
          window.intact = () => instance.$data === store;
          window.cleanup = () => app.unmount();
        } else {
          let handle;
          const Component = san.defineComponent({template: '<button on-click="increment">{{count}}</button>',
            initData() {return {count: 0};}, increment() {handle.invoke('increment');}});
          const runtime = new Component(), store = runtime.data;
          handle = publicPrototype.createPublicInstance(runtime, {stateKeys: ['count'], methods});
          window.instance = handle.instance;
          window.intact = () => runtime.data === store;
          window.cleanup = () => handle.dispose();
          runtime.attach(document.getElementById('app'));
        }
      }, kind);
    }
    for (const {kind, page} of pages) {
      const states = [];
      const observe = async () => page.evaluate(() => ({text: document.querySelector('button').textContent,
        count: instance.count, intact: intact(), publicData: instance.data,
        publicWatch: instance.watch, vuePresent: typeof window.Vue !== 'undefined'}));
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
      await page.evaluate(() => {instance.setValue('dispose', null); cleanup();});
      assert.equal(await page.$('button'), null, `${kind} disposal`);
      observations.push({kind, states, disposal_succeeded: true});
    }
    assert.deepEqual(errors, [], 'Warnings/errors must not be hidden');
    const projected = item => item.states.map(({vuePresent, ...state}) => state);
    assert.deepEqual(projected(observations[1]), projected(observations[0]));
    assert.ok(observations[1].states.every(state => !state.vuePresent), 'Target page must not load Vue');
    const fingerprints = Object.fromEntries([
      __filename, path.join(__dirname, 'runtime.cjs'),
      path.join(project, 'frontend/node_modules/vue/dist/vue.global.js'),
      path.join(project, 'engine/node_modules/san/dist/san.dev.js')
    ].map(file => [path.relative(project, file).replaceAll('\\', '/'),
      createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
    return {status: 'prototype_two_page_functional_check_only', observations, errors, fingerprints,
      browser_version: await browser.version(),
      rendered_texts: observations[1].states.map(state => state.text),
      target_has_no_vue_runtime: true, native_clicks_per_page: 2,
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
