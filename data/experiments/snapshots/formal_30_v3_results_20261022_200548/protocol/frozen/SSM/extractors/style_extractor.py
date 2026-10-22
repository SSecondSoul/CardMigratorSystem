"""
SSM Extractors — 样式结构提取器

从 Vue 组件的 <style> 块中提取：
- style_blocks       样式块列表（含量/属性）
- css_rules          CSS 规则摘要
- css_variables      CSS 自定义属性（变量）
- layout_features    布局特征

同时分析模板中的 class/style 绑定，提取：
- static_classes     静态类名
- dynamic_class_bindings  动态类名绑定
- dynamic_style_bindings  动态样式绑定
"""

import re
from typing import Any, Optional, List


# ── CSS 解析工具 ──────────────────────────────────────────

class CSSRuleParser:
    """轻量级 CSS 规则解析器（不依赖 PostCSS）。"""

    def __init__(self, css_text: str):
        self.css_text = css_text
        self.rules: list[dict] = []
        self.variables: list[dict] = []
        self.layout_features: list[dict] = []

    def parse(self):
        self._extract_rules()
        self._extract_variables()
        self._extract_layout_features()

    def _extract_rules(self):
        """提取 CSS 规则。"""
        # 匹配选择器块: selector { declarations }
        rule_re = re.compile(
            r'([^{}]+)\s*\{([^{}]*)\}',
            re.DOTALL
        )

        for match in rule_re.finditer(self.css_text):
            selector_text = match.group(1).strip()
            declarations_text = match.group(2).strip()

            if not selector_text or not declarations_text:
                continue

            # 跳过 @-rules（它们有单独处理）
            if selector_text.strip().startswith("@"):
                continue

            selectors = [s.strip() for s in selector_text.split(",") if s.strip()]

            declarations = {}
            for decl in declarations_text.split(";"):
                decl = decl.strip()
                if ":" in decl:
                    key, _, val = decl.partition(":")
                    declarations[key.strip()] = val.strip()

            # 检测特征
            has_pseudo = any(
                ":" in s and not s.startswith(":root") and not s.startswith(":host")
                for s in selectors
            )
            has_media = "@media" in self.css_text
            has_keyframes = "@keyframes" in self.css_text

            # 相关类名
            related_classes = []
            for sel in selectors:
                classes = re.findall(r'\.([a-zA-Z_][\w-]*)', sel)
                related_classes.extend(classes)

            self.rules.append({
                "selectors": selectors,
                "declarations": declarations,
                "has_pseudo": has_pseudo,
                "has_media": has_media,
                "has_keyframes": has_keyframes,
                "related_classes": list(set(related_classes)),
            })

    def _extract_variables(self):
        """提取 CSS 自定义属性（--* 变量）。"""
        var_decl_re = re.compile(
            r'(\-\-[\w-]+)\s*:\s*([^;]+);'
        )

        for match in var_decl_re.finditer(self.css_text):
            name = match.group(1)
            value = match.group(2).strip()

            # 查找定义该变量的选择器
            pos = match.start()
            scope_selector = self._find_parent_selector(pos)

            self.variables.append({
                "name": name,
                "value": value,
                "scope_selector": scope_selector,
            })

    def _extract_layout_features(self):
        """从 CSS 推断布局特征。"""
        features_map = {
            "flex": [r'display\s*:\s*flex', r'display\s*:\s*inline-flex'],
            "grid": [r'display\s*:\s*grid', r'display\s*:\s*inline-grid'],
            "absolute": [r'position\s*:\s*absolute'],
            "fixed": [r'position\s*:\s*fixed'],
            "relative": [r'position\s*:\s*relative'],
            "transition": [r'transition\s*:', r'animation\s*:'],
            "transform": [r'transform\s*:'],
            "responsive": [r'@media\s+'],
        }

        for feature, patterns in features_map.items():
            for pat in patterns:
                if re.search(pat, self.css_text, re.IGNORECASE):
                    self.layout_features.append({
                        "feature": feature,
                        "evidence": f"匹配模式: {pat}",
                    })
                    break

    def _find_parent_selector(self, pos: int) -> Optional[str]:
        """从指定位置向前查找所在的选择器。"""
        before = self.css_text[:pos]
        # 向前找最近的 {
        brace_pos = before.rfind("{")
        if brace_pos < 0:
            return ":root"

        # 向前找选择器
        chunk = self.css_text[brace_pos - 300:brace_pos] if brace_pos > 300 else self.css_text[:brace_pos]
        selectors = re.findall(r'([^{};]+)$', chunk.split("}")[-1] if "}" in chunk else chunk)
        if selectors:
            return selectors[-1].strip()
        return ":root"


