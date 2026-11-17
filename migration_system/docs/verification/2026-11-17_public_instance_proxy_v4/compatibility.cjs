/* Actual native Vue/San compatibility experiments; no LLM, database or SFC edits. */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const {createHash} = require('node:crypto');
const {createPublicInstance} = require('./runtime.cjs');
const project = path.resolve(__dirname, '../..');
const engineRequire = createRequire(path.join(project, 'engine/package.json'));
const frontendRequire = createRequire(path.join(project, 'frontend/package.json'));
const Vue = frontendRequire('vue');
const R = frontendRequire('@vue/reactivity/dist/reactivity.cjs.js');
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

function fixture(target, options = {}) {
  const warnings = [];
  const errors = [];
  const seed = options.data ? options.data(R) : initial();
  const sourceMethods = {...methods, ...options.methods};
  const sourceComputed = {...computed, ...options.computed};
  if (target) {
    const Component = san.defineComponent({template: '<div></div>', initData() {return seed;}});
    const runtime = new Component();
    const handle = createPublicInstance(runtime, {stateKeys: Reflect.ownKeys(seed), sourceData: seed,
      reactivity: R, props: {title: 'original'}, methods: sourceMethods, computed: sourceComputed,
      // This Node fixture has no DOM (Vue also uses a render-null host).
      // Use an explicit microtask barrier double here; actual San nextTick and
      // actual DOM timing are verified separately by browser_probe.cjs.
      nextRender: callback => queueMicrotask(callback), parseNativeExpr: san.parseExpr, evaluateNativeExpr: san.evalExpr,
      onError: options.errorRouting ? (error, proxy, type) => errors.push({name: error.name,
        phase: {2: 'watcher getter', 3: 'watcher callback', 4: 'watcher cleanup function'}[type], receiver: proxy === handle.instance}) : undefined,
      warn: text => warnings.push(text)});
    const store = runtime.data;
    return {vm: handle.instance, warnings, errors, data: handle.data, runtime, handle, seed,
      get: key => store.get({type: 4, paths: [{type: 1, value: key}]}),
      intact: () => runtime.data === store,
      watch() {handle.instance.$watch('count', () => {})();}, dispose: () => handle.dispose()};
  }
  const app = renderer.createApp({data() {return seed;}, props: {title: {default: 'original'}},
    methods: sourceMethods, computed: sourceComputed, render() {return null;}});
  app.config.warnHandler = text => warnings.push(text);
  const vm = app.mount({}), data = vm.$data;
  if (options.errorRouting) app.config.errorHandler = (error, proxy, phase) => errors.push({name: error.name, phase, receiver: proxy === vm});
  return {vm, data, warnings, errors, app, seed, get: key => data[key], intact: () => vm.$data === data,
    watch() {vm.$watch('count', () => {})();}, dispose: () => app.unmount()};
}

