'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const {createRequire} = require('node:module');
const project = path.resolve(__dirname, '../..');
const requireEngine = createRequire(path.join(project, 'engine/package.json'));
const requireFrontend = createRequire(path.join(project, 'frontend/package.json'));
const san = requireEngine('san');
const R = requireFrontend('@vue/reactivity/dist/reactivity.cjs.js');
const {createPublicInstance} = require('./runtime.cjs');

function run() {
  const seed = {count: 0, objectValue: {x: 0}};
  const C = san.defineComponent({template: '<div/>', initData() {return seed;}});
  const runtime = new C(), other = new C(), store = runtime.data;
  const prototype = Object.getPrototypeOf(store), originalGet = prototype.get, originalSet = prototype.set;
  const customGet = function (...args) {return originalGet.apply(this, args);};
  Object.defineProperty(store, 'get', {value: customGet, configurable: true, writable: true, enumerable: false});
  const before = Object.getOwnPropertyDescriptor(store, 'get');
  const handle = createPublicInstance(runtime, {sourceData: seed, stateKeys: Object.keys(seed),
    reactivity: R, parseNativeExpr: san.parseExpr, methods: {setValue(k, v) {this[k] = v;}}});
  const result = {};
  try {
    other.data.set('count', 44);
    result.borrowed_receiver = store.get.call(other.data, 'count') === 44;
    result.no_global_prototype_patch = prototype.get === originalGet && prototype.set === originalSet;
    result.root_raw_identity = R.toRaw(handle.instance.$data) === seed && store.raw !== seed;
    store.get('count');
    let events = 0;
    store.listen(change => {if (change.expr.paths[0].value === 'count') events++;});
    handle.instance.setValue('count', 1);
    result.single_root_notification = events === 1;
    events = 0;
    store.set('count', 2);
    result.native_root_write = handle.instance.count === 2 && events === 1;
    let error;
    try {store.set('objectValue.x', 3);} catch (caught) {error = caught;}
    result.nested_native_write_declines = error?.code === 'public_instance_prototype_unproven' && handle.instance.objectValue.x === 0;
    handle.dispose();
    const after = Object.getOwnPropertyDescriptor(store, 'get');
    result.own_descriptor_restored = after.value === before.value && after.enumerable === before.enumerable &&
      after.writable === before.writable && after.configurable === before.configurable;
  } finally {handle.dispose(); other.dispose();}
  const native = new C(), data = native.data, raw = data.raw;
  try {
    let error;
    try {createPublicInstance(native, {stateKeys: Object.keys(seed),
      reactivity: requireFrontend('@vue/reactivity/dist/reactivity.cjs.prod.js')});}
    catch (caught) {error = caught;}
    result.unpinned_production_hook_declines_before_mutation =
      error?.code === 'public_instance_prototype_unproven' && native.data === data && data.raw === raw;
  } finally {native.dispose();}
  for (const [name, passed] of Object.entries(result)) assert.equal(passed, true, name);
  return {status: 'prototype_boundary_controls', controls: result,
    production_admission_eligible: false, model_calls: 0, live_database_writes: 0};
}
if (require.main === module) {
  const result = run();
  if (process.argv.length > 2) {
    assert.equal(process.argv[2], '--output');
    const output = path.resolve(process.argv[3]);
    assert.ok(output.startsWith(path.join(project, 'var') + path.sep));
    fs.mkdirSync(path.dirname(output), {recursive: true});
    fs.writeFileSync(output, JSON.stringify(result, null, 2), {flag: 'wx'});
  }
  console.log(JSON.stringify(result));
}
module.exports = {run};
