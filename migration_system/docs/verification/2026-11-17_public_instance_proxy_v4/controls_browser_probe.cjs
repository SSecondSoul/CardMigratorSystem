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
  const observations = [], errors = [];
  const v1 = fs.readFileSync(path.join(project, 'research/public_instance_v1/runtime.cjs'), 'utf8');
  const implementation = fs.readFileSync(path.join(__dirname, 'runtime.cjs'), 'utf8');
  try {
    for (const kind of ['source', 'target']) {
      const context = await browser.createBrowserContext(), page = await context.newPage();
      try {
        page.on('pageerror', error => errors.push({kind, message: error.message}));
        page.on('console', msg => {if (['warning', 'error'].includes(msg.type())) errors.push({kind, message: msg.text()});});
        await page.setRequestInterception(true);
        page.on('request', request => request.abort());
        await page.setContent('<!doctype html><main id="app"></main>');
        await page.addScriptTag({path: path.join(project, kind === 'source' ?
          'frontend/node_modules/vue/dist/vue.global.js' : 'engine/node_modules/san/dist/san.dev.js')});
        if (kind === 'target') {
          await page.addScriptTag({path: path.join(project, 'frontend/node_modules/@vue/reactivity/dist/reactivity.global.js')});
          await page.addScriptTag({content: `(() => {
            const previous=(()=>{const module={exports:{}};${v1}\nreturn module.exports;})();
            const require=name=>{if(name!=='../public_instance_v1/runtime.cjs')throw Error('Unexpected dependency');return previous;};
            const module={exports:{}};${implementation}\nwindow.publicPrototype=module.exports;})();`});
        }
        await page.evaluate(kind => {
          const form = {title: 'start', done: false, 'literal.dot': 'literal'};
          const seed = {form, alias: form, rows: [{priority: 'low'}]};
          const methods = {setValue(key, value) {this[key] = value;}};
          if (kind === 'source') {
            const app = Vue.createApp({data() {return seed;}, methods, render() {
              return Vue.h('div', [
                Vue.h('input', {id: 'title', value: this.form.title, onInput: e => {this.form.title = e.target.value;}}),
                Vue.h('input', {id: 'done', type: 'checkbox', checked: this.form.done, onChange: e => {this.form.done = e.target.checked;}}),
                Vue.h('select', {id: 'priority', value: this.rows[0].priority, onChange: e => {this.rows[0].priority = e.target.value;}},
                  [Vue.h('option', {value: 'low'}, 'low'), Vue.h('option', {value: 'high'}, 'high')]),
                Vue.h('input', {id: 'literal', value: this.form['literal.dot'], onInput: e => {this.form['literal.dot'] = e.target.value;}}),
                Vue.h('output', {id: 'echo'}, `${this.alias.title}|${this.form.done}|${this.rows[0].priority}|${this.form['literal.dot']}`)
              ]);
            }});
            window.instance = app.mount('#app'); window.cleanup = () => app.unmount();
          } else {
            const Component = san.defineComponent({
              template: `<div><input id="title" value="{=form.title=}"><input id="done" type="checkbox" checked="{=form.done=}">
                <select id="priority" value="{=rows[0].priority=}"><option value="low">low</option><option value="high">high</option></select>
                <input id="literal" value="{=form['literal.dot']=}"><output id="echo">{{alias.title}}|{{form.done}}|{{rows[0].priority}}|{{form['literal.dot']}}</output></div>`,
              initData() {return seed;}
            });
            const runtime = new Component();
            const handle = publicPrototype.createPublicInstance(runtime, {sourceData: seed, stateKeys: Object.keys(seed), methods,
              reactivity: VueReactivity, parseNativeExpr: san.parseExpr, evaluateNativeExpr: san.evalExpr,
              nextRender: callback => san.nextTick(callback)});
            window.instance = handle.instance; window.cleanup = () => handle.dispose();
            runtime.attach(document.getElementById('app'));
          }
          window.originalForm = instance.form; window.originalRow = instance.rows[0]; window.watchCalls = [];
          instance.$watch('form.title', (value, old) => watchCalls.push([value, old]), {flush: 'sync'});
          // User business fields must not replace the runtime handles needed by controls.
          instance.setValue('data', null); instance.setValue('watch', 42);
        }, kind);
        const states = [];
        const waitEcho = async expected => {
          try {await page.waitForFunction(value => document.querySelector('#echo').textContent === value, {timeout: 5000}, expected);}
          catch (error) {
            const actual = await page.evaluate(() => ({dom: document.querySelector('#echo')?.textContent,
              input: document.querySelector('#title')?.value, title: instance.form.title, alias: instance.alias.title,
              done: instance.form.done, priority: instance.rows[0].priority, watches: watchCalls}));
            throw new Error(`${kind} expected ${expected}: ${JSON.stringify({actual, errors})}`, {cause: error});
          }
        };
        const observe = () => page.evaluate(() => ({title: instance.form.title, done: instance.form.done,
          priority: instance.rows[0].priority, literal: instance.form['literal.dot'],
          sameForm: instance.form === originalForm, alias: instance.alias === instance.form,
          sameRow: instance.rows[0] === originalRow, echo: document.querySelector('#echo').textContent,
          input: document.querySelector('#title').value, checked: document.querySelector('#done').checked,
          selected: document.querySelector('#priority').value, publicData: instance.data, publicWatch: instance.watch}));
        states.push(await observe());
        await page.focus('#title');
        await page.keyboard.down('Control'); await page.keyboard.press('a'); await page.keyboard.up('Control');
        await page.keyboard.press('Backspace'); await page.type('#title', 'edited');
        await waitEcho('edited|false|low|literal');
        states.push(await observe());
        await page.click('#done'); await page.select('#priority', 'high');
        await waitEcho('edited|true|high|literal');
        states.push(await observe());
        await page.click('#done');
        await page.focus('#literal');
        await page.keyboard.down('Control'); await page.keyboard.press('a'); await page.keyboard.up('Control');
        await page.keyboard.press('Backspace'); await page.type('#literal', 'dot');
        await waitEcho('edited|false|high|dot');
        states.push(await observe());
        const watches = await page.evaluate(() => watchCalls);
        assert.equal(watches.length, 7, 'clear + six real character inputs must reach watcher');
        const runtime = await page.evaluate(() => ({vue: typeof window.Vue !== 'undefined', kernel: typeof window.VueReactivity !== 'undefined'}));
        await page.evaluate(() => {instance.setValue('dispose', null); cleanup();});
        assert.equal(await page.$('#title'), null);
        observations.push({kind, states, watches, runtime, disposed: true});
      } finally {await context.close();}
    }
    assert.deepEqual(observations[1].states, observations[0].states);
    assert.deepEqual(observations[1].watches, observations[0].watches);
    assert.deepEqual(observations[1].runtime, {vue: false, kernel: true});
    assert.deepEqual(errors, []);
    const fingerprints = Object.fromEntries([__filename, path.join(__dirname, 'runtime.cjs'),
      path.join(project, 'research/public_instance_v1/runtime.cjs'),
      path.join(project, 'frontend/node_modules/vue/dist/vue.global.js'),
      path.join(project, 'frontend/node_modules/@vue/reactivity/dist/reactivity.global.js'),
      path.join(project, 'engine/node_modules/san/dist/san.dev.js')]
      .map(file => [path.relative(project, file).replaceAll('\\', '/'), createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
    return {status: 'native_nested_controls_dom_verified', browser_version: await browser.version(), observations, errors,
      fingerprints, page_count: 2, real_native_controls: ['text-input', 'checkbox-on-off', 'select', 'literal-dot-input'],
      production_admission_eligible: false, arbitrary_public_key_contract_complete: false, model_calls: 0, live_database_writes: 0};
  } finally {await browser.close();}
}
if (require.main === module) {
  const value = JSON.parse(fs.readFileSync(0, 'utf8'));
  run(value.executable).then(result => {
    if (value.output) {
      const output = path.resolve(value.output); assert.ok(output.startsWith(path.join(project, 'var') + path.sep));
      fs.mkdirSync(path.dirname(output), {recursive: true}); fs.writeFileSync(output, JSON.stringify(result, null, 2), {flag: 'wx'});
    }
    console.log(JSON.stringify(result));
  }).catch(error => {console.error(error.stack); process.exitCode = 1;});
}
module.exports = {run};
