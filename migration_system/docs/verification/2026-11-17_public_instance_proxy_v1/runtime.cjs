/* Compatibility prototype, NOT a production runtime or an admission waiver.
 * No Vue dependency; the compatibility harness alone loads Vue as an oracle.
 * The public receiver and native San receiver are different objects by design.
 */
'use strict';

const hasOwn = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
const path = key => ({type: 4, paths: [{type: 1, value: key}]});

// Pinned Vue 3.5.45 Options instance slot NAMES, not allowed business keys.
// These affect Vue's `$name` write rejection. They do not implement the private
// Vue instance graph. Reading that graph must fail explicitly in this prototype.
const INSTANCE_FIELDS = new Set([
  'uid', 'vnode', 'type', 'parent', 'appContext', 'root', 'next', 'subTree',
  'effect', 'update', 'job', 'scope', 'render', 'proxy', 'exposed', 'exposeProxy',
  'withProxy', 'provides', 'ids', 'accessCache', 'renderCache', 'components',
  'directives', 'propsOptions', 'emitsOptions', 'emit', 'emitted', 'propsDefaults',
  'inheritAttrs', 'ctx', 'data', 'props', 'attrs', 'slots', 'refs', 'setupState',
  'setupContext', 'suspense', 'suspenseId', 'asyncDep', 'asyncResolved',
  'isMounted', 'isUnmounted', 'isDeactivated', 'bc', 'c', 'bm', 'm', 'bu', 'u',
  'um', 'bum', 'da', 'a', 'rtg', 'rtc', 'ec', 'sp'
]);
const PUBLIC_NAMES = [
  '$', '$el', '$data', '$props', '$attrs', '$slots', '$refs', '$parent', '$root',
  '$host', '$emit', '$options', '$forceUpdate', '$nextTick', '$watch'
];

class PrototypeCapabilityError extends Error {
  constructor(capability) {
    super(`Public-instance prototype has not implemented: ${capability}`);
    this.name = 'PrototypeCapabilityError';
    this.code = 'public_instance_prototype_unproven';
    this.capability = capability;
  }
}

