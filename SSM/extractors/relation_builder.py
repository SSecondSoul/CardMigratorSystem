"""
SSM Extractors — 跨块关联分析器

负责交叉分析 template、script、styles 三个块的提取结果，生成：
- binding_graph       数据绑定关系图
- event_model         事件交互模型
- style_model         样式特征模型
- migration_hints     迁移提示
- sub_components      子组件摘要
"""

import re
from typing import Any, Optional, List, Dict


def _kebab_case(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '-', name).lower()


class RelationBuilder:
    """跨块关联分析器。"""

    def __init__(self):
        pass

    def build(self,
              template_result: dict,
              script_result: dict,
              style_result: dict) -> dict:
        """基于三个块的分析结果，构建所有跨块模型。"""

        script_options = script_result.get("options", {})

        return {
            "binding_graph": self._build_binding_graph(
                template_result, script_options),
            "event_model": self._build_event_model(
                template_result, script_options),
            "style_model": self._build_style_model(
                template_result, style_result),
            "sub_components": self._build_sub_components(
                template_result, script_options),
            "migration_hints": self._build_migration_hints(
                template_result, script_options, script_result.get("imports", [])),
        }

    # ── Binding Graph ──────────────────────────────────────

    def _build_binding_graph(self, template_result: dict,
                             script_options: dict) -> dict:
        """构建数据绑定关系图。"""
        nodes: list[dict] = []
        edges: list[dict] = []

        # ── 创建节点 ──
        # data 字段节点
        for df in script_options.get("data", []):
            nodes.append({
                "node_id": f"data.{df['name']}",
                "kind": "data",
                "name": df["name"],
                "source_location": "script.data",
            })

        # props 节点
        for p in script_options.get("props", []):
            nodes.append({
                "node_id": f"prop.{p['name']}",
                "kind": "prop",
                "name": p["name"],
                "source_location": "script.props",
            })

        # computed 节点
        for cp in script_options.get("computed", []):
            nodes.append({
                "node_id": f"computed.{cp['name']}",
                "kind": "computed",
                "name": cp["name"],
                "source_location": "script.computed",
            })

        # method 节点
        for m in script_options.get("methods", []):
            nodes.append({
                "node_id": f"method.{m['name']}",
                "kind": "method",
                "name": m["name"],
                "source_location": "script.methods",
            })

        # template 节点
        dom_tree = template_result.get("dom_tree", {})
        self._add_template_nodes(nodes, dom_tree)

        # ── 创建边 ──
        # 1) 模板绑定 → 数据源
        self._add_template_binding_edges(
            edges, dom_tree, nodes, script_options)

        # 2) computed 依赖 → data/props/computed
        self._add_computed_dependency_edges(edges, script_options)

        # 3) method 读写 → data/props
        self._add_method_access_edges(edges, script_options)

        # 4) watch 依赖 → data/props
        self._add_watch_edges(edges, script_options)

        # ── data_fields_usage ──
        data_usage = self._build_data_usage(
            dom_tree, script_options, edges)

        return {
            "nodes": nodes,
            "edges": edges,
            "data_fields_usage": data_usage,
        }

    def _add_template_nodes(self, nodes: list, dom_tree: dict):
        """递归添加模板节点。"""
        if not dom_tree:
            return

        node_id = dom_tree.get("node_id", "")
        if node_id:
            nodes.append({
                "node_id": f"template.{node_id}",
                "kind": "template_node",
                "name": node_id,
                "source_location": f"template.{dom_tree.get('source_tag', '')}",
            })

        for child in dom_tree.get("children", []):
            self._add_template_nodes(nodes, child)

    def _add_template_binding_edges(self, edges: list, dom_tree: dict,
                                    all_nodes: list, script_options: dict):
        """从模板节点的依赖创建绑定边。"""
        if not dom_tree:
            return

        self._node_binding_edges(edges, dom_tree, all_nodes, script_options)

        for child in dom_tree.get("children", []):
            self._add_template_binding_edges(edges, child, all_nodes, script_options)

    def _node_binding_edges(self, edges: list, node: dict,
                            all_nodes: list, script_options: dict):
        """单个节点的绑定边。"""
        node_id = node.get("node_id", "")

        # 指令依赖
        for d in node.get("directives", []):
            for dep in d.get("dependencies", []):
                target = self._resolve_dependency(
                    dep, all_nodes, script_options)
                if target:
                    edges.append({
                        "from": f"template.{node_id}",
                        "to": target,
                        "edge_type": "binds_to",
                        "expression": d.get("expression", ""),
                        "san_access": f"this.data.get('{dep}')",
                    })

        # 动态属性依赖
        for da in node.get("dynamic_attrs", []):
            for dep in da.get("dependencies", []):
                target = self._resolve_dependency(
                    dep, all_nodes, script_options)
                if target:
                    edges.append({
                        "from": f"template.{node_id}",
                        "to": target,
                        "edge_type": "binds_to",
                        "expression": da.get("expression", ""),
                        "san_access": f"this.data.get('{dep}')",
                    })

        # 文本插值依赖
        for tb in node.get("text_bindings", []):
            for dep in tb.get("dependencies", []):
                target = self._resolve_dependency(
                    dep, all_nodes, script_options)
                if target:
                    edges.append({
                        "from": f"template.{node_id}",
                        "to": target,
                        "edge_type": "binds_to",
                        "expression": tb.get("raw_text", ""),
                        "san_access": f"this.data.get('{dep}')",
                    })

    def _resolve_dependency(self, dep: str, all_nodes: list,
                            script_options: dict) -> Optional[str]:
        """将依赖标识符解析为节点 ID。"""
        # 数据字段
        for df in script_options.get("data", []):
            if df["name"] == dep or dep.startswith(df["name"] + "."):
                return f"data.{df['name']}"

        # props
        for p in script_options.get("props", []):
            if p["name"] == dep:
                return f"prop.{p['name']}"

        # computed
        for cp in script_options.get("computed", []):
            if cp["name"] == dep:
                return f"computed.{cp['name']}"

        return None

    def _add_computed_dependency_edges(self, edges: list, script_options: dict):
        for cp in script_options.get("computed", []):
            for dep in cp.get("dependencies_inferred", []):
                for df in script_options.get("data", []):
                    if df["name"] == dep:
                        edges.append({
                            "from": f"computed.{cp['name']}",
                            "to": f"data.{df['name']}",
                            "edge_type": "depends_on",
                            "expression": dep,
                            "san_access": f"this.data.get('{dep}')",
                        })

    def _add_method_access_edges(self, edges: list, script_options: dict):
        for m in script_options.get("methods", []):
            for dep in m.get("reads_inferred", []):
                for df in script_options.get("data", []):
                    if df["name"] == dep:
                        edges.append({
                            "from": f"method.{m['name']}",
                            "to": f"data.{df['name']}",
                            "edge_type": "reads",
                            "expression": dep,
                            "san_access": f"this.data.get('{dep}')",
                        })

    def _add_watch_edges(self, edges: list, script_options: dict):
        for w in script_options.get("watch", []):
            expr = w.get("expression", "")
            for df in script_options.get("data", []):
                if df["name"] == expr or expr.startswith(df["name"] + "."):
                    edges.append({
                        "from": f"watcher.{expr}",
                        "to": f"data.{df['name']}",
                        "edge_type": "depends_on",
                        "expression": expr,
                        "san_access": "this.watch",
                    })

    def _build_data_usage(self, dom_tree: dict,
                          script_options: dict,
                          edges: list) -> List[dict]:
        """为每个 data 字段生成使用摘要。"""
        usage = []
        for df in script_options.get("data", []):
            fname = df["name"]
            data_id = f"data.{fname}"

            # 模板使用
            read_in_template = [
                e["from"] for e in edges
                if e["to"] == data_id and e["from"].startswith("template.")
            ]

            # computed 使用
            read_in_computed = []
            for cp in script_options.get("computed", []):
                if fname in cp.get("dependencies_inferred", []):
                    read_in_computed.append(cp["name"])

            # method 使用
            read_in_methods = []
            written_in_methods = []
            for m in script_options.get("methods", []):
                if fname in m.get("reads_inferred", []):
                    read_in_methods.append(m["name"])
                if fname in m.get("writes_inferred", []):
                    written_in_methods.append(m["name"])

            # watcher
            watched_by = []
            for w in script_options.get("watch", []):
                if fname in w.get("expression", ""):
                    watched_by.append(w.get("expression"))

            # 初始来源
            init_from_props = any(
                df["name"] in m.get("reads_inferred", [])
                for m in script_options.get("methods", [])
                for h in script_options.get("lifecycle_hooks", [])
                if h.get("vue_hook") in ("created", "mounted")
            )
            init_from_external = self._detect_external_init(
                script_options, fname)

            usage.append({
                "field_name": fname,
                "read_in_template_nodes": read_in_template,
                "read_in_computed": read_in_computed,
                "read_in_methods": read_in_methods,
                "written_in_methods": written_in_methods,
                "watched_by": watched_by,
                "initialized_from_props": init_from_props,
                "initialized_from_external": init_from_external,
            })

        return usage

    @staticmethod
    def _detect_external_init(script_options: dict, field_name: str) -> Optional[str]:
        for m in script_options.get("methods", []):
            body = m.get("body", "")
            if "localStorage" in body and field_name in body:
                return "localStorage"
            if "fetch(" in body and field_name in body:
                return "api"
        return None

    # ── Event Model ────────────────────────────────────────

    def _build_event_model(self, template_result: dict,
                           script_options: dict) -> dict:
        """构建事件交互模型。"""
        dom_events: list[dict] = []
        custom_events: list[dict] = []

        # DOM 事件（来自模板）
        all_events = template_result.get("event_bindings", [])
        # 也递归收集 dom_tree 中的事件
        dom_tree = template_result.get("dom_tree", {})
        self._collect_dom_events(dom_events, dom_tree, script_options)

        # 如果 event_bindings 已包含，则使用它们填充 handler 签名
        method_map = {
            m["name"]: m for m in script_options.get("methods", [])
        }

        for evt in dom_events:
            hname = evt.get("handler_name", "")
            if hname in method_map:
                method = method_map[hname]
                evt["handler_signature_inferred"] = (
                    f"{hname}({', '.join(method.get('params', []))})"
                )
                evt["handler_method_ref"] = hname
                evt["reads"] = method.get("reads_inferred", [])
                evt["writes"] = method.get("writes_inferred", [])
                evt["side_effects"] = method.get("side_effects_inferred", [])
                evt["san_event_syntax"] = (
                    f"on-{evt.get('event_name', 'click')}"
                    f"=\"{hname}\""
                )

        # 自定义事件（父子通信）
        component_event_listeners = [
            evt for evt in template_result.get("event_bindings", [])
            if evt.get("is_component_event")
        ]

        for m in script_options.get("methods", []):
            for emit_name in m.get("emits_inferred", []):
                matched_listener = next(
                    (evt for evt in component_event_listeners if evt.get("event_name") == emit_name),
                    None,
                )
                target_component = None
                if matched_listener:
                    target_component = self._find_component_name_by_node_id(
                        template_result.get("component_refs", []),
                        matched_listener.get("node_id"),
                    )

                custom_events.append({
                    "event_name": emit_name,
                    "source_component": script_options.get("name", "unknown"),
                    "target_component": target_component,
                    "emit_points": [m["name"]],
                    "emit_expression": f"$emit('{emit_name}', ...)",
                    "san_emit": f"this.fire('{emit_name}', ...)",
                    "listener_handler": matched_listener.get("handler_name") if matched_listener else None,
                    "listener_node_id": matched_listener.get("node_id") if matched_listener else None,
                    "payload_schema": {"type": "unknown", "fields_inferred": []},
                    "state_impact": m.get("writes_inferred", []),
                })

        return {
            "dom_events": dom_events,
            "custom_events": custom_events,
        }

    def _collect_dom_events(self, events: list, dom_node: dict,
                            script_options: dict):
        """递归收集 DOM 事件。"""
        if not dom_node:
            return
        for evt in dom_node.get("event_bindings", []):
            evt_copy = dict(evt)
            evt_copy["is_native"] = not evt.get("is_component_event", False)
            events.append(evt_copy)

        for child in dom_node.get("children", []):
            self._collect_dom_events(events, child, script_options)

    def _find_component_name_by_node_id(self, component_refs: list, node_id: Optional[str]) -> Optional[str]:
        if not node_id:
            return None
        for ref in component_refs:
            if ref.get("node_id") == node_id:
                return ref.get("source_name")
        return None

    # ── Style Model ────────────────────────────────────────

    def _build_style_model(self, template_result: dict,
                           style_result: dict) -> dict:
        """构建样式特征模型。"""
        scoped = any(b.get("scoped", False) for b in style_result.get("style_blocks", []))

        # 模板中的 style 相关提取
        dom_tree = template_result.get("dom_tree", {})

        static_classes = self._collect_static_classes(dom_tree)
        dynamic_classes = self._collect_dynamic_classes(dom_tree)
        dynamic_styles = self._collect_dynamic_styles(dom_tree)

        # CSS 规则摘要
        css_rules = style_result.get("css_rules", [])
        css_summary = []
        for rule in css_rules:
            related = rule.get("related_classes", [])
            affected = [
                c for c in related
                if any(sc.get("class_name") == c for sc in static_classes)
            ]
            css_summary.append({
                "selector": ", ".join(rule.get("selectors", [])),
                "declarations": rule.get("declarations", {}),
                "pseudo_state": (
                    "hover" if ":hover" in ", ".join(rule.get("selectors", []))
                    else "focus" if ":focus" in ", ".join(rule.get("selectors", []))
                    else "active" if ":active" in ", ".join(rule.get("selectors", []))
                    else None
                ),
                "affected_classes": affected,
                "migration_keep": True,
            })

        return {
            "scoped": scoped,
            "static_classes": static_classes,
            "dynamic_class_bindings": dynamic_classes,
            "dynamic_style_bindings": dynamic_styles,
            "css_rules_summary": css_summary,
            "layout_features_inferred": style_result.get("layout_features_inferred", []),
        }

    def _collect_static_classes(self, dom_node: dict) -> List[dict]:
        """递归收集静态类名。"""
        results: List[dict] = []
        if not dom_node:
            return results

        static_attrs = dom_node.get("static_attrs", {})
        if "class" in static_attrs:
            for cn in static_attrs["class"].split():
                cn = cn.strip()
                if cn:
                    results.append({
                        "class_name": cn,
                        "node_ids": [dom_node.get("node_id", "")],
                        "semantic_role": dom_node.get("semantic_role", "generic"),
                    })

        for child in dom_node.get("children", []):
            results.extend(self._collect_static_classes(child))

        return results

    def _collect_dynamic_classes(self, dom_node: dict) -> List[dict]:
        """递归收集动态类名绑定。"""
        results: List[dict] = []
        if not dom_node:
            return results

        for da in dom_node.get("dynamic_attrs", []):
            if da.get("target_attr") == "class":
                deps = da.get("dependencies", [])
                # 从表达式中提取类名
                expr = da.get("expression", "")
                expr_type = "object" if "{" in expr else (
                    "array" if "[" in expr else (
                        "ternary" if "?" in expr else "unknown"
                    )
                )
                possible = re.findall(r'["\']([^"\']+)["\']', expr)

                results.append({
                    "node_id": dom_node.get("node_id", ""),
                    "source_expression": expr,
                    "expression_type": expr_type,
                    "dependencies": deps,
                    "possible_classes": possible,
                    "san_strategy": self._class_san_strategy(expr_type),
                })

        for child in dom_node.get("children", []):
            results.extend(self._collect_dynamic_classes(child))

        return results

    def _collect_dynamic_styles(self, dom_node: dict) -> List[dict]:
        """递归收集动态样式绑定。"""
        results: List[dict] = []
        if not dom_node:
            return results

        for da in dom_node.get("dynamic_attrs", []):
            if da.get("target_attr") == "style":
                results.append({
                    "node_id": dom_node.get("node_id", ""),
                    "source_expression": da.get("expression", ""),
                    "expression_type": "object" if "{" in da.get("expression", "") else "unknown",
                    "dependencies": da.get("dependencies", []),
                    "san_strategy": "style 字符串绑定",
                })

        for child in dom_node.get("children", []):
            results.extend(self._collect_dynamic_styles(child))

        return results

    @staticmethod
    def _class_san_strategy(expr_type: str) -> str:
        return {
            "object": "class=\"{{cond ? 'active' : ''}}\" 字符串拼接",
            "array": "数组展开为字符串拼接",
            "ternary": "class=\"{{cond ? 'a' : 'b'}}\"",
        }.get(expr_type, "需要手动迁移")

    # ── Sub Components ─────────────────────────────────────

    def _build_sub_components(self, template_result: dict,
                              script_options: dict) -> List[dict]:
        """构建子组件摘要。"""
        component_refs = template_result.get("component_refs", [])
        script_components = script_options.get("components", [])

        # 构建 registry map
        registry_map = {c["registered_name"]: c for c in script_components}
        for component in script_components:
            source_name = component.get("source_name", "")
            if source_name:
                registry_map.setdefault(source_name, component)

        subs = []
        for ref in component_refs:
            source_name = ref.get("source_name", "")
            # 匹配 script 中的注册
            reg_match = registry_map.get(source_name) or registry_map.get(
                _kebab_case(source_name))

            subs.append({
                "name": source_name,
                "is_inline": (
                    reg_match.get("definition_location") == "inline"
                    if reg_match else False
                ),
                "is_imported": (
                    reg_match.get("definition_location") == "unknown"
                    if reg_match else False
                ),
                "import_source": None,
                "template_summary": {
                    "tag": ref.get("source_tag"),
                    "props_count": len(ref.get("props_bindings", [])),
                    "event_count": len(ref.get("event_bindings", [])),
                },
                "props": [p["prop_name"] for p in ref.get("props_bindings", [])],
                "data_fields": [],
                "computed_props": [],
                "methods": [],
                "emits": [e.get("event_name", "") for e in ref.get("event_bindings", [])],
                "events_to_parent": [],
                "san_registration": f"components: {{ '{_kebab_case(source_name)}': {source_name} }}",
            })

        return subs

    # ── Migration Hints ────────────────────────────────────

    def _build_migration_hints(self, template_result: dict,
                               script_options: dict,
                               imports: list) -> dict:
        """自动检测迁移模式并生成提示。"""
        directives_registry = template_result.get("directives_registry", [])

        patterns = self._detect_patterns(
            directives_registry, script_options, template_result)

        data_access = self._build_data_access_plan(script_options)

        return {
            "detected_patterns": patterns,
            "data_access_conversion_plan": data_access,
        }

    def _detect_patterns(self, directives: list,
                         script_options: dict,
                         template_result: dict) -> list:
        """基于 AST 特征检测迁移模式。"""
        dir_names = {d["directive_name"] for d in directives} if directives else set()

        # 模板指令模式
        template_patterns = [
            ("event_click", "v-on" in dir_names,
             "存在 @click 或 v-on，需转为 on-click", "low"),
            ("v_if", "v-if" in dir_names,
             "存在 v-if，需转为 s-if", "low"),
            ("v_for", "v-for" in dir_names,
             "存在 v-for，需转为 s-for", "low"),
            ("v_model", "v-model" in dir_names,
             "存在 v-model，需转为 value={= field =}", "medium"),
            ("v_show", "v-show" in dir_names,
             "存在 v-show，需转为 s-if 或 CSS display 控制", "medium"),
            ("dynamic_bind", "v-bind" in dir_names,
             "存在 :attr 动态绑定，需保留属性绑定语法", "low"),
        ]

        # 脚本模式
        script_patterns = [
            ("emit", any(
                m.get("emits_inferred") for m in
                script_options.get("methods", [])
            ),
             "存在 $emit 调用，需转为 this.fire", "low"),
            ("data_access", True,  # 几乎所有 Vue 组件都需要
             "methods 中存在 this.xxx 访问，需统一改为 this.data.get/set", "high"),
            ("lifecycle_mounted", any(
                h["vue_hook"] == "mounted"
                for h in script_options.get("lifecycle_hooks", [])
            ),
             "存在 mounted 钩子，需转为 attached", "medium"),
            ("lifecycle_beforeDestroy", any(
                h["vue_hook"] == "beforeDestroy"
                for h in script_options.get("lifecycle_hooks", [])
            ),
             "存在 beforeDestroy 钩子，需转为 disposed", "medium"),
            ("watch_deep", any(
                w.get("deep") for w in script_options.get("watch", [])
            ),
             "存在 deep: true watcher，San 需避免深度监听，可改用写入时显式 set", "high"),
            ("timer", any(
                "timer" in m.get("side_effects_inferred", [])
                for m in script_options.get("methods", [])
            ),
             "存在 setInterval/setTimeout，需在 attached/disposed 中管理", "medium"),
            ("local_storage", any(
                "localStorage" in m.get("side_effects_inferred", [])
                for m in script_options.get("methods", [])
            ),
             "存在 localStorage 操作，需在生命周期中管理读写", "medium"),
            ("async_await", any(
                m.get("is_async") for m in script_options.get("methods", [])
            ),
             "存在 async/await，保留语法，状态读写改为 this.data.get/set", "low"),
            ("filter", len(script_options.get("filters", [])) > 0,
             "存在 Vue 2 过滤器，需转为 method 或 computed", "medium"),
        ]

        patterns = []
        for pname, cond, note, risk in template_patterns + script_patterns:
            if cond:
                patterns.append({
                    "pattern_id": pname,
                    "pattern_name": pname,
                    "detected_by": "AST 特征自动检测",
                    "note": note,
                    "risk_level": risk,
                })

        # 组件标签 PascalCase 检测
        comp_refs = template_result.get("component_refs", [])
        pascal_refs = [r for r in comp_refs if r.get("source_tag", "")[0].isupper()]
        if pascal_refs:
            patterns.append({
                "pattern_id": "pascal_component_tag",
                "pattern_name": "pascal_component_tag",
                "detected_by": f"模板中存在 PascalCase 组件标签: {[r['source_tag'] for r in pascal_refs]}",
                "note": "PascalCase 组件标签需改为短横线命名并在 components 中注册",
                "risk_level": "high",
            })

        # SVG 检测
        svg_in_template = any(
            d.get("source_tag", "").lower() in ("svg", "path", "circle", "line", "polyline", "rect", "g", "text")
            for d in self._collect_all_nodes(template_result.get("dom_tree", {}))
        )
        if svg_in_template:
            patterns.append({
                "pattern_id": "svg_drawing",
                "pattern_name": "svg_drawing",
                "detected_by": "模板中存在 SVG 元素",
                "note": "SVG 标签和属性绑定需保留，动态属性改为 San 属性绑定",
                "risk_level": "medium",
            })

        return patterns

    def _collect_all_nodes(self, dom_node: dict) -> List[dict]:
        nodes = []
        if not dom_node:
            return nodes
        nodes.append(dom_node)
        for child in dom_node.get("children", []):
            nodes.extend(self._collect_all_nodes(child))
        return nodes

    def _build_data_access_plan(self, script_options: dict) -> dict:
        """为每个 data 字段生成 San 访问方案。"""
        plan = {}
        for df in script_options.get("data", []):
            fname = df["name"]
            read = f"this.data.get('{fname}')"
            write = f"this.data.set('{fname}', value)" if df.get("value_type_inferred") not in ("function",) else None
            init = f"initData 中声明 {fname}，默认值 {df.get('default_value_summary', 'null')}"

            plan[fname] = {
                "read_plan": read,
                "write_plan": write,
                "init_plan": init,
            }

        return plan


# 便捷调用
def build_relations(template_result: dict, script_result: dict,
                    style_result: dict) -> dict:
    return RelationBuilder().build(template_result, script_result, style_result)