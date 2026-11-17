/* Root-owner research bridge. No parent tree, transitions or production loader. */
'use strict';
const {PrototypeCapabilityError} = require('../public_instance_v1/runtime.cjs');
const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
const supported = new Set(['beforeMount', 'mounted', 'beforeUpdate', 'updated', 'beforeUnmount', 'unmounted']);

function connectRootOwner(runtime, handle, hooks = {}) {
  const decline = reason => {throw new PrototypeCapabilityError(reason);};
  if (handle.runtime !== runtime || typeof handle.connectOwner !== 'function') decline('owner handle mismatch');
  if (runtime.owner || runtime.parent || runtime.transition || runtime.aNode?.directives?.transition || runtime.source?.directives?.transition) {
    decline('root owner without parent or transition required');
  }
  if (runtime.lifeCycle?.attached || runtime.lifeCycle?.disposed) decline('owner must connect before attachment');
  const callbacks = {};
  for (const name of Reflect.ownKeys(hooks)) {
    if (!supported.has(name)) decline(`unimplemented owner hook: ${String(name)}`);
    callbacks[name] = Array.isArray(hooks[name]) ? [...hooks[name]] : [hooks[name]];
    if (!callbacks[name].every(fn => typeof fn === 'function')) decline('owner hooks must be functions');
  }
  const names = ['attach', '_update', 'dispose', 'detach'];
  const originals = {}, descriptors = {};
  // Preflight every override before modifying the native instance.
  for (const name of names) {
    originals[name] = runtime[name]; descriptors[name] = Object.getOwnPropertyDescriptor(runtime, name);
    if (typeof originals[name] !== 'function' || descriptors[name]?.configurable === false || !Object.isExtensible(runtime)) {
      decline(`native owner descriptor: ${name}`);
    }
  }
  let state = 'created', connection;
  const run = name => {
    for (const fn of callbacks[name] || []) connection.callHook(fn, `${name} hook`);
  };
  const updated = () => {if (state === 'mounted') run('updated');};
  const wrappers = {
    attach(...args) {
      if (this !== runtime) return originals.attach.apply(this, args);
      if (state === 'mounted') return undefined;
      if (state !== 'created') decline('owner cannot remount after disposal');
      state = 'mounting'; run('beforeMount');
      const result = originals.attach.apply(runtime, args);
      connection.markMounted(); state = 'mounted'; run('mounted');
      return result;
    },
    _update(...args) {
      if (this !== runtime) return originals._update.apply(this, args);
      if (state !== 'mounted') return originals._update.apply(runtime, args);
      // Native _update may be called without real local data changes.
      const changed = !!runtime._dataChanges;
      if (changed) run('beforeUpdate');
      const result = originals._update.apply(runtime, args);
      if (changed && callbacks.updated?.length) connection.enqueueUpdated(updated);
      return result;
    },
    dispose(...args) {
      if (this !== runtime) return originals.dispose.apply(this, args);
      if (state === 'disposed' || state === 'unmounting') return undefined;
      if (state === 'mounting') decline('dispose during beforeMount is unproven');
      state = 'unmounting';
      // beforeUnmount observes live scope and old DOM; cleanup follows it.
      run('beforeUnmount');
      connection.release();
      let result;
      try {result = originals.dispose.apply(runtime, args); run('unmounted');}
      finally {
        connection.markUnmounted(); state = 'disposed';
        // Keep this instance's idempotent dispose/attach guards. Restore only
        // the update hook: already-queued tasks still safely see disposed San.
        if (runtime._update === wrappers._update) {
          if (descriptors._update) Object.defineProperty(runtime, '_update', descriptors._update);
          else delete runtime._update;
        }
      }
      return result;
    },
    detach(...args) {
      if (this !== runtime) return originals.detach.apply(this, args);
      // San's own synchronous dispose calls detach internally. This is not an
      // externally requested detach/KeepAlive operation.
      if (state === 'unmounting') return originals.detach.apply(runtime, args);
      decline('native detach is not root Vue unmount or KeepAlive');
    }
  };
  connection = handle.connectOwner(() => wrappers.dispose.call(runtime));
  for (const name of names) Object.defineProperty(runtime, name, {
    value: wrappers[name], configurable: true, writable: true, enumerable: descriptors[name]?.enumerable ?? false
  });
  return Object.freeze({get state() {return state;},
    attach(...args) {return wrappers.attach.apply(runtime, args);},
    dispose(...args) {return wrappers.dispose.apply(runtime, args);},
    status: 'root_owner_research_not_production'});
}
module.exports = {connectRootOwner};