function observe(target, operation, options) {
  const value = fixture(target, options), oldWarn = console.warn;
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

async function run() {
  assert.equal(Vue.version, '3.5.45', 'Review compatibility when the oracle changes');
  assert.equal(san.version, '3.15.6', 'Review native Data operations when San changes');
  const cases = [];
  const add = (name, operation, options) => {
    const source = observe(false, operation, options), target = observe(true, operation, options);
    const equal = JSON.stringify(source) === JSON.stringify(target);
    cases.push({name, source, target, equal});
    assert.deepEqual(target, source, name);
  };
  const asyncObserve = async (target, operation, options) => {
    const value = fixture(target, options), oldWarn = console.warn;
    console.warn = (...args) => value.warnings.push(warningText(args));
    try {return await operation(value);} finally {console.warn = oldWarn; value.dispose();}
  };
  const addAsync = async (name, operation, options) => {
    const source = await asyncObserve(false, operation, options);
    const target = await asyncObserve(true, operation, options);
    cases.push({name, source, target, equal: true});
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
  const gap = (name, operation, options) => {
    const source = observe(false, operation, options), target = observe(true, operation, options);
    assert.notDeepEqual(target, source, `Known gap unexpectedly closed; review and update: ${name}`);
    gaps.push({name, source, target, status: 'unresolved_not_waived'});
  };
  add('declared-state-object-reactive-identity', fixture => {
    const object = {x: 1}; fixture.vm.setValue('objectValue', object);
    return {publicSameAsRawValue: fixture.vm.objectValue === object};
  });
  add('logical-instance-record-and-aliases', fixture => {
    const vm = fixture.vm;
    return {kind: typeof vm.$, proxySame: vm.$.proxy === vm, dataSame: vm.$.data === vm.$data,
      contextSame: vm.$.ctx === vm.$.proxy.$.ctx, rootSame: vm.$root === vm,
      parentNull: vm.$parent === null, rawSame: R.toRaw(vm.$data) === fixture.seed,
      nativeRecordDistinct: fixture.runtime ? vm.$ !== fixture.runtime : vm.$ !== vm};
  });
  add('dollar-key-write-and-public-read', fixture => {
    let writeError = null;
    try {fixture.vm.setValue('$', 42);} catch (error) {writeError = error.name;}
    try {return {writeError, kind: typeof fixture.vm.$};}
    catch (error) {return {writeError, readError: error.name};}
  });
  add('public-watch-api', fixture => {
    try {return {kind: typeof fixture.vm.$watch};} catch (error) {return {error: error.name};}
  });
  add('object-array-map-cycle-and-alias-identity', fixture => {
    const nested = {x: 1}, raw = {nested, array: [nested], map: new Map([['x', nested]])}; raw.self = raw;
    fixture.vm.setValue('objectValue', raw);
    const value = fixture.vm.objectValue;
    return {reactive: R.isReactive(value), sameRaw: value === raw,
      childReactive: R.isReactive(value.nested), arrayReactive: R.isReactive(value.array),
      mapReactive: R.isReactive(value.map), repeated: value === fixture.vm.objectValue,
      aliases: value.nested === value.array[0] && value.nested === value.map.get('x'),
      cycle: value.self === value, originalUnchanged: fixture.seed.objectValue === raw,
      rawSame: R.toRaw(value) === raw};
  });
  add('root-data-self-identity', fixture => {
    fixture.vm.setValue('objectValue', fixture.vm.$data);
    return {same: fixture.vm.objectValue === fixture.vm.$data,
      originalRawSame: R.toRaw(fixture.vm.$data) === fixture.seed};
  });
  add('refs-unwrapping-and-existing-ref-assignment', fixture => {
    const ref = fixture.seed.count;
    const before = fixture.vm.count;
    fixture.vm.setValue('count', 8);
    return {before, after: fixture.vm.count, originalRefKept: fixture.seed.count === ref,
      refValue: ref.value, isRefInRaw: R.isRef(fixture.seed.count)};
  }, {data: () => ({...initial(), count: R.ref(1)})});
  add('computed-caches-and-invalidates', fixture => {
    const values = [fixture.vm.cached, fixture.vm.cached];
    const first = fixture.vm.trace.length;
    fixture.vm.setValue('count', 3);
    const beforeRead = fixture.vm.trace.length;
    values.push(fixture.vm.cached, fixture.vm.cached);
    return {values, first, beforeRead, final: fixture.vm.trace.length};
  }, {data: () => ({...initial(), trace: []}),
    computed: {cached() {this.trace.push('get'); return this.count * 2;}}});
  add('props-readonly-proxy-flags', fixture => ({readonly: R.isReadonly(fixture.vm.$props),
    reactive: R.isReactive(fixture.vm.$props), shallow: R.isShallow(fixture.vm.$props),
    title: fixture.vm.$props.title}));
  add('no-eager-or-duplicate-root-getter-read', fixture => {
    const before = fixture.seed._reads;
    const value = fixture.vm.count;
    return {before, value, after: fixture.seed._reads};
  }, {data: () => {
    const seed = {...initial(), _reads: 0};
    Object.defineProperty(seed, 'count', {enumerable: true, configurable: true,
      get() {seed._reads++; return 0;}}); return seed;
  }});
  await addAsync('watch-default-batches-pause-resume-cleanup-stop', async fixture => {
    const vm = fixture.vm, calls = [];
    const stop = vm.$watch('count', function (value, old, cleanup) {
      calls.push(['call', value, old, this === vm]); cleanup(() => calls.push(['cleanup', value]));
    });
    vm.setValue('count', 1); vm.setValue('count', 2);
    const beforeTick = calls.length;
    await vm.$nextTick();
    vm.setValue('count', 3); await vm.$nextTick();
    stop.pause(); vm.setValue('count', 4); await vm.$nextTick();
    const whilePaused = calls.length;
    stop.resume(); await vm.$nextTick(); stop.stop();
    vm.setValue('count', 5); await vm.$nextTick();
    return {beforeTick, whilePaused, calls};
  });
  await addAsync('watch-immediate-once-sync', async fixture => {
    const calls = [], vm = fixture.vm;
    vm.$watch('count', (value, old) => calls.push(['once', value, old]), {immediate: true, once: true});
    const stop = vm.$watch('count', (value, old) => calls.push(['sync', value, old]), {flush: 'sync'});
    vm.setValue('count', 1); vm.setValue('count', 2);
    const beforeTick = calls.length;
    await vm.$nextTick(); stop(); return {calls, beforeTick};
  });
  await addAsync('watch-path-deep-array-and-map-mutations', async fixture => {
    const vm = fixture.vm, calls = [];
    vm.setValue('objectValue', {nested: {x: 0}, array: [], map: new Map()});
    const stopPath = vm.$watch('objectValue.nested.x', (value, old) => calls.push(['path', value, old]));
    const stopDeep = vm.$watch('objectValue', (value, old) => calls.push(['deep', value === old]), {deep: true});
    vm.objectValue.nested.x = 1; vm.objectValue.nested.x = 2;
    vm.objectValue.array.push(1); vm.objectValue.map.set('x', 1);
    await vm.$nextTick(); stopPath(); stopDeep(); return {calls};
  });
  await addAsync('watch-getter-public-receiver-and-nextTick-callback', async fixture => {
    const vm = fixture.vm, reads = [], calls = [];
    const stop = vm.$watch(function (proxy) {reads.push([this === vm, proxy === vm]); return this.count;},
      function (value, old) {calls.push([value, old, this === vm]);});
    vm.setValue('count', 1);
    let callbackThis;
    await vm.$nextTick(function () {callbackThis = this === vm;});
    stop(); return {reads, calls, callbackThis, stableNextTick: vm.$nextTick === vm.$nextTick,
      freshWatchBinding: vm.$watch !== vm.$watch};
  });
  await addAsync('watch-disposal-cancels-pending-callback', async fixture => {
    const vm = fixture.vm, calls = [];
    vm.$watch('count', value => calls.push(value)); vm.setValue('count', 1);
    fixture.dispose(); await Promise.resolve(); await Promise.resolve();
    return {calls};
  });
  await addAsync('watch-numeric-deep-and-handler-object', async fixture => {
    const vm = fixture.vm, calls = [];
    vm.setValue('objectValue', {nested: {x: 0}});
    const stop = vm.$watch('objectValue', {deep: 1, handler(value, old) {calls.push([value === old, this === vm]);}});
    vm.objectValue.nested.x = 1; await vm.$nextTick();
    const afterNested = calls.length;
    vm.objectValue.extra = 1; await vm.$nextTick(); stop();
    return {calls, afterNested};
  });
  await addAsync('watch-callback-cleanup-error-policy', async fixture => {
    const vm = fixture.vm, calls = [];
    const stop = vm.$watch('count', (value, old, cleanup) => {
      cleanup(() => {throw new RangeError('cleanup');});
      cleanup(() => calls.push('later-cleanup'));
      throw new TypeError('callback');
    });
    vm.setValue('count', 1); await vm.$nextTick(); stop();
    return {calls, errors: fixture.errors, warnings: fixture.warnings};
  }, {errorRouting: true});
  await addAsync('watch-getter-error-policy', async fixture => {
    const vm = fixture.vm, calls = [];
    const stop = vm.$watch(() => {if (!vm.count) throw new RangeError('getter'); return vm.count;},
      (value, old) => calls.push([value, old]));
    vm.setValue('count', 1); await vm.$nextTick(); stop();
    return {calls, errors: fixture.errors, warnings: fixture.warnings};
  }, {errorRouting: true});
  await addAsync('watch-async-rejection-recording-policy', async fixture => {
    const vm = fixture.vm;
    const stop = vm.$watch('count', async () => {throw new TypeError('async-callback');});
    vm.setValue('count', 1); await vm.$nextTick(); await Promise.resolve(); stop();
    return {errors: fixture.errors, warnings: fixture.warnings};
  }, {errorRouting: true});
  add('native-consumer-does-not-evaluate-nested-getter-twice', fixture => {
    let reads = 0;
    const raw = {get value() {reads++; return 7;}};
    fixture.vm.setValue('objectValue', raw);
    const value = fixture.runtime ? fixture.runtime.data.get('objectValue.value') : fixture.vm.objectValue.value;
    return {value, reads};
  });
  gap('private-instance-renderer-vnode-graph', fixture => {
    try {return {kind: typeof fixture.vm.$.vnode};} catch (error) {return {error: error.name};}
  });
  add('escaped-ref-native-state-mirror', fixture => {
    fixture.get('count');
    fixture.seed.count.value = 6;
    return {publicCount: fixture.vm.count, nativeState: fixture.get('count')};
  }, {data: () => ({...initial(), count: R.ref(1)})});
  // Actual prototype dependencies are separate from the migration engine manifest.
  const fingerprints = Object.fromEntries([
    __filename, path.join(__dirname, 'runtime.cjs'),
    frontendRequire.resolve('@vue/runtime-core/dist/runtime-core.cjs.js'),
    frontendRequire.resolve('@vue/reactivity/dist/reactivity.cjs.js'),
    path.join(project, 'research/public_instance_v1/runtime.cjs'),
    engineRequire.resolve('san/dist/san.dev.js')
  ].map(file => [path.relative(project, file).replaceAll('\\', '/'),
    createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
  return {schema_version: 4, status: 'render_scheduled_prototype_partial_compatibility_not_production',
    versions: {vue: Vue.version, san: san.version}, fingerprints,
    matched_cases: cases.length, cases, gaps, production_admission_eligible: false,
    arbitrary_public_key_contract_complete: false,
    native_browser_render_verified: false, model_calls: 0, live_database_writes: 0,
    source_or_generated_components_modified: false,
    standalone_reactivity_kernel_used: true,
    node_render_barrier_is_test_double: true,
    description: 'Standalone reactive-kernel prototype; not a full Vue private-instance graph or production admission.'};
}

if (require.main === module) {
  run().then(result => {
  if (process.argv.length > 2) {
    assert.equal(process.argv[2], '--output');
    const output = path.resolve(process.argv[3]);
    assert.ok(output.startsWith(path.join(project, 'var') + path.sep), 'Evidence must stay inside project/var');
    fs.mkdirSync(path.dirname(output), {recursive: true});
    fs.writeFileSync(output, JSON.stringify(result, null, 2), {flag: 'wx'});
    console.log(JSON.stringify({status: result.status, matched_cases: result.matched_cases, gaps: result.gaps}, null, 2));
  } else console.log(JSON.stringify(result));
  }).catch(error => {console.error(error.stack); process.exitCode = 1;});
}
module.exports = {run, fixture, observe};
