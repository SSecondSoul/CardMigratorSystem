"""
SSM Extractors — 组装协调器

负责：
1. 调用 vue_parser 解析 SFC 源码
2. 调用 template/script/style extractor 提取各块
3. 调用 relation_builder 做跨块关联分析
4. 组装 metadata 和 san_generation_contract
5. 输出符合 SSM Schema v3 的完整 dict
"""

import os
import re
from typing import Any, Optional

from .vue_parser import VueSFCParser
from .template_extractor import TemplateExtractor
from .script_extractor import ScriptExtractor
from .style_extractor import StyleExtractor
from .relation_builder import RelationBuilder


class SSMFactory:
    """SSM 组装工厂。输入 .vue 文件或源码，输出完整的 SSM dict。"""

    def __init__(self, use_node_bridge: bool = True):
        self.vue_parser = VueSFCParser(use_node_bridge=use_node_bridge)
        self.template_extractor = TemplateExtractor()
        self.script_extractor = ScriptExtractor()
        self.style_extractor = StyleExtractor()
        self.relation_builder = RelationBuilder()

    def build_from_file(self, file_path: str) -> dict:
        """从 .vue 文件构建完整 SSM。"""
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        return self.build(source, file_path)

    def build(self, source: str, file_path: str = "", source_file: str = "") -> dict:
        """从 Vue SFC 源码构建完整 SSM。

        Args:
            source: Vue SFC 源码字符串
            file_path: 文件路径（用于日志/推断）
            source_file: 对外展示的文件路径
        """
        display_path = source_file or file_path or "inline"

        # ── Step 1: 解析 SFC ──
        parsed = self.vue_parser.parse(source, file_path)

        # ── Step 2: 提取各块 ──
        # 模板
        template_html = ""
        if self.vue_parser.has_template(parsed):
            template_html = parsed["blocks"]["template"]["content"]
        template_analysis = parsed.get("analysis", {}).get("template")
        if template_analysis:
            template_result = self.template_extractor.extract_from_ast_analysis(template_analysis)
        else:
            template_result = self.template_extractor.extract(template_html)

        # 脚本
        script_source = ""
        if self.vue_parser.has_script(parsed):
            script_source = parsed["blocks"]["script"]["content"]
        script_analysis = parsed.get("analysis", {}).get("script")
        if script_analysis:
            script_result = self.script_extractor.extract_from_ast_analysis(script_analysis)
        else:
            script_result = self.script_extractor.extract(script_source)

        # 样式
        style_blocks = parsed["blocks"]["style"]
        style_result = self.style_extractor.extract(style_blocks)

        # 模板中的样式特征
        template_style = self.style_extractor.extract_template_classes(template_html)

        # ── Step 3: 跨块关联分析 ──
        relations = self.relation_builder.build(
            template_result, script_result, style_result)

        # ── Step 4: 组装 metadata ──
        metadata = self._build_metadata(parsed, display_path)

        # ── Step 5: 组装 san_generation_contract ──
        generation_contract = self._build_generation_contract()

        # ── Step 6: 构建最终 SSM ──
        ssm = {
            "schema_version": "3.0",
            "schema_name": "San Source Model (Generic)",
            "metadata": metadata,
            "template": template_result,
            "script": script_result,
            "styles": {
                **style_result,
                **template_style,
            },
            "binding_graph": relations["binding_graph"],
            "event_model": relations["event_model"],
            "style_model": relations["style_model"],
            "sub_components": relations["sub_components"],
            "migration_hints": relations["migration_hints"],
            "san_generation_contract": generation_contract,
        }

        return ssm

    def _build_metadata(self, parsed: dict, display_path: str) -> dict:
        return {
            "component_name": parsed.get("component_name", "unknown"),
            "source_file": display_path,
            "source_framework": "Vue",
            "target_framework": "San",
            "sfc_blocks": {
                "has_template": self.vue_parser.has_template(parsed),
                "has_script": self.vue_parser.has_script(parsed),
                "has_style": self.vue_parser.has_style(parsed),
                "style_scoped": self.vue_parser.get_style_scoped(parsed),
                "style_lang": self.vue_parser.get_style_lang(parsed),
            },
        }

    def _build_generation_contract(self) -> dict:
        return {
            "must_preserve": [
                "metadata.component_name 和根节点语义",
                "template.dom_tree 的层级结构、节点顺序与语义角色",
                "template.component_refs 中每个子组件的注册名和父子通信事件",
                "binding_graph 中 data/props/computed 到模板节点的可见绑定",
                "event_model 中每个 DOM 事件和自定义事件的触发时机与 payload",
                "style_model 中动态类名、动态样式、scoped CSS 和关键视觉状态",
                "script.options.lifecycle_hooks 中的副作用初始化与清理逻辑",
                "script.options.data 中所有字段的默认值和外部初始化来源",
            ],
            "san_syntax_requirements": [
                "输出完整的 .san 单文件组件，包含 <template>、<script>、<style> 三个代码块；若无样式也保留空 style 或显式说明无样式",
                "脚本块显式引入 san：const san = require('san')，并使用 module.exports = san.defineComponent(...) 导出组件",
                "props 使用 san.DataTypes 声明，与 script.options.props 一一对应；优先输出 DataTypes.number / string / bool / array / object",
                "组件定义使用 san.defineComponent",
                "组件名来自 metadata.component_name，并显式输出 name 字段",
                "data 使用 initData 返回默认值，与 script.options.data 一一对应；不要在 initData 中直接依赖复杂运行时读取",
                "当 data 字段来源于 props 或外部初始化时，优先在 inited/attached 中用 this.data.set 完成同步",
                "模板中使用 s-if、s-for、on-event、value={= =}、checked={= =} 等 San 语法",
                "状态访问统一使用 this.data.get() / this.data.set()",
                "优先将 methods 直接定义在组件对象顶层，避免保留 Vue 风格的 methods: {} 包裹",
                "子组件标签使用短横线命名",
                "子组件在 components 中显式注册",
                "样式块需尽量完整输出，优先复用 styles/style_model 中已有 class 与 css_rules 信息",
                "定时器、timeout、外部监听等副作用在 attached/disposed 中管理",
            ],
            "quality_checks": [
                "template.component_refs 中每个子组件都在 script.components 或 san_registration 中有定义",
                "binding_graph.edges 中每条 template 依赖都能在 script.options 中找到来源",
                "event_model.dom_events 中每个 handler_name 都存在于 script.options.methods",
                "event_model.custom_events 中每个 emit_points 都对应 method 中的 $emit 调用",
                "style_model.dynamic_class_bindings 的 dependencies 都存在于 binding_graph.nodes",
                "script.options.watch 中的 deep watcher 在 migration_hints 中被标记并给出替代策略",
            ],
        }


# 便捷调用
def build_ssm(source_or_path: str, is_path: bool = True,
              source_file: str = "") -> dict:
    """构建 SSM 的顶层便捷函数。

    Args:
        source_or_path: Vue SFC 源码字符串或文件路径
        is_path: True 表示 source_or_path 是文件路径
        source_file: 对外展示的文件路径
    """
    factory = SSMFactory()
    if is_path and os.path.isfile(source_or_path):
        return factory.build_from_file(source_or_path)
    return factory.build(source_or_path, source_file=source_file)