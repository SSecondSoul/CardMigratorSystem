/* Source Vue async-watch oracle vs retained San and an in-memory naive move. No production rewrite. */
'use strict';
const fs = require('fs'), vm = require('vm'), crypto = require('crypto');
const parser = require('@babel/parser'), generate = require('@babel/generator').default;
const {parentOf} = require('./utils/inline_identifier_recovery.cjs');
const EPOCH = Date.UTC(2026, 10, 11, 12);
const clone = value => JSON.parse(JSON.stringify(value));
const script = text => /<script\b[^>]*>([\s\S]*?)<\/script>/.exec(text)[1];

function naiveEarly(code) {
    const text = script(code), ast = parser.parse(text, {sourceType: 'unambiguous'});
    const parent = parentOf(ast), hook = name => parent.properties.find(p => p.key.name === name);
    const init = hook('inited'), attached = hook('attached');
    const registrations = attached.body.body.filter(s => s.type === 'ExpressionStatement'
        && s.expression.type === 'CallExpression' && s.expression.callee.type === 'MemberExpression'
        && s.expression.callee.object.type === 'ThisExpression' && s.expression.callee.property.name === 'watch');
    if (registrations.length !== 2 || init.body.body.length !== 0) throw new Error('Unexpected frozen lifecycle shape');
    // Counterfactual only: show why simply moving identical registration statements is insufficient.
    init.body.body.push(...registrations);
    attached.body.body = attached.body.body.filter(s => !registrations.includes(s));
    return generate(ast).code;
}

function sandbox() {
    let events = [], store = new Map(), intervals = new Map(), timeouts = new Map();
    let intervalId = 0, timeoutId = 1000, phase = 'construct';
    const warnings = [], errors = [];
    class FixedDate extends Date {constructor(...args) {super(...(args.length ? args : [EPOCH]));} static now() {return EPOCH;}}
    const log = event => events.push(clone({phase, ...event}));
    const context = vm.createContext({Date: FixedDate, Promise,
        process: {env: {NODE_ENV: 'development'}},
        console: {log() {}, warn: (...args) => warnings.push(args.join(' ')), error: (...args) => errors.push(args.join(' '))},
        setInterval(callback, delay) {const id = ++intervalId; intervals.set(id, {callback, delay}); log({kind: 'interval-start', id, delay}); return id;},
        clearInterval(id) {const existed = intervals.delete(id); log({kind: 'interval-clear', id, existed});},
        setTimeout(callback, delay) {const id = ++timeoutId; timeouts.set(id, {callback, delay}); return id;},
        clearTimeout(id) {timeouts.delete(id);},
        localStorage: {
            getItem(key) {log({kind: 'storage-read', key}); return store.has(key) ? store.get(key) : null;},
            setItem(key, text) {const value = JSON.parse(text); log({kind: 'storage-write', key, value}); store.set(key, text);}
        }});
    // No browser globals/MessageChannel: actual framework Promise scheduler, not a hand-written watcher queue.
    context.global = context;
    return {context, log, warnings, errors,
        initialize(value) {if (value !== null) store.set('task_manager_data', value);},
        phase(value) {phase = value; events = [];},
        events: () => clone(events),
        stored: () => {const text = store.get('task_manager_data'); if (!text) return null; try {return JSON.parse(text);} catch (_) {return {malformed: text};}},
        timers: () => [...intervals.values()].map(t => t.delay).sort((a, b) => a - b),
        pendingNotificationTimeouts: () => [...timeouts.values()].filter(t => t.delay === 3000).length};
}

function evaluate(text, env, requireFunction) {
    env.context.__module = {exports: {}};
    env.context.__require = requireFunction || (() => {throw new Error('Unexpected Vue runtime dependency');});
    vm.runInContext('(function(module,exports,require){\n' + text + '\n})(__module,__module.exports,__require)', env.context, {timeout: 5000});
    const exported = env.context.__module.exports;
    delete env.context.__module; delete env.context.__require;
    return exported;
}

