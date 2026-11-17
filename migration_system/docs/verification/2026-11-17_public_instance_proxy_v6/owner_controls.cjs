'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const {createHash} = require('node:crypto');
const {createRequire} = require('node:module');
const project = path.resolve(__dirname, '../..');
const requireEngine = createRequire(path.join(project, 'engine/package.json'));
const requireFrontend = createRequire(path.join(project, 'frontend/package.json'));
const san = requireEngine('san'), R = requireFrontend('@vue/reactivity/dist/reactivity.cjs.js');
const {createPublicInstance} = require('./runtime.cjs');
const {connectRootOwner} = require('./owner.cjs');
function fixture(template = '<div/>') {
  const seed = {count: 0}, C = san.defineComponent({template, initData() {return seed;}});
  const native = new C();
  const handle = createPublicInstance(native, {sourceData: seed, stateKeys: ['count'], reactivity: R,
    parseNativeExpr: san.parseExpr, evaluateNativeExpr: san.evalExpr, nextRender: callback => queueMicrotask(callback)});
  return {native, handle, C};
}
function run() {
  const controls = {};
  function check(name, operation, template) {
    const f = fixture(template);
    try {operation(f); controls[name] = true;} finally {f.handle.dispose();}
  }
  const declined = operation => assert.throws(operation, {code: 'public_instance_prototype_unproven'});
  check('unknown_hook_rejected_before_owner_or_native_mutation', f => {
    const attach = f.native.attach;
    declined(() => connectRootOwner(f.native, f.handle, {activated() {}}));
    assert.equal(f.native.attach, attach);
    const owner = connectRootOwner(f.native, f.handle); assert.equal(owner.state, 'created');
  });
  check('parent_scope_rejected_before_mutation', f => {
    const attach = f.native.attach; f.native.parent = {};
    declined(() => connectRootOwner(f.native, f.handle));
    assert.equal(f.native.attach, attach); f.native.parent = null;
  });
  check('transition_rejected_before_mutation', f => {
    f.native.transition = {};
    declined(() => connectRootOwner(f.native, f.handle)); delete f.native.transition;
  });
  check('parsed_transition_directive_rejected_before_mutation', f => {
    const attach = f.native.attach;
    assert.ok(f.native.aNode.directives.transition);
    declined(() => connectRootOwner(f.native, f.handle));
    assert.equal(f.native.attach, attach);
  }, '<div s-transition="fade"/>');
  check('nonconfigurable_method_rejected_before_partial_install', f => {
    const attach = f.native.attach;
    Object.defineProperty(f.native, '_update', {value: f.native._update, configurable: false});
    declined(() => connectRootOwner(f.native, f.handle)); assert.equal(f.native.attach, attach);
  });
  check('duplicate_owner_binding_rejected_without_replacing_first', f => {
    const owner = connectRootOwner(f.native, f.handle), attach = f.native.attach;
    declined(() => connectRootOwner(f.native, f.handle)); assert.equal(f.native.attach, attach);
    assert.equal(owner.state, 'created');
  });
  check('external_detach_declines_without_stopping_scope', f => {
    connectRootOwner(f.native, f.handle);
    declined(() => f.native.detach()); assert.equal(f.handle.scope.active, true);
  });
  check('borrowed_receiver_delegates_without_disposing_owner', f => {
    const prototype = Object.getPrototypeOf(f.native), dispose = prototype.dispose;
    connectRootOwner(f.native, f.handle);
    const other = new f.C();
    f.native.dispose.call(other);
    assert.equal(other.lifeCycle.disposed, true); assert.equal(f.handle.scope.active, true);
    assert.equal(prototype.dispose, dispose);
  });
  check('direct_dispose_is_idempotent_and_restores_store_descriptors', f => {
    const nativeGet = Object.getPrototypeOf(f.native.data).get;
    let cleaned = 0;
    f.handle.instance.$watch('count', (value, old, cleanup) => cleanup(() => cleaned++), {flush: 'sync'});
    const owner = connectRootOwner(f.native, f.handle);
    f.handle.instance.count = 1; f.native.dispose(); f.handle.dispose(); owner.dispose();
    assert.equal(cleaned, 1); assert.equal(f.handle.scope.active, false);
    assert.equal(f.native.data.get, nativeGet); assert.equal(owner.state, 'disposed');
    declined(() => owner.attach(null));
  });
  check('nonextensible_native_rejected_before_owner_binding', f => {
    Object.preventExtensions(f.native);
    declined(() => connectRootOwner(f.native, f.handle));
  });
  const fingerprints = Object.fromEntries([__filename, path.join(__dirname, 'owner.cjs'), path.join(__dirname, 'runtime.cjs')]
    .map(file => [path.relative(project, file).replaceAll('\\', '/'), createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
  return {status: 'root_owner_boundary_controls', controls, fingerprints, node_render_barrier_is_test_double: true,
    production_admission_eligible: false, arbitrary_public_key_contract_complete: false, model_calls: 0, live_database_writes: 0};
}
if (require.main === module) {
  const report = run();
  if (process.argv[2] === '--output') {
    const output = path.resolve(process.argv[3]); assert.ok(output.startsWith(path.join(project, 'var') + path.sep));
    fs.mkdirSync(path.dirname(output), {recursive: true}); fs.writeFileSync(output, JSON.stringify(report, null, 2), {flag: 'wx'});
  }
  console.log(JSON.stringify(report));
}
module.exports = {run};
