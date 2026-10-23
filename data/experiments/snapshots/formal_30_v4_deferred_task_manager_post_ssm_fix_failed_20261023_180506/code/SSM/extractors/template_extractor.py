"""
SSM Extractors — 模板结构提取器

从 Vue 模板 HTML 中提取：
- dom_tree         递归 DOM 节点树
- component_refs   子组件引用
- slot_distribution 插槽分布
- directives_registry 指令汇总
- event_bindings   事件绑定列表
"""

import re
from typing import Any, Optional, List
from html.parser import HTMLParser


# ── 静态工具 ──────────────────────────────────────────────

def _kebab_case(name: str) -> str:
    """PascalCase / camelCase → kebab-case。"""
    return re.sub(r'(?<!^)(?=[A-Z])', '-', name).lower()


def _is_likely_component(tag: str) -> bool:
    """判断标签名是否为 Vue 组件（首字母大写或包含连字符且非标准 HTML）。"""
    STANDARD_HTML_TAGS = {
        "div", "span", "p", "a", "img", "input", "button", "form",
        "select", "option", "textarea", "label", "table", "tr", "td",
        "th", "thead", "tbody", "ul", "ol", "li", "h1", "h2", "h3",
        "h4", "h5", "h6", "header", "footer", "section", "article",
        "nav", "main", "aside", "svg", "path", "circle", "g", "line",
        "polyline", "polygon", "rect", "text", "br", "hr", "pre",
        "code", "em", "strong", "i", "b", "u", "small", "style",
        "script", "template", "slot", "component", "transition",
        "keep-alive", "transition-group", "teleport", "suspense",
    }
    tag_lower = tag.lower()
    if tag_lower in STANDARD_HTML_TAGS:
        return False
    if tag[0].isupper():
        return True
    if "-" in tag and tag_lower not in STANDARD_HTML_TAGS:
        return True
    return False


# ── Vue 指令解析 ──────────────────────────────────────────

