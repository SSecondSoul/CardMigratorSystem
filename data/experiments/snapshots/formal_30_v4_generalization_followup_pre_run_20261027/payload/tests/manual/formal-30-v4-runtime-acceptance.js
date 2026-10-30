(function () {
  'use strict';

  const CONFIG_PATH = '../../migration_pipeline/interaction_configs/formal_30_v4_runtime_acceptance.json';
  const PROJECT_ROOT = new URL('../../', location.href);
  const host = document.getElementById('component-host');
  const report = document.getElementById('report');
  const sampleInput = document.getElementById('sample');
  const artifactInput = document.getElementById('artifact');
  const runButton = document.getElementById('run');
  const runtimeErrors = [];
  let config;
  let app;

  window.addEventListener('error', event => {
    runtimeErrors.push(String(event.error || event.message));
  });
  window.addEventListener('unhandledrejection', event => {
    runtimeErrors.push(String(event.reason));
  });

  function projectURL(path) {
    const url = new URL(path, PROJECT_ROOT);
    if (url.origin !== PROJECT_ROOT.origin || !url.pathname.startsWith(PROJECT_ROOT.pathname)) {
      throw new Error('产物路径必须位于当前项目内：' + path);
    }
    return url;
  }

  async function loadSanSfc(path) {
    const response = await fetch(projectURL(path));
    if (!response.ok) throw new Error('San 文件加载失败：' + path + ' (' + response.status + ')');
    const source = await response.text();
    const template = source.match(/<template\b[^>]*>([\s\S]*?)<\/template>/i);
    const script = source.match(/<script\b[^>]*>([\s\S]*?)<\/script>/i);
    const style = source.match(/<style\b[^>]*>([\s\S]*?)<\/style>/i);
    if (!template || !script) throw new Error('San 文件缺少 template 或 script：' + path);
    const module = {exports: {}};
    const localRequire = name => {
      if (name === 'san') return window.san;
      throw new Error('仅支持 require("san")，当前：' + name);
    };
    new Function('module', 'exports', 'require', script[1])(module, module.exports, localRequire);
    const component = module.exports;
    if (!component || (typeof component !== 'object' && typeof component !== 'function')) {
      throw new Error('San 文件未导出组件：' + path);
    }
    component.template = template[1].trim();
    if (typeof component === 'function' && component.prototype) {
      component.prototype.template = component.template;
    }
    if (style) {
      const styleElement = document.createElement('style');
      styleElement.id = 'tested-component-style';
      styleElement.textContent = style[1];
      document.head.appendChild(styleElement);
    }
    return component;
  }

  function elementFor(step) {
    const matches = host.querySelectorAll(step.selector);
    return matches[step.index || 0] || null;
  }

  function check(step) {
    const matches = host.querySelectorAll(step.selector);
    const element = elementFor(step);
    switch (step.expect) {
      case 'exists': return Boolean(element);
      case 'absent': return matches.length === 0;
      case 'count_at_least': return matches.length >= step.value;
      case 'text_nonempty': {
        const value = element && element.textContent.trim();
        return Boolean(value && !/^(undefined|NaN|null)$/.test(value));
      }
      case 'text_includes': return Boolean(element && element.textContent.includes(step.value));
      case 'text_matches': return Boolean(element && new RegExp(step.value).test(element.textContent));
      case 'class_contains': return Boolean(element && element.classList.contains(step.value));
      case 'class_absent': return Boolean(element && !element.classList.contains(step.value));
      case 'value_equals': return Boolean(element && element.value === step.value);
      case 'checked_equals': return Boolean(element && element.checked === step.value);
      case 'attribute_nonempty': return Boolean(element && element.getAttribute(step.attribute));
      case 'background_visible': {
        if (!element) return false;
        const color = getComputedStyle(element).backgroundColor;
        return Boolean(color && color !== 'transparent' && color !== 'rgba(0, 0, 0, 0)');
      }
      case 'background_equals': return Boolean(element && getComputedStyle(element).backgroundColor === step.value);
      default: throw new Error('未知的断言：' + step.expect);
    }
  }

  async function waitFor(step) {
    const deadline = Date.now() + (step.timeout_ms || 5000);
    while (Date.now() < deadline) {
      if (runtimeErrors.length) throw new Error('浏览器运行时错误：' + runtimeErrors[0]);
      if (check(step)) return;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    throw new Error('断言超时：' + JSON.stringify(step));
  }

  async function runStep(step) {
    if (step.op === 'wait_for') return waitFor(step);
    const element = elementFor(step);
    if (!element) throw new Error('操作目标不存在：' + step.selector);
    if (step.op === 'click') element.click();
    else if (step.op === 'select') {
      element.value = step.value;
      element.dispatchEvent(new Event('change', {bubbles: true}));
    } else if (step.op === 'set_checked') {
      if (element.checked !== step.value) element.click();
    } else throw new Error('未知操作：' + step.op);
    await new Promise(resolve => setTimeout(resolve, 0));
    if (runtimeErrors.length) throw new Error('浏览器运行时错误：' + runtimeErrors[0]);
  }

  async function run() {
    const scenario = config.samples.find(item => item.sample_id === sampleInput.value);
    if (!scenario) throw new Error('未知样本');
    runButton.disabled = true;
    runtimeErrors.length = 0;
    if (app) { app.dispose(); app = null; }
    host.replaceChildren();
    document.getElementById('tested-component-style')?.remove();
    const lines = [`样本：${scenario.sample_id}`, `San：${artifactInput.value}`, '状态：运行中'];
    report.textContent = lines.join('\n');
    try {
      const component = await loadSanSfc(artifactInput.value.trim());
      const App = san.defineComponent({
        template: `<div><${scenario.component_tag}></${scenario.component_tag}></div>`,
        components: {[scenario.component_tag]: component}
      });
      app = new App();
      app.attach(host);
      for (const step of scenario.steps) {
        await runStep(step);
        lines.push('✓ ' + step.name);
        report.textContent = lines.join('\n');
      }
      if (runtimeErrors.length) throw new Error('浏览器运行时错误：' + runtimeErrors[0]);
      lines[2] = '状态：通过';
      lines.push('结果：运行时场景通过；仍需人工视觉复核。');
    } catch (error) {
      lines[2] = '状态：失败';
      lines.push('结果：失败 — ' + String(error));
      console.error(error);
    } finally {
      report.textContent = lines.join('\n');
      runButton.disabled = false;
    }
  }

  fetch(CONFIG_PATH).then(response => {
    if (!response.ok) throw new Error('场景配置加载失败：' + response.status);
    return response.json();
  }).then(value => {
    config = value;
    for (const sample of config.samples) {
      sampleInput.add(new Option(sample.sample_id, sample.sample_id));
    }
    const selected = new URLSearchParams(location.search).get('sample');
    if (selected && config.samples.some(item => item.sample_id === selected)) sampleInput.value = selected;
    sampleInput.dispatchEvent(new Event('change'));
  }).catch(error => { report.textContent = String(error); });

  sampleInput.addEventListener('change', () => {
    const scenario = config.samples.find(item => item.sample_id === sampleInput.value);
    artifactInput.value = scenario ? scenario.baseline_san_file : '';
  });
  runButton.addEventListener('click', () => { run().catch(error => { report.textContent = String(error); }); });
}());
