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
from types import ModuleType
from typing import Any, Optional

from SSM.schema import get_default_schema_module_path, resolve_schema_module

from .vue_parser import VueSFCParser
from .template_extractor import TemplateExtractor
from .script_extractor import ScriptExtractor
from .style_extractor import StyleExtractor
from .relation_builder import RelationBuilder


DEFAULT_SCHEMA_MODULE = get_default_schema_module_path()


class SSMFactory:
    """SSM 组装工厂。输入 .vue 文件或源码，输出完整的 SSM dict。"""

    def __init__(
        self,
        use_node_bridge: bool = True,
        schema_module: str | ModuleType = DEFAULT_SCHEMA_MODULE,
    ):
        self.schema = self._load_schema_module(schema_module)
        self._validate_schema_module(self.schema)
        self.vue_parser = VueSFCParser(use_node_bridge=use_node_bridge)
        self.template_extractor = TemplateExtractor()
        self.script_extractor = ScriptExtractor()
        self.style_extractor = StyleExtractor()
        self.relation_builder = RelationBuilder()

    @staticmethod
    def _load_schema_module(schema_module: str | ModuleType) -> ModuleType:
        return resolve_schema_module(schema_module)

    @staticmethod
    def _validate_schema_module(schema_module: ModuleType) -> None:
        required_attrs = [
            "SSM_SCHEMA_VERSION",
            "SSM_SCHEMA_NAME",
            "build_ssm_metadata",
            "build_san_generation_contract",
            "build_ssm_shell",
        ]
        missing = [attr for attr in required_attrs if not hasattr(schema_module, attr)]
        if missing:
            raise AttributeError(
                f"Schema module {schema_module.__name__} is missing required attributes: {', '.join(missing)}"
            )

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
        ssm = self.schema.build_ssm_shell()
        ssm["schema_version"] = self.schema.SSM_SCHEMA_VERSION
        ssm["schema_name"] = self.schema.SSM_SCHEMA_NAME
        ssm["metadata"] = metadata
        ssm["template"] = template_result
        ssm["script"] = script_result
        ssm["styles"] = {
            **style_result,
            **template_style,
        }
        ssm["binding_graph"] = relations["binding_graph"]
        ssm["event_model"] = relations["event_model"]
        ssm["style_model"] = relations["style_model"]
        ssm["sub_components"] = relations["sub_components"]
        ssm["migration_hints"] = relations["migration_hints"]
        ssm["san_generation_contract"] = generation_contract

        return ssm

    def _build_metadata(self, parsed: dict, display_path: str) -> dict:
        return self.schema.build_ssm_metadata(
            component_name=parsed.get("component_name", "unknown"),
            source_file=display_path,
            has_template=self.vue_parser.has_template(parsed),
            has_script=self.vue_parser.has_script(parsed),
            has_style=self.vue_parser.has_style(parsed),
            style_scoped=self.vue_parser.get_style_scoped(parsed),
            style_lang=self.vue_parser.get_style_lang(parsed),
        )

    def _build_generation_contract(self) -> dict:
        return self.schema.build_san_generation_contract()


# 便捷调用
def build_ssm(
    source_or_path: str,
    is_path: bool = True,
    source_file: str = "",
    schema_module: str | ModuleType = DEFAULT_SCHEMA_MODULE,
) -> dict:
    """构建 SSM 的顶层便捷函数。

    Args:
        source_or_path: Vue SFC 源码字符串或文件路径
        is_path: True 表示 source_or_path 是文件路径
        source_file: 对外展示的文件路径
        schema_module: schema 模块路径或模块对象
    """
    factory = SSMFactory(schema_module=schema_module)
    if is_path and os.path.isfile(source_or_path):
        return factory.build_from_file(source_or_path)
    return factory.build(source_or_path, source_file=source_file)
