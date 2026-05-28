import json
import os
import re
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request

from SSM.extractors.factory import SSMFactory
from local_server.client.factory import create_llm_client
from local_server.config import settings


evaluation_bp = Blueprint("evaluation", __name__, url_prefix="/api/evaluation")


def _build_generation_prompt(ssm: dict[str, Any], extra_instruction: str = "") -> str:
    ssm_json = json.dumps(ssm, ensure_ascii=False, indent=2)
    return (
        "请仅基于给定 SSM 生成可运行、可直接落盘的 San 单文件组件代码。\n"
        "输出要求：\n"
        "1. 直接输出完整 .san 文件内容，必须包含 <template>、<script>、<style> 三段，不要只输出组件对象片段。\n"
        "2. <script> 中必须显式包含 const san = require('san')、const DataTypes = san.DataTypes，并使用 module.exports = san.defineComponent(...) 导出。\n"
        "3. 组件中必须显式输出 name，值来自 metadata.component_name。\n"
        "4. props 要映射到 DataTypes.number / string / bool / array / object 等标准 San 类型，不要写成普通字符串 'number'。\n"
        "5. data 初始化优先拆成稳定默认值 + 生命周期同步：initData 负责默认值，props 到 state 的同步优先放到 inited/attached 中。\n"
        "6. 优先将 methods 直接定义在组件对象顶层，不要保留 Vue 风格的 methods: {} 包裹，除非 SSM 明确要求。\n"
        "7. 必须尽量完整输出样式，复用 styles 和 style_model 中已有的 class、selector、css_rules，不要省略 <style>。\n"
        "8. 模板中保留现有 DOM 结构、类名、文本内容与事件绑定；插值格式尽量使用 {{ value }} 这种更易读风格。\n"
        "9. 若 SSM 信息不足，可做最小必要假设，但不要编造未出现的复杂业务逻辑。\n"
        "10. 除代码外不要输出解释、标题或 Markdown 代码围栏。\n\n"
        f"补充要求：{extra_instruction or '保持输出风格尽量贴近项目内已有 san 组件：完整 SFC、显式 DataTypes、保留样式、代码可直接保存为 .san 文件。'}\n\n"
        "--- SSM ---\n"
        f"{ssm_json}"
    )


def _load_vue_source(payload: dict[str, Any]) -> tuple[str, str]:
    vue_source = (payload.get("vue_source") or "").strip()
    vue_file_path = (payload.get("vue_file_path") or "").strip()

    if vue_source:
        return vue_source, vue_file_path or "inline.vue"

    if not vue_file_path:
        raise ValueError("Either ssm, vue_source or vue_file_path is required")
    if not os.path.isfile(vue_file_path):
        raise FileNotFoundError(f"Vue file not found: {vue_file_path}")

    with open(vue_file_path, "r", encoding="utf-8") as file_obj:
        return file_obj.read(), vue_file_path


def _default_output_path(source_name: str, component_name: str) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    experiments_dir = project_root / "data" / "experiments"

    if source_name and source_name != "inline.vue":
        stem = Path(source_name).stem
    else:
        stem = component_name or "generated_component"

    safe_stem = stem.replace(" ", "_")
    return experiments_dir / f"{safe_stem}.san"


def _strip_code_fences(code: str) -> str:
    text = (code or "").strip()
    fence_match = re.match(r'^```[a-zA-Z0-9_-]*\n([\s\S]*?)\n```$', text)
    if fence_match:
        return fence_match.group(1).strip() + "\n"
    return text + ("\n" if text else "")


def _save_generated_code(payload: dict[str, Any], source_name: str, ssm: dict[str, Any], code: str) -> str:
    requested_path = (payload.get("output_file_path") or "").strip()
    default_path = _default_output_path(
        source_name,
        ssm.get("metadata", {}).get("component_name", "generated_component"),
    )
    output_path = Path(requested_path) if requested_path else default_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code, encoding="utf-8")

    if requested_path and default_path != output_path and default_path.exists():
        default_path.unlink()

    return str(output_path)


@evaluation_bp.get("/health")
def evaluation_health():
    return jsonify(
        {
            "ok": True,
            "service": "evaluation",
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "llm_configured": bool(settings.llm_api_key),
        }
    )


@evaluation_bp.post("/extract")
def extract_only():
    payload = request.get_json(silent=True) or {}
    try:
        vue_source, source_name = _load_vue_source(payload)
        factory = SSMFactory(use_node_bridge=True)
        ssm = factory.build(vue_source, file_path=source_name, source_file=source_name)
        return jsonify({"ok": True, "source_file": source_name, "ssm": ssm})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@evaluation_bp.post("/run")
@evaluation_bp.post("/generate")
def run_generation():
    payload = request.get_json(silent=True) or {}
    try:
        source_name = "inline.vue"
        extra_instruction = (payload.get("instruction") or "").strip()
        provided_ssm = payload.get("ssm")

        if provided_ssm:
            ssm = provided_ssm
            source_name = payload.get("source_file") or source_name
        else:
            vue_source, source_name = _load_vue_source(payload)
            factory = SSMFactory(use_node_bridge=True)
            ssm = factory.build(vue_source, file_path=source_name, source_file=source_name)

        client = create_llm_client()
        prompt = _build_generation_prompt(ssm, extra_instruction)
        llm_result = client.generate(
            prompt=prompt,
            system_prompt="You are an expert Vue-to-San code generator. Output only San component code.",
        )
        generated_code = _strip_code_fences(llm_result["content"])
        saved_file_path = _save_generated_code(payload, source_name, ssm, generated_code)

        return jsonify(
            {
                "ok": True,
                "source_file": source_name,
                "ssm": ssm,
                "generation": {
                    "provider": llm_result["provider"],
                    "model": llm_result["model"],
                    "code": generated_code,
                    "saved_file_path": saved_file_path,
                    "usage": llm_result.get("usage", {}),
                },
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
