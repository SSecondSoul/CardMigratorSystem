/* Research v3: v2 plus transactional native control writes.
 * Not imported by production. No Vue component/renderer is used here.
 */
'use strict';

const {INSTANCE_FIELDS, PrototypeCapabilityError} = require('../public_instance_v1/runtime.cjs');
const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
const rootPath = key => ({type: 4, paths: [{type: 1, value: key}]});

function createQueue(nextRender) {
  const pre = new Set(), post = new Set();
  let pending = null, active = true;
  const drain = jobs => {
    while (jobs.size && active) {
      const job = jobs.values().next().value;
      jobs.delete(job);
      job();
    }
  };
  function schedule(job, flush) {
    if (!active) return;
    if (flush === 'sync') return job();
    (flush === 'post' ? post : pre).add(job);
    if (!pending) {
      pending = Promise.resolve().then(async () => {
        try {
          do {
            drain(pre);
            if (post.size && active) {
              await new Promise(resolve => nextRender(resolve));
              drain(post);
            }
          } while ((pre.size || post.size) && active);
        } finally {
          pending = null;
          pre.clear(); post.clear();
        }
      });
    }
  }
  return {
    schedule,
    tick(callback, receiver) {
      const promise = pending || Promise.resolve();
      return callback ? promise.then(callback.bind(receiver)) : promise;
    },
    stop() {active = false; pre.clear(); post.clear();}
  };
}

