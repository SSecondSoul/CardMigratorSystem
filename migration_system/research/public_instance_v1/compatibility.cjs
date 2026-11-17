/* Actual native Vue/San compatibility experiments; no LLM, database or SFC edits. */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const {createHash} = require('node:crypto');
const {createPublicInstance, PrototypeCapabilityError} = require('./runtime.cjs');
const project = path.resolve(__dirname, '../..');
const engineRequire = createRequire(path.join(project, 'engine/package.json'));
const frontendRequire = createRequire(path.join(project, 'frontend/package.json'));
const Vue = frontendRequire('vue');
const san = engineRequire('san');
const renderer = Vue.createRenderer({
  createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
  insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {},
  parentNode: () => null, nextSibling: () => null
});
const initial = () => ({count: 0, other: 1, objectValue: null});
const methods = {
  setValue(key, value) {this[key] = value;},
  increment() {this.count++;}
};
const computed = {
  doubled() {return this.count * 2;},
  writable: {get() {return this.count * 2;}, set(value) {this.count = value / 2;}}
};
const Native = san.defineComponent({template: '<div></div>', initData: initial});
// runtime-core writes `[Vue warn]:`, reactivity writes `[Vue warn]`.
// Compare the diagnostic text and retain counts, not these two console prefixes.
const warningText = args => String(args[0]).replace(/^\[Vue warn\]:?\s*/, '').trim();

function fixture(target) {
  const warnings = [];
  if (target) {
    const runtime = new Native();
    const handle = createPublicInstance(runtime, {stateKeys: Object.keys(initial()),
      props: {title: 'original'}, methods, computed, warn: text => warnings.push(text)});
    const store = runtime.data;
    return {vm: handle.instance, warnings, data: handle.data, runtime, handle,
      get: key => store.get({type: 4, paths: [{type: 1, value: key}]}),
      intact: () => runtime.data === store,
      watch() {runtime.watch('count', () => {});}, dispose: () => handle.dispose()};
  }
  const app = renderer.createApp({data: initial, props: {title: {default: 'original'}},
    methods, computed, render() {return null;}});
  app.config.warnHandler = text => warnings.push(text);
  const vm = app.mount({}), data = vm.$data;
  return {vm, data, warnings, app, get: key => data[key], intact: () => vm.$data === data,
    watch() {vm.$watch('count', () => {})();}, dispose: () => app.unmount()};
}

function observe(target, operation) {
  const value = fixture(target), oldWarn = console.warn;
  console.warn = (...args) => value.warnings.push(warningText(args));
  try {
    return operation(value);
  } finally {
    console.warn = oldWarn;
    value.dispose();
  }
}

function assignment(keyFactory, valueFactory = () => 7) {
  return fixture => {
    const conversions = [], key = keyFactory(conversions), value = valueFactory();
    const setter = fixture.vm.setValue;
    let error = null;
    try {setter(key, value);} catch (caught) {error = caught.name;}
    // Reading with a coercing key would call ToPropertyKey again and taint the
    // measurement. The key factory exposes a separate primitive probe key.
    const objectKey = typeof key === 'object' && key !== null;
    const primitive = objectKey ? key.probeKey : key;
    let matches = null;
    if (!error && (!objectKey || Object.hasOwn(key, 'probeKey'))) matches = Object.is(fixture.vm[primitive], value);
    const countAfterAssignment = fixture.get('count');
    let businessError = null, watchError = null;
    try {fixture.vm.increment();} catch (caught) {businessError = caught.name;}
    try {fixture.watch();} catch (caught) {watchError = caught.name;}
    return {error, matches, countAfterAssignment, countAfterBusiness: fixture.get('count'),
      dataPointerIntact: fixture.intact(), businessError, watchError, conversions,
      warnings: fixture.warnings.slice()};
  };
}

