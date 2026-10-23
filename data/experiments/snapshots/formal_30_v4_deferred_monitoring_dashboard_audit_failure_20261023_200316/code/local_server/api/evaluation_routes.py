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


# Retained to make the v3-to-v4 prompt change auditable; production calls use
# the UTF-8 implementation below.
def _build_generation_prompt_v3_legacy(ssm: dict[str, Any], extra_instruction: str = "") -> str:
    ssm_json = json.dumps(ssm, ensure_ascii=False, indent=2)
    return (
        "请仅基于给定 SSM 生成可运行、可直接落盘的 San 单文件组件代码。\n"
        "输出要求：\n"
        "1. 直接输出完整 .san 文件内容，必须包含 <template>、<script>、<style> 三段，不要只输出组件对象片段。\n"
        "2. <script> 中必须显式包含 const san = require('san')、const DataTypes = san.DataTypes，并使用 module.exports = san.defineComponent(...) 导出。\n"
        "3. 组件中必须显式输出 name，值来自 metadata.component_name。\n"
        "4. Vue props 必须迁移到 san.defineComponent 的 dataTypes: {...} 选项中，并映射为 DataTypes.number / string / bool / array / object 等标准 San 类型；禁止输出 props: {...} 或 propTypes: {...}，也不要把类型写成普通字符串 'number'。\n"
        "5. data 初始化优先拆成稳定默认值 + 生命周期同步：Vue props 中声明的 default（包括数组/对象工厂默认值）必须作为同名字段落入 initData；props 到内部 state 的同步优先放到 inited/attached 中。\n"
        "6. 优先将 methods 直接定义在组件对象顶层，不要保留 Vue 风格的 methods: {} 包裹；Vue 的 this.$emit(...) 或 emitEvent 包装方法必须迁移为 this.fire(...)，禁止用 this.dispatch(...) 代替自定义事件。\n"
        "7. 必须尽量完整输出样式，复用 styles 和 style_model 中已有的 class、selector、css_rules；样式标签必须写成 <style>，禁止输出 <style scoped>。\n"
        "8. 模板中保留现有 DOM 结构、类名、文本内容与完整事件表达式；例如 move(-1)、select(task.id) 必须直接迁移为 on-click=\"move(-1)\"、on-click=\"select(task.id)\"，禁止丢失参数或改用 data-args/getAttribute 绕行。Vue v-for 的循环项和索引别名必须完整迁移；如果表达式使用 index，就必须显式写成 s-for=\"phase, index in phases trackby phase.key\"，禁止只声明 phase 却继续引用未绑定的 index。Vue v-for 上的 :key 必须迁移到 San s-for 内联 trackby，例如 s-for=\"task in tasks trackby task.id\"；禁止输出独立 key=\"{{ task.id }}\" 或 key=\"{= task.id =}\"。所有 {{ ... }} 和 {= ... =} 插值必须完整闭合。双向绑定 {= assignable.path =} 只允许可赋值的数据路径；disabled、checked、selected 等派生属性必须使用 disabled=\"{{ expression }}\" 一类单向插值，禁止 disabled=\"{= expression =}\"。\n"
        "9. 若 SSM 信息不足，可做最小必要假设，但不要编造未出现的复杂业务逻辑。\n"
        "10. 除代码外不要输出解释、标题或 Markdown 代码围栏。\n\n"
        f"补充要求：{extra_instruction or '保持输出风格尽量贴近项目内已有 san 组件：完整 SFC、显式 DataTypes、保留样式、代码可直接保存为 .san 文件。'}\n\n"
        "--- SSM ---\n"
        f"{ssm_json}"
    )


