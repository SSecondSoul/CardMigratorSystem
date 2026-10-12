import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SanRenderResult:
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


class SanRenderChecker:
    def __init__(self, node_bin: str = "node", timeout: int = 20):
        self.node_bin = node_bin
        self.timeout = timeout

    def render_file(
        self,
        san_file_path: str | Path,
        props: dict[str, Any] | None = None,
        component_tag: str = "tested-component",
    ) -> SanRenderResult:
        path = Path(san_file_path)
        if not path.exists():
            return SanRenderResult(
                passed=False,
                reason="san_file_not_found",
                diagnostics=[{
                    "code": "san_file_not_found",
                    "message": f"San 文件不存在：{path}",
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
        san_source: str,
        source_name: str = "inline.san",
        props: dict[str, Any] | None = None,
        component_tag: str = "tested-component",
    ) -> SanRenderResult:
        if not shutil.which(self.node_bin):
            return SanRenderResult(
                passed=True,
                skipped=True,
                reason="node_not_found",
                diagnostics=[{
                    "code": "node_not_found",
                    "message": f"未找到 Node 可执行文件：{self.node_bin}，已跳过 San 渲染校验。",
                    "severity": "warning",
                }],
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            runner_path = Path(temp_dir) / "san_render_check.js"
            input_path = Path(temp_dir) / "input.san"
            config_path = Path(temp_dir) / "render_config.json"
            input_path.write_text(san_source, encoding="utf-8")
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
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired as exc:
                return SanRenderResult(
                    passed=False,
                    reason="san_render_timeout",
                    stdout=exc.stdout or "",
                    stderr=exc.stderr or "",
                    diagnostics=[{
                        "code": "san_render_timeout",
                        "message": f"San 渲染校验超时：{self.timeout}s。",
                        "severity": "error",
                    }],
                )

        return self._parse_result(completed.stdout, completed.stderr, completed.returncode)

    def _parse_result(self, stdout: str, stderr: str, return_code: int) -> SanRenderResult:
        stdout = stdout or ""
        stderr = stderr or ""
        lines = [line for line in stdout.splitlines() if line.strip()]
        payload = None
        if lines:
            try:
                payload = json.loads(lines[-1])
            except json.JSONDecodeError:
                payload = None

        if not payload:
            return SanRenderResult(
                passed=False,
                reason="san_render_runner_error",
                stdout=stdout,
                stderr=stderr,
                diagnostics=[{
                    "code": "san_render_runner_error",
                    "message": "San 渲染校验脚本没有返回合法 JSON。",
                    "severity": "error",
                    "detail": stderr or stdout,
                }],
            )

        passed = bool(payload.get("passed")) and return_code == 0
        return SanRenderResult(
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
  if (value == null) {
    return '';
  }
  if (Array.isArray(value)) {
    return value.join(',');
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

function createDataStore(initial) {
  const store = Object.assign({}, initial || {});
  return {
    get(path) {
      return store[path];
    },
    set(path, value) {
      store[path] = value;
    },
    raw() {
      return store;
    }
  };
}

function createSanStub() {
  const DataTypes = new Proxy({}, {
    get(target, prop) {
      if (!target[prop]) {
        target[prop] = { type: String(prop) };
      }
      return target[prop];
    }
  });

  return {
    DataTypes,
    defineComponent(definition) {
      if (!definition || typeof definition !== 'object') {
        throw new Error('san.defineComponent expects an object definition');
      }
      return definition;
    }
  };
}

function evaluateComponent(script, sourceName) {
  const sandbox = {
    module: { exports: {} },
    exports: {},
    require(name) {
      if (name === 'san') {
        return createSanStub();
      }
      return {};
    },
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
    Promise
  };
  sandbox.exports = sandbox.module.exports;
  vm.createContext(sandbox);
  new vm.Script(script, { filename: sourceName + '#script' }).runInContext(sandbox, { timeout: 1000 });
  return sandbox.module.exports;
}

function buildInitialData(component, props) {
  let data = Object.assign({}, props || {});
  if (component && typeof component.initData === 'function') {
    const context = { data: createDataStore(data) };
    const initResult = component.initData.call(context);
    if (initResult && typeof initResult === 'object') {
      data = Object.assign(data, initResult);
    }
  }
  return Object.assign(data, props || {});
}

function createComponentContext(component, dataStore) {
  const context = {
    data: dataStore,
    watch() {},
    fire() {}
  };
  Object.keys(component || {}).forEach(function (name) {
    if (typeof component[name] === 'function' && !['initData', 'inited', 'attached', 'disposed'].includes(name)) {
      context[name] = component[name].bind(context);
    }
  });
  return context;
}

function evaluateComputed(component, dataStore) {
  const values = {};
  const computed = component && component.computed;
  if (!computed || typeof computed !== 'object') {
    return values;
  }
  const context = createComponentContext(component, dataStore);
  Object.keys(computed).forEach(function (name) {
    const getter = computed[name];
    try {
      if (typeof getter === 'function') {
        values[name] = getter.call(context);
      } else if (getter && typeof getter.get === 'function') {
        values[name] = getter.get.call(context);
      }
    } catch (error) {
      diagnostics.push({
        code: 'san_computed_error',
        message: `computed ${name} 执行失败：${error.message}`,
        severity: 'warning'
      });
      values[name] = '';
    }
  });
  return values;
}

function buildRenderData(component, dataStore) {
  return Object.assign({}, dataStore.raw(), evaluateComputed(component, dataStore));
}

function renderTemplate(template, data) {
  let html = template;

  html = renderForBlocks(html, data);
  html = html.replace(/\s+s-if="([^"]+)"/g, function (_, expr) {
    const value = evaluateExpression(expr, data);
    return value ? '' : ' data-san-hidden="true"';
  });

  html = html.replace(/\s+(?:key|trackby)="[^"]*"/g, '');
  html = html.replace(/\s+on-[\w:-]+="[^"]*"/g, '');
  html = html.replace(/\s+s-else(?:-if)?="[^"]*"/g, '');
  html = html.replace(/\s+s-else\b/g, '');
  html = html.replace(/\s+disabled="\{\{\s*([^}]+?)\s*\}\}"/g, function (_, expr) {
    const value = evaluateExpression(expr, data);
    return value ? ' disabled="true"' : '';
  });
  html = html.replace(/\s+class="\{\{\s*([^}]+?)\s*\}\}"/g, function (_, expr) {
    const value = evaluateExpression(expr, data);
    return value ? ` class="${escapeHtml(stringifyValue(value))}"` : '';
  });
  html = html.replace(/\s+value="\{=\s*([^=]+?)\s*=\}"/g, function (_, expr) {
    return ` value="${escapeHtml(stringifyValue(evaluateExpression(expr, data)))}"`;
  });
  html = html.replace(/\s+([\w:-]+)="\{\{\s*([^}]+?)\s*\}\}"/g, function (_, attr, expr) {
    const value = evaluateExpression(expr, data);
    if (value === false || value == null) return '';
    return ` ${attr}="${escapeHtml(stringifyValue(value))}"`;
  });

  html = html.replace(/\{\{\s*([^}]+?)\s*\}\}/g, function (_, expr) {
    return escapeHtml(stringifyValue(evaluateExpression(expr, data)));
  });

  return html;
}

function renderForBlocks(html, data) {
  const openingPattern = /<([a-zA-Z][\w-]*)([^>]*)\s+s-for="([^"]+)"([^>]*)>/;
  const opening = openingPattern.exec(html);
  if (!opening) return html;
  const tag = opening[1];
  const tokenPattern = new RegExp(`<\\/?${tag}\\b[^>]*>`, 'gi');
  tokenPattern.lastIndex = opening.index + opening[0].length;
  let depth = 1;
  let closing = null;
  let token;
  while ((token = tokenPattern.exec(html)) !== null) {
    if (token[0].startsWith('</')) depth -= 1;
    else if (!/\/\s*>$/.test(token[0])) depth += 1;
    if (depth === 0) { closing = token; break; }
  }
  if (!closing) return html;
  const directive = opening[3].replace(/\s+trackby\s+.+$/, '').trim();
  const match = directive.match(/^\s*(?:\((\w+)\s*,\s*(\w+)\)|([\w$]+))\s+in\s+(.+)$/);
  if (!match) return html;
  const itemName = match[1] || match[3];
  const indexName = match[2] || 'index';
  const list = evaluateExpression(match[4], data);
  const inner = html.slice(opening.index + opening[0].length, closing.index);
  const attrs = `${opening[2]}${opening[4]}`;
  const replacement = Array.isArray(list) ? list.map(function (item, index) {
    const scopedData = Object.assign({}, data, { [itemName]: item, [indexName]: index });
    return renderTemplate(`<${tag}${attrs}>${inner}</${tag}>`, scopedData);
  }).join('') : '';
  const replaced = html.slice(0, opening.index) + replacement + html.slice(tokenPattern.lastIndex);
  return renderForBlocks(replaced, data);
}