function sourceOptions(code, env) {return evaluate(script(code), env);}
function hookTrace(options, name, env) {
    const original = options[name];
    if (typeof original !== 'function') throw new Error('Missing source hook: ' + name);
    options[name] = function (...args) {env.log({kind: 'hook', name}); return original.apply(this, args);};
}
const methods = ['loadInitialData', 'updateStatistics', 'saveToLocalStorage', 'startAutoSync', 'updateSyncInterval', 'showNotification'];
function traceMethods(object, env) {
    for (const name of methods) {
        const original = object[name];
        object[name] = function (...args) {env.log({kind: 'call', name}); return original.apply(this, args);};
    }
}

async function runOne(input, variant, scenario) {
    const env = sandbox(); env.initialize(scenario.value);
    let instance, runtime, read, setTitle, spliceRows, destroy, constructionEvents;
    if (variant === 'vue_source') {
        runtime = evaluate(input.vueRuntime, env);
        if (runtime.version !== '2.7.16' || runtime.config.async !== true) throw new Error('Expected pinned default-async Vue 2.7.16');
        runtime.config.warnHandler = message => env.warnings.push(message);
        runtime.config.errorHandler = error => env.errors.push(String(error));
        const options = sourceOptions(input.vue, env);
        traceMethods(options.methods, env); hookTrace(options, 'mounted', env); hookTrace(options, 'beforeDestroy', env);
        for (const field of ['tasks', 'settings']) {
            const original = options.watch[field].handler;
            options.watch[field].handler = function (...args) {env.log({kind: 'watch-callback', field}); return original.apply(this, args);};
        }
        const nativeWatch = runtime.prototype.$watch;
        runtime.prototype.$watch = function (field, listener, options) {
            env.log({kind: 'watch-register', field, taskCount: this.tasks.length, autoSave: this.settings.autoSave});
            return nativeWatch.call(this, field, listener, options);
        };
        // Real root lifecycle + watcher scheduler, dummy render/no-op headless patch. No child/DOM/UI claim.
        options.render = h => h('section');
        instance = new runtime(options);
        constructionEvents = env.events();
        env.phase('mount_sync'); instance.$mount();
        read = field => instance[field];
        setTitle = value => {if (instance.tasks.length) instance.tasks[0].title = value;};
        spliceRows = row => instance.tasks.splice(0, 1, row);
        destroy = () => instance.$destroy();
    }
    else {
        runtime = evaluate(input.sanRuntime, env);
        const nativeWatch = runtime.Component.prototype.watch;
        runtime.Component.prototype.watch = function (field, listener, ...ignored) {
            env.log({kind: 'watch-register', field, taskCount: this.data.get('tasks').length, autoSave: this.data.get('settings.autoSave')});
            return nativeWatch.call(this, field, function (...args) {env.log({kind: 'watch-callback', field}); return listener.apply(this, args);}, ...ignored);
        };
        const Parent = evaluate(variant === 'san_naive_early' ? naiveEarly(input.code) : script(input.code), env,
            name => {if (name !== 'san') throw new Error('Unexpected component require'); return runtime;});
        Parent.prototype.template = /<template\b[^>]*>([\s\S]*?)<\/template>/.exec(input.code)[1];
        traceMethods(Parent.prototype, env);
        for (const name of ['inited', 'attached', 'disposed']) {
            const original = Parent.prototype[name];
            Parent.prototype[name] = function (...args) {env.log({kind: 'hook', name}); return original.apply(this, args);};
        }
        instance = new Parent(); constructionEvents = env.events(); env.phase('mount_sync'); instance.attached();
        read = field => instance.data.get(field);
        setTitle = value => {if (read('tasks').length) instance.data.set('tasks[0].title', value);};
        // Keep inserted arrays/objects in the framework's realm.
        spliceRows = row => {env.context.__instance = instance; env.context.__row = JSON.stringify(row);
            vm.runInContext("__instance.data.splice('tasks',[0,1,JSON.parse(__row)])", env.context);};
        destroy = () => instance.dispose(true, true);
    }
    const drain = async () => {await new Promise(resolve => runtime.nextTick(resolve)); await new Promise(resolve => runtime.nextTick(resolve));};
    const phases = [];
    const capture = name => phases.push({name, events: env.events(), state: {
        tasks: clone(read('tasks')), settings: clone(read('settings')),
        statistics: clone(read('statistics')).map(s => s.value), stored: env.stored(),
        activeIntervalDelays: env.timers(), pendingNotificationTimeouts: env.pendingNotificationTimeouts(),
        frameworkDisposed: variant === 'vue_source' ? !!instance._isDestroyed : !!instance.lifeCycle.disposed}});
    capture('mount_sync'); env.phase('mount_tick'); await drain(); capture('mount_tick');
    async function phase(name, action) {
        env.phase(name + '_sync'); action(); capture(name + '_sync');
        env.phase(name + '_tick'); await drain(); capture(name + '_tick');
    }
    await phase('nested_twice', () => {setTitle('draft-one'); setTitle('draft-two');});
    await phase('settings_before_tasks', () => {instance.updateSettings('syncInterval', 30);
        instance.updateSettings('defaultView', 'board'); setTitle('combined-final');});
    await phase('autosave_off', () => {instance.updateSettings('autoSave', false); setTitle('not-saved');});
    await phase('autosave_on', () => {instance.updateSettings('autoSave', true); setTitle('saved-one'); setTitle('saved-two');});
    await phase('splice', () => spliceRows({id: 91, title: 'replacement', description: '', completed: true, tags: [], priority: 'low', dueDate: ''}));
    await phase('manual_interval', () => instance.updateSettings('syncInterval', 0));
    env.phase('destroy_before_flush_sync'); instance.updateSettings('syncInterval', 30); destroy(); capture('destroy_before_flush_sync');
    env.phase('destroy_before_flush_tick'); await drain(); capture('destroy_before_flush_tick');
    await phase('post_destroy_change', () => setTitle('after-destroy'));
    if (env.errors.length || env.warnings.length) throw new Error('Unexpected framework warning/error: '+JSON.stringify({warnings:env.warnings,errors:env.errors}));
    return {scenario: scenario.name, variant, phases, constructionEvents,
        frameworkVersion: runtime.version,
        boundary: {vueRealRootMount: variant === 'vue_source', sourceDummyRender: variant === 'vue_source',
            sanFullAttach: false, sanApplicationHookInvokedDirectly: variant !== 'vue_source',
            sanFrameworkDisposeExecuted: variant !== 'vue_source',
            realApplicationTimers: false, realStorage: false, browser: false,
            notificationTimeoutCallbacksExecuted: false, naiveEarlyIsProductionFix: false}};
}