function run() {
  assert.equal(Vue.version, '3.5.45', 'Review compatibility when the oracle changes');
  assert.equal(san.version, '3.15.6', 'Review native Data operations when San changes');
  const cases = [];
  const add = (name, operation) => {
    const source = observe(false, operation), target = observe(true, operation);
    const equal = JSON.stringify(source) === JSON.stringify(target);
    cases.push({name, source, target, equal});
    assert.deepEqual(target, source, name);
  };
  add('declared-root', assignment(() => 'count'));
  add('declared-root-key-coercion', assignment(log => ({probeKey: 'count',
    [Symbol.toPrimitive](hint) {log.push(hint); return 'count';}})));
  add('coercion-to-symbol', assignment(log => {
    const key = Symbol('business');
    return {probeKey: key, [Symbol.toPrimitive](hint) {log.push(hint); return key;}};
  }));
  add('throwing-key', assignment(log => ({[Symbol.toPrimitive](hint) {log.push(hint); throw new RangeError('key');}})));
  add('invalid-primitive-conversion', assignment(log => ({[Symbol.toPrimitive](hint) {log.push(hint); return {};}})));
  add('ordinary-conversion-fallback', assignment(log => ({probeKey: 'count',
    toString() {log.push('toString'); return {};}, valueOf() {log.push('valueOf'); return 'count';}})));
  for (const [name, key] of [
    ['dotted-literal', 'extra.key'], ['bracket-literal', 'extra[0]'], ['empty-key', ''],
    ['numeric-key', 12], ['negative-zero-key', -0], ['undefined-key', undefined],
    ['null-key', null], ['boolean-key', true], ['bigint-key', 12n],
    ['symbol-key', Symbol('key')], ['well-known-symbol', Symbol.toStringTag],
    ['constructor-key', 'constructor'], ['prototype-key', 'prototype'],
    ['toString-key', 'toString'], ['hasOwnProperty-key', 'hasOwnProperty'],
    ['unknown-dollar-key', '$business'], ['symbol-runtime-key', Symbol.for('data')],
    ['Vue-marker-skip', '__v_skip'], ['Vue-marker-isVue', '__isVue']
  ]) add(name, assignment(() => key));
  for (const name of ['data', 'watch', 'fire', 'attach', 'dispose', 'el', 'computed', '__cardmig_runtime__']) {
    for (const [label, factory] of [['null', () => null], ['number', () => 42], ['object', () => ({marker: 7})]]) {
      add(`native-namespace-${name}-${label}`, assignment(() => name, factory));
    }
  }
  add('coerced-native-data', assignment(log => ({probeKey: 'data',
    [Symbol.toPrimitive](hint) {log.push(hint); return 'data';}}), () => null));
  for (const [name, factory] of [
    ['object-value', () => ({x: 1})], ['function-value', () => function callback() {}],
    ['symbol-value', () => Symbol('value')], ['bigint-value', () => 99n],
    ['NaN-value', () => NaN], ['cyclic-context-value', () => {const x = {}; x.self = x; return x;}]
  ]) add(name, assignment(() => 'extra', factory));
  add('readonly-prop-strict', assignment(() => 'title'));
  add('readonly-computed', fixture => {
    fixture.vm.setValue('doubled', 88);
    return {count: fixture.get('count'), doubled: fixture.vm.doubled, warnings: fixture.warnings.slice()};
  });
  add('writable-computed', assignment(() => 'writable', () => 18));
  for (const name of ['$data', '$props', '$ctx', '$uid', '$constructor', '$emit', '$attrs', '_']) {
    add(`readonly-namespace-${name}`, assignment(() => name));
  }
  add('captured-bound-method-survives-replacement', fixture => {
    const captured = fixture.vm.increment;
    fixture.vm.setValue('increment', 0);
    captured.call({count: 1000});
    let error = null;
    try {fixture.vm.increment();} catch (caught) {error = caught.name;}
    return {count: fixture.get('count'), error};
  });
  add('captured-setter-survives-self-replacement', fixture => {
    const captured = fixture.vm.setValue;
    captured('setValue', null);
    captured('data', null);
    fixture.vm.increment();
    return {publicSetter: fixture.vm.setValue, publicData: fixture.vm.data,
      count: fixture.get('count'), intact: fixture.intact()};
  });
  add('prototype-assignment-is-context-only', fixture => {
    const inherited = {sentinel: 3};
    fixture.vm.setValue('__proto__', inherited);
    fixture.vm.increment();
    return {prototypeMatches: Object.getPrototypeOf(fixture.vm) === inherited,
      publicInheritedRead: fixture.vm.sentinel === undefined, publicHas: 'sentinel' in fixture.vm,
      count: fixture.get('count'), intact: fixture.intact()};
  });
  add('repeated-inherited-key-writes-and-descriptors', fixture => {
    const out = [];
    for (const key of ['__proto__', 'constructor', 'toString', 'hasOwnProperty']) {
      fixture.vm.setValue(key, 1); fixture.vm.setValue(key, 2);
      const descriptor = Object.getOwnPropertyDescriptor(fixture.vm, key);
      out.push({key, value: fixture.vm[key], writable: descriptor.writable,
        configurable: descriptor.configurable, enumerable: descriptor.enumerable});
    }
    return out;
  });
  add('frozen-public-context-does-not-freeze-native-store', fixture => {
    Object.preventExtensions(fixture.vm);
    let error = null;
    try {fixture.vm.setValue('newKey', 1);} catch (caught) {error = caught.name;}
    fixture.vm.increment();
    return {error, count: fixture.get('count'), intact: fixture.intact()};
  });
  add('literal-key-did-not-create-a-state-path', fixture => {
    fixture.vm.setValue('a.b', 3);
    return {literal: fixture.vm['a.b'], rootMissing: fixture.vm.a === undefined,
      dataRootMissing: fixture.get('a') === undefined, own: Object.hasOwn(fixture.vm, 'a.b')};
  });
  const gaps = [];
  const gap = (name, operation) => {
    const source = observe(false, operation), target = observe(true, operation);
    assert.notDeepEqual(target, source, `Known gap unexpectedly closed; review and update: ${name}`);
    gaps.push({name, source, target, status: 'unresolved_not_waived'});
  };
  gap('declared-state-object-reactive-identity', fixture => {
    const object = {x: 1}; fixture.vm.setValue('objectValue', object);
    return {publicSameAsRawValue: fixture.vm.objectValue === object};
  });
  gap('private-instance-reflection', fixture => {
    try {return {kind: typeof fixture.vm.$};} catch (error) {return {error: error.name};}
  });
  gap('dollar-key-write-and-public-read', fixture => {
    let writeError = null;
    try {fixture.vm.setValue('$', 42);} catch (error) {writeError = error.name;}
    try {return {writeError, kind: typeof fixture.vm.$};}
    catch (error) {return {writeError, readError: error.name};}
  });
  gap('public-watch-api', fixture => {
    try {return {kind: typeof fixture.vm.$watch};} catch (error) {return {error: error.name};}
  });
  // Actual prototype dependencies are separate from the migration engine manifest.
  const fingerprints = Object.fromEntries([
    __filename, path.join(__dirname, 'runtime.cjs'),
    frontendRequire.resolve('@vue/runtime-core/dist/runtime-core.cjs.js'),
    frontendRequire.resolve('@vue/reactivity/dist/reactivity.cjs.js'),
    engineRequire.resolve('san/dist/san.dev.js')
  ].map(file => [path.relative(project, file).replaceAll('\\', '/'),
    createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
  return {schema_version: 1, status: 'prototype_partial_compatibility_not_production',
    versions: {vue: Vue.version, san: san.version}, fingerprints,
    matched_cases: cases.length, cases, gaps, production_admission_eligible: false,
    arbitrary_public_key_contract_complete: false,
    native_browser_render_verified: false, model_calls: 0, live_database_writes: 0,
    source_or_generated_components_modified: false,
    description: 'Unrestricted key conversion/context writes tested; full object reactivity, public framework APIs and integration remain unproven.'};
}

if (require.main === module) {
  const result = run();
  if (process.argv.length > 2) {
    assert.equal(process.argv[2], '--output');
    const output = path.resolve(process.argv[3]);
    assert.ok(output.startsWith(path.join(project, 'var') + path.sep), 'Evidence must stay inside project/var');
    fs.mkdirSync(path.dirname(output), {recursive: true});
    fs.writeFileSync(output, JSON.stringify(result, null, 2), {flag: 'wx'});
    console.log(JSON.stringify({...result, cases: result.cases.map(({name, equal}) => ({name, equal}))}, null, 2));
  } else console.log(JSON.stringify(result));
}
module.exports = {run, fixture, observe};
