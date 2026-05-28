"""
SSM Extractors — 脚本结构提取器

从 Vue 组件的 <script> 块中提取：
- export_info       导出类型
- name              组件名
- components        注册的子组件
- props             属性声明（支持数组/对象语法）
- data              数据字段
- computed          计算属性
- watch             监听器
- methods           方法表
- lifecycle_hooks   生命周期钩子
- emits             声明的事件
- filters           过滤器（Vue 2）
- imports           导入语句
- top_level_declarations 顶层声明
"""

import re
from typing import Any, Optional, List


COMMENT_LINE_RE = re.compile(r'(^|\n)\s*//.*?(?=\n|$)')
COMMENT_BLOCK_RE = re.compile(r'/\*.*?\*/', re.DOTALL)


# ── 辅助工具 ──────────────────────────────────────────────

JS_KEYWORDS = {"true", "false", "null", "undefined", "this", "new",
               "return", "if", "else", "in", "of", "typeof", "void",
               "function", "const", "let", "var", "class", "async", "await",
               "Math", "Date", "JSON", "Object", "Array", "String",
               "Number", "Boolean", "Promise", "Error", "console",
               "parseInt", "parseFloat", "isNaN", "setTimeout", "setInterval",
               "clearTimeout", "clearInterval", "localStorage", "sessionStorage",
               "document", "window", "navigator", "RegExp", "Map", "Set",
               "module", "exports", "require", "import", "export", "default"}


def _extract_identifiers(expr: str) -> List[str]:
    """从 JS 表达式中提取标识符名，过滤关键字。"""
    idents = re.findall(r'\b([a-zA-Z_$][\w]*)', expr)
    return [x for x in idents if x not in JS_KEYWORDS and not x.isdigit()]


def _extract_object_body(source: str, start_pos: int) -> str:
    """从 source 的 start_pos 开始提取匹配的 { ... } 内容。

    处理嵌套大括号。
    """
    depth = 0
    in_string = False
    string_char = ""
    escape = False

    for i in range(start_pos, len(source)):
        ch = source[i]

        if escape:
            escape = False
            continue

        if ch == "\\":
            escape = True
            continue

        if in_string:
            if ch == string_char:
                in_string = False
            continue

        if ch in ('"', "'", "`"):
            in_string = True
            string_char = ch
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start_pos:i + 1]

    return source[start_pos:]


def _strip_js_comments(source: str) -> str:
    source = COMMENT_BLOCK_RE.sub("", source)
    source = COMMENT_LINE_RE.sub(lambda m: m.group(1), source)
    return source


def _extract_object_properties(obj_body: str) -> List[dict]:
    """从对象字面量的 body 文本中提取属性列表。

    返回 [{"key": "...", "value": "...", "is_method": bool, "is_object": bool}, ...]
    """
    if not obj_body.strip():
        return []

    body = _strip_js_comments(obj_body)

    # 去掉最外层 { }
    body = body.strip()
    if body.startswith("{") and body.endswith("}"):
        body = body[1:-1].strip()

    properties = []
    # 简单分割（用 , 分割顶层属性）
    # 使用括号深度追踪
    depth = 0
    in_string = False
    string_char = ""
    escape = False
    current_start = 0

    for i, ch in enumerate(body):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if in_string:
            if ch == string_char:
                in_string = False
            continue
        if ch in ('"', "'", "`"):
            in_string = True
            string_char = ch
            continue
        if ch in ("{", "[", "("):
            depth += 1
        elif ch in ("}", "]", ")"):
            depth -= 1
        elif ch == "," and depth == 0:
            prop_text = body[current_start:i].strip()
            if prop_text:
                properties.append(prop_text)
            current_start = i + 1

    # 最后一个属性
    last = body[current_start:].strip()
    if last:
        properties.append(last)

    result = []
    for prop in properties:
        # 匹配 key: value 或 methodName() {}
        method_match = re.match(
            r'^(\w+)\s*\((.*?)\)\s*\{',
            prop, re.DOTALL
        )
        key_match = re.match(
            r'(\w+|\"[^\"]+\"|\'[^\']+\')\s*:\s*(.+)',
            prop, re.DOTALL
        )

        if method_match and not key_match:
            mname = method_match.group(1)
            params = [p.strip() for p in method_match.group(2).split(",") if p.strip()]
            body_start = prop.index("{")
            body_text = _extract_object_body(prop, body_start)
            # 完整源码
            result.append({
                "key": mname,
                "value": prop,
                "is_method": True,
                "is_object": False,
                "params": params,
                "body": body_text,
            })
        elif key_match:
            key = key_match.group(1).strip('"').strip("'")
            value = key_match.group(2).strip()
            is_obj = value.startswith("{")
            result.append({
                "key": key,
                "value": value,
                "is_method": False,
                "is_object": is_obj,
            })
        else:
            result.append({
                "key": prop,
                "value": prop,
                "is_method": False,
                "is_object": False,
            })

    return result