# ── 样式提取器主类 ────────────────────────────────────────

class StyleExtractor:

    def __init__(self):
        pass

    def extract(self, style_blocks_raw: list[dict]) -> dict:
        """从原始样式块列表提取结构化样式。

        Args:
            style_blocks_raw: 来自 vue_parser 的 style 块列表，
              每项: {"content": "...", "scoped": True/False, "lang": "css", ...}
        """
        if not style_blocks_raw:
            return {
                "style_blocks": [],
                "css_rules": [],
                "css_variables": [],
                "layout_features_inferred": [],
            }

        all_rules = []
        all_variables = []
        all_layout_features = []
        formatted_blocks = []

        for block in style_blocks_raw:
            attrs = block.get("attrs", {})
            content = block.get("content", "")
            lang = block.get("lang") or attrs.get("lang", "css")
            scoped = bool(block.get("scoped", attrs.get("scoped", False)))
            module = bool(block.get("module", attrs.get("module", False)))

            formatted_blocks.append({
                "content": content,
                "lang": lang,
                "scoped": scoped,
                "module": module,
                "attrs": attrs,
            })

            if content.strip():
                parser = CSSRuleParser(content)
                parser.parse()
                all_rules.extend(parser.rules)
                all_variables.extend(parser.variables)
                all_layout_features.extend(parser.layout_features)

        return {
            "style_blocks": formatted_blocks,
            "css_rules": all_rules,
            "css_variables": all_variables,
            "layout_features_inferred": all_layout_features,
        }

    def extract_template_classes(self, template_html: str) -> dict:
        """从模板 HTML 中提取静态/动态类名和样式绑定。

        返回 {"static_classes": [...], "dynamic_class_bindings": [...],
               "dynamic_style_bindings": [...]}
        """
        static_classes = self._extract_static_classes(template_html)
        dynamic_class_bindings = self._extract_dynamic_class_bindings(template_html)
        dynamic_style_bindings = self._extract_dynamic_style_bindings(template_html)

        return {
            "static_classes": static_classes,
            "dynamic_class_bindings": dynamic_class_bindings,
            "dynamic_style_bindings": dynamic_style_bindings,
        }

    def _extract_static_classes(self, html: str) -> List[dict]:
        """提取 static class 属性值。避免误匹配 :class / v-bind:class。"""
        results = []
        seen = set()

        class_re = re.compile(
            r'(?<![:@\w-])class\s*=\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        )

        for match in class_re.finditer(html):
            class_value = match.group(1)

            if "{{" in class_value or "{" in class_value:
                continue

            for cn in class_value.split():
                cn = cn.strip()
                if cn and cn not in seen:
                    seen.add(cn)
                    results.append({
                        "class_name": cn,
                        "node_ids": [],
                        "semantic_role": self._infer_semantic_role(cn),
                    })

        return results

    def _extract_dynamic_class_bindings(self, html: str) -> List[dict]:
        """提取 :class="..." 动态绑定。"""
        results = []

        # :class="expr" 或 v-bind:class="expr"
        patterns = [
            r'(?<!\w):class\s*=\s*["\']([^"\']+)["\']',
            r'v-bind\s*:\s*class\s*=\s*["\']([^"\']+)["\']',
        ]

        for pat in patterns:
            for match in re.finditer(pat, html):
                expr = match.group(1)

                # 判断表达式类型
                expr_type = self._classify_class_expression(expr)

                # 提取可能的类名
                possible_classes = self._extract_possible_classes(expr, expr_type)

                deps = re.findall(r'\b([a-zA-Z_$][\w.$]*)', expr)
                KEYWORDS = {"true", "false", "null", "undefined", "this", "Math", "Date"}
                deps = [d for d in deps if d not in KEYWORDS and not d.isdigit()]

                san_strategy = self._class_san_strategy(expr_type)

                results.append({
                    "node_id": "",
                    "source_expression": expr,
                    "expression_type": expr_type,
                    "dependencies": deps,
                    "possible_classes": possible_classes,
                    "san_strategy": san_strategy,
                })

        return results

    def _extract_dynamic_style_bindings(self, html: str) -> List[dict]:
        """提取 :style="..." 动态绑定。"""
        results = []

        patterns = [
            r'(?<!\w):style\s*=\s*["\']([^"\']+)["\']',
            r'v-bind\s*:\s*style\s*=\s*["\']([^"\']+)["\']',
        ]

        for pat in patterns:
            for match in re.finditer(pat, html):
                expr = match.group(1)
                expr_type = "object" if "{" in expr else ("string" if "'" in expr or '"' in expr else "unknown")
                deps = re.findall(r'\b([a-zA-Z_$][\w.$]*)', expr)
                KEYWORDS = {"true", "false", "null", "undefined", "this", "Math", "Date"}
                deps = [d for d in deps if d not in KEYWORDS and not d.isdigit()]

                results.append({
                    "node_id": "",
                    "source_expression": expr,
                    "expression_type": expr_type,
                    "dependencies": deps,
                    "san_strategy": f"style=\"{{{{ {expr} }}}}\"" if expr_type == "string"
                                    else "style 字符串绑定的方式",
                })

        return results

    @staticmethod
    def _classify_class_expression(expr: str) -> str:
        """分类 :class 绑定表达式。"""
        expr = expr.strip()
        if expr.startswith("{"):
            return "object"
        if expr.startswith("["):
            return "array"
        if "?" in expr and ":" in expr:
            return "ternary"
        if re.match(r'^[a-zA-Z_$][\w.$]*$', expr):
            return "string"
        return "unknown"

    @staticmethod
    def _extract_possible_classes(expr: str, expr_type: str) -> List[str]:
        """从 :class 表达式中提取可能出现的 CSS 类名。"""
        classes = []
        if expr_type == "object":
            # {'class-a': cond, 'class-b': cond2}
            keys = re.findall(r'["\']([^"\']+)["\']\s*:', expr)
            classes.extend(keys)
        elif expr_type == "array":
            # ['class-a', expr, { 'class-b': cond }]
            strings = re.findall(r'["\']([^"\']+)["\']', expr)
            classes.extend(strings)
        elif expr_type == "ternary":
            # cond ? 'class-a' : 'class-b'
            strings = re.findall(r'["\']([^"\']+)["\']', expr)
            classes.extend(strings)
        return classes

    @staticmethod
    def _class_san_strategy(expr_type: str) -> str:
        return {
            "object": "将对象形式转为字符串拼接，如 class=\"{{cond ? 'active' : ''}}\"",
            "array": "将数组展开为字符串拼接",
            "ternary": "class=\"{{cond ? 'a' : 'b'}}\"",
            "string": "直接作为 class 值",
        }.get(expr_type, "需要手动迁移")

    @staticmethod
    def _infer_semantic_role(class_name: str) -> str:
        """从类名推断语义角色。"""
        role_map = {
            "header": "header",
            "footer": "footer",
            "nav": "navigation",
            "modal": "modal",
            "sidebar": "sidebar",
            "container": "container",
            "card": "card",
            "list": "list",
            "item": "item",
            "btn": "button",
            "button": "button",
            "input": "input",
            "form": "form",
            "table": "table",
            "overlay": "overlay",
            "tooltip": "tooltip",
            "badge": "badge",
            "avatar": "avatar",
            "icon": "icon",
            "loading": "loading",
            "empty": "empty-state",
            "error": "error",
            "success": "success",
            "warning": "warning",
        }
        for keyword, role in role_map.items():
            if keyword in class_name.lower():
                return role
        return "generic"


# 便捷调用
def extract_styles(style_blocks: list) -> dict:
    return StyleExtractor().extract(style_blocks)


def extract_template_classes(html: str) -> dict:
    return StyleExtractor().extract_template_classes(html)