function createPublicInstance(runtime, {
  reactivity: R, sourceData, stateKeys, props = {}, methods = {}, computed = {},
  attrs = {}, slots = {}, refs = {}, sourceOptions, warn = () => {}, onError,
  nextRender = callback => queueMicrotask(callback), parseNativeExpr, evaluateNativeExpr
}) {
  if (!R || !['reactive', 'computed', 'watch', 'effectScope', 'track', 'effect'].every(key => typeof R[key] === 'function')) {
    throw new TypeError('The explicitly pinned standalone reactivity kernel is required');
  }
  const probeRaw = {value: 0}, probe = R.reactive(probeRaw);
  let hookObserved = false;
  const check = R.effect(() => R.track(probeRaw, 'get', 'value'), {
    onTrigger() {hookObserved = true;}
  });
  probe.value = 1; R.stop(check);
  if (!hookObserved) throw new PrototypeCapabilityError('pinned development reactive trigger hook');
  const store = runtime.data;
  if (!store || typeof store.get !== 'function' || typeof store.set !== 'function') throw new TypeError('Native San Data is required');
  if (!Array.isArray(stateKeys)) throw new TypeError('Compiler state layout is required');
  // Retain the actual source data object when supplied by the future compiler.
  // No per-read proxy wrappers: the kernel's identity/cache/ref rules stay intact.
  const rawState = sourceData || Object.fromEntries(stateKeys.map(key => [key, store.get(rootPath(key))]));
  if (store.raw === rawState) {
    // San retains the initData object. Separate its mirror BEFORE installing
    // reactive values, otherwise synchronization would mutate source raw data.
    const mirror = Object.create(Object.getPrototypeOf(rawState));
    Object.defineProperties(mirror, Object.getOwnPropertyDescriptors(rawState));
    store.raw = mirror;
  }
  const data = R.reactive(rawState), scope = R.effectScope(true), queue = createQueue(nextRender);
  const nativeGet = store.get, nativeSet = store.set, nativeRaw = store.raw;
  const getDescriptor = Object.getOwnPropertyDescriptor(store, 'get');
  const setDescriptor = Object.getOwnPropertyDescriptor(store, 'set');
  let internalWrite = 0, nativeTransaction = null;
  const virtualRaw = new Proxy(nativeRaw, {
    get(target, key, receiver) {
      return own(rawState, key) ? data[key] : Reflect.get(target, key, receiver);
    }
  });
  store.raw = virtualRaw;
  const objectReads = new WeakMap(), stringReads = new Map();
  function parseAccess(expr) {
    if (typeof expr === 'string') return parseNativeExpr ? parseNativeExpr(expr) : null;
    return expr;
  }
  function observedGet(expr, callee) {
    if (this !== store || !expr || internalWrite || !scope.active) return nativeGet.call(this, expr, callee);
    const parsed = parseAccess(expr), key = parsed?.paths?.[0]?.value;
    if (parsed?.type !== 4 || !own(rawState, key)) return nativeGet.call(this, expr, callee);
    const owner = callee || store;
    if (typeof owner !== 'object') return nativeGet.call(this, expr, callee);
    const cache = typeof expr === 'string' ? stringReads : objectReads;
    let receivers = cache.get(expr);
    if (!receivers) {receivers = new WeakMap(); cache.set(expr, receivers);}
    let effect = receivers.get(owner);
    if (!effect) {
      effect = scope.run(() => new R.ReactiveEffect(() => nativeGet.call(store, expr, callee)));
      let nestedChange = false;
      effect.onTrigger = event => {nestedChange = event.target !== rawState;};
      effect.scheduler = () => {
        // Root writes already have one root-mirror notification. Do not emit
        // a second native event merely because a view also read that root.
        if (nestedChange) syncRoot(key);
        nestedChange = false;
      };
      receivers.set(owner, effect);
    }
    // Track the ACTUAL native read, once. No recursive deep traversal or
    // separately re-evaluated source template/getter is introduced here.
    return effect.run();
  }
  function forwardedSet(expr, value, option) {
    if (this !== store || internalWrite || !scope.active) return nativeSet.call(this, expr, value, option);
    const parsed = parseAccess(expr), key = parsed?.paths?.[0]?.value;
    if (parsed?.type !== 4 || !own(rawState, key)) return nativeSet.call(this, expr, value, option);
    if (nativeTransaction) throw new PrototypeCapabilityError('reentrant native control write');
    // Native controls write THROUGH the source reactive object, not San's
    // immutableSet (which would break aliases, refs and source object identity).
    // Resolve every path before mutation. In particular, never create missing
    // parents: a source JS member assignment would fail there as well.
    const segments = parsed.paths.slice(1).map(part => {
      let property;
      if (part.type === 1 || part.type === 2) property = part.value;
      else {
        if (!evaluateNativeExpr) throw new PrototypeCapabilityError('native dynamic path evaluator');
        property = evaluateNativeExpr(part, store);
      }
      return Reflect.ownKeys({[property]: true})[0];
    });
    let receiver = data, property = key;
    for (const segment of segments) {
      receiver = receiver[property]; property = segment;
      if (receiver === null || (typeof receiver !== 'object' && typeof receiver !== 'function')) {
        throw new PrototypeCapabilityError('native write through non-object parent');
      }
    }
    const policy = option || {};
    // San controls have === / force semantics. Root/raw mutations continue to
    // use the reactive kernel's rules; silent affects San events, NOT $watch.
    if (receiver[property] === value && !policy.force) return undefined;
    const transaction = {roots: new Set(), root: key, policy};
    nativeTransaction = transaction;
    try {
      if (!Reflect.set(receiver, property, value)) throw new TypeError('Native control assignment failed');
      transaction.roots.add(key);
    } finally {
      nativeTransaction = null;
      // Synchronous source watcher side effects must not disappear. Flush every
      // touched root once, even if a later setter/watch callback throws.
      for (const root of transaction.roots) {
        syncRoot(root, root === key ? policy : undefined);
      }
    }
    return undefined;
  }
  store.get = observedGet;
  store.set = forwardedSet;
  const ctx = {}, globalProperties = {}, cache = Object.create(null), dirty = new Set();
  const unsupported = capability => {throw new PrototypeCapabilityError(capability);};
  let instance, disposed = false;
  const internal = {data, props: R.shallowReactive(props), attrs, slots, refs, ctx, accessCache: cache, scope,
    setupState: {}, parent: null, root: null, proxy: null,
    appContext: {config: {globalProperties}}, type: sourceOptions || {methods, computed},
    isMounted: false, isUnmounted: false};
  // A real, separate logical record, NOT a counterfeit Vue vnode/renderer graph.
  // Unimplemented known slots throw rather than returning invented success data.
  for (const field of INSTANCE_FIELDS) if (!own(internal, field)) {
    Object.defineProperty(internal, field, {enumerable: true, configurable: true,
      get: () => unsupported(`private instance slot: ${field}`)});
  }
  internal.root = internal;
  Object.defineProperty(ctx, '_', {configurable: true, enumerable: false, get: () => internal});
  function syncRoot(key, policy) {
    if (nativeTransaction) {nativeTransaction.roots.add(key); return;}
    const notification = policy || {force: true};
    let value;
    internalWrite++;
    R.pauseTracking();
    try {
      if (own(rawState, key)) {
        value = data[key];
        // Check native types without leaking internal mirror-write flags.
        nativeSet.call(store, rootPath(key), value, {force: true, silent: true});
      }
      else {
        nativeSet.call(store, rootPath(key), undefined, {force: true, silent: true});
        Reflect.deleteProperty(store.raw, key);
      }
    } finally {
      R.resetTracking(); internalWrite--;
    }
    // Listener-triggered writes must re-enter the bridge, not bypass it under
    // an internalWrite flag and silently fork the native/source state planes.
    if (!(notification.silent || notification.silence || notification.quiet)) {
      store.fire({type: 1, expr: rootPath(key), value, option: notification});
    }
  }
  // Root writes are mirrored without traversing values/getters. Nested aliases
  // and refs are tracked at observedGet's actual render/consumer read instead.
  let trackRoots;
  trackRoots = scope.run(() => R.effect(() => {
    R.track(rawState, 'iterate', R.ITERATE_KEY);
    for (const key of Reflect.ownKeys(rawState)) R.track(rawState, 'get', key);
  }, {
    onTrigger(event) {if (event.target === rawState) dirty.add(event.key);},
    scheduler() {
      trackRoots();
      const roots = [...dirty]; dirty.clear();
      for (const key of roots) syncRoot(key);
    }
  }));

  function publicWatch(source, callback, options) {
    if (disposed) return unsupported('watch registration after disposal');
    const getter = typeof source === 'string' ? () => {
      let value = instance;
      for (const segment of source.split('.')) {
        if (!value) break;
        value = value[segment];
      }
      return value;
    } : source.bind(instance, instance);
    if (typeof callback !== 'function') {options = callback; callback = callback.handler;}
    const policy = options || {}, bound = callback.bind(instance);
    return scope.run(() => R.watch(getter, bound, {
      ...policy,
      scheduler(job, first) {
        if (first && policy.flush !== 'post') job();
        else queue.schedule(job, policy.flush || 'pre');
      },
      onWarn: warn,
      // Parent/global routing and async rejection phases need a separate proof.
      // Do not swallow errors when no explicit test policy was provided.
      call: function callWatch(fn, type, args) {
        if (Array.isArray(fn)) return fn.map(item => callWatch(item, type, args));
        try {
          const result = args ? fn(...args) : fn();
          if (result && typeof result.then === 'function' && onError) {
            result.catch(error => onError(error, instance, type));
          }
          return result;
        }
        catch (error) {
          if (!onError) throw error;
          onError(error, instance, type);
          // Vue's error handler return is not a successful getter value.
          return undefined;
        }
      }
    }));
  }
  const getters = Object.assign(Object.create(null), {
    $: i => i, $data: i => i.data, $props: i => R.shallowReadonly(i.props),
    $attrs: i => R.shallowReadonly(i.attrs), $slots: i => R.shallowReadonly(i.slots),
    $refs: i => R.shallowReadonly(i.refs), $el: () => runtime.el, $host: () => undefined,
    $root: i => i.root.proxy, $parent: i => i.parent ? i.parent.proxy : null,
    $options: i => i.type,
    $nextTick: i => i.n || (i.n = callback => queue.tick(callback, instance)),
    $watch: () => publicWatch.bind(instance),
    $emit: () => unsupported('Vue event error/argument policy'),
    $forceUpdate: () => unsupported('Vue forced render queue')
  });
  for (const name of Object.keys(getters)) Object.defineProperty(ctx, name, {
    configurable: true, enumerable: false, get: () => getters[name](internal), set() {}
  });
  instance = new Proxy(ctx, {
    get(target, key) {
      if (key === '__v_skip' || key === '__isVue') return true;
      const i = target._;
      if (key[0] !== '$') {
        const cached = i.accessCache[key];
        if (cached === 'data') return i.data[key];
        if (cached === 'props') return i.props[key];
        if (cached === 'ctx') return i.ctx[key];
        if (own(i.data, key)) {i.accessCache[key] = 'data'; return i.data[key];}
        if (own(i.props, key)) {i.accessCache[key] = 'props'; return i.props[key];}
        if (own(i.ctx, key)) {i.accessCache[key] = 'ctx'; return i.ctx[key];}
      }
      if (own(getters, key)) return getters[key](i);
      if (own(i.ctx, key)) {i.accessCache[key] = 'ctx'; return i.ctx[key];}
      if (own(i.appContext.config.globalProperties, key)) return i.appContext.config.globalProperties[key];
    },
    set(target, key, value) {
      const i = target._;
      if (own(i.data, key)) {
        i.data[key] = value;
        return true;
      }
      if (own(i.props, key)) {
        warn(`Attempting to mutate prop "${String(key)}". Props are readonly.`); return false;
      }
      if (key[0] === '$' && key.slice(1) in i) {
        warn(`Attempting to mutate public property "${key}". Properties starting with $ are reserved and readonly.`); return false;
      }
      if (key in i.appContext.config.globalProperties) {
        Object.defineProperty(i.ctx, key, {enumerable: true, configurable: true, value});
      } else i.ctx[key] = value;
      return true;
    },
    has(target, key) {
      const i = target._;
      return !!(i.accessCache[key] || (key[0] !== '$' && own(i.data, key)) ||
        own(i.props, key) || own(i.ctx, key) || own(getters, key) || own(i.appContext.config.globalProperties, key));
    },
    defineProperty(target, key, descriptor) {
      if (descriptor.get != null) target._.accessCache[key] = undefined;
      else if (own(descriptor, 'value')) this.set(target, key, descriptor.value);
      return Reflect.defineProperty(target, key, descriptor);
    }
  });
  internal.proxy = instance;
  for (const key of Reflect.ownKeys(props)) Object.defineProperty(ctx, key, {
    enumerable: true, configurable: true, get: () => internal.props[key], set() {}
  });
  for (const [key, fn] of Object.entries(methods)) Object.defineProperty(ctx, key, {
    value: fn.bind(instance), writable: true, enumerable: true, configurable: true
  });
  for (const key of stateKeys) if (typeof key === 'string' && key[0] !== '_' && key[0] !== '$') {
    Object.defineProperty(ctx, key, {enumerable: true, configurable: true, get: () => data[key], set() {}});
  }
  for (const [name, option] of Object.entries(computed)) {
    const get = typeof option === 'function' ? option : option.get;
    const set = typeof option === 'object' && option.set;
    const ref = scope.run(() => R.computed({get: () => get.call(instance, instance),
      set: value => set ? set.call(instance, value) : warn(`Write operation failed: computed property "${name}" is readonly.`)}));
    Object.defineProperty(ctx, name, {enumerable: true, configurable: true,
      get: () => ref.value, set: value => {ref.value = value;}});
  }
  return Object.freeze({instance, runtime, data, scope,
    status: 'native_control_public_instance_v3_research_not_production',
    invoke(name, ...args) {return instance[name](...args);},
    nextTick(callback) {return queue.tick(callback, instance);},
    dispose() {
      if (disposed) return;
      disposed = true; queue.stop(); scope.stop(); internal.isUnmounted = true;
      if (store.get === observedGet) {
        if (getDescriptor) Object.defineProperty(store, 'get', getDescriptor); else delete store.get;
      }
      if (store.set === forwardedSet) {
        if (setDescriptor) Object.defineProperty(store, 'set', setDescriptor); else delete store.set;
      }
      if (store.raw === virtualRaw) store.raw = nativeRaw;
      return runtime.dispose();
    }
  });
}

module.exports = {createPublicInstance};