function evaluateExpression(expr, data) {
  const trimmed = String(expr || '').trim();
  if (!trimmed) {
    return '';
  }
  if (/^[A-Za-z_$][\w$]*$/.test(trimmed)) {
    return data[trimmed];
  }
  try {
    return Function('data', `with (data) { return (${trimmed}); }`)(data);
  } catch (error) {
    diagnostics.push({
      code: 'san_render_expression_error',
      message: `表达式渲染失败：${trimmed}，${error.message}`,
      severity: 'warning'
    });
    return '';
  }
}

function buildDomSnapshot(html) {
  const tree = parseHtmlTree(html);
  const elements = [];
  const texts = [];
  const paths = [];
  let maxDepth = 0;

  function walk(node, depth, path) {
    if (!node) {
      return;
    }
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
    if (!token || token.startsWith('<!--')) {
      continue;
    }
    if (token.startsWith('</')) {
      const closingTag = token.match(/^<\/\s*([a-zA-Z][\w-]*)/);
      if (closingTag) {
        closeTag(stack, closingTag[1].toLowerCase());
      }
      continue;
    }
    if (token.startsWith('<')) {
      const openTag = parseOpenTag(token);
      if (!openTag) {
        continue;
      }
      const node = createElementNode(openTag.tag, openTag.attrs, false);
      stack[stack.length - 1].children.push(node);
      if (!openTag.selfClosing && !isVoidTag(openTag.tag)) {
        stack.push(node);
      }
      continue;
    }

    const text = token.replace(/\s+/g, ' ').trim();
    if (text) {
      stack[stack.length - 1].children.push({
        type: 'text',
        text
      });
    }
  }

  return root;
}

