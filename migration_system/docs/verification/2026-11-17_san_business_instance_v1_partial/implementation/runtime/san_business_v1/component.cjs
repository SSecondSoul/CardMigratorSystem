'use strict';
const {createPublicInstance} = require('./runtime.cjs');
const {connectComponentOwner} = require('./owner.cjs');
const {PrototypeCapabilityError} = require('./errors.cjs');
const {installDOMPolicy,synchronizeClassPresence} = require('./dom.cjs');
const {registryFor} = require('./registry.cjs');
const handles = new WeakMap();
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const hooks = ['beforeMount', 'mounted', 'beforeUpdate', 'updated', 'beforeUnmount', 'unmounted'];
const supported = new Set(['name', 'props', 'data', 'methods', 'computed', 'watch', 'emits', 'inheritAttrs',
  'beforeCreate', 'created', ...hooks]);
const callHooks = (option, receiver) => {for (const fn of option ? [].concat(option) : []) fn.call(receiver);};
const camelize = name => name.replace(/-(\w)/g, (_, letter) => letter.toUpperCase());
const hyphenate = name => name.replace(/\B([A-Z])/g, '-$1').toLowerCase();
const reservedInput = new Set(['', 'key', 'ref', 'ref_for', 'ref_key', 'onVnodeBeforeMount', 'onVnodeMounted',
  'onVnodeBeforeUpdate', 'onVnodeUpdated', 'onVnodeBeforeUnmount', 'onVnodeUnmounted']);

function propDefinitions(options) {
  const definitions=Array.isArray(options.props) ? Object.fromEntries(options.props.map(name => [name, {}])) : options.props || {};
  return Object.fromEntries(Object.entries(definitions).map(([name,definition])=>[camelize(name),definition]));
}
function splitInputs(definitions, emitted, raw) {
  const props=Object.create(null),attrs={};
  const declared=new Set(Array.isArray(emitted)?emitted:Object.keys(emitted||{}));
  for(const [name,value]of Object.entries(raw)) {
    if(reservedInput.has(name)) {
      // These are public renderer callbacks, not ordinary attrs. Do not drop a
      // supplied callback merely because the current bridge cannot execute it.
      if(value!=null&&(name==='ref'||name.startsWith('onVnode')))throw new PrototypeCapabilityError('root renderer input: '+name);
      continue;
    }
    const normalized=camelize(name);
    if(own(definitions,normalized)){props[normalized]=value;continue;}
    // Match pinned Vue isEmitListener, NOT "all onX fields are listeners".
    // Undeclared onClick and lowercase onlower are observable through $attrs.
    let listener=false;
    if(emitted&&/^on[^a-z]/.test(name)) {
      let event=name.slice(2);if(event!=='Once')event=event.replace(/Once$/,'');
      listener=declared.has(event[0].toLowerCase()+event.slice(1))||declared.has(hyphenate(event))||declared.has(event);
    }
    if(!listener)attrs[name]=value;
  }
  return {props,attrs};
}
function resolveProps(definitions, raw, previousDefaults) {
  const props = {}, defaults = previousDefaults || Object.create(null);
  const optionFor = definition => typeof definition === 'function' || Array.isArray(definition) ? {type: definition} : definition || {};
  const needsCast = name => {const option=optionFor(definitions[name]);return own(option,'default')||[].concat(option.type||[]).includes(Boolean);};
  for(const name of Object.keys(raw))if(own(definitions,name)&&!needsCast(name))props[name]=raw[name];
  for (const [name, definition] of Object.entries(definitions)) {
    if(!needsCast(name))continue;
    const option = optionFor(definition);
    const types = [].concat(option.type || []);let value = raw[name];
    if (value === undefined && own(option, 'default')) {
      if (!own(defaults, name)) defaults[name] = typeof option.default === 'function' && option.type !== Function ?
        option.default.call(null, props) : option.default;
      value = defaults[name];
    }
    const boolean = types.indexOf(Boolean), string = types.indexOf(String);
    if (boolean >= 0) {
      if (!own(raw, name) && !own(option, 'default')) value = false;
      else if ((value === '' || value === name.replace(/\B([A-Z])/g, '-$1').toLowerCase()) && (string < 0 || boolean < string)) value = true;
    }
    props[name] = value;
  }
  for(const name of Object.keys(definitions))if(!own(props,name))props[name]=undefined;
  return {props, defaults};
}