def _find_option(source: str, key: str) -> Optional[str]:
    """从 Vue 选项对象中提取指定 key 的值文本。"""
    patterns = [
        rf'{key}\s*:\s*([^\n]*)',  # 单行
        rf'{key}\s*:\s*\(',        # 函数形式（data()）
    ]
    for pat in patterns[:1]:
        m = re.search(pat, source)
        if m:
            return m.group(1).strip()
    return None


# ── Script 提取器主类 ─────────────────────────────────────

class ScriptExtractor:

    def __init__(self):
        pass

    def extract_from_ast_analysis(self, script_analysis: dict) -> dict:
        """直接消费 Node/Babel AST 分析结果。"""
        if not script_analysis:
            return self.extract("")

        return {
            "export_info": script_analysis.get("export_info", {"export_type": "unknown", "has_export": False}),
            "options": script_analysis.get("options", {}),
            "imports": script_analysis.get("imports", []),
            "top_level_declarations": script_analysis.get("top_level_declarations", []),
        }

    LIFECYCLE_HOOKS = [
        "beforeCreate", "created", "beforeMount", "mounted",
        "beforeUpdate", "updated", "beforeDestroy", "destroyed",
        "activated", "deactivated", "errorCaptured",
    ]

    SAN_LIFECYCLE_MAP = {
        "beforeCreate": "compiled",
        "created": "inited",
        "beforeMount": "created",
        "mounted": "attached",
        "beforeUpdate": None,
        "updated": "updated",
        "beforeDestroy": None,
        "destroyed": "disposed",
        "activated": "attached",
        "deactivated": "disposed",
        "errorCaptured": None,
    }

    SIDE_EFFECT_PATTERNS = [
        ("localStorage", "localStorage"),
        ("sessionStorage", "sessionStorage"),
        ("setInterval", "timer"),
        ("setTimeout", "timer"),
        ("clearInterval", "timer"),
        ("clearTimeout", "timer"),
        ("fetch(", "fetch"),
        ("axios", "fetch"),
        ("XMLHttpRequest", "fetch"),
        ("Date.now", "Date"),
        ("new Date", "Date"),
        ("Math.", "Math"),
        ("document.", "DOM"),
        ("window.", "DOM"),
        ("console.", "console"),
    ]

    def extract(self, script_source: str) -> dict:
        """从 script 源码提取组件选项结构。"""
        if not script_source or not script_source.strip():
            return {
                "export_info": {"export_type": "unknown", "has_export": False},
                "options": {},
                "imports": [],
                "top_level_declarations": [],
            }

        # 提取 imports
        imports = self._extract_imports(script_source)

        # 提取导出信息
        export_info = self._extract_export_info(script_source)

        # 提取各选项
        options = self._extract_options(script_source)

        # 提取顶层声明
        top_decls = self._extract_top_level_declarations(script_source)

        return {
            "export_info": export_info,
            "options": options,
            "imports": imports,
            "top_level_declarations": top_decls,
        }

    def _extract_imports(self, source: str) -> List[dict]:
        """提取 import 和 require 语句。"""
        imports = []

        # ES6 import
        es6_patterns = [
            # import X from 'Y'
            r'import\s+(\w+)\s+from\s+["\']([^"\']+)["\']',
            # import { X, Y } from 'Z'
            r'import\s+\{([^}]+)\}\s+from\s+["\']([^"\']+)["\']',
            # import * as X from 'Y'
            r'import\s+\*\s+as\s+(\w+)\s+from\s+["\']([^"\']+)["\']',
            # import 'X'
            r'import\s+["\']([^"\']+)["\']',
        ]

        for pat in es6_patterns:
            for m in re.finditer(pat, source):
                imports.append({
                    "kind": "import",
                    "source": m.group(2) if len(m.groups()) >= 2 else m.group(1),
                    "specifiers": [g for g in m.groups() if g and not g.startswith("'") and not g.startswith('"')],
                    "is_default": "from" in m.group(0) and "{" not in m.group(0),
                })

        # CommonJS require
        require_pattern = r'(?:const|let|var)\s+(\{?[\w\s,{}]*\}?)\s*=\s*require\s*\(\s*["\']([^"\']+)["\']\)'
        for m in re.finditer(require_pattern, source):
            spec_str = m.group(1).strip()
            specifiers = re.findall(r'(\w+)', spec_str)
            imports.append({
                "kind": "require",
                "source": m.group(2),
                "specifiers": specifiers,
                "is_default": len(specifiers) == 1 and "{" not in spec_str,
            })

        return imports

    def _extract_export_info(self, source: str) -> dict:
        """提取导出类型。"""
        if "export default" in source:
            # 定位 export default 后的表达式
            m = re.search(r'export\s+default\s+', source)
            if m:
                rest = source[m.end():].strip()
                return {
                    "export_type": "default_export",
                    "has_export": True,
                    "declaration_start": m.end(),
                    "declaration_preview": rest[:60],
                }

        if "module.exports" in source:
            m = re.search(r'module\.exports\s*=', source)
            if m:
                rest = source[m.end():].strip()
                return {
                    "export_type": "module_exports",
                    "has_export": True,
                    "declaration_start": m.end(),
                    "declaration_preview": rest[:60],
                }

        return {
            "export_type": "unknown",
            "has_export": False,
        }

    def _extract_options(self, source: str) -> dict:
        """提取组件各选项。"""
        options: dict[str, Any] = {}

        # name
        name_match = re.search(r'name\s*:\s*["\']([^"\']+)["\']', source)
        options["name"] = name_match.group(1) if name_match else None

        # components
        options["components"] = self._extract_components_option(source)

        # props
        options["props"] = self._extract_props(source)

        # data
        options["data"] = self._extract_data(source)

        # computed
        options["computed"] = self._extract_computed(source)

        # watch
        options["watch"] = self._extract_watch(source)

        # methods
        options["methods"] = self._extract_methods(source)

        # lifecycle hooks
        options["lifecycle_hooks"] = self._extract_lifecycle_hooks(source)

        # emits
        options["emits"] = self._extract_emits(source)

        # filters (Vue 2)
        options["filters"] = self._extract_filters(source)

        # provide/inject
        options["provide_keys"] = self._extract_simple_list(source, "provide")
        options["inject_keys"] = self._extract_simple_list(source, "inject")

        # mixins/extends
        options["mixins"] = self._extract_simple_list(source, "mixins")
        options["extends"] = self._extract_simple_list(source, "extends")

        return options

    def _extract_components_option(self, source: str) -> List[dict]:
        """提取 components: { ... } 注册表。"""
        components = []

        # 找到 components: { 后的内容
        m = re.search(r'components\s*:\s*\{', source)
        if not m:
            return components

        body = _extract_object_body(source, m.end() - 1)
        props = _extract_object_properties(body)

        for prop in props:
            key = prop["key"]
            value = prop["value"]
            registered_tag = key  # 注册用名

            components.append({
                "registered_name": key,
                "registered_tag": registered_tag,
                "source_name": value if not prop["is_object"] else f"inline_{key}",
                "definition_location": "inline" if prop["is_object"] else "unknown",
                "inline_definition": None,
            })

        return components

    def _extract_props(self, source: str) -> List[dict]:
        """提取 props 声明。支持数组和对象语法。"""
        props = []

        # 数组语法: props: ['a', 'b']
        arr_match = re.search(r'props\s*:\s*\[([^\]]+)\]', source)
        if arr_match:
            items = re.findall(r'["\']([^"\']+)["\']', arr_match.group(1))
            for item in items:
                props.append({
                    "name": item,
                    "type": "unknown",
                    "required": False,
                    "default": None,
                    "validator": False,
                })
            return props

        # 对象语法: props: { a: { type: String, required: true }, ... }
        m = re.search(r'props\s*:\s*\{', source)
        if not m:
            return props

        body = _extract_object_body(source, m.end() - 1)
        prop_props = _extract_object_properties(body)

        for pp in prop_props:
            pname = pp["key"]
            required = bool(re.search(r'\brequired\s*:\s*true\b', pp["value"]))
            validator = bool(re.search(r'\bvalidator\s*:', pp["value"]))
            type_match = re.search(r'\btype\s*:\s*([A-Za-z_$][\w$]*)', pp["value"])
            default_match = re.search(r'\bdefault\s*:\s*([^,}\n]+)', pp["value"])

            props.append({
                "name": pname,
                "type": type_match.group(1) if type_match else "unknown",
                "required": required,
                "default": default_match.group(1).strip() if default_match else None,
                "validator": validator,
            })

        return props

    def _extract_data(self, source: str) -> List[dict]:
        """提取 data 字段。"""
        fields = []

        # data() { return { ... } }
        func_match = re.search(r'data\s*\(\s*\)\s*\{', source)
        if func_match:
            # 找 return 中的对象
            ret_match = re.search(r'return\s*\{', source[func_match.end():])
            if ret_match:
                abs_start = func_match.end() + ret_match.end() - 1
                body = _extract_object_body(source, abs_start)
                props = _extract_object_properties(body)
                for pp in props:
                    default_val = pp["value"]
                    fields.append({
                        "name": pp["key"],
                        "default_value_summary": default_val[:50] if len(default_val) > 50 else default_val,
                        "value_type_inferred": self._infer_type(default_val),
                    })
        else:
            # data: { ... } 直接对象
            m = re.search(r'data\s*:\s*\{', source)
            if m:
                body = _extract_object_body(source, m.end() - 1)
                props = _extract_object_properties(body)
                for pp in props:
                    fields.append({
                        "name": pp["key"],
                        "default_value_summary": pp["value"][:50],
                        "value_type_inferred": self._infer_type(pp["value"]),
                    })

        return fields

    def _extract_computed(self, source: str) -> List[dict]:
        """提取 computed 属性。"""
        computed = []
        m = re.search(r'computed\s*:\s*\{', source)
        if not m:
            return computed

        body = _extract_object_body(source, m.end() - 1)
        props = _extract_object_properties(body)

        for pp in props:
            has_setter = "set" in pp["value"]
            deps = _extract_identifiers(pp["value"]) if pp["is_method"] else _extract_identifiers(pp["value"])
            computed.append({
                "name": pp["key"],
                "has_setter": has_setter,
                "getter_body": pp["value"][:200],
                "dependencies_inferred": deps,
                "return_type_inferred": None,
            })

        return computed

    def _extract_watch(self, source: str) -> List[dict]:
        """提取 watch 声明。"""
        watches = []
        m = re.search(r'watch\s*:\s*\{', source)
        if not m:
            return watches

        body = _extract_object_body(source, m.end() - 1)
        props = _extract_object_properties(body)

        for pp in props:
            deep = "deep" in pp["value"]
            immediate = "immediate" in pp["value"]
            handler_type = "method_name"
            handler_name = pp["value"].split("{")[0].strip() if not pp["is_method"] else ""

            watches.append({
                "expression": pp["key"],
                "deep": deep,
                "immediate": immediate,
                "handler_type": "method_name" if not pp["is_method"] else "object_config",
                "handler_name": handler_name,
                "handler_body": pp["value"][:200],
            })

        return watches

    def _extract_methods(self, source: str) -> List[dict]:
        """提取 methods。"""
        methods = []
        m = re.search(r'methods\s*:\s*\{', source)
        if not m:
            return methods

        body = _extract_object_body(source, m.end() - 1)
        props = _extract_object_properties(body)

        method_names = [pp["key"] for pp in props if pp["is_method"]]

        for pp in props:
            if not pp["is_method"]:
                continue

            body_text = pp.get("body", pp["value"])
            reads = _extract_identifiers(body_text)
            is_async = "async" in pp["value"]
            emits = re.findall(r'\$emit\s*\(\s*["\'](\w+)["\']', body_text)
            writes = self._extract_writes(body_text)
            calls = self._extract_method_calls(body_text, method_names, pp["key"])

            lifecycle_names = {hook["vue_hook"] for hook in self._extract_lifecycle_hooks(source)}
            reads = [name for name in reads if name not in lifecycle_names]

            # 检测副作用
            effects = []
            for pattern, effect_type in self.SIDE_EFFECT_PATTERNS:
                if pattern in body_text:
                    if effect_type not in effects:
                        effects.append(effect_type)

            methods.append({
                "name": pp["key"],
                "params": pp.get("params", []),
                "body": body_text[:500],
                "is_async": is_async,
                "reads_inferred": reads,
                "writes_inferred": writes,
                "emits_inferred": emits,
                "calls_inferred": calls,
                "side_effects_inferred": effects,
            })

        return methods

    def _extract_lifecycle_hooks(self, source: str) -> List[dict]:
        """提取生命周期钩子。"""
        hooks = []

        for hook_name in self.LIFECYCLE_HOOKS:
            body_text = ""

            func_pat = re.search(rf'{hook_name}\s*\((.*?)\)\s*\{{', source, re.DOTALL)
            assign_pat = re.search(rf'{hook_name}\s*:\s*(?:async\s+)?function\s*\((.*?)\)\s*\{{', source, re.DOTALL)

            match = func_pat or assign_pat
            if not match:
                continue

            brace_start = source.find('{', match.start())
            if brace_start >= 0:
                body_text = _extract_object_body(source, brace_start)

            reads = _extract_identifiers(body_text)
            writes = self._extract_writes(body_text)
            responsibilities = self._infer_lifecycle_responsibilities(body_text)

            hooks.append({
                "vue_hook": hook_name,
                "san_hook": self.SAN_LIFECYCLE_MAP.get(hook_name),
                "body": body_text[:500],
                "responsibilities_inferred": responsibilities,
                "state_reads": reads,
                "state_writes": writes,
                "cleanup_required": hook_name in ("mounted", "beforeDestroy", "destroyed"),
            })

        return hooks

    def _extract_emits(self, source: str) -> List[str]:
        """提取 emits 声明。"""
        # emits: ['a', 'b']
        arr_match = re.search(r'emits\s*:\s*\[([^\]]+)\]', source)
        if arr_match:
            return re.findall(r'["\']([^"\']+)["\']', arr_match.group(1))

        # emits: { 'a': null, 'b': function }
        obj_match = re.search(r'emits\s*:\s*\{([^}]+)\}', source)
        if obj_match:
            return re.findall(r'["\']?(\w+)["\']?\s*:', obj_match.group(1))

        return []

    def _extract_filters(self, source: str) -> List[dict]:
        """提取 Vue 2 过滤器。"""
        filters = []
        m = re.search(r'filters\s*:\s*\{', source)
        if not m:
            return filters

        body = _extract_object_body(source, m.end() - 1)
        props = _extract_object_properties(body)

        for pp in props:
            filters.append({
                "name": pp["key"],
                "params": pp.get("params", []),
                "body": pp["value"][:200],
            })

        return filters

    def _extract_simple_list(self, source: str, key: str) -> List[str]:
        """提取简单数组或对象 key 选项。"""
        # 数组: key: ['a', 'b']
        arr_match = re.search(rf'{key}\s*:\s*\[([^\]]+)\]', source)
        if arr_match:
            return re.findall(r'["\']([^"\']+)["\']', arr_match.group(1))
        # 对象: key: { a: ..., b: ... }
        obj_match = re.search(rf'{key}\s*:\s*\{{([^}}]+)\}}', source)
        if obj_match:
            return re.findall(r'["\']?(\w+)["\']?\s*:', obj_match.group(1))
        return []

    def _extract_top_level_declarations(self, source: str) -> List[dict]:
        """提取 script 顶层声明。"""
        decls = []
        # const/let/var 声明
        var_pat = r'(const|let|var)\s+(\w+)\s*=\s*'
        for m in re.finditer(var_pat, source):
            decls.append({
                "name": m.group(2),
                "kind": m.group(1),
                "is_used_in_component": False,
            })

        # function 声明
        func_pat = r'function\s+(\w+)\s*\('
        for m in re.finditer(func_pat, source):
            decls.append({
                "name": m.group(1),
                "kind": "function",
                "is_used_in_component": False,
            })

        return decls

    def _extract_writes(self, body_text: str) -> List[str]:
        writes: list[str] = []

        assignment_patterns = [
            r'this\.(\w+)\s*=\s*',
            r'this\.(\w+)\s*\+=\s*',
            r'this\.(\w+)\s*-=\s*',
            r'this\.(\w+)\+\+',
            r'this\.(\w+)--',
            r'this\.data\.set\(\s*["\']([^"\']+)["\']',
        ]
        for pat in assignment_patterns:
            writes.extend(re.findall(pat, body_text))

        mutation_targets = re.findall(r'this\.(\w+)\.(?:push|pop|shift|unshift|splice|sort|reverse)\s*\(', body_text)
        writes.extend(mutation_targets)

        deduped: list[str] = []
        for item in writes:
            if item not in deduped:
                deduped.append(item)
        return deduped

    def _extract_method_calls(self, body_text: str, method_names: List[str], self_name: str) -> List[str]:
        calls: list[str] = []
        for name in method_names:
            if name == self_name:
                continue
            if re.search(rf'(?:this\.)?{name}\s*\(', body_text):
                calls.append(name)
        return calls

    def _infer_lifecycle_responsibilities(self, body_text: str) -> List[str]:
        responsibilities: list[str] = []
        if re.search(r'(this\.|this\.data\.set\()', body_text):
            responsibilities.append('init_state')
        if 'setInterval' in body_text or 'setTimeout' in body_text:
            responsibilities.append('start_timer')
        if 'clearInterval' in body_text or 'clearTimeout' in body_text:
            responsibilities.append('cleanup')
        if 'localStorage' in body_text or 'sessionStorage' in body_text:
            responsibilities.append('read_storage')
        if 'fetch(' in body_text or 'axios' in body_text or 'await ' in body_text:
            responsibilities.append('async_init')
        if not responsibilities:
            responsibilities.append('unknown')
        return responsibilities

    @staticmethod
    def _infer_type(value: str) -> str:
        v = value.strip()
        if v in ("true", "false"):
            return "boolean"
        if v in ("null", "undefined"):
            return "null"
        if re.match(r'^-?\d+(\.\d+)?$', v):
            return "number"
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            return "string"
        if v.startswith("["):
            return "array"
        if v.startswith("{"):
            return "object"
        if v in ("() =>", "function"):
            return "function"
        return "unknown"


# 便捷调用
def extract_script(source: str) -> dict:
    return ScriptExtractor().extract(source)