function createPublicInstance(runtime, {stateKeys, props = {}, methods = {}, computed = {}, warn = () => {}}) {
  const store = runtime.data;
  if (!store || typeof store.get !== 'function' || typeof store.set !== 'function') {
    throw new TypeError('A native San Data receiver is required');
  }
  if (!Array.isArray(stateKeys)) throw new TypeError('Compiler-declared state keys are required');
  const state = {};
  for (const key of stateKeys) {
    if (typeof key !== 'string' && typeof key !== 'symbol') throw new TypeError('Invalid declared state key');
    Object.defineProperty(state, key, {
      value: store.get(path(key)), writable: true, enumerable: true, configurable: true
    });
  }
  // The captured native Data object is never looked up through the public
  // receiver. `data`, `watch`, and every other business key remain writable.
  const data = new Proxy(state, {
    get(target, key, receiver) {
      return hasOwn(target, key) ? store.get(path(key)) : Reflect.get(target, key, receiver);
    },
    set(target, key, value) {
      if (!Reflect.set(target, key, value, target)) return false;
      store.set(path(key), value);
      return true;
    },
    deleteProperty(target, key) {
      if (!Reflect.deleteProperty(target, key)) return false;
      if (hasOwn(store.raw, key)) {
        store.set(path(key), undefined);
        Reflect.deleteProperty(store.raw, key);
      }
      return true;
    },
    getOwnPropertyDescriptor(target, key) {
      const descriptor = Reflect.getOwnPropertyDescriptor(target, key);
      if (descriptor && descriptor.configurable && 'value' in descriptor) {
        return {...descriptor, value: store.get(path(key))};
      }
      return descriptor;
    }
  });
  const ctx = {};
  const globalProperties = {};
  let instance;
  const unsupported = name => {throw new PrototypeCapabilityError(name);};
  Object.defineProperty(ctx, '_', {configurable: true, enumerable: false,
    get: () => unsupported('Vue private instance graph')});
  const publicGetters = Object.assign(Object.create(null), {
    $: () => unsupported('Vue private instance graph'),
    $data: () => data,
    $props: () => unsupported('shallow-readonly props reflection'),
    $el: () => runtime.el,
    $host: () => undefined,
    $parent: () => unsupported('component ancestry'),
    $root: () => unsupported('component ancestry'),
    $emit: () => unsupported('Vue event error/argument policy'),
    $options: () => unsupported('merged Options identity'),
    $forceUpdate: () => unsupported('Vue update queue'),
    $nextTick: () => unsupported('Vue update queue'),
    $watch: () => unsupported('Vue watcher queue')
  });
  for (const name of PUBLIC_NAMES) {
    Object.defineProperty(ctx, name, {configurable: true, enumerable: false,
      get: () => (publicGetters[name] || (() => unsupported(name)))(), set() {}});
  }
  const cache = Object.create(null);
  instance = new Proxy(ctx, {
    get(target, key) {
      if (key === '__v_skip' || key === '__isVue') return true;
      if (key[0] !== '$') {
        const cached = cache[key];
        if (cached === 'data') return data[key];
        if (cached === 'props') return props[key];
        if (cached === 'ctx') return target[key];
        if (hasOwn(state, key)) {cache[key] = 'data'; return data[key];}
        if (hasOwn(props, key)) {cache[key] = 'props'; return props[key];}
        if (hasOwn(target, key)) {cache[key] = 'ctx'; return target[key];}
      }
      if (hasOwn(publicGetters, key)) return publicGetters[key]();
      if (hasOwn(target, key)) {cache[key] = 'ctx'; return target[key];}
      return undefined;
    },
    set(target, key, value) {
      if (hasOwn(state, key)) {data[key] = value; return true;}
      if (hasOwn(props, key)) {
        warn(`Attempting to mutate prop "${String(key)}". Props are readonly.`);
        return false;
      }
      if (key[0] === '$' && (INSTANCE_FIELDS.has(key.slice(1)) || key.slice(1) in Object.prototype)) {
        warn(`Attempting to mutate public property "${key}". Properties starting with $ are reserved and readonly.`);
        return false;
      }
      // Native assignment performs context setters/prototype semantics. Key
      // coercion already occurred ONCE before entering this Proxy trap.
      // Vue also takes this branch for inherited Object.prototype names in
      // its default globalProperties object. In particular __proto__ becomes
      // an OWN literal context property, not a prototype mutation.
      if (key in globalProperties) {
        Object.defineProperty(target, key, {enumerable: true, configurable: true, value});
      } else target[key] = value;
      return true;
    },
    has(target, key) {
      return !!(cache[key] || (key[0] !== '$' && hasOwn(state, key)) ||
        hasOwn(props, key) || hasOwn(target, key) || PUBLIC_NAMES.includes(key));
    },
    defineProperty(target, key, descriptor) {
      if (descriptor.get != null) cache[key] = undefined;
      else if (hasOwn(descriptor, 'value')) this.set(target, key, descriptor.value);
      return Reflect.defineProperty(target, key, descriptor);
    }
  });
  for (const key of Reflect.ownKeys(props)) {
    Object.defineProperty(ctx, key, {enumerable: true, configurable: true, get: () => props[key], set() {}});
  }
  for (const [name, fn] of Object.entries(methods)) {
    if (typeof fn !== 'function') throw new TypeError(`Non-callable source method: ${name}`);
    Object.defineProperty(ctx, name, {value: fn.bind(instance), enumerable: true, writable: true, configurable: true});
  }
  for (const key of stateKeys) {
    if (typeof key === 'string' && key[0] !== '_' && key[0] !== '$') {
      Object.defineProperty(ctx, key, {enumerable: true, configurable: true, get: () => data[key], set() {}});
    }
  }
  for (const [name, option] of Object.entries(computed)) {
    const get = typeof option === 'function' ? option : option.get;
    const set = typeof option === 'object' && option.set;
    Object.defineProperty(ctx, name, {enumerable: true, configurable: true,
      get: () => get.call(instance, instance),
      set: value => set ? set.call(instance, value) : warn(`Write operation failed: computed property "${name}" is readonly.`)});
  }
  // Not stored on `instance`, not a discoverable magic property or Symbol.
  // Loaders own this handle; public methods and San internals have separate receivers.
  return Object.freeze({instance, runtime, data,
    status: 'compatibility_prototype_not_production',
    invoke(name, ...args) {return instance[name](...args);},
    dispose() {return runtime.dispose();}});
}

module.exports = {createPublicInstance, PrototypeCapabilityError, INSTANCE_FIELDS};