class VueDirective:
    """解析后的 Vue 指令。"""

    DIRECTIVE_NAMES = {
        "v-if": "v-if", "v-else-if": "v-else-if", "v-else": "v-else",
        "v-show": "v-show", "v-for": "v-for", "v-model": "v-model",
        "v-bind": "v-bind", "v-on": "v-on", "v-slot": "v-slot",
        "v-html": "v-html", "v-text": "v-text", "v-once": "v-once",
        "v-pre": "v-pre", "v-cloak": "v-cloak",
        ":": "v-bind", "@": "v-on", "#": "v-slot",
    }

    SAN_EQUIVALENTS = {
        "v-if": "s-if",
        "v-else-if": "s-else-if",
        "v-else": "s-else",
        "v-for": "s-for",
        "v-show": "s-if 或 CSS display 控制",
        "v-bind": "attr 绑定或 class/style 字符串拼接",
        "v-on": "on-event",
        "v-model": "value={= field =}",
        "v-html": "s-html",
        "v-slot": "slot",
    }

    MIGRATION_NOTES = {
        ("v-if",): "v-if → s-if，语法一致",
        ("v-for",): "v-for=\"item in list\" → s-for=\"item in list\"，语法基本一致",
        ("v-bind", "class"): ":class 对象/数组需转为字符串拼接",
        ("v-bind", "style"): ":style 对象需转为 style 字符串绑定",
        ("v-on",): "@event → on-event，修饰符需显式处理",
        ("v-model",): "v-model → value={= field =}，复选框用 checked={= field =}",
        ("v-show",): "v-show → s-if 或通过 CSS display 控制",
    }

    def __init__(self, attr_name: str, value: str = ""):
        self.raw = attr_name
        self.raw_value = value
        self.directive_name = ""
        self.argument = ""
        self.modifiers: list[str] = []
        self.expression = value
        self._parse()

    def _parse(self):
        raw = self.raw
        value = self.raw_value

        # 支持：v-directive:arg.mod1.mod2 / @click.stop / :class / #default
        full_match = re.match(
            r'^(v-[a-z-]+)(?::([a-zA-Z_$][\w.$-]*))?((?:\.[a-zA-Z_$][\w.$-]*)*)$',
            raw
        )
        shorthand_match = re.match(
            r'^([@:#])([a-zA-Z_$][\w.$-]*)?((?:\.[a-zA-Z_$][\w.$-]*)*)$',
            raw
        )

        if full_match:
            prefix = full_match.group(1)
            self.argument = full_match.group(2) or ""
            modifier_text = full_match.group(3) or ""
        elif shorthand_match:
            prefix = shorthand_match.group(1)
            self.argument = shorthand_match.group(2) or ""
            modifier_text = shorthand_match.group(3) or ""
        else:
            self.directive_name = "custom"
            self.argument = raw
            self.expression = value
            return

        self.modifiers = re.findall(r'\.([a-zA-Z_$][\w.$-]*)', modifier_text)

        # 解析前缀
        self.directive_name = self.DIRECTIVE_NAMES.get(prefix, prefix)
        self.expression = value

    def is_event(self) -> bool:
        return self.directive_name in ("v-on",) or self.raw.startswith("@")

    def is_bind(self) -> bool:
        return self.directive_name in ("v-bind",) or self.raw.startswith(":")

    def is_model(self) -> bool:
        return self.directive_name == "v-model"

    def get_event_name(self) -> str:
        if self.is_event():
            return self.argument or "click"
        return ""

    def get_bind_attr(self) -> str:
        if self.is_bind():
            return self.argument or ""
        return ""

    def get_san_equivalent(self) -> str:
        base = self.SAN_EQUIVALENTS.get(self.directive_name, self.directive_name)
        return base

    def get_migration_note(self) -> str:
        for (dname, *arg), note in self.MIGRATION_NOTES.items():
            if self.directive_name == dname:
                if not arg or self.argument in arg:
                    return note
        return f"{self.directive_name} → 需要迁移"

    def extract_dependencies(self) -> List[str]:
        """从表达式中提取标识符。"""
        if not self.expression:
            return []
        # 匹配 JS 标识符
        idents = re.findall(r'\b([a-zA-Z_$][\w.$]*)', self.expression)
        # 过滤关键字
        KEYWORDS = {"true", "false", "null", "undefined", "this", "new",
                    "return", "if", "else", "in", "of", "typeof", "void",
                    "Math", "Date", "JSON", "Object", "Array", "String",
                    "Number", "Boolean"}
        return [i for i in idents if i not in KEYWORDS and not i.isdigit()]

    def to_dict(self) -> dict:
        return {
            "directive_name": self.directive_name,
            "argument": self.argument,
            "modifiers": self.modifiers,
            "expression": self.expression,
            "dependencies": self.extract_dependencies(),
            "san_equivalent": self.get_san_equivalent(),
            "migration_note": self.get_migration_note(),
        }

    def to_event_dict(self, node_id: str = "", tag: str = "",
                      is_component_event: bool = False) -> dict:
        handler_type = "identifier"
        handler_name = self.expression
        args: list[str] = []

        # 处理方法调用: handler(arg1, arg2)
        call_match = re.match(r'(\w+)\s*\((.*)\)', self.expression)
        if call_match:
            handler_type = "method_call"
            handler_name = call_match.group(1)
            args = [a.strip() for a in call_match.group(2).split(",") if a.strip()]
        elif re.match(r'^\(.*\)\s*=>', self.expression):
            handler_type = "inline_expression"
            handler_name = ""
        elif re.match(r'^\{', self.expression):
            handler_type = "inline_expression"
            handler_name = ""

        return {
            "node_id": node_id,
            "element_tag": tag,
            "event_name": self.get_event_name(),
            "modifiers": self.modifiers,
            "handler_expression": self.expression,
            "handler_type": handler_type,
            "handler_name": handler_name,
            "arguments": args,
            "is_component_event": is_component_event,
        }


# ── 模板 DOM 节点 ──────────────────────────────────────────