function parseOpenTag(token) {
  const match = token.match(/^<\s*([a-zA-Z][\w-]*)([\s\S]*?)\/?\s*>$/);
  if (!match) {
    return null;
  }
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
  if (node.type === 'element') {
    return node.tag + '[' + index + ']';
  }
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
    diagnostics.push({ code: 'missing_template_block', message: 'San 文件缺少 <template>。', severity: 'error' });
  }
  if (!script) {
    diagnostics.push({ code: 'missing_script_block', message: 'San 文件缺少 <script>。', severity: 'error' });
  }

  let component = {};
  if (script) {
    component = evaluateComponent(script, config.sourceName || filePath);
  }

  if (component && typeof component === 'object') {
    component.template = component.template || template;
  }

  const data = buildInitialData(component, config.props || {});
  const dataStore = createDataStore(data);
  const context = createComponentContext(component, dataStore);
  if (component && typeof component.inited === 'function') {
    component.inited.call(context);
  }
  if (component && typeof component.attached === 'function') {
    component.attached.call(context);
  }
  const renderData = buildRenderData(component, dataStore);

  const renderedTemplate = template ? renderTemplate(template, renderData) : '';
  const htmlSnapshot = [renderedTemplate, style ? `<style>${style}</style>` : ''].filter(Boolean).join('\n');
  const domSnapshot = buildDomSnapshot(renderedTemplate);
  const hasErrors = diagnostics.some(item => item.severity === 'error');

  emit({
    passed: !hasErrors,
    skipped: false,
    reason: hasErrors ? 'san_render_failed' : 'san_render_passed',
    diagnostics,
    htmlSnapshot,
    domSnapshot
  });
  process.exit(hasErrors ? 1 : 0);
} catch (error) {
  emit({
    passed: false,
    skipped: false,
    reason: 'san_render_failed',
    diagnostics: [{
      code: 'san_render_error',
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


def render_san_component(
    san_source: str | None = None,
    san_file_path: str | Path | None = None,
    props: dict[str, Any] | None = None,
    component_tag: str = "tested-component",
    node_bin: str = "node",
    timeout: int = 20,
) -> SanRenderResult:
    checker = SanRenderChecker(node_bin=node_bin, timeout=timeout)
    if san_source is not None:
        return checker.render_source(
            san_source,
            source_name=str(san_file_path or "inline.san"),
            props=props,
            component_tag=component_tag,
        )
    if san_file_path is not None:
        return checker.render_file(san_file_path, props=props, component_tag=component_tag)
    raise ValueError("render_san_component requires san_source or san_file_path")