def _build_generation_prompt(ssm: dict[str, Any], extra_instruction: str = "") -> str:
    ssm_json = json.dumps(ssm, ensure_ascii=False, indent=2)
    data_access_rule = (
        "San data access rule: never destructure this.data or treat it as a plain object. "
        "Read fields separately, for example const initialGroups = "
        "this.data.get('initialGroups'), then write state with this.data.set(...).\n"
    )
    class_attribute_rule = (
        "Each template element must have exactly one class attribute: merge static and dynamic classes "
        "into that single attribute instead of emitting duplicate class attributes.\n"
    )
    directive_rule = (
        "San s-if/s-else-if/s-for directive values use raw expressions: "
        "s-if=\"showSettings\" and s-for=\"item in items trackby item.id\". "
        "Never use s-if=\"{{showSettings}}\", s-if=\"{= showSettings =}\", "
        "or s-for=\"{{item in items}}\".\n"
    )
    return data_access_rule + class_attribute_rule + directive_rule + (
        "请仅基于给定 SSM 生成可运行、可直接落盘的 San 单文件组件代码。\n"
        "输出要求：\n"
        "1. 直接输出完整 .san 文件内容，必须包含 <template>、<script>、<style> 三段，不要输出解释或 Markdown 代码围栏。\n"
        "2. <script> 必须包含 const san = require('san')、const DataTypes = san.DataTypes，并使用 module.exports = san.defineComponent(...) 导出。\n"
        "3. 必须输出来自 metadata.component_name 的 name。Vue props 必须迁移为 dataTypes，并使用标准 DataTypes 类型，禁止保留 props 或 propTypes。\n"
        "4. initData 必须精确保留 Vue props default 和 data() 的类型、数值、嵌套对象与数组内容；依赖 props 的内部状态应在 inited/attached 中通过 this.data.get/set 同步。\n"
        "5. 状态和 computed 必须通过 this.data.get/set 访问；禁止 this.props、this.computed.foo()、this.xxx 状态访问以及直接修改嵌套对象或数组。更新嵌套状态时创建新值并写回根字段。\n"
        "6. methods 必须直接定义在组件对象顶层。Vue this.$emit(...) 或 emitEvent 包装调用必须迁移为 this.fire(...)，禁止用 this.dispatch(...) 代替自定义事件。\n"
        "7. template 使用 San 的 on-*、s-if、s-for 语法，完整保留 DOM 结构、文本、class、子节点顺序以及方法调用的全部参数。事件参数不得丢失或改用 data-args/getAttribute 绕行。\n"
        "8. Vue v-for 的循环项和索引别名必须完整迁移；:key 必须写入 s-for 的 trackby 子句，例如 s-for=\"task in tasks trackby task.id\"，禁止独立 key 属性，也禁止写成独立 trackby=\"task.id\" 属性。\n"
        "9. {= assignable.path =} 只用于源 Vue v-model 对应的原生 input/select/textarea 可赋值路径；Vue :prop 和普通自定义组件 props 必须使用 {{ ... }} 单向插值，例如 value=\"{{ stat.value }}\"。方法、computed、disabled、checked、selected 等派生表达式也使用 {{ ... }}，例如 disabled=\"{{ expression }}\"，禁止 disabled=\"{= expression =}\"。所有插值必须完整闭合。\n"
        "10. value、checked、selected、disabled 等关键属性必须逐元素保留 Vue 原表达式，禁止把相邻或同级元素的条件合并进来。例如 select 的 :disabled=\"previewMode\" 必须迁移为 disabled=\"{{ previewMode }}\"，不能误用旁边按钮的 !canConnect || previewMode。\n"
        "11. class、style、checked、selected、disabled、s-if、s-for 和文本插值调用普通方法时，响应式依赖必须出现在模板表达式中或作为参数显式传入。必须保留 SSM/Vue 表达式中的完整参数，例如 s-if=\"isOpen(module.id, openIds)\"、s-for=\"lesson in visibleLessons(module.lessons, completedIds, unfinishedOnly) trackby lesson.id\"。\n"
        "12. 完整迁移 created/mounted/beforeDestroy/destroyed 和 watch 行为到 San 生命周期与 this.watch(...)，不能保留空钩子。\n"
        "13. 复用 style_model 中的 class、selector 和 css_rules；使用 <style>，禁止 <style scoped>。不要重新设计组件或编造业务逻辑。\n\n"
        f"补充要求：{extra_instruction or '保持完整 SFC、显式 DataTypes、原始样式和可直接运行的 San 代码。'}\n\n"
        "--- SSM ---\n"
        f"{ssm_json}"
    )


def _build_repair_prompt(payload: dict[str, Any]) -> str:
    repair_prompt = (payload.get("repair_prompt") or payload.get("instruction") or "").strip()
    if repair_prompt:
        return repair_prompt

    ssm = payload.get("ssm") or {}
    current_code = (payload.get("current_code") or payload.get("generated_code") or "").strip()
    repair_report = payload.get("repair_report") or {}
    directive_rule = (
        "San s-if/s-else-if/s-for directive values use raw expressions: "
        "s-if=\"showSettings\" and s-for=\"item in items trackby item.id\". "
        "Never use s-if=\"{{showSettings}}\", s-if=\"{= showSettings =}\", "
        "or s-for=\"{{item in items}}\".\n"
    )
    return directive_rule + (
        "你是一个 Vue 到 San 迁移修复专家。请根据 SSM、当前 San 代码和修复报告，输出修复后的完整 .san 文件。\n"
        "要求：只输出代码，不要输出解释或 Markdown 代码围栏。\n\n"
        "--- SSM ---\n"
        f"{json.dumps(ssm, ensure_ascii=False, indent=2)}\n\n"
        "--- Current San Code ---\n"
        f"{current_code}\n\n"
        "--- Repair Report ---\n"
        f"{json.dumps(repair_report, ensure_ascii=False, indent=2)}"
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

    if requested_path:
        output_path = Path(requested_path)
        if output_path.name == default_path.name and output_path != default_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(code, encoding="utf-8")
            if default_path.exists():
                default_path.unlink()
            return str(output_path)
    else:
        output_path = default_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code, encoding="utf-8")
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


@evaluation_bp.post("/repair")
def run_repair():
    payload = request.get_json(silent=True) or {}
    try:
        source_name = payload.get("source_file") or "inline.vue"
        ssm = payload.get("ssm") or {}
        if not ssm:
            raise ValueError("Repair request requires ssm")

        prompt = _build_repair_prompt(payload)
        if not prompt:
            raise ValueError("Repair request requires repair_prompt or repair report inputs")

        client = create_llm_client()
        llm_result = client.generate(
            prompt=prompt,
            system_prompt="You are an expert Vue-to-San repair agent. Output only repaired San component code.",
        )
        repaired_code = _strip_code_fences(llm_result["content"])
        saved_file_path = _save_generated_code(payload, source_name, ssm, repaired_code)

        return jsonify(
            {
                "ok": True,
                "source_file": source_name,
                "ssm": ssm,
                "repair": {
                    "provider": llm_result["provider"],
                    "model": llm_result["model"],
                    "code": repaired_code,
                    "saved_file_path": saved_file_path,
                    "usage": llm_result.get("usage", {}),
                },
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

