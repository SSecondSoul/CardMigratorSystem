/* Native controls are an adapter boundary, not Vue's public Data.set API. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const {createRequire} = require('node:module');
const {fixture} = require('./compatibility.cjs');
const project = path.resolve(__dirname, '../..');
const requireFrontend = createRequire(path.join(project, 'frontend/package.json'));
const R = requireFrontend('@vue/reactivity/dist/reactivity.cjs.js');
const cases = [];

async function run() {
  cases.length = 0;
  async function compare(name, seed, operation) {
    const results = [];
    for (const target of [false, true]) {
      const f = fixture(target, {data: seed});
      try {results.push(await operation(f, target));} finally {f.dispose();}
    }
    assert.deepEqual(results[1], results[0], name);
    cases.push({name, source: results[0], target: results[1], equal: true});
  }
  await compare('shared-object-alias-stays-live', () => {
    const form = {title: 'old'}; return {count: 0, form, alias: form};
  }, async (f, target) => {
    const before = f.vm.form;
    const calls = [];
    f.vm.$watch('form.title', (v, old) => calls.push([v, old]));
    if (target) f.runtime.data.set('form.title', 'new'); else f.vm.form.title = 'new';
    await f.vm.$nextTick();
    return {title: f.vm.form.title, aliasTitle: f.vm.alias.title,
      aliasSame: f.vm.form === f.vm.alias, identity: before === f.vm.form, calls};
  });
  await compare('array-item-with-dynamic-index', () => ({count: 0, index: 1, rows: [{priority: 'low'}, {priority: 'low'}]}),
    async (f, target) => {
      const array = f.vm.rows, item = f.vm.rows[1];
      if (target) f.runtime.data.set('rows[index].priority', 'high'); else f.vm.rows[f.vm.index].priority = 'high';
      await f.vm.$nextTick();
      return {values: f.vm.rows.map(x => x.priority), array: f.vm.rows === array, item: f.vm.rows[1] === item};
    });
  await compare('nested-ref-unwrapped-with-original-ref-retained', () => ({count: 0, form: {amount: R.ref(1)}}),
    async (f, target) => {
      const ref = f.seed.form.amount;
      if (target) f.runtime.data.set('form.amount', 7); else f.vm.form.amount = 7;
      await f.vm.$nextTick();
      return {public: f.vm.form.amount, refValue: ref.value, original: f.seed.form.amount === ref};
    });
  await compare('literal-dot-empty-and-symbol-nested-keys', () => ({count: 0, form: {'a.b': 1, '': 2}}),
    async (f, target) => {
      const key = Symbol('nested');
      if (target) {
        f.runtime.data.set("form['a.b']", 8);
        f.runtime.data.set("form['']", 9);
        f.runtime.data.set({type: 4, paths: [{type: 1, value: 'form'}, {type: 1, value: key}]}, 10);
      } else {f.vm.form['a.b'] = 8; f.vm.form[''] = 9; f.vm.form[key] = 10;}
      await f.vm.$nextTick();
      return {dot: f.vm.form['a.b'], empty: f.vm.form[''], symbol: f.vm.form[key], nestedNotInvented: !('a' in f.vm.form)};
    });
  await compare('synchronous-watcher-mutates-second-root-and-same-root', () => ({count: 0, form: {title: 'old', noted: false}}),
    async (f, target) => {
      const calls = [];
      f.vm.$watch('form.title', v => {calls.push(v); f.vm.count++; f.vm.form.noted = true;}, {flush: 'sync'});
      if (target) {
        // Multiple native reads must not cause multiple notifications for a write.
        f.runtime.data.get('form.title'); f.runtime.data.get('form.noted'); f.runtime.data.get('count');
        f.runtime.data.set('form.title', 'new');
      } else f.vm.form.title = 'new';
      await f.vm.$nextTick();
      return {count: f.vm.count, title: f.vm.form.title, noted: f.vm.form.noted, calls};
    });
  const controls = {};
  function control(seed, operation) {
    const f = fixture(true, {data: seed});
    try {operation(f);} finally {f.dispose();}
  }
  control(() => ({count: 0, form: {title: 'old', noted: false}}), f => {
    const events = [], store = f.runtime.data;
    store.get('form.title'); store.get('form.noted'); store.get('count');
    store.listen(change => events.push(change));
    f.vm.$watch('form.title', () => {f.vm.count++; f.vm.form.noted = true;}, {flush: 'sync'});
    const option = {target: {id: 'input-fixture', prop: 'value'}};
    store.set('form.title', 'new', option);
    assert.equal(events.filter(x => x.expr.paths[0].value === 'form').length, 1);
    assert.equal(events.filter(x => x.expr.paths[0].value === 'count').length, 1);
    assert.equal(events.find(x => x.expr.paths[0].value === 'form').option, option);
    controls.single_notification_per_touched_root_and_option_identity = true;
  });
  for (const flag of ['silent', 'silence', 'quiet']) control(() => ({count: 0, form: {title: 'old'}}), f => {
    let events = 0, watches = 0;
    f.runtime.data.get('form.title');
    f.runtime.data.listen(() => events++);
    f.vm.$watch('form.title', () => watches++, {flush: 'sync'});
    f.runtime.data.set('form.title', 'new', {[flag]: true});
    assert.equal(events, 0); assert.equal(watches, 1);
    assert.equal(f.runtime.data.get('form.title'), 'new');
    controls[`${flag}_only_suppresses_native_event_not_source_watcher`] = true;
  });
  control(() => ({count: 0, form: {title: 'old'}}), f => {
    let events = 0;
    f.runtime.data.listen(() => events++);
    f.runtime.data.set('form.title', 'old'); assert.equal(events, 0);
    const policy = {force: true};
    f.runtime.data.set('form.title', 'old', policy); assert.equal(events, 1);
    controls.same_value_noop_and_explicit_force = true;
  });
  control(() => ({count: 0, form: null}), f => {
    let events = 0; f.runtime.data.listen(() => events++);
    assert.throws(() => f.runtime.data.set('form.title', 'new'), {code: 'public_instance_prototype_unproven'});
    assert.equal(f.vm.form, null); assert.equal(events, 0);
    controls.missing_parent_rejected_without_inventing_objects = true;
  });
  control(() => ({count: 0, form: {title: 'old'}}), f => {
    f.runtime.data.listen(change => {if (change.expr.paths[0].value === 'form') f.runtime.data.set('count', 9);});
    f.runtime.data.set('form.title', 'new');
    assert.equal(f.vm.count, 9); assert.equal(f.runtime.data.get('count'), 9);
    controls.native_listener_write_reenters_source_plane = true;
  });
  control(() => ({count: 0, form: {title: 'old'}}), f => {
    let error;
    f.vm.$watch('form.title', () => {
      try {f.runtime.data.set('count', 99);} catch (caught) {error = caught;}
    }, {flush: 'sync'});
    f.runtime.data.set('form.title', 'new');
    assert.equal(error?.code, 'public_instance_prototype_unproven'); assert.equal(f.vm.count, 0);
    controls.reentrant_native_write_explicitly_declines = true;
  });
  const fingerprints = Object.fromEntries([__filename, path.join(__dirname, 'runtime.cjs'),
    path.join(__dirname, 'compatibility.cjs'), requireFrontend.resolve('@vue/reactivity/dist/reactivity.cjs.js')]
    .map(file => [path.relative(project, file).replaceAll('\\', '/'), createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
  return {status: 'native_write_bridge_research_not_production', cases, matched_cases: cases.length, controls, fingerprints,
    production_admission_eligible: false, arbitrary_public_key_contract_complete: false, model_calls: 0, live_database_writes: 0};
}
if (require.main === module) run().then(result => {
  if (process.argv[2] === '--output') {
    const output = path.resolve(process.argv[3]);
    assert.ok(output.startsWith(path.join(project, 'var') + path.sep));
    fs.mkdirSync(path.dirname(output), {recursive: true});
    fs.writeFileSync(output, JSON.stringify(result, null, 2), {flag: 'wx'});
  }
  console.log(JSON.stringify(result));
}).catch(error => {console.error(error.stack); process.exitCode = 1;});
module.exports = {run};
