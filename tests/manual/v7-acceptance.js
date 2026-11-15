/* Reusable local full-template acceptance shell. No business-code patching. */
(function () {
  'use strict';
  const projectRoot = new URL('../../', location.href);
  const params = new URL(location.href).searchParams;
  const framework = params.get('framework') || 'san';
  const node = id => document.getElementById('acceptance-' + id);
  const originalConsoleError = console.error.bind(console);
  const logs = [];
  let app = null, disposed = false, ready = false, failNextSave = false;
  let manifest = null, selected = null, storagePrefix = '';

  function log(kind, message) {
    logs.push(new Date().toLocaleTimeString() + ' [' + kind + '] ' + message);
    if (logs.length > 200) logs.shift();
    node('log').textContent = logs.join('\n');
  }
  function reportError(error, _subject, info) {
    const text = error && (error.stack || error.message) || String(error);
    log('组件错误', String(info || '') + '\n' + text);
    originalConsoleError(error);
  }
  function localURL(path) {
    if (typeof path !== 'string' || !path || path.startsWith('/') || path.includes('\\') ||
        path.split('/').some(part => part === '..' || part === '.') || /[?#]/.test(path)) {
      throw new Error('非法项目相对路径：' + path);
    }
    const url = new URL(path, projectRoot);
    if (url.origin !== projectRoot.origin || !url.pathname.startsWith(projectRoot.pathname) || url.search || url.hash) {
      throw new Error('拒绝加载项目外资源：' + path);
    }
    return url;
  }
  async function jsonFile(path) {
    const response = await fetch(localURL(path), {cache: 'no-store'});
    if (!response.ok) throw new Error('配置加载失败：' + path + ' / HTTP ' + response.status);
    return response.json();
  }
  async function checkedText(asset) {
    if (!asset || !/^[a-f0-9]{64}$/.test(asset.sha256)) throw new Error('资源缺少有效 SHA-256');
    const response = await fetch(localURL(asset.path), {cache: 'no-store'});
    if (!response.ok) throw new Error('资源加载失败：' + asset.path + ' / HTTP ' + response.status);
    const bytes = await response.arrayBuffer();
    const sum = await crypto.subtle.digest('SHA-256', bytes);
    const actual = Array.from(new Uint8Array(sum), b => b.toString(16).padStart(2, '0')).join('');
    if (actual !== asset.sha256) throw new Error('文件指纹不匹配，停止加载：' + asset.path);
    return new TextDecoder('utf-8', {fatal: true}).decode(bytes);
  }
  function evaluate(source, requireLocal, storage) {
    const module = {exports: {}};
    const requireFn = requireLocal || (name => {throw new Error('不支持的依赖：' + name);});
    new Function('module', 'exports', 'require', 'process', 'localStorage', source)(
      module, module.exports, requireFn, {env: {NODE_ENV: 'development'}}, storage
    );
    return module.exports;
  }
  function splitSfc(source) {
    const template = /<template\b[^>]*>([\s\S]*?)<\/template\s*>/i.exec(source);
    const script = /<script\b[^>]*>([\s\S]*?)<\/script\s*>/i.exec(source);
    if (!template || !script) throw new Error('SFC 缺少 template 或 script');
    return {template: template[1], script: script[1],
      styles: Array.from(source.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style\s*>/gi), m => m[1])};
  }
  function pageURL(caseId, targetFramework) {
    const url = new URL(location.href);
    url.search = ''; url.hash = '';
    url.searchParams.set('case', caseId); url.searchParams.set('framework', targetFramework);
    return url;
  }
  function link(id, url, label) {
    node(id).href = url.href;
    if (label) node(id).textContent = label;
    node(id).hidden = false;
  }
  function cleanup() {
    if (disposed) return;
    disposed = true;
    if (!app) return;
    if (framework === 'vue') app.$destroy();
    else app.dispose();
  }
  function disableFaultInjection() {
    failNextSave = false;
    node('fail').textContent = '让下一次保存故意失败（可选）';
  }
  const storage = Object.freeze({
    getItem(key) { return window.localStorage.getItem(storagePrefix + key); },
    setItem(key, value) {
      if (failNextSave) {
        disableFaultInjection(); log('故障注入', '已触发一次保存失败，后续保存恢复正常。');
        throw new Error('ManualAcceptanceStorageWriteFailure');
      }
      return window.localStorage.setItem(storagePrefix + key, value);
    },
    removeItem(key) { return window.localStorage.removeItem(storagePrefix + key); }
  });
  function configureSanAdapter(Subject, adapter) {
    if (adapter === 'none') return;
    if (adapter !== 'v7-parent-watch-report-only' || typeof Subject.prototype.inited !== 'function') {
      throw new Error('未支持的 San 验收适配配置：' + adapter);
    }
    const originalInited = Subject.prototype.inited;
    Subject.prototype.inited = function () {
      originalInited.call(this);
      if (typeof this.__watcherScope_v7Configure !== 'function') {
        throw new Error('候选不包含 v7 私有 watcher 配置接口；不能伪装为适配成功');
      }
      this.__watcherScope_v7Configure({
        channel: 'async-parent-watch', environment: 'browser', trackingPolicy: 'no-reactive-reads-or-writes',
        parentOf: component => component.parentComponent,
        // This profile explicitly declares no ancestor capture hooks. It is
        // not proof of arbitrary component ancestry or production integration.
        hooksOf: () => [], globalHandler: () => reportError, logError: reportError
      });
    };
  }
  window.addEventListener('error', event => log('window.error', event.error && (event.error.stack || event.error.message) || event.message));
  window.addEventListener('unhandledrejection', event => log('未处理拒绝', String(event.reason && (event.reason.stack || event.reason.message) || event.reason)));
  window.addEventListener('pagehide', cleanup);
  node('clear-log').addEventListener('click', () => {logs.length = 0; node('log').textContent = '尚无日志。';});
  node('copy-log').addEventListener('click', async () => {
    const info = [node('title').textContent, location.href, node('identity').textContent,
      node('boundary').textContent, node('status').textContent, ...logs].join('\n');
    try { await navigator.clipboard.writeText(info); log('工具栏', '已复制验收信息与日志。'); }
    catch (error) { log('工具栏', '无法复制，请手动复制日志区：' + error.message); }
  });
  node('fail').addEventListener('click', () => {
    if (!ready) return;
    failNextSave = !failNextSave;
    node('fail').textContent = failNextSave ? '已启用一次保存失败（再点取消）' : '让下一次保存故意失败（可选）';
    log('故障注入', failNextSave ? '下一次保存故意失败；请在组件中修改设置或任务。' : '已取消。');
  });
  node('reset').addEventListener('click', () => {
    if (!ready || !window.confirm('只清空本验收项 ' + framework + ' 的隔离数据并重新加载，继续吗？')) return;
    disableFaultInjection(); cleanup(); // disposal may save, so delete afterwards
    manifest.storage_keys.forEach(key => storage.removeItem(key));
    location.reload();
  });

  (async function () {
    if (!['http:', 'https:'].includes(location.protocol)) throw new Error('请通过本地 HTTP 服务打开，不要双击 file:// 页面。');
    if (!['vue', 'san'].includes(framework)) throw new Error('framework 只支持 vue / san');
    if (!crypto.subtle) throw new Error('无法校验 SHA-256，请使用 localhost 或 127.0.0.1');
    const registry = await jsonFile('tests/manual/v7-acceptance-config.json');
    if (registry.schema_version !== 1 || !Array.isArray(registry.cases) || !registry.cases.length ||
        registry.cases.some(c => !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(c.id) || typeof c.label !== 'string') ||
        new Set(registry.cases.map(c => c.id)).size !== registry.cases.length) throw new Error('无效或重复的验收项配置');
    const caseId = params.get('case') || registry.default_case;
    selected = registry.cases.find(c => c.id === caseId);
    if (!selected) throw new Error('未知验收项：' + caseId);
    registry.cases.forEach(c => {
      const option = document.createElement('option'); option.value = c.id; option.textContent = c.label;
      node('case').appendChild(option);
    });
    node('case').value = selected.id; node('framework').value = framework;
    node('case').disabled = node('framework').disabled = false;
    node('case').addEventListener('change', () => location.assign(pageURL(node('case').value, framework).href));
    node('framework').addEventListener('change', () => location.assign(pageURL(selected.id, node('framework').value).href));
    link('counterpart', pageURL(selected.id, framework === 'vue' ? 'san' : 'vue'), '打开 ' + (framework === 'vue' ? 'San' : 'Vue') + ' 对照页');
    link('manifest', localURL(selected.manifest));
    manifest = await jsonFile(selected.manifest);
    if (manifest.schema_version !== 1 || manifest.case_id !== selected.id || manifest.manual_status !== 'awaiting_user' ||
        !/^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$/.test(manifest.component_tag) ||
        !manifest.props || typeof manifest.props !== 'object' || Array.isArray(manifest.props) ||
        Object.keys(manifest.props).some(k => !/^[A-Za-z_$][\w$]*$/.test(k) || ['__proto__','constructor','prototype'].includes(k)) ||
        !['none', 'v7-parent-watch-report-only'].includes(manifest.san_adapter) ||
        !Array.isArray(manifest.storage_keys) || manifest.storage_keys.some(k => typeof k !== 'string' || !k) ||
        manifest.storage_namespace !== 'cardmig:v7-acceptance:' + selected.id + ':<framework>:') {
      throw new Error('manifest 身份、props、存储或适配边界不合法');
    }
    storagePrefix = manifest.storage_namespace.replace('<framework>', framework);
    node('title').textContent = selected.label + ' · ' + framework.toUpperCase();
    document.title = node('title').textContent;
    node('boundary').textContent = manifest.boundary;
    link('checklist', localURL(manifest.checklist));
    const config = manifest.frameworks[framework];
    if (!config || config.version !== (framework === 'vue' ? '2.7.16' : '3.15.6')) throw new Error('此入口仅支持 Vue 2.7.16 / San 3.15.6');
    node('identity').textContent = '候选：' + config.component.path + '；配置：' + manifest.san_adapter;
    const [runtimeSource, componentSource] = await Promise.all([checkedText(config.runtime), checkedText(config.component)]);
    const runtime = evaluate(runtimeSource);
    if (runtime.version !== config.version) throw new Error('实际运行时版本不匹配：' + runtime.version);
    const sfc = splitSfc(componentSource);
    sfc.styles.forEach(css => {const style = document.createElement('style'); style.textContent = css; document.head.appendChild(style);});
    const host = document.getElementById('component-host');
    if (framework === 'vue') {
      if (typeof runtime.compile !== 'function') throw new Error('必须使用含模板编译器的 Vue 完整构建');
      runtime.config.errorHandler = reportError;
      const options = evaluate(sfc.script, null, storage);
      options.template = sfc.template; // never substitute a minimal render
      const Subject = runtime.extend(options);
      app = new runtime({render: h => h(Subject, {props: manifest.props})});
      app.$mount(); host.appendChild(app.$el);
    } else {
      const Subject = evaluate(sfc.script, name => {
        if (name !== 'san') throw new Error('仅支持 require("san")，当前：' + name);
        return runtime;
      }, storage);
      if (typeof Subject !== 'function') throw new Error('San SFC 必须导出组件类');
      Subject.template = sfc.template; Subject.prototype.template = sfc.template;
      configureSanAdapter(Subject, manifest.san_adapter);
      const bindings = Object.keys(manifest.props).map(k => k + '="{{ acceptanceProps.' + k + ' }}"').join(' ');
      const App = runtime.defineComponent({
        template: '<div><' + manifest.component_tag + ' ' + bindings + '></' + manifest.component_tag + '></div>',
        components: {[manifest.component_tag]: Subject},
        initData() { return {acceptanceProps: manifest.props}; }
      });
      app = new App(); app.attach(host);
    }
    ready = true;
    node('reset').disabled = false;
    node('fail').disabled = !manifest.storage_keys.length;
    node('status').textContent = '已加载 ' + framework + ' ' + runtime.version + '；SHA-256 ' + config.component.sha256.slice(0, 16) + '…；等待你人工确认。';
    log('加载', '完整父/内联模板与原样式；隔离前缀 ' + storagePrefix + '；未替换业务计时器。');
  })().catch(error => {
    node('status').textContent = '加载失败：' + (error.message || error);
    reportError(error, null, 'acceptance-load'); cleanup();
  });
})();
