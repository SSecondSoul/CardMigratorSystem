import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from migration_pipeline import GenerateStageInput, MigrationPipelineOrchestrator


DEFAULT_REPORT_DIR = PROJECT_ROOT / "data" / "experiments" / "repair_reports"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the full migration pipeline with multi-round repair and export repair metrics.",
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--vue-file",
        help="Path to the Vue source file used to build SSM before generation.",
    )
    source_group.add_argument(
        "--ssm-file",
        help="Path to a JSON file containing a prebuilt SSM.",
    )
    parser.add_argument(
        "--output-file",
        help="Optional target path for the initially generated .san file.",
    )
    parser.add_argument(
        "--source-file",
        default="",
        help="Optional logical source file name passed to generation and repair services.",
    )
    parser.add_argument(
        "--instruction",
        default="",
        help="Extra instruction appended for San generation.",
    )
    parser.add_argument(
        "--metadata-file",
        help="Optional JSON file with extra metadata passed to generation service.",
    )
    parser.add_argument(
        "--max-repair-rounds",
        type=int,
        default=3,
        help="Maximum repair rounds before the pipeline stops. Default: 3.",
    )
    parser.add_argument(
        "--report-file",
        help="Optional JSON report path. Defaults to data/experiments/repair_reports/<source>_repair_history.json.",
    )
    parser.add_argument(
        "--disable-node-bridge",
        action="store_true",
        help="Disable Node bridge when building SSM from Vue input.",
    )
    parser.add_argument(
        "--include-state",
        action="store_true",
        help="Include the full final pipeline state in the JSON report.",
    )
    return parser


def load_json_file(file_path: str) -> dict[str, Any]:
    return json.loads(Path(file_path).read_text(encoding="utf-8"))


def resolve_report_file(args: argparse.Namespace) -> Path:
    if args.report_file:
        return Path(args.report_file)

    source_path = args.vue_file or args.ssm_file or args.output_file or "pipeline_run"
    source_stem = Path(source_path).stem or "pipeline_run"
    return DEFAULT_REPORT_DIR / f"{source_stem}_repair_history.json"


def count_items(result: dict[str, Any] | None, key: str) -> int:
    if not isinstance(result, dict):
        return 0
    value = result.get(key, [])
    return len(value) if isinstance(value, list) else 0


def compact_validate_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    return {
        "validation_passed": result.get("validation_passed", result.get("passed")),
        "error_count": count_items(result, "validation_errors"),
        "warning_count": count_items(result, "validation_warnings"),
        "summary": result.get("validation_summary", result.get("summary", "")),
    }


def compact_visual_eval_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    return {
        "visual_eval_passed": result.get("visual_eval_passed", result.get("passed")),
        "error_count": count_items(result, "visual_eval_errors"),
        "warning_count": count_items(result, "visual_eval_warnings"),
        "tree_edit_distance": result.get("tree_edit_distance"),
        "structure_similarity": result.get("structure_similarity"),
        "tag_sequence_similarity": result.get("tag_sequence_similarity"),
        "text_similarity": result.get("text_similarity"),
        "summary": result.get("visual_eval_summary", result.get("summary", "")),
    }


def compact_repair_history_entry(entry: dict[str, Any]) -> dict[str, Any]:
    validate_result = entry.get("validate_result")
    visual_eval_result = entry.get("visual_eval_result")
    repair_result = entry.get("repair_result") if isinstance(entry.get("repair_result"), dict) else {}
    return {
        "repair_attempt": entry.get("repair_attempt"),
        "passed": entry.get("passed"),
        "validation_passed": entry.get("validation_passed"),
        "visual_eval_passed": entry.get("visual_eval_passed"),
        "validation_error_count": count_items(validate_result, "validation_errors"),
        "validation_warning_count": count_items(validate_result, "validation_warnings"),
        "visual_eval_error_count": count_items(visual_eval_result, "visual_eval_errors"),
        "visual_eval_warning_count": count_items(visual_eval_result, "visual_eval_warnings"),
        "tree_edit_distance": entry.get("tree_edit_distance"),
        "structure_similarity": entry.get("structure_similarity"),
        "tag_sequence_similarity": entry.get("tag_sequence_similarity"),
        "text_similarity": entry.get("text_similarity"),
        "repaired_file_path": repair_result.get("repaired_file_path"),
        "repair_provider": repair_result.get("provider"),
        "repair_model": repair_result.get("model"),
        "repair_usage": repair_result.get("usage", {}),
    }


def build_report(
    args: argparse.Namespace,
    state: dict[str, Any],
    report_file: Path,
) -> dict[str, Any]:
    repair_history = state.get("repair_history", [])
    compact_history = [
        compact_repair_history_entry(entry)
        for entry in repair_history
        if isinstance(entry, dict)
    ]
    report = {
        "inputs": {
            "vue_file": args.vue_file,
            "ssm_file": args.ssm_file,
            "source_file": args.source_file,
            "output_file": args.output_file,
            "max_repair_rounds": args.max_repair_rounds,
        },
        "outputs": {
            "report_file": str(report_file),
            "generated_file_path": state.get("generate_result", {}).get("saved_file_path"),
            "final_file_path": state.get("final_file_path"),
        },
        "summary": {
            "final_passed": state.get("final_passed", False),
            "stop_reason": state.get("stop_reason", ""),
            "repair_rounds": state.get("repair_rounds", 0),
            "max_repair_rounds": state.get("max_repair_rounds", args.max_repair_rounds),
            "final_structure_similarity": state.get("structure_similarity"),
            "final_tree_edit_distance": state.get("tree_edit_distance"),
        },
        "initial": {
            "validate": compact_validate_result(state.get("initial_validate_result")),
            "visual_eval": compact_visual_eval_result(state.get("initial_visual_eval_result")),
        },
        "final": {
            "validate": compact_validate_result(state.get("final_validate_result")),
            "visual_eval": compact_visual_eval_result(state.get("final_visual_eval_result")),
        },
        "repair_history": compact_history,
    }
    if args.include_state:
        report["state"] = state
    return report


def write_report(report_file: Path, report: dict[str, Any]) -> None:
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = build_parser().parse_args()
    if args.max_repair_rounds < 0:
        raise ValueError("--max-repair-rounds must be greater than or equal to 0")

    metadata = load_json_file(args.metadata_file) if args.metadata_file else {}
    ssm = load_json_file(args.ssm_file) if args.ssm_file else None
    report_file = resolve_report_file(args)

    stage_input = GenerateStageInput(
        vue_file_path=args.vue_file,
        ssm=ssm,
        source_file=args.source_file,
        instruction=args.instruction,
        output_file_path=args.output_file,
        use_node_bridge=not args.disable_node_bridge,
        metadata=metadata,
    )
    result = MigrationPipelineOrchestrator().run_generate_validate_visual_eval_and_repair_loop(
        stage_input=stage_input,
        max_repair_rounds=args.max_repair_rounds,
    )
    report = build_report(args, result.state, report_file)
    write_report(report_file, report)

    print(f"final_passed: {result.state.get('final_passed')}")
    print(f"stop_reason: {result.state.get('stop_reason')}")
    print(f"repair_rounds: {result.state.get('repair_rounds')}")
    print(f"final_file_path: {result.state.get('final_file_path')}")
    print(f"report_file: {report_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