class TemplateNode:
    """模板 DOM 树节点。"""
    _NODE_ID_COUNTER = 0

    def __init__(self, tag: str, attrs: dict, parent: Optional["TemplateNode"] = None,
                 is_void: bool = False):
        TemplateNode._NODE_ID_COUNTER += 1
        self.node_id = f"{tag or 'text'}_{TemplateNode._NODE_ID_COUNTER}"
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.is_void = is_void
        self.children: list[TemplateNode] = []
        self.text_content: str = ""
        self.depth = parent.depth + 1 if parent else 0
        self.node_type = self._infer_type()

        self.directives: list[VueDirective] = []
        self.event_bindings: list[dict] = []
        self.static_attrs: dict[str, str] = {}
        self.dynamic_attrs: list[dict] = []
        self.text_bindings: list[dict] = []

        self._process_attrs()

    def _infer_type(self) -> str:
        if not self.tag:
            return "text"
        if self.tag.lower() == "slot":
            return "slot"
        if _is_likely_component(self.tag):
            return "component"
        return "element"

    def _process_attrs(self):
        for attr_name, attr_value in self.attrs.items():
            # 指令
            if attr_name.startswith("v-") or attr_name.startswith("@") or \
               attr_name.startswith(":") or attr_name.startswith("#"):
                d = VueDirective(attr_name, attr_value)
                self.directives.append(d)

                # 事件绑定
                if d.is_event():
                    event_dict = d.to_event_dict(
                        node_id=self.node_id,
                        tag=self.tag,
                        is_component_event=(self.node_type == "component")
                    )
                    self.event_bindings.append(event_dict)

                # 动态属性
                if d.is_bind() and d.get_bind_attr():
                    self.dynamic_attrs.append({
                        "source_attr": attr_name,
                        "target_attr": d.get_bind_attr(),
                        "expression": d.expression,
                        "dependencies": d.extract_dependencies(),
                        "san_strategy": d.get_san_equivalent(),
                    })
                elif d.is_model():
                    self.dynamic_attrs.append({
                        "source_attr": attr_name,
                        "target_attr": "value",
                        "expression": d.expression,
                        "dependencies": d.extract_dependencies(),
                        "san_strategy": d.get_san_equivalent(),
                    })
            else:
                self.static_attrs[attr_name] = attr_value

    def to_dict(self) -> dict:
        semantic_role = ""
        if "class" in self.static_attrs:
            classes = self.static_attrs["class"].split()
            if classes:
                semantic_role = classes[0]

        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "source_tag": self.tag,
            "san_tag": _kebab_case(self.tag) if self.node_type == "component" else self.tag,
            "depth": self.depth,
            "parent_id": self.parent.node_id if self.parent else None,
            "path": self._build_path(),
            "semantic_role": semantic_role,
            "is_root": self.depth == 0,
            "is_void": self.is_void or self.tag.lower() in {
                "input", "img", "br", "hr", "meta", "link", "area", "base",
                "col", "embed", "source", "track", "wbr",
            },
            "static_attrs": self.static_attrs,
            "dynamic_attrs": self.dynamic_attrs,
            "directives": [d.to_dict() for d in self.directives],
            "event_bindings": self.event_bindings,
            "text_bindings": self.text_bindings,
            "children": [c.to_dict() for c in self.children],
        }

    def _build_path(self) -> str:
        if not self.parent:
            return f"/{self.tag or 'text'}[0]"
        siblings = [c for c in self.parent.children if c.tag == self.tag]
        idx = siblings.index(self)
        return f"{self.parent._build_path()}/{self.tag or 'text'}[{idx}]"


# ── 模板 HTML 解析器 ──────────────────────────────────────

class TemplateHTMLParser(HTMLParser):
    """解析 Vue 模板 HTML 并构建 DOM 树。"""

    VOID_TAGS = {"input", "img", "br", "hr", "meta", "link", "area",
                 "base", "col", "embed", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.root: Optional[TemplateNode] = None
        self._current: Optional[TemplateNode] = None
        self._nodes: list[TemplateNode] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]):
        attrs = {k: (v or "") for k, v in attrs_list}
        is_void = tag.lower() in self.VOID_TAGS

        node = TemplateNode(tag=tag, attrs=attrs, parent=self._current,
                           is_void=is_void)

        if self._current:
            self._current.children.append(node)
        else:
            self.root = node

        self._nodes.append(node)

        if not is_void:
            self._current = node

        if is_void and self._current:
            # 自闭合标签不进入子节点
            pass

    def handle_endtag(self, tag: str):
        if self._current and self._current.tag.lower() == tag.lower():
            self._current = self._current.parent

    def handle_data(self, data: str):
        text = data.strip()
        if not text:
            return
        if not self._current:
            return

        # 检测插值表达式 {{ ... }}
        interpolation_re = re.compile(r'\{\{(.+?)\}\}')
        parts = interpolation_re.split(text)  # ["text", "expr", "text", ...]

        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue

            if i % 2 == 1:
                # 插值
                idents = re.findall(r'\b([a-zA-Z_$][\w.$]*)', part)
                KEYWORDS = {"true", "false", "null", "undefined", "this"}
                deps = [x for x in idents if x not in KEYWORDS and not x.isdigit()]
                self._current.text_bindings.append({
                    "raw_text": f"{{{{{part}}}}}",
                    "is_interpolation": True,
                    "expression": part,
                    "dependencies": deps,
                    "san_text": "{{" + part + "}}",
                })
            else:
                self._current.text_bindings.append({
                    "raw_text": part,
                    "is_interpolation": False,
                    "expression": None,
                    "dependencies": [],
                    "san_text": part,
                })

    def handle_comment(self, data: str):
        pass  # 跳过注释

    def get_result(self) -> TemplateNode:
        return self.root if self.root else TemplateNode(tag="div", attrs={})


# ── 模板提取器主类 ────────────────────────────────────────

