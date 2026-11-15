/* Diagnostic only: execute frozen methods and installed San declarations, no DOM/UI. */
'use strict';
const fs = require('fs');
const crypto = require('crypto');
const parser = require('@babel/parser');
const generate = require('@babel/generator').default;
// Expose one bundled internal function in memory only. Directly requiring San's
// unbundled parser internals hits their CommonJS circular-dependency build order.
const bundlePath = require.resolve('san/dist/san.dev.js');
const bundle = fs.readFileSync(bundlePath, 'utf8');
if (bundle.split('var san = {').length !== 2) throw new Error('Unexpected San bundle export shape');
const instrumented = {exports: {}};
new Function('require', 'module', 'exports', bundle.replace('var san = {',
    'var san = {__auditGetEventListener: getEventListener,'))(require, instrumented, instrumented.exports);
const san = instrumented.exports;
const parseTemplate = san.parseTemplate;
const getEventListener = san.__auditGetEventListener;

function audit(input) {
    const script = text => /<script\b[^>]*>([\s\S]*?)<\/script>/.exec(text)[1];
    const ast = parser.parse(script(input.vue), {sourceType: 'module'});
    const exported = ast.program.body.find(n => n.type === 'ExportDefaultDeclaration');
    const parent = exported ? exported.declaration : ast.program.body.find(n =>
        n.type === 'ExpressionStatement' && n.expression.type === 'AssignmentExpression'
        && generate(n.expression.left).code === 'module.exports').expression.right;
    const prop = (object, name) => object.properties.find(p => (p.key.name || p.key.value) === name);
    const method = (object, name) => {
        const value = prop(object, name);
        if (!value) throw new Error('Missing frozen source method: ' + name);
        return new Function(...value.params.map(p => generate(p).code), generate(value.body).code.slice(1, -1));
    };
    const sourceMethods = prop(parent, 'methods').value;
    const sourceChild = ast.program.body.filter(n => n.type === 'VariableDeclaration')
        .flatMap(n => n.declarations).find(n => n.id.name === 'TaskItem').init;
    const moduleObject = {exports: {}};
    new Function('require', 'module', script(input.code))(name => {
        if (name !== 'san') throw new Error('Unexpected component dependency: ' + name);
        return san;
    }, moduleObject);
    const Parent = moduleObject.exports;
    Parent.prototype.template = /<template\b[^>]*>([\s\S]*?)<\/template>/.exec(input.code)[1];
    const Child = Parent.prototype.components['task-item'];
    const savedGlobals = {};
    for (const name of ['localStorage', 'setInterval', 'clearInterval', 'setTimeout', 'clearTimeout']) {
        savedGlobals[name] = Object.getOwnPropertyDescriptor(globalThis, name);
    }
    let events = [], storage = new Map(), intervals = new Map(), timeouts = new Map(), nextId = 1;
    globalThis.localStorage = {
        getItem(key) { events.push({kind: 'storage-read', key}); return storage.get(key) || null; },
        setItem(key, text) {
            const value = JSON.parse(text);
            events.push({kind: 'storage-write', key, count: value.tasks.length, autoSave: value.settings.autoSave});
            storage.set(key, text);
        }
    };
    globalThis.setInterval = (callback, delay) => {
        const id = nextId++; intervals.set(id, {callback, delay});
        events.push({kind: 'interval-start', delay}); return id;
    };
    globalThis.clearInterval = id => { intervals.delete(id); events.push({kind: 'interval-clear'}); };
    globalThis.setTimeout = (callback, delay) => {
        const id = nextId++; timeouts.set(id, {callback, delay}); return id;
    };
    globalThis.clearTimeout = id => timeouts.delete(id);
    const lifecycle = [];
    try {
        for (const scenario of ['empty', 'saved', 'saved-autosave-off', 'malformed']) {
            events = []; storage = new Map(); intervals = new Map(); timeouts = new Map();
            if (scenario === 'malformed') storage.set('task_manager_data', '{broken');
            if (scenario.startsWith('saved')) storage.set('task_manager_data', JSON.stringify({
                tasks: [{id: 10, title: 'saved', completed: false, tags: [], dueDate: ''}],
                settings: {syncInterval: 0, autoSave: scenario !== 'saved-autosave-off'}
            }));
            const instance = new Parent();
            const registrations = [];
            const nativeWatch = instance.watch;
            instance.watch = function (field, listener, ...options) {
                registrations.push({field, taskCount: this.data.get('tasks').length,
                    afterLoad: events.some(e => e.kind === 'call' && e.name === 'loadInitialData'),
                    ignoredThirdOptions: options[0]});
                events.push({kind: 'watch-register', field});
                return nativeWatch.call(this, field, function (...args) {
                    events.push({kind: 'watch-callback', field}); return listener.apply(this, args);
                }, ...options);
            };
            for (const name of ['loadInitialData', 'updateStatistics', 'saveToLocalStorage', 'updateSyncInterval']) {
                const original = instance[name];
                instance[name] = function (...args) { events.push({kind: 'call', name}); return original.apply(this, args); };
            }
            // Invoke the actual application hook directly, not San attach or a DOM lifecycle.
            instance.attached();
            const initial = {
                taskCount: instance.data.get('tasks').length,
                statisticsTotal: instance.data.get('statistics')[0].value,
                saves: events.filter(e => e.kind === 'storage-write').length,
                watchCallbacks: events.filter(e => e.kind === 'watch-callback').length,
                registrations, events: events.slice(), activeIntervals: intervals.size,
                syncInterval: instance.data.get('settings.syncInterval')
            };
            events = [];
            instance.data.set('tasks[0].title', 'edited');
            instance.updateSettings('syncInterval', 0);
            const afterEdit = {events: events.slice(), activeIntervals: intervals.size};
            events = [];
            instance.disposed();
            const afterDisposed = {events: events.slice(), activeIntervals: intervals.size};
            lifecycle.push({scenario, initial, afterEdit, afterDisposed});
        }

        // Runtime observation, not an emulation of Vue's async/deep watcher queue.
        const Watch = san.defineComponent({template: '<div/>', initData() {return {rows: [{title: 'a'}]};}});
        const w = new Watch(), changes = [];
        w.watch('rows', (value, info) => changes.push({type: info.change.type, title: value[0]?.title}), {deep: true, immediate: true});
        const immediateCount = changes.length;
        w.data.set('rows[0].title', 'nested');
        const nestedCount = changes.length;
        w.data.get('rows')[0].title = 'direct';
        const directMutationCount = changes.length;
        w.data.set('rows', w.data.get('rows'));
        const sameReferenceCount = changes.length;
        w.data.splice('rows', [0, 1, {title: 'splice'}]);
        const watcher = {formalArgumentCount: san.Component.prototype.watch.length, immediateCount, nestedCount,
            directMutationCount, sameReferenceCount, spliceCount: changes.length,
            directMutationNotObserved: directMutationCount === nestedCount, changes};

        function nodes(root) {return [root, ...(root.children || []).flatMap(nodes)];}
        const outer = parseTemplate(/<template\b[^>]*>([\s\S]*?)<\/template>/.exec(input.code)[1]);
        const itemNode = nodes(outer).find(n => n.tagName === 'task-item');
        const listNode = nodes(outer).find(n => n.events?.some(e => e.name === 'drop' && e.expr.name.paths[0].value === 'onDropToEnd'));
        const itemRoot = parseTemplate(Child.prototype.template).children.find(n => n.tagName);
        const rows = ['a', 'b', 'c', 'd', 'e', 'f', 'g'].map((id, i) => ({id, title: id, tags: [],
            completed: i % 2 === 0, priority: 'medium', dueDate: '', description: ''}));
        const drag = [];
        for (const operation of ['onto-down', 'onto-up', 'list-end', 'self', 'cancel', 'disabled']) {
            const p = new Parent();
            p.data.set('tasks', rows.slice()); p.data.set('currentFilter', 'active');
            const notes = []; p.showNotification = (...args) => notes.push(args);
            const indices = operation === 'onto-up' ? [1, 0] : [0, 1];
            const children = indices.map(index => {
                const child = new Child({data: {task: p.data.get('filteredTasks')[index], index,
                    draggable: operation !== 'disabled'}});
                // Bind actual parsed declarations using the installed San listener and emitter.
                for (const declaration of itemNode.events) {
                    child.on(declaration.name, getEventListener(declaration, p, p.data, 1));
                }
                return child;
            });
            const calls = [];
            const event = () => ({dataTransfer: {effectAllowed: null,
                setData(...args) {calls.push({kind: 'setData', args});}},
                preventDefault() {calls.push({kind: 'prevent'});},
                stopPropagation() {calls.push({kind: 'stop'});}});
            const dispatch = (node, name, owner, e) => {
                const declaration = node.events.find(d => d.name === name);
                if (!declaration) throw new Error('Missing parsed event ' + name);
                return getEventListener(declaration, owner, owner.data, 0)(e);
            };
            const firstEvent = event(); dispatch(itemRoot, 'dragstart', children[0], firstEvent);
            const startIndex = p.data.get('dragStartIndex');
            let bubblePrevented = null;
            if (operation === 'list-end') {
                dispatch(listNode, 'dragover', p, event()); dispatch(listNode, 'drop', p, event());
            }
            else if (['onto-down', 'onto-up', 'self'].includes(operation)) {
                dispatch(itemRoot, 'dragover', children[1], event());
                dispatch(itemRoot, 'drop', children[operation === 'self' ? 0 : 1], event());
                bubblePrevented = calls.some(c => c.kind === 'stop');
            }
            dispatch(itemRoot, 'dragend', children[0], event());
            const sourceContext = {tasks: rows.slice(), filteredTasks: rows.filter(t => !t.completed),
                dragStartIndex: operation === 'disabled' ? null : indices[0],
                showNotification() {}};
            if (!['cancel', 'disabled'].includes(operation)) method(sourceMethods, 'moveTask')
                .call(sourceContext, sourceContext.dragStartIndex, operation === 'self' ? indices[0] :
                    operation === 'list-end' ? sourceContext.filteredTasks.length - 1 : indices[1], operation === 'list-end');
            drag.push({operation, startIndex, finalDragIndex: p.data.get('dragStartIndex'),
                order: p.data.get('tasks').map(t => t.id), sourceExpectedOrder: sourceContext.tasks.map(t => t.id),
                oldArrayUnchanged: rows.map(t => t.id).join('') === 'abcdefg',
                elementIdentitiesPreserved: p.data.get('tasks').every(t => rows.includes(t)),
                bubblePrevented, notes, calls, dataTransferEffectAllowed: firstEvent.dataTransfer.effectAllowed});
        }
        const sourceTransfer = [];
        const sourceEvent = {dataTransfer: {effectAllowed: null,
            setData(...args) {sourceTransfer.push(args);}}};
        const sourceStart = method(prop(sourceChild, 'methods').value, 'onDragStart');
        const sourceEmits = [];
        sourceStart.call({draggable: true, index: 0, $emit: (...args) => sourceEmits.push(args)}, sourceEvent);
        const sourceDisabled = [];
        sourceStart.call({draggable: false, index: 0, $emit: (...args) => sourceDisabled.push(args)},
            {dataTransfer: {setData() {throw new Error('Disabled source should not write');}}});

        const watcherKeys = prop(parent, 'watch').value.properties.map(p => p.key.name || p.key.value);
        const sourceLifecycle = {watcherKeys, deepWatchers: watcherKeys.filter(name =>
            prop(prop(parent, 'watch').value, name).value.properties.some(p => p.key.name === 'deep' && p.value.value === true)),
            mounted: generate(prop(parent, 'mounted')).code,
            beforeDestroy: generate(prop(parent, 'beforeDestroy')).code,
            vueRuntimeExecuted: false,
            sourceWatchOrdering: 'declarative Vue watch before mounted; not runtime-verified here'};
        return {lifecycle, watcher, drag,
            sourceDragStart: {setData: sourceTransfer, effectAllowed: sourceEvent.dataTransfer.effectAllowed,
                emitted: sourceEmits, disabledEmitted: sourceDisabled}, sourceLifecycle,
            sanVersion: require('san/package.json').version, nodeVersion: process.version,
            sanBundleSha256: crypto.createHash('sha256').update(fs.readFileSync(bundlePath)).digest('hex'),
            sanEventListenerExposure: 'in-memory export only; original bundled function body unchanged',
            boundary: {browserUsed: false, realTimersUsed: false, realStorageUsed: false,
                nativeDragGestureExecuted: false, fullSanAttachExecuted: false, hookInvokedDirectly: true,
                productionCodeChanged: false, newBatchOrManualAcceptance: false},
            loadedModuleSha256: Object.fromEntries(Object.keys(require.cache).filter(p => p.startsWith(process.cwd()))
                .sort().map(p => [p.slice(process.cwd().length + 1).replace(/\\/g, '/'),
                    crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')]))};
    }
    finally {
        for (const [name, descriptor] of Object.entries(savedGlobals)) {
            if (descriptor) Object.defineProperty(globalThis, name, descriptor); else delete globalThis[name];
        }
    }
}
if (require.main === module) {
    process.stdout.write(JSON.stringify(audit(JSON.parse(fs.readFileSync(0, 'utf8')))));
}
module.exports = {audit};