async function audit(input) {
    const task = {id: 10, title: 'saved', description: '', completed: false, tags: [], priority: 'medium', dueDate: ''};
    const saved = (autoSave, syncInterval) => JSON.stringify({tasks: [task], settings: {autoSave, syncInterval, defaultView: 'list', notifications: true}});
    const scenarios = [{name:'empty',value:null}, {name:'saved_manual',value:saved(true,0)},
        {name:'saved_autosave_off',value:saved(false,30)}, {name:'saved_interval_30',value:saved(true,30)},
        {name:'malformed',value:'{broken'}];
    const runs = [];
    for (const scenario of scenarios) for (const variant of ['vue_source','san_current','san_naive_early']) {
        runs.push(await runOne(input, variant, scenario));
    }
    return {runs, scenarios: scenarios.map(s => s.name), variants:['vue_source','san_current','san_naive_early'],
        epoch:EPOCH, nodeVersion:process.version,
        vueRuntimeSha256:crypto.createHash('sha256').update(input.vueRuntime).digest('hex'),
        sanRuntimeSha256:crypto.createHash('sha256').update(input.sanRuntime).digest('hex'),
        productionRuleChanged:false, modelRequests:0, browserUsed:false,
        limitations:['Vue dummy root render does not exercise source template/child/DOM events.',
            'San attached application hook is direct; native headless dispose is executed but no DOM attach/removal is exercised.',
            'Application timers/storage are fakes; Promise watcher queues are real framework implementations.',
            'Vue 2.7.16 is pinned for diagnosis, not proof of browser unversioned vue@2 patch version.',
            'Naive early registration exists only as an in-memory counterfactual, not a production fix.',
            'Notification timeout callbacks are not fired/cleared by this harness; do not claim all timers cleaned.']};
}
if (require.main === module) audit(JSON.parse(fs.readFileSync(0,'utf8')))
    .then(result => process.stdout.write(JSON.stringify(result))).catch(error => {process.stderr.write(error.stack);process.exitCode=1;});
module.exports={audit};