// Input functions are source Options; template is the migrated San template.
// Neither Vue.createApp nor a Vue renderer is used to execute these functions.
function defineBusinessComponent(san, R, options, template, metadata = {}) {
  if (san.version !== '3.15.6') throw new PrototypeCapabilityError('unreviewed San runtime version');
  const registry=registryFor(san,R,metadata.reactivityHash);R=registry.kernel;
  for (const name of Reflect.ownKeys(options)) if (!supported.has(name)) throw new PrototypeCapabilityError('source option: ' + String(name));
  if (typeof options.data !== 'undefined' && typeof options.data !== 'function') throw new TypeError('data must be a function');
  if (options.inheritAttrs !== undefined && options.inheritAttrs !== false) throw new PrototypeCapabilityError('automatic attrs fallthrough not verified');
  const definitions = propDefinitions(options), methodNames = Object.keys(options.methods || {});
  const nativeMethods = Object.fromEntries([...new Set([...methodNames, '$emit', '$forceUpdate', '$nextTick', '$watch'])].map(name => [name, function(...args) {
    const handle = handles.get(this);
    if (!handle) throw new Error('business_receiver_not_initialized');
    return handle.instance[name](...args);
  }]));
  const Definition = san.defineComponent({template, ...nativeMethods, inheritAttrs: false, components: metadata.components || {},
    filters:{__businessDisplay:metadata.toDisplayString||String},
    initData() {return {};},
    inited() {
      const native = this, raw = {...native.data.raw};
      installDOMPolicy(native.aNode,metadata.domPolicy);
      const inputs=splitInputs(definitions,options.emits,raw);
      const {props, defaults} = resolveProps(definitions, inputs.props);
      const attrs = inputs.attrs;
      if (options.inheritAttrs !== false && Object.keys(attrs).length) throw new PrototypeCapabilityError('attrs fallthrough not verified');
      if (native.sourceSlots && Object.keys(native.sourceSlots).some(name => native.sourceSlots[name]?.length)) {
        throw new PrototypeCapabilityError('source slot receiver bridge not verified');
      }
      if(native.source?.events?.length)throw new PrototypeCapabilityError('native parent event argument bridge not verified');
      const refs = {};
      const errors = (error, receiver, phase) => {
        if (metadata.onError) return metadata.onError(error, receiver, phase);
        // Default errors remain visible; do not substitute successful values.
        throw error;
      };
      const handle = createPublicInstance(native, {reactivity: R, sourceData: options.data?{}:registry.emptyData, stateKeys: [], props,
        ownerRecordRegistry:registry.records,
        initialEmptyData:registry.emptyData,
        methods: options.methods, computed: options.computed, attrs, refs,
        sourceOptions: metadata.sourceTemplate === undefined ? options : {...options, template: metadata.sourceTemplate},
        eventProps: raw, warn: metadata.warn || (message => console.warn(message)), onError: errors,
        parseNativeExpr: san.parseExpr, evaluateNativeExpr: san.evalExpr, nextRender: callback => san.nextTick(callback),
        forceRender() {
          const keys = new Set([...Reflect.ownKeys(handle.data), ...Object.keys(options.computed || {}),
            ...Object.keys(options.methods || {}), ...Object.keys(definitions), ...Object.keys(handle.instance)]);
          // One native root notification for every actual source namespace root;
          // template dependency filtering and San's queue do the real DOM work.
          for (const key of keys) if (typeof key === 'string' && key !== '_') {
            native.data.fire({type: 1, expr: {type: 4, paths: [{type: 1, value: key}]}, value: native.data.get(key), option: {force: true}});
          }
        },
        beforeInitialize(vm) {callHooks(options.beforeCreate, vm);},
        initializeData: options.data ? vm=>options.data.call(vm,vm) : undefined
      });
      handles.set(native, handle);
      for (const [path, value] of Object.entries(options.watch || {})) for (const item of [].concat(value)) {
        const option = typeof item === 'function' || typeof item === 'string' ? {handler: item} : item;
        handle.instance.$watch(path, option);
      }
      callHooks(options.created, handle.instance);
      const nativeHooks = {};
      const syncRefs = () => {for (const name of metadata.refs || []) refs[name] = native.ref(name) || null;};
      for (const name of hooks) if (options[name]) nativeHooks[name] = [].concat(options[name]);
      nativeHooks.mounted = [syncRefs, ...(nativeHooks.mounted || [])];
      nativeHooks.updated = [syncRefs, ...(nativeHooks.updated || [])];
      nativeHooks.unmounted = [() => {for (const name of Object.keys(refs)) refs[name] = null;}, ...(nativeHooks.unmounted || [])];
      const prepareParentUpdate = changes => {
        if (native.source?.directives?.bind || native.attrs?.length || Object.keys(native.sourceSlots || {}).some(name => native.sourceSlots[name]?.length)) {
          throw new PrototypeCapabilityError('complex parent input update bridge');
        }
        const next = {...handle.instance.$props};
        for (const binding of native.binds || []) {
          if ([1, 2, 3].includes(binding.expr.type)) continue;
          const name=camelize(binding.name);
          if (!own(definitions, name) || binding.expr.type !== 4 ||
              binding.expr.paths.some(part => ![1, 2].includes(part.type))) {
            throw new PrototypeCapabilityError('parent input binding expression');
          }
          if (changes.some(change => change.expr?.paths?.[0]?.value === binding.expr.paths[0].value)) {
            next[name] = san.evalExpr(binding.expr, native.scope, native.owner);
          }
        }
        handle.updateProps(resolveProps(definitions, next, defaults).props);
      };
      connectComponentOwner(native, handle, nativeHooks, false, prepareParentUpdate,()=>synchronizeClassPresence(native),registry.owners);
    }
  });
  Object.defineProperty(Definition, 'business', {value: native => {
    const handle = handles.get(native);
    if (!handle || !(native instanceof Definition)) throw new TypeError('foreign business component');
    return handle;
  }});
  Object.defineProperty(Definition, 'contract', {value: 'san-business-instance-v1'});
  return Definition;
}
module.exports = {defineBusinessComponent, resolveProps, splitInputs};