class TemplateExtractor:

    def __init__(self):
        pass

    def extract_from_ast_analysis(self, template_analysis: dict) -> dict:
        """直接消费 Node/Vue template AST 分析结果。"""
        if not template_analysis:
            return self.extract("")
        return {
            "dom_tree": template_analysis.get("dom_tree", {}),
            "component_refs": template_analysis.get("component_refs", []),
            "slot_distribution": template_analysis.get("slot_distribution", []),
            "directives_registry": template_analysis.get("directives_registry", []),
            "event_bindings": template_analysis.get("event_bindings", []),
        }

    def extract(self, template_html: str) -> dict:
        """从模板 HTML 字符串提取完整模板结构。"""
        if not template_html or not template_html.strip():
            return {
                "dom_tree": {},
                "component_refs": [],
                "slot_distribution": [],
                "directives_registry": [],
                "event_bindings": [],
            }

        # 解析 DOM 树
        parser = TemplateHTMLParser()
        parser.feed(template_html)
        root = parser.get_result()
        all_nodes = self._collect_nodes(root)

        # 组件引用
        component_refs = self._extract_component_refs(all_nodes)

        # 插槽分布
        slot_distribution = self._extract_slot_distribution(root, all_nodes)

        # 指令注册表
        directives_registry = self._build_directives_registry(all_nodes)

        # 所有事件绑定
        all_events = []
        for node in all_nodes:
            all_events.extend(node.event_bindings)

        return {
            "dom_tree": root.to_dict(),
            "component_refs": component_refs,
            "slot_distribution": slot_distribution,
            "directives_registry": directives_registry,
            "event_bindings": all_events,
        }

    def _collect_nodes(self, root: TemplateNode) -> list[TemplateNode]:
        """收集所有节点（递归）。"""
        nodes = [root]
        for child in root.children:
            nodes.extend(self._collect_nodes(child))
        return nodes

    def _extract_component_refs(self, nodes: list[TemplateNode]) -> list[dict]:
        """提取所有组件引用。"""
        refs = []
        for node in nodes:
            if node.node_type != "component":
                continue

            props_bindings = []
            for da in node.dynamic_attrs:
                if da.get("target_attr") not in ("", None):
                    props_bindings.append({
                        "prop_name": da["target_attr"],
                        "binding_type": "expression",
                        "source_expression": da["expression"],
                        "dependencies": da["dependencies"],
                    })
            for key, val in node.static_attrs.items():
                if key not in ("class", "style", "id"):
                    props_bindings.append({
                        "prop_name": key,
                        "binding_type": "literal",
                        "source_expression": val,
                        "dependencies": [],
                    })

            slot_contents = []
            for child in node.children:
                slot_contents.append({
                    "node_id": child.node_id,
                    "tag": child.tag,
                    "type": child.node_type,
                })

            refs.append({
                "node_id": node.node_id,
                "source_name": node.tag,
                "source_tag": node.tag,
                "san_tag": _kebab_case(node.tag),
                "kebab_name": _kebab_case(node.tag),
                "pascal_name": node.tag[0].upper() + node.tag[1:] if node.tag else "",
                "definition_location": "unknown",
                "is_builtin": node.tag.lower() in {
                    "slot", "component", "transition", "keep-alive",
                    "transition-group", "teleport", "suspense",
                },
                "props_bindings": props_bindings,
                "event_bindings": node.event_bindings,
                "slot_contents": slot_contents,
            })

        return refs

    def _extract_slot_distribution(self, root: TemplateNode,
                                   nodes: list[TemplateNode]) -> list[dict]:
        """提取插槽分布信息。"""
        slots = []
        for node in nodes:
            if node.tag.lower() != "slot":
                continue
            slot_name = node.static_attrs.get("name", "default")

            # 是否有回退内容
            fallback = len(node.children) > 0 or bool(node.text_bindings)

            slots.append({
                "slot_name": slot_name,
                "node_id": node.node_id,
                "owner_component_id": None,
                "scope_bindings": [],
                "fallback_content": fallback,
                "usage_points": [],
            })

        return slots

    def _build_directives_registry(self, nodes: list[TemplateNode]) -> list[dict]:
        """构建指令注册表（去重统计）。"""
        registry: dict[str, dict] = {}
        for node in nodes:
            for d in node.directives:
                dname = d.directive_name
                if dname not in registry:
                    registry[dname] = {
                        "directive_name": dname,
                        "count": 0,
                        "example_nodes": [],
                    }
                registry[dname]["count"] += 1
                if len(registry[dname]["example_nodes"]) < 3:
                    registry[dname]["example_nodes"].append(node.node_id)
        return list(registry.values())


# 便捷调用
def extract_template(html: str) -> dict:
    return TemplateExtractor().extract(html)