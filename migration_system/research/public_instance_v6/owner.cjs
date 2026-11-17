/* Finite synchronous San owner families, not a complete Vue component tree. */
'use strict';
const {PrototypeCapabilityError} = require('../public_instance_v1/runtime.cjs');
const owners = new WeakMap(), idle = Promise.resolve();
const supported = new Set(['beforeMount','mounted','beforeUpdate','updated','beforeUnmount','unmounted']);
const decline = reason => {throw new PrototypeCapabilityError(reason);};

function createFamily() {
  const family = {records: new Set(), mounting: null, disposing: null, pendingUnmounts: new Set(), completion: null};
  family.tick = () => {
    if (family.completion) return family.completion;
    if (![...family.records].some(record => record.connection.hasPending())) return idle;
    family.completion = (async () => {
      while ([...family.records].some(record => record.connection.hasPending())) {
        await Promise.all([...family.records].map(record => record.connection.tick()));
      }
    })().finally(() => {family.completion = null;});
    return family.completion;
  };
  return family;
}

function connectComponentOwner(runtime, handle, hooks = {}, rootOnly = false) {
  if (handle.runtime !== runtime || typeof handle.connectOwner !== 'function' || owners.has(runtime)) decline('owner handle mismatch or duplicate');
  const parent = runtime.owner ? owners.get(runtime.owner) : null;
  if ((runtime.owner && !parent) || (!parent && runtime.parent) || (rootOnly && (runtime.owner || runtime.parent))) decline('unregistered native parent owner');
  if (parent && !['mounting','mounted'].includes(parent.state)) decline('parent is not live');
  if (runtime.transition || runtime.aNode?.directives?.transition || runtime.source?.directives?.transition) decline('owner transitions unproven');
  if (runtime.lifeCycle?.attached || runtime.lifeCycle?.disposed) decline('owner must connect before attachment');
  const callbacks = {};
  for (const name of Reflect.ownKeys(hooks)) {
    if (!supported.has(name)) decline('unimplemented owner hook: ' + String(name));
    callbacks[name] = Array.isArray(hooks[name]) ? [...hooks[name]] : [hooks[name]];
    if (!callbacks[name].every(fn => typeof fn === 'function')) decline('owner hooks must be functions');
  }
  const names = ['attach','_update','dispose','detach'], originals = {}, descriptors = {};
  for (const name of names) {
    originals[name] = runtime[name]; descriptors[name] = Object.getOwnPropertyDescriptor(runtime, name);
    if (typeof originals[name] !== 'function' || descriptors[name]?.configurable === false || !Object.isExtensible(runtime)) decline('native owner descriptor: ' + name);
  }
  const family = parent ? parent.family : createFamily();
  const record = {runtime, handle, parent, family, children: new Set(), state: 'created', updating: false, connection: null};
  const run = name => {for (const fn of callbacks[name] || []) record.connection.callHook(fn, name + ' hook');};
  const updated = () => {if (record.state === 'mounted') run('updated');};
  const finishUnmount = () => {
    try {run('unmounted');}
    finally {
      record.connection.markUnmounted(); record.state = 'disposed';
      family.records.delete(record); parent?.children.delete(record);
      if (runtime._update === wrappers._update) {
        if (descriptors._update) Object.defineProperty(runtime, '_update', descriptors._update); else delete runtime._update;
      }
    }
  };
  const wrappers = {
    attach(...args) {
      if (this !== runtime) return originals.attach.apply(this, args);
      if (record.state === 'mounted') return;
      if (record.state !== 'created') decline('owner cannot remount after disposal');
      const outer = !parent && !family.mounting;
      if (outer) family.mounting = [];
      record.state = 'mounting'; run('beforeMount');
      // Vue inserts the root container after its descendants are constructed.
      // Build a real detached DOM subtree, then insert once before mounted.
      let result;
      if (outer && args[0]?.ownerDocument) {
        const fragment = args[0].ownerDocument.createDocumentFragment();
        result = originals.attach.call(runtime, fragment);
        args[0].insertBefore(fragment, args[1] || null);
      } else result = originals.attach.apply(runtime, args);
      record.connection.markMounted(); record.state = 'mounted';
      const mounted = () => {if (record.state === 'mounted') run('mounted');};
      if (family.mounting) family.mounting.push(mounted);
      else if (parent) parent.connection.enqueueUpdated(mounted);
      else mounted();
      if (outer) {
        const jobs = family.mounting; family.mounting = null;
        for (const job of jobs) job();
      }
      return result;
    },
    _update(...args) {
      if (this !== runtime) return originals._update.apply(this, args);
      if (record.state !== 'mounted') return originals._update.apply(runtime, args);
      const changed = !!runtime._dataChanges;
      if (changed) run('beforeUpdate');
      record.updating = true;
      let result;
      try {result = originals._update.apply(runtime, args);} finally {record.updating = false;}
      if (changed && callbacks.updated?.length) record.connection.enqueueUpdated(updated);
      return result;
    },
    dispose(...args) {
      if (this !== runtime) return originals.dispose.apply(this, args);
      if (['unmounting','disposed'].includes(record.state)) return;
      if (record.state === 'mounting') decline('dispose during beforeMount is unproven');
      const outer = !family.disposing;
      if (outer) {
        family.disposing = [];
        for (const frame of family.pendingUnmounts) family.disposing.push(...frame);
        family.pendingUnmounts.clear();
      }
      record.state = 'unmounting'; run('beforeUnmount'); record.connection.release();
      // Native bulk disposal walks children in reverse and may leave their DOM
      // visible until the root is removed. Dispose registered siblings in their
      // actual current DOM order, retaining post-order unmounted callbacks.
      const children = [...record.children].filter(child => !['unmounting','disposed'].includes(child.state)).sort((a,b) => {
        const position = a.runtime.el?.compareDocumentPosition(b.runtime.el);
        return position & 4 ? -1 : position & 2 ? 1 : 0;
      });
      // Keep descendant DOM until the parent bulk removal, as in the source
      // root unmount, while still running forward sibling cleanup order.
      for (const child of children) child.runtime.dispose(1, 1);
      const result = originals.dispose.apply(runtime, args);
      family.disposing.push(finishUnmount);
      if (outer) {
        const jobs = family.disposing; family.disposing = null;
        const flush = () => {if (family.pendingUnmounts.delete(jobs)) for (const job of jobs) job();};
        family.pendingUnmounts.add(jobs);
        if (parent && parent.state === 'mounted') parent.connection.enqueueUpdated(flush);
        else flush();
      }
      return result;
    },
    detach(...args) {
      if (this !== runtime || record.state === 'unmounting') return originals.detach.apply(this, args);
      decline('native detach is not Vue unmount or KeepAlive');
    }
  };
  record.connection = handle.connectOwner(() => wrappers.dispose.call(runtime));
  if (parent) record.connection.linkParent(parent.connection);
  record.connection.setTickCoordinator(family.tick);
  for (const name of names) Object.defineProperty(runtime, name, {value: wrappers[name], configurable: true, writable: true,
    enumerable: descriptors[name]?.enumerable ?? false});
  family.records.add(record); parent?.children.add(record); owners.set(runtime, record);
  return Object.freeze({get state() {return record.state;}, attach(...args) {return wrappers.attach.apply(runtime, args);},
    dispose(...args) {return wrappers.dispose.apply(runtime, args);}, status: 'native_owner_family_research_not_production'});
}
function connectRootOwner(runtime, handle, hooks) {return connectComponentOwner(runtime, handle, hooks, true);}
module.exports = {connectRootOwner, connectComponentOwner};
