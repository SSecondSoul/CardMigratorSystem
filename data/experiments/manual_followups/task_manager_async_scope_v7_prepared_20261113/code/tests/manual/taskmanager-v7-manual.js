/* Standalone full-template manual acceptance. Never rewrites frozen sources. */
(function () {
  'use strict';
  const framework = document.body.dataset.framework;
  const projectRoot = new URL('../../', location.href);
  const manifestPath = 'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113/manifest.json';
  const status = document.getElementById('audit-status');
  const logNode = document.getElementById('audit-log');
  const storagePrefix = 'cardmig:taskmanager-async-scope-v7-manual:' + framework + ':';
  const businessStorageKey = 'task_manager_data';
  const originalConsoleError = console.error.bind(console);
  let failNextSave = false;
  let app = null;
  let disposed = false;
  let ready = false;
  const logs = [];

  function log(kind, text) {
    logs.push(new Date().toLocaleTimeString() + ' [' + kind + '] ' + text);
    logNode.textContent = logs.slice(-100).join('\n');
  }
  function reportError(error, _subject, info) {
    // Only logs plain Error/info into external DOM, not component reactive data.
    const text = error && (error.stack || error.message) || String(error);
    log('组件错误', String(info || '') + '\n' + text);
    originalConsoleError(error);
  }
  function localURL(path) {
    const url = new URL(path, projectRoot);
    if (url.origin !== projectRoot.origin || !url.pathname.startsWith(projectRoot.pathname)) {
      throw new Error('拒绝加载项目外资源：' + path);
    }
    return url;
  }
  async function checkedText(asset) {
    const response = await fetch(localURL(asset.path), {cache: 'no-store'});
    if (!response.ok) throw new Error('资源加载失败：' + asset.path + ' / HTTP ' + response.status);
    const bytes = await response.arrayBuffer();
    const sum = await crypto.subtle.digest('SHA-256', bytes);
    const hex = Array.from(new Uint8Array(sum), b => b.toString(16).padStart(2, '0')).join('');
    if (hex !== asset.sha256) throw new Error('文件指纹不匹配，停止加载：' + asset.path);
    return new TextDecoder('utf-8', {fatal: true}).decode(bytes);
  }
  function evaluate(code, requireFn, storage) {
    const module = {exports: {}};
    const requireLocal = requireFn || (name => {throw new Error('不支持的依赖：' + name);});
    new Function('module', 'exports', 'require', 'process', 'localStorage', code)(
      module, module.exports, requireLocal, {env: {NODE_ENV: 'development'}}, storage
    );
    return module.exports;
  }
  function splitSfc(source) {
    const template = /<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(source);
    const script = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(source);
    if (!template || !script) throw new Error('SFC缺少完整template或script');
    return {template: template[1], script: script[1],
      styles: Array.from(source.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style\s*>/gi), m => m[1])};
  }
  const storage = Object.freeze({
    getItem(key) { return window.localStorage.getItem(storagePrefix + key); },
    setItem(key, value) {
      if (failNextSave) {
        failNextSave = false;
        document.getElementById('audit-fail').textContent = '让下一次保存故意失败（可选异常验收）';
        log('故障注入', '已触发一次保存失败；后续保存恢复正常。');
        throw new Error('ManualAcceptanceStorageWriteFailure');
      }
      return window.localStorage.setItem(storagePrefix + key, value);
    },
    removeItem(key) { return window.localStorage.removeItem(storagePrefix + key); }
  });

  window.addEventListener('error', event => log('window.error', event.error && (event.error.stack || event.error.message) || event.message));
  window.addEventListener('unhandledrejection', event => log('未处理拒绝', String(event.reason && (event.reason.stack || event.reason.message) || event.reason)));
  document.getElementById('audit-clear-log').addEventListener('click', () => {logs.length = 0; logNode.textContent = '尚无日志。';});
  document.getElementById('audit-fail').addEventListener('click', () => {
    failNextSave = !failNextSave;
    document.getElementById('audit-fail').textContent = failNextSave ? '已设置下一次保存失败（再点取消）' : '让下一次保存故意失败（可选异常验收）';
    log('故障注入', failNextSave ? '已启用一次保存失败；请在组件里修改设置或任务。' : '已取消。');
  });
  document.getElementById('audit-reset').addEventListener('click', () => {
    if (!ready || !window.confirm('只清空当前' + framework + '验收页的隔离数据并重新加载，继续吗？')) return;
    // Never call localStorage.clear() or remove the original application's key.
    failNextSave = false;
    cleanup(); // beforeDestroy may save; remove the isolated key afterwards.
    storage.removeItem(businessStorageKey);
    location.reload();
  });
  function cleanup() {
    if (disposed) return;
    disposed = true;
    if (framework === 'vue') app && app.$destroy();
    else app && app.dispose();
  }
  window.addEventListener('pagehide', cleanup);

  (async function () {
    if (!['vue', 'san'].includes(framework)) throw new Error('未知验收框架');
    if (!['http:', 'https:'].includes(location.protocol)) throw new Error('请通过本地HTTP服务器打开，不要双击file://页面。');
    if (!crypto.subtle) throw new Error('浏览器无法校验SHA-256；请使用localhost或127.0.0.1。');
    const response = await fetch(localURL(manifestPath), {cache: 'no-store'});
    if (!response.ok) throw new Error('请先准备验收资源：manifest HTTP ' + response.status);
    const manifest = await response.json();
    if (manifest.schema_version !== 1 || manifest.component !== 'TaskManager' || manifest.manual_status !== 'awaiting_user') {
      throw new Error('非预期验收manifest；停止加载。');
    }
    const config = manifest.frameworks[framework];
    const [runtimeSource, componentSource] = await Promise.all([checkedText(config.runtime), checkedText(config.component)]);
    const runtime = evaluate(runtimeSource);
    if (runtime.version !== config.version) throw new Error('框架版本不匹配：' + runtime.version);
    const sfc = splitSfc(componentSource);
    for (const css of sfc.styles) {
      const style = document.createElement('style'); style.textContent = css; document.head.appendChild(style);
    }
    const host = document.getElementById('component-host');
    if (framework === 'vue') {
      if (typeof runtime.compile !== 'function') throw new Error('需要含模板编译器的Vue 2.7.16完整构建');
      runtime.config.errorHandler = reportError;
      const options = evaluate(sfc.script, null, storage);
      if (options.props && Object.keys(options.props).length) throw new Error('本验收协议没有声明父组件props');
      // Keep complete parent and inline-child templates; do not replace render.
      options.template = sfc.template;
      const Subject = runtime.extend(options);
      app = new runtime({render: h => h(Subject)});
      app.$mount(); host.appendChild(app.$el);
    } else {
      const Subject = evaluate(sfc.script, name => {
        if (name !== 'san') throw new Error('仅支持require("san")：' + name);
        return runtime;
      }, storage);
      if (typeof Subject !== 'function' || typeof Subject.prototype.inited !== 'function') throw new Error('候选没有预期的San组件/生命周期');
      Subject.template = sfc.template; Subject.prototype.template = sfc.template;
      const originalInited = Subject.prototype.inited;
      Subject.prototype.inited = function () {
        originalInited.call(this);
        this.__watcherScope_v7Configure({
          channel: 'async-parent-watch', environment: 'browser', trackingPolicy: 'no-reactive-reads-or-writes',
          parentOf: component => component.parentComponent,
          // This isolated application declares no source ancestor capture hooks.
          // Do not infer Vue errorCaptured semantics from San.error.
          hooksOf: () => [], globalHandler: () => reportError, logError: reportError
        });
      };
      const App = runtime.defineComponent({template: '<div><task-manager></task-manager></div>', components: {'task-manager': Subject}});
      app = new App(); app.attach(host);
    }
    ready = true;
    document.getElementById('audit-reset').disabled = false;
    document.getElementById('audit-fail').disabled = false;
    status.textContent = '已加载 ' + framework + ' ' + runtime.version + '；组件SHA256 ' + config.component.sha256.slice(0, 16) + '…；等待人工验收。';
    log('加载', '完整父/子模板、原样式；存储前缀 ' + storagePrefix + '；未使用模拟业务timer。');
  })().catch(error => {
    status.textContent = '加载失败：' + (error.message || error);
    reportError(error, null, 'manual-runner-load'); cleanup();
  });
})();
