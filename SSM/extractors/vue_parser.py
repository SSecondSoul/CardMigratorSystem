"""
SSM Extractors — SFC 解析器
负责将 .vue 文件拆分为 template / script / style 三个源码块，
并尝试通过 `parse_sfc.cjs` 调用 @vue/compiler-sfc / @babel 相关能力做深度 AST 解析。
若 Node.js 或相关依赖不可用，退化为正则切分 + 启发式解析。

输出结构：
{
    "source": "原始源码",
    "file_path": "文件路径",
    "blocks": {
        "template": {"content": "...", "start": 0, "end": 100, "attrs": {}},
        "script":   {"content": "...", "start": 101, "end": 200, "attrs": {}, "lang": "js"},
        "style":    [{"content": "...", "scoped": True, "lang": "css", ...},  ...]
    }
}
"""

import re
import os
import json
import subprocess
from typing import Any, Optional


class SFCBlock:
    """单个 SFC 块的抽象。"""
    def __init__(self, content: str, start: int = 0, end: int = 0,
                 attrs: Optional[dict] = None):
        self.content = content
        self.start = start
        self.end = end
        self.attrs = attrs or {}

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "start": self.start,
            "end": self.end,
            "attrs": self.attrs,
        }


class VueSFCParser:
    """Vue 单文件组件解析器。

    优先级：
    1. 尝试通过 `parse_sfc.cjs` 调用 Node 侧 AST bridge
    2. 退化为正则切分
    """

    # 匹配 <template>, <script>, <style> 块的正则
    BLOCK_RE = re.compile(
        r'<(?P<tag>template|script|style)'
        r'(?P<attrs>[^>]*)>'
        r'(?P<content>.*?)'
        r'</(?P=tag)>',
        re.DOTALL | re.IGNORECASE
    )

    NODE_BRIDGE_SCRIPT = os.path.join(os.path.dirname(__file__), "parse_sfc.cjs")

    def __init__(self, use_node_bridge: bool = True):
        self.use_node_bridge = use_node_bridge

    def parse_file(self, file_path: str) -> dict:
        """解析 .vue 文件，返回结构化块。"""
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        return self.parse(source, file_path)

    def parse(self, source: str, file_path: str = "") -> dict:
        """解析 Vue SFC 源码字符串。"""

        # 1) 尝试通过 parse_sfc.cjs 调用 Node 侧 AST bridge
        if self.use_node_bridge:
            node_result = self._try_node_bridge(source, file_path)
            if node_result:
                node_result["source"] = source
                node_result["file_path"] = file_path
                node_result.setdefault("component_name", self._infer_component_name(source, file_path))
                node_result.setdefault("analysis", {})
                return node_result

        # 2) 退化为正则切分
        blocks = self._regex_parse(source)

        # 3) 从文件名推断组件名
        component_name = self._infer_component_name(source, file_path)

        result = {
            "source": source,
            "file_path": file_path,
            "component_name": component_name,
            "blocks": {
                "template": blocks.get("template"),
                "script": blocks.get("script"),
                "style": blocks.get("style", []),
            },
        }
        return result

    def _try_node_bridge(self, source: str, file_path: str) -> Optional[dict]:
        """通过 `parse_sfc.cjs` 调用 Node 侧 AST bridge 解析。"""
        if not os.path.exists(self.NODE_BRIDGE_SCRIPT):
            return None

        try:
            env = os.environ.copy()
            env.setdefault("NODE_OPTIONS", "--no-warnings")
            proc = subprocess.run(
                ["node", self.NODE_BRIDGE_SCRIPT, file_path or "inline.vue"],
                input=source,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                payload = json.loads(proc.stdout)
                if isinstance(payload, dict) and payload.get("error"):
                    return None
                return payload
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

        return None

    def _regex_parse(self, source: str) -> dict:
        """正则切分 SFC 块。"""
        blocks: dict[str, Any] = {"template": None, "script": None, "style": []}

        for match in self.BLOCK_RE.finditer(source):
            tag = match.group("tag").lower()
            attrs_str = match.group("attrs")
            content = match.group("content")
            attrs = self._parse_attrs(attrs_str)

            block = SFCBlock(
                content=content.strip(),
                start=match.start(),
                end=match.end(),
                attrs=attrs,
            )

            if tag == "template":
                blocks["template"] = block.to_dict()
            elif tag == "script":
                lang = attrs.get("lang", "").lower()
                block.attrs["lang"] = lang if lang in ("js", "ts", "tsx", "jsx") else "js"
                blocks["script"] = block.to_dict()
            elif tag == "style":
                block.attrs["lang"] = attrs.get("lang", "css").lower()
                block.attrs["scoped"] = "scoped" in attrs_str
                block.attrs["module"] = "module" in attrs_str
                blocks["style"].append(block.to_dict())

        return blocks

    def _parse_attrs(self, attrs_str: str) -> dict:
        """解析 HTML 属性字符串为字典。"""
        attrs = {}
        attr_re = re.compile(
            r'(?P<key>[\w-]+)(?:=(?:"(?P<v1>[^"]*)"|\'(?P<v2>[^\']*)\'|(?P<v3>\S+)))?'
        )
        for match in attr_re.finditer(attrs_str):
            key = match.group("key")
            value = match.group("v1") or match.group("v2") or match.group("v3") or ""
            attrs[key] = value
        return attrs

    def _infer_component_name(self, source: str, file_path: str) -> str:
        """从 script 块的 name 选项或文件名推断组件名。"""
        # 尝试从 script 中提取 name: 'xxx'
        name_match = re.search(
            r'(?:name\s*:\s*["\'])([^"\']+)(?:["\'])',
            source
        )
        if name_match:
            return name_match.group(1)

        # 从文件名推断
        if file_path:
            base = os.path.splitext(os.path.basename(file_path))[0]
            return base
        return "unknown"

    def has_template(self, parsed: dict) -> bool:
        return parsed["blocks"]["template"] is not None

    def has_script(self, parsed: dict) -> bool:
        return parsed["blocks"]["script"] is not None

    def has_style(self, parsed: dict) -> bool:
        return len(parsed["blocks"]["style"]) > 0

    def get_style_scoped(self, parsed: dict) -> bool:
        """返回任一 style 块是否 scoped。兼容顶层字段和 attrs 字段。"""
        styles = parsed["blocks"]["style"]
        if not styles:
            return False
        return any(
            bool(style.get("scoped", style.get("attrs", {}).get("scoped", False)))
            for style in styles
        )

    def get_style_lang(self, parsed: dict) -> Optional[str]:
        styles = parsed["blocks"]["style"]
        if styles:
            first = styles[0]
            return first.get("lang") or first.get("attrs", {}).get("lang", "css")
        return None


# 便捷调用
def parse_vue_sfc(source_or_path: str, is_path: bool = True) -> dict:
    """解析 Vue SFC 的顶层便捷函数。"""
    parser = VueSFCParser(use_node_bridge=False)
    if is_path and os.path.isfile(source_or_path):
        return parser.parse_file(source_or_path)
    return parser.parse(source_or_path)