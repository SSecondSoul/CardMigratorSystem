import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VueRenderResult:
    passed: bool
    skipped: bool = False
    reason: str = ""
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    html_snapshot: str = ""
    dom_snapshot: dict[str, Any] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VueRenderChecker:
    def __init__(self, node_bin: str = "node", timeout: int = 20):
        self.node_bin = node_bin
        self.timeout = timeout

    def render_file(
        self,
        vue_file_path: str | Path,
        props: dict[str, Any] | None = None,
        component_tag: str = "tested-component",
    ) -> VueRenderResult:
        path = Path(vue_file_path)
        if not path.exists():
            return VueRenderResult(
                passed=False,
                reason="vue_file_not_found",
                diagnostics=[{
                    "code": "vue_file_not_found",
                    "message": f"Vue 文件不存在：{path}",
                    "severity": "error",
                }],
            )
        return self.render_source(
            path.read_text(encoding="utf-8"),
            source_name=str(path),
            props=props,
            component_tag=component_tag,
        )

    def render_source(
        self,
        vue_source: str,
        source_name: str = "inline.vue",
        props: dict[str, Any] | None = None,
        component_tag: str = "tested-component",
    ) -> VueRenderResult:
        if not shutil.which(self.node_bin):
            return VueRenderResult(
                passed=True,
                skipped=True,
                reason="node_not_found",
                diagnostics=[{
                    "code": "node_not_found",
                    "message": f"未找到 Node 可执行文件：{self.node_bin}，已跳过 Vue 渲染校验。",
                    "severity": "warning",
                }],
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            runner_path = Path(temp_dir) / "vue_render_check.js"
            input_path = Path(temp_dir) / "input.vue"
            config_path = Path(temp_dir) / "render_config.json"
            input_path.write_text(vue_source, encoding="utf-8")
            config_path.write_text(json.dumps({
                "sourceName": source_name,
                "props": props or {},
                "componentTag": component_tag,
            }, ensure_ascii=False), encoding="utf-8")
            runner_path.write_text(self._runner_script(), encoding="utf-8")

            try:
                completed = subprocess.run(
                    [self.node_bin, str(runner_path), str(input_path), str(config_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired as exc:
                return VueRenderResult(
                    passed=False,
                    reason="vue_render_timeout",
                    stdout=exc.stdout or "",
                    stderr=exc.stderr or "",
                    diagnostics=[{
                        "code": "vue_render_timeout",
                        "message": f"Vue 渲染校验超时：{self.timeout}s。",
                        "severity": "error",
                    }],
                )

        return self._parse_result(completed.stdout, completed.stderr, completed.returncode)

    def _parse_result(self, stdout: str, stderr: str, return_code: int) -> VueRenderResult:
        lines = [line for line in stdout.splitlines() if line.strip()]
        payload = None
        if lines:
            try:
                payload = json.loads(lines[-1])
            except json.JSONDecodeError:
                payload = None

        if not payload:
            return VueRenderResult(
                passed=False,
                reason="vue_render_runner_error",
                stdout=stdout,
                stderr=stderr,
                diagnostics=[{
                    "code": "vue_render_runner_error",
                    "message": "Vue 渲染校验脚本没有返回合法 JSON。",
                    "severity": "error",
                    "detail": stderr or stdout,
                }],
            )

        passed = bool(payload.get("passed")) and return_code == 0
        return VueRenderResult(
            passed=passed,
            skipped=bool(payload.get("skipped", False)),
            reason=payload.get("reason", ""),
            diagnostics=payload.get("diagnostics", []),
            html_snapshot=payload.get("htmlSnapshot", ""),
            dom_snapshot=payload.get("domSnapshot", {}),
            stdout=stdout,
            stderr=stderr,
        )

    def _runner_script(self) -> str:
        return r'''
const fs = require('fs');
const vm = require('vm');

const filePath = process.argv[2];
const configPath = process.argv[3];
const source = fs.readFileSync(filePath, 'utf8');
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
const diagnostics = [];

function emit(result) {
  process.stdout.write(JSON.stringify(result) + '\n');
}

function extractBlock(source, tag) {
  const pattern = new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i');
  const match = source.match(pattern);
  return match ? match[1].trim() : '';
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function stringifyValue(value) {
  if (value == null) return '';
  if (Array.isArray(value)) return value.join(',');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function evaluateComponent(script, sourceName) {
  const sandbox = {
    module: { exports: {} },
    exports: {},
    require() { return {}; },
    console,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    Date,
    Math,
    JSON,
    Array,
    Object,
    String,
    Number,
    Boolean,
    RegExp,
    Promise,
    localStorage: createStorageStub(),
    sessionStorage: createStorageStub()
  };
  sandbox.exports = sandbox.module.exports;
  vm.createContext(sandbox);
  new vm.Script(script, { filename: sourceName + '#script' }).runInContext(sandbox, { timeout: 1000 });
  return sandbox.module.exports;
}

function createStorageStub() {
  const values = {};
  return {
    getItem(key) { return values[key] || null; },
    setItem(key, value) { values[key] = String(value); },
    removeItem(key) { delete values[key]; },
    clear() { Object.keys(values).forEach(key => delete values[key]); }
  };
}

function buildProps(component, explicitProps) {
  const props = {};
  const declarations = component && component.props;
  if (Array.isArray(declarations)) {
    declarations.forEach(name => {
      props[name] = explicitProps && Object.prototype.hasOwnProperty.call(explicitProps, name) ? explicitProps[name] : undefined;
    });
  } else if (declarations && typeof declarations === 'object') {
    Object.keys(declarations).forEach(name => {
      if (explicitProps && Object.prototype.hasOwnProperty.call(explicitProps, name)) {
        props[name] = explicitProps[name];
        return;
      }
      props[name] = resolveDefaultValue(declarations[name]);
    });
  }
  return Object.assign(props, explicitProps || {});
}

function resolveDefaultValue(declaration) {
  if (!declaration || typeof declaration !== 'object') {
    return undefined;
  }
  const value = declaration.default;
  if (typeof value === 'function') {
    try {
      return value();
    } catch (error) {
      diagnostics.push({
        code: 'vue_prop_default_error',
        message: `props default 执行失败：${error.message}`,
        severity: 'warning'
      });
      return undefined;
    }
  }
  return value;
}

function buildInitialData(component, props) {
  const data = Object.assign({}, props || {});
  if (component && typeof component.data === 'function') {
    const context = createVueContext(data, component);
    const dataResult = component.data.call(context);
    if (dataResult && typeof dataResult === 'object') {
      Object.assign(data, dataResult);
    }
  }
  applyComputed(data, component);
  return data;
}

function createVueContext(data, component) {
  return new Proxy(data, {
    get(target, prop) {
      if (prop === '$emit') {
        return function () {};
      }
      if (component && component.methods && typeof component.methods[prop] === 'function') {
        return component.methods[prop].bind(createVueContext(target, component));
      }
      return target[prop];
    },
    set(target, prop, value) {
      target[prop] = value;
      return true;
    }
  });
}

function applyComputed(data, component) {
  if (!component || !component.computed || typeof component.computed !== 'object') {
    return;
  }
  Object.keys(component.computed).forEach(name => {
    const computedValue = component.computed[name];
    try {
      if (typeof computedValue === 'function') {
        data[name] = computedValue.call(createVueContext(data, component));
      } else if (computedValue && typeof computedValue.get === 'function') {
        data[name] = computedValue.get.call(createVueContext(data, component));
      }
    } catch (error) {
      diagnostics.push({
        code: 'vue_computed_error',
        message: `computed ${name} 执行失败：${error.message}`,
        severity: 'warning'
      });
      data[name] = '';
    }
  });
}

function renderTemplate(template, data) {
  let html = template;
  html = renderForBlocks(html, data);
  html = renderIfBlocks(html, data);
  html = html.replace(/\s+v-if="([^"]+)"/g, function (_, expr) {
    const value = evaluateExpression(expr, data);
    return value ? '' : ' data-vue-hidden="true"';
  });
  html = html.replace(/\s+v-else-if="[^"]*"/g, '');
  html = html.replace(/\s+v-else\b/g, '');
  html = html.replace(/\s+v-model="([^"]+)"/g, function (_, expr) {
    return ` value="${escapeHtml(stringifyValue(evaluateExpression(expr, data)))}"`;
  });
  html = html.replace(/\s+@[\w:.:-]+="[^"]*"/g, '');
  html = html.replace(/\s+v-on:[\w:.:-]+="[^"]*"/g, '');
  html = html.replace(/\s+:class="([^"]+)"/g, function (_, expr) {
    const value = evaluateClassBinding(expr, data);
    return value ? ` class="${escapeHtml(value)}"` : '';
  });
  html = html.replace(/\s+:([\w:-]+)="([^"]+)"/g, function (_, attr, expr) {
    const value = evaluateExpression(expr, data);
    if (value === false || value == null) {
      return '';
    }
    return ` ${attr}="${escapeHtml(stringifyValue(value))}"`;
  });
  html = html.replace(/\s+v-bind:([\w:-]+)="([^"]+)"/g, function (_, attr, expr) {
    const value = evaluateExpression(expr, data);
    if (value === false || value == null) {
      return '';
    }
    return ` ${attr}="${escapeHtml(stringifyValue(value))}"`;
  });
  html = html.replace(/\{\{\s*([^}]+?)\s*\}\}/g, function (_, expr) {
    return escapeHtml(stringifyValue(evaluateExpression(expr, data)));
  });
  return html;
}

function renderIfBlocks(html, data) {
  const pattern = /<([a-zA-Z][\w-]*)([^>]*)\s+v-if="([^"]+)"([^>]*)>([\s\S]*?)<\/\1>/g;
  return html.replace(pattern, function (full, tag, beforeAttrs, expr, afterAttrs, inner) {
    const value = evaluateExpression(expr, data);
    return value ? `<${tag}${beforeAttrs}${afterAttrs}>${inner}</${tag}>` : '';
  });
}

function renderForBlocks(html, data) {
  const pattern = /<([a-zA-Z][\w-]*)([^>]*)\s+v-for="\s*(?:\((\w+)\s*,\s*(\w+)\)|(\w+))\s+in\s+([^"]+)"([^>]*)>([\s\S]*?)<\/\1>/g;
  return html.replace(pattern, function (full, tag, beforeAttrs, tupleItem, tupleIndex, singleItem, listExpr, afterAttrs, inner) {
    const list = evaluateExpression(listExpr, data);
    if (!Array.isArray(list) || !list.length) {
      return '';
    }
    const itemName = tupleItem || singleItem;
    const indexName = tupleIndex || 'index';
    return list.map(function (item, index) {
      const scopedData = Object.assign({}, data);
      scopedData[itemName] = item;
      scopedData[indexName] = index;
      return `<${tag}${beforeAttrs}${afterAttrs}>${renderTemplate(inner, scopedData)}</${tag}>`;
    }).join('');
  });
}

function evaluateClassBinding(expr, data) {
  const value = evaluateExpression(expr, data);
  if (!value) return '';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.filter(Boolean).join(' ');
  if (typeof value === 'object') {
    return Object.keys(value).filter(key => Boolean(value[key])).join(' ');
  }
  return String(value);
}

function evaluateExpression(expr, data) {
  const trimmed = String(expr || '').trim();
  if (!trimmed) return '';
  if (/^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$/.test(trimmed)) {
    return getPath(data, trimmed);
  }
  try {
    return Function('data', `with (data) { return (${trimmed}); }`)(data);
  } catch (error) {
    diagnostics.push({
      code: 'vue_render_expression_error',
      message: `表达式渲染失败：${trimmed}，${error.message}`,
      severity: 'warning'
    });
    return '';
  }
}

function getPath(data, path) {
  return path.split('.').reduce(function (current, key) {
    if (current == null) return undefined;
    return current[key];
  }, data);
}

function buildDomSnapshot(html) {
  const tree = parseHtmlTree(html);
  const elements = [];
  const texts = [];
  const paths = [];
  let maxDepth = 0;

  function walk(node, depth, path) {
    if (!node) return;
    if (node.type === 'element') {
      elements.push(node);
      paths.push(path);
      maxDepth = Math.max(maxDepth, depth);
      node.children.forEach(function (child, index) {
        walk(child, depth + 1, path + '/' + childLabel(child, index));
      });
    } else if (node.type === 'text' && node.text) {
      texts.push(node.text);
    }
  }

  tree.children.forEach(function (child, index) {
    walk(child, 1, '/' + childLabel(child, index));
  });

  return {
    root_tag: elements.length ? elements[0].tag : '',
    node_count: elements.length,
    text_node_count: texts.length,
    max_depth: maxDepth,
    tags: elements.map(function (node) { return node.tag; }),
    paths,
    text_content: texts.join(' ').replace(/\s+/g, ' ').trim(),
    tree: tree.children.length === 1 ? tree.children[0] : tree
  };
}

function parseHtmlTree(html) {
  const root = createElementNode('root', {}, true);
  const stack = [root];
  const tokenPattern = /<!--([\s\S]*?)-->|<\/?[a-zA-Z][^>]*>|[^<]+/g;
  let match;

  while ((match = tokenPattern.exec(html)) !== null) {
    const token = match[0];
    if (!token || token.startsWith('<!--')) continue;
    if (token.startsWith('</')) {
      const closingTag = token.match(/^<\/\s*([a-zA-Z][\w-]*)/);
      if (closingTag) closeTag(stack, closingTag[1].toLowerCase());
      continue;
    }
    if (token.startsWith('<')) {
      const openTag = parseOpenTag(token);
      if (!openTag) continue;
      const node = createElementNode(openTag.tag, openTag.attrs, false);
      stack[stack.length - 1].children.push(node);
      if (!openTag.selfClosing && !isVoidTag(openTag.tag)) {
        stack.push(node);
      }
      continue;
    }

    const text = token.replace(/\s+/g, ' ').trim();
    if (text) {
      stack[stack.length - 1].children.push({ type: 'text', text });
    }
  }
  return root;
}

function parseOpenTag(token) {
  const match = token.match(/^<\s*([a-zA-Z][\w-]*)([\s\S]*?)\/?\s*>$/);
  if (!match) return null;
  const tag = match[1].toLowerCase();
  const attrSource = match[2] || '';
  return {
    tag,
    attrs: parseAttributes(attrSource),
    selfClosing: /\/\s*>$/.test(token)
  };
}

function parseAttributes(source) {
  const attrs = {};
  const attrPattern = /([:@a-zA-Z_][\w:.-]*)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s"'>/]+))?/g;
  let match;
  while ((match = attrPattern.exec(source)) !== null) {
    const name = match[1];
    let value = match[2] || true;
    if (typeof value === 'string') {
      value = value.replace(/^['"]|['"]$/g, '');
    }
    attrs[name] = value;
  }
  return attrs;
}

function createElementNode(tag, attrs, isRoot) {
  return {
    type: 'element',
    tag,
    attrs,
    children: [],
    is_root: Boolean(isRoot)
  };
}

function closeTag(stack, tag) {
  for (let index = stack.length - 1; index > 0; index -= 1) {
    if (stack[index].tag === tag) {
      stack.length = index;
      return;
    }
  }
}

function childLabel(node, index) {
  if (node.type === 'element') return node.tag + '[' + index + ']';
  return 'text[' + index + ']';
}

function isVoidTag(tag) {
  return ['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'].includes(tag);
}

try {
  const template = extractBlock(source, 'template');
  const script = extractBlock(source, 'script');
  const style = extractBlock(source, 'style');

  if (!template) {
    diagnostics.push({ code: 'missing_template_block', message: 'Vue 文件缺少 <template>。', severity: 'error' });
  }
  if (!script) {
    diagnostics.push({ code: 'missing_script_block', message: 'Vue 文件缺少 <script>。', severity: 'error' });
  }

  let component = {};
  if (script) {
    component = evaluateComponent(script, config.sourceName || filePath);
  }

  const props = buildProps(component, config.props || {});
  const data = buildInitialData(component, props);
  const renderedTemplate = template ? renderTemplate(template, data) : '';
  const htmlSnapshot = [renderedTemplate, style ? `<style>${style}</style>` : ''].filter(Boolean).join('\n');
  const domSnapshot = buildDomSnapshot(renderedTemplate);
  const hasErrors = diagnostics.some(item => item.severity === 'error');

  emit({
    passed: !hasErrors,
    skipped: false,
    reason: hasErrors ? 'vue_render_failed' : 'vue_render_passed',
    diagnostics,
    htmlSnapshot,
    domSnapshot
  });
  process.exit(hasErrors ? 1 : 0);
} catch (error) {
  emit({
    passed: false,
    skipped: false,
    reason: 'vue_render_failed',
    diagnostics: [{
      code: 'vue_render_error',
      message: error.message,
      severity: 'error',
      stack: error.stack
    }],
    htmlSnapshot: '',
    domSnapshot: {}
  });
  process.exit(1);
}
'''


def render_vue_component(
    vue_source: str | None = None,
    vue_file_path: str | Path | None = None,
    props: dict[str, Any] | None = None,
    component_tag: str = "tested-component",
    node_bin: str = "node",
    timeout: int = 20,
) -> VueRenderResult:
    checker = VueRenderChecker(node_bin=node_bin, timeout=timeout)
    if vue_source is not None:
        return checker.render_source(
            vue_source,
            source_name=str(vue_file_path or "inline.vue"),
            props=props,
            component_tag=component_tag,
        )
    if vue_file_path is not None:
        return checker.render_file(vue_file_path, props=props, component_tag=component_tag)
    raise ValueError("render_vue_component requires vue_source or vue_file_path")
