import argparse
import hashlib
import json
import re
import sys
import time
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from migration_pipeline import GenerateStageInput, MigrationPipelineOrchestrator
from migration_pipeline.config import settings
from migration_pipeline.run_pipeline import build_report, write_report


DEFAULT_CONFIG_FILE = PROJECT_ROOT / "migration_pipeline" / "batch_configs" / "pilot_9_v3.json"
VALID_COMPLEXITIES = {"simple", "medium", "complex"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a resumable, failure-isolated batch of Vue-to-San pipeline experiments.",
    )
    parser.add_argument(
        "--config-file",
        default=str(DEFAULT_CONFIG_FILE),
        help="Batch JSON config. Defaults to the 9-sample pilot config.",
    )
    parser.add_argument("--output-dir", help="Override the generated San output directory.")
    parser.add_argument("--report-dir", help="Override the per-sample report directory.")
    parser.add_argument("--summary-file", help="Override the batch checkpoint/summary JSON path.")
    parser.add_argument(
        "--max-repair-rounds",
        type=int,
        help="Override max repair rounds from the batch config.",
    )
    parser.add_argument(
        "--sample-id",
        action="append",
        dest="sample_ids",
        help="Run only this sample id. Repeat to select multiple samples.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rerun selected samples even if the checkpoint marks them completed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the plan without contacting local_server or writing results.",
    )
    parser.add_argument(
        "--include-state",
        action="store_true",
        help="Include full pipeline state in every per-sample report.",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip the local_server /health preflight check.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first execution exception. By default later samples continue.",
    )
    return parser


def load_batch_config(config_file: str | Path) -> tuple[Path, dict[str, Any]]:
    path = Path(config_file).resolve()
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_batch_config(config)
    return path, config


def config_fingerprint(config: dict[str, Any]) -> str:
    canonical = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_batch_config(config: dict[str, Any]) -> None:
    batch_id = config.get("batch_id")
    if not isinstance(batch_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", batch_id):
        raise ValueError("batch_id must contain only letters, numbers, underscores, or hyphens")

    max_rounds = config.get("max_repair_rounds", 3)
    if not isinstance(max_rounds, int) or max_rounds < 0:
        raise ValueError("max_repair_rounds must be a non-negative integer")

    samples = config.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("samples must be a non-empty list")

    ids: set[str] = set()
    counts: Counter[str] = Counter()
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ValueError(f"samples[{index}] must be an object")
        sample_id = sample.get("id")
        if not isinstance(sample_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", sample_id):
            raise ValueError(f"samples[{index}].id is invalid: {sample_id!r}")
        if sample_id in ids:
            raise ValueError(f"duplicate sample id: {sample_id}")
        ids.add(sample_id)

        complexity = sample.get("complexity")
        if complexity not in VALID_COMPLEXITIES:
            raise ValueError(f"sample {sample_id} has invalid complexity: {complexity!r}")
        counts[complexity] += 1

        component_name = sample.get("component_name")
        if not isinstance(component_name, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]+", component_name
        ):
            raise ValueError(
                f"sample {sample_id} component_name must be filesystem-safe"
            )

        vue_file = sample.get("vue_file")
        if not isinstance(vue_file, str) or not vue_file.endswith(".vue"):
            raise ValueError(f"sample {sample_id} requires a .vue vue_file")
        resolved_vue = resolve_project_path(vue_file)
        if not resolved_vue.is_file():
            raise FileNotFoundError(f"sample {sample_id} Vue file not found: {resolved_vue}")

        coverage_focus = sample.get("coverage_focus")
        if coverage_focus is not None and (
            not isinstance(coverage_focus, list)
            or not coverage_focus
            or any(not isinstance(item, str) or not item.strip() for item in coverage_focus)
        ):
            raise ValueError(
                f"sample {sample_id} coverage_focus must be a non-empty list of strings"
            )

    expected_counts = config.get("expected_counts")
    if expected_counts is not None:
        if not isinstance(expected_counts, dict):
            raise ValueError("expected_counts must be an object")
        for complexity, expected in expected_counts.items():
            if complexity not in VALID_COMPLEXITIES or not isinstance(expected, int):
                raise ValueError(f"invalid expected_counts entry: {complexity}={expected!r}")
            if counts[complexity] != expected:
                raise ValueError(
                    f"expected {expected} {complexity} samples, found {counts[complexity]}"
                )


def resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def default_paths(batch_id: str) -> tuple[Path, Path, Path]:
    output_dir = PROJECT_ROOT / "data" / "experiments" / "pipeline" / "batches" / batch_id
    report_dir = PROJECT_ROOT / "data" / "experiments" / "repair_reports" / "batches" / batch_id
    summary_file = PROJECT_ROOT / "data" / "experiments" / "batch_reports" / f"{batch_id}_summary.json"
    return output_dir, report_dir, summary_file


def health_url() -> str:
    parsed = urlsplit(settings.generation_api_url)
    return f"{parsed.scheme}://{parsed.netloc}/health"


def check_local_server(timeout: float = 5.0) -> dict[str, Any]:
    url = health_url()
    with urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(f"local_server health check did not return ok=true: {payload}")
    return payload


def load_checkpoint(
    summary_file: Path,
    batch_id: str,
    fingerprint: str,
) -> dict[str, Any]:
    if not summary_file.exists():
        return {
            "batch_id": batch_id,
            "config_sha256": fingerprint,
            "started_at": now_iso(),
            "updated_at": now_iso(),
            "samples": [],
            "aggregate": {},
        }
    checkpoint = json.loads(summary_file.read_text(encoding="utf-8"))
    if checkpoint.get("batch_id") != batch_id:
        raise ValueError(
            f"checkpoint batch_id {checkpoint.get('batch_id')!r} does not match {batch_id!r}"
        )
    if checkpoint.get("config_sha256") != fingerprint:
        raise ValueError(
            "batch config changed after checkpoint creation; use a new summary file "
            "or remove the old checkpoint explicitly"
        )
    if not isinstance(checkpoint.get("samples"), list):
        raise ValueError("checkpoint samples must be a list")
    return checkpoint


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def usage_tokens(usage: Any) -> int:
    if not isinstance(usage, dict):
        return 0
    value = usage.get("total_tokens", 0)
    return value if isinstance(value, int) else 0


def issue_codes(result: Any, key: str) -> list[str]:
    if not isinstance(result, dict) or not isinstance(result.get(key), list):
        return []
    return [
        str(issue.get("code", "unknown"))
        for issue in result[key]
        if isinstance(issue, dict)
    ]


def compact_sample_result(
    *,
    sample: dict[str, Any],
    state: dict[str, Any],
    output_file: Path,
    report_file: Path,
    started_at: str,
    elapsed_seconds: float,
    max_repair_rounds: int,
) -> dict[str, Any]:
    initial_validate = state.get("initial_validate_result") or {}
    initial_visual = state.get("initial_visual_eval_result") or {}
    final_validate = state.get("final_validate_result") or {}
    final_visual = state.get("final_visual_eval_result") or {}
    generation_usage = state.get("generation_usage", {})
    repair_usages = [
        entry.get("repair_result", {}).get("usage", {})
        for entry in state.get("repair_history", [])
        if isinstance(entry, dict) and isinstance(entry.get("repair_result"), dict)
    ]
    generation_tokens = usage_tokens(generation_usage)
    repair_tokens = sum(usage_tokens(usage) for usage in repair_usages)

    return {
        "id": sample["id"],
        "component_name": sample["component_name"],
        "complexity": sample["complexity"],
        "coverage_focus": sample.get("coverage_focus", []),
        "vue_file": display_path(resolve_project_path(sample["vue_file"])),
        "output_file": display_path(output_file),
        "report_file": display_path(report_file),
        "final_file_path": state.get("final_file_path", ""),
        "status": "completed",
        "started_at": started_at,
        "finished_at": now_iso(),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "final_passed": bool(state.get("final_passed")),
        "stop_reason": state.get("stop_reason", ""),
        "repair_rounds": state.get("repair_rounds", 0),
        "max_repair_rounds": max_repair_rounds,
        "initial_validation_passed": initial_validate.get("validation_passed"),
        "initial_validation_error_codes": issue_codes(initial_validate, "validation_errors"),
        "initial_validation_warning_codes": issue_codes(initial_validate, "validation_warnings"),
        "initial_visual_eval_passed": initial_visual.get("visual_eval_passed"),
        "initial_visual_error_codes": issue_codes(initial_visual, "visual_eval_errors"),
        "initial_visual_warning_codes": issue_codes(initial_visual, "visual_eval_warnings"),
        "initial_structure_similarity": initial_visual.get("structure_similarity"),
        "final_validation_passed": final_validate.get("validation_passed"),
        "final_validation_error_codes": issue_codes(final_validate, "validation_errors"),
        "final_visual_eval_passed": final_visual.get("visual_eval_passed"),
        "final_visual_error_codes": issue_codes(final_visual, "visual_eval_errors"),
        "final_structure_similarity": final_visual.get("structure_similarity"),
        "final_tag_sequence_similarity": final_visual.get("tag_sequence_similarity"),
        "final_text_similarity": final_visual.get("text_similarity"),
        "final_tree_edit_distance": final_visual.get("tree_edit_distance"),
        "generation_provider": state.get("generation_provider", ""),
        "generation_model": state.get("generation_model", ""),
        "generation_tokens": generation_tokens,
        "repair_tokens": repair_tokens,
        "total_tokens": generation_tokens + repair_tokens,
    }


def build_aggregate(config: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {item.get("id"): item for item in results if item.get("id")}
    configured_ids = [sample["id"] for sample in config["samples"]]
    relevant = [by_id[sample_id] for sample_id in configured_ids if sample_id in by_id]
    completed = [item for item in relevant if item.get("status") == "completed"]
    errors = [item for item in relevant if item.get("status") == "error"]
    passed = [item for item in completed if item.get("final_passed")]
    failed = [item for item in completed if not item.get("final_passed")]
    repair_rounds = [item.get("repair_rounds", 0) for item in completed]

    complexity: dict[str, dict[str, int]] = {}
    for level in ("simple", "medium", "complex"):
        level_items = [item for item in relevant if item.get("complexity") == level]
        level_completed = [item for item in level_items if item.get("status") == "completed"]
        complexity[level] = {
            "configured": sum(1 for sample in config["samples"] if sample["complexity"] == level),
            "completed": len(level_completed),
            "passed": sum(1 for item in level_completed if item.get("final_passed")),
            "failed": sum(1 for item in level_completed if not item.get("final_passed")),
            "execution_errors": sum(1 for item in level_items if item.get("status") == "error"),
            "pass_rate_completed": (
                round(
                    sum(1 for item in level_completed if item.get("final_passed"))
                    / len(level_completed),
                    4,
                )
                if level_completed
                else None
            ),
        }

    initial_validation_error_counts = Counter(
        code
        for item in completed
        for code in item.get("initial_validation_error_codes", [])
    )
    initial_visual_error_counts = Counter(
        code
        for item in completed
        for code in item.get("initial_visual_error_codes", [])
    )
    final_validation_error_counts = Counter(
        code
        for item in completed
        for code in item.get("final_validation_error_codes", [])
    )
    final_visual_error_counts = Counter(
        code
        for item in completed
        for code in item.get("final_visual_error_codes", [])
    )
    initial_passed = sum(
        1
        for item in completed
        if item.get("initial_validation_passed") and item.get("initial_visual_eval_passed")
    )
    stop_reason_counts = Counter(
        str(item.get("stop_reason") or "unknown")
        for item in completed
    )

    return {
        "configured": len(configured_ids),
        "completed": len(completed),
        "passed": len(passed),
        "failed": len(failed),
        "execution_errors": len(errors),
        "pending": len(configured_ids) - len(completed) - len(errors),
        "pass_rate_completed": round(len(passed) / len(completed), 4) if completed else None,
        "initial_passed": initial_passed,
        "initial_pass_rate_completed": (
            round(initial_passed / len(completed), 4) if completed else None
        ),
        "repaired_to_pass": sum(
            1
            for item in passed
            if not (
                item.get("initial_validation_passed")
                and item.get("initial_visual_eval_passed")
            )
        ),
        "repair_rounds_total": sum(repair_rounds),
        "repair_rounds_average": (
            round(sum(repair_rounds) / len(repair_rounds), 3) if repair_rounds else 0.0
        ),
        "generation_tokens": sum(item.get("generation_tokens", 0) for item in completed),
        "repair_tokens": sum(item.get("repair_tokens", 0) for item in completed),
        "total_tokens": sum(item.get("total_tokens", 0) for item in completed),
        "stop_reason_counts": dict(sorted(stop_reason_counts.items())),
        "error_code_counts": {
            "initial_validation": dict(sorted(initial_validation_error_counts.items())),
            "initial_visual": dict(sorted(initial_visual_error_counts.items())),
            "final_validation": dict(sorted(final_validation_error_counts.items())),
            "final_visual": dict(sorted(final_visual_error_counts.items())),
        },
        "by_complexity": complexity,
    }


def upsert_result(results: list[dict[str, Any]], result: dict[str, Any]) -> None:
    for index, existing in enumerate(results):
        if existing.get("id") == result.get("id"):
            results[index] = result
            return
    results.append(result)


def build_plan(
    config: dict[str, Any],
    selected_ids: list[str] | None,
    output_dir: Path,
    report_dir: Path,
) -> list[dict[str, Any]]:
    selected = set(selected_ids or [])
    known = {sample["id"] for sample in config["samples"]}
    unknown = selected - known
    if unknown:
        raise ValueError(f"unknown sample ids: {', '.join(sorted(unknown))}")

    plan = []
    for sample in config["samples"]:
        if selected and sample["id"] not in selected:
            continue
        complexity_dir = sample["complexity"]
        safe_name = sample["component_name"]
        plan.append({
            **sample,
            "resolved_vue_file": resolve_project_path(sample["vue_file"]),
            "output_file": output_dir / complexity_dir / f"{safe_name}.san",
            "report_file": report_dir / complexity_dir / f"{safe_name}_repair_history.json",
        })
    return plan


def execute_batch(
    *,
    config_file: str | Path,
    output_dir: str | Path | None = None,
    report_dir: str | Path | None = None,
    summary_file: str | Path | None = None,
    max_repair_rounds: int | None = None,
    sample_ids: list[str] | None = None,
    force: bool = False,
    dry_run: bool = False,
    include_state: bool = False,
    skip_health_check: bool = False,
    fail_fast: bool = False,
    orchestrator_factory: Callable[[], Any] = MigrationPipelineOrchestrator,
) -> tuple[dict[str, Any], int]:
    resolved_config_file, config = load_batch_config(config_file)
    batch_id = config["batch_id"]
    fingerprint = config_fingerprint(config)
    default_output, default_reports, default_summary = default_paths(batch_id)
    output_path = resolve_project_path(output_dir) if output_dir else default_output
    report_path = resolve_project_path(report_dir) if report_dir else default_reports
    summary_path = resolve_project_path(summary_file) if summary_file else default_summary
    repair_rounds = (
        max_repair_rounds
        if max_repair_rounds is not None
        else config.get("max_repair_rounds", 3)
    )
    if repair_rounds < 0:
        raise ValueError("max_repair_rounds must be non-negative")

    plan = build_plan(config, sample_ids, output_path, report_path)
    if dry_run:
        return {
            "batch_id": batch_id,
            "config_sha256": fingerprint,
            "config_file": display_path(resolved_config_file),
            "max_repair_rounds": repair_rounds,
            "summary_file": display_path(summary_path),
            "samples": [
                {
                    "id": item["id"],
                    "component_name": item["component_name"],
                    "complexity": item["complexity"],
                    "coverage_focus": item.get("coverage_focus", []),
                    "vue_file": display_path(item["resolved_vue_file"]),
                    "output_file": display_path(item["output_file"]),
                    "report_file": display_path(item["report_file"]),
                }
                for item in plan
            ],
        }, 0

    checkpoint = load_checkpoint(summary_path, batch_id, fingerprint)
    existing_rounds = checkpoint.get("max_repair_rounds")
    if checkpoint.get("samples") and existing_rounds != repair_rounds:
        raise ValueError(
            "max_repair_rounds changed after checkpoint creation; use a new summary file "
            "or remove the old checkpoint explicitly"
        )
    checkpoint.update({
        "batch_id": batch_id,
        "description": config.get("description", ""),
        "config_file": display_path(resolved_config_file),
        "max_repair_rounds": repair_rounds,
        "output_dir": display_path(output_path),
        "report_dir": display_path(report_path),
        "summary_file": display_path(summary_path),
    })
    results = checkpoint["samples"]
    existing = {item.get("id"): item for item in results}
    candidates = [
        item for item in plan
        if force or existing.get(item["id"], {}).get("status") != "completed"
    ]

    if candidates and not skip_health_check:
        checkpoint["local_server"] = check_local_server()

    exit_code = 0
    for item in candidates:
        started_at = now_iso()
        running = {
            "id": item["id"],
            "component_name": item["component_name"],
            "complexity": item["complexity"],
            "coverage_focus": item.get("coverage_focus", []),
            "vue_file": display_path(item["resolved_vue_file"]),
            "status": "running",
            "started_at": started_at,
        }
        upsert_result(results, running)
        checkpoint["updated_at"] = now_iso()
        checkpoint["aggregate"] = build_aggregate(config, results)
        write_json_atomic(summary_path, checkpoint)

        start_clock = time.monotonic()
        try:
            item["output_file"].parent.mkdir(parents=True, exist_ok=True)
            stage_input = GenerateStageInput(
                vue_file_path=str(item["resolved_vue_file"]),
                source_file=item["component_name"],
                output_file_path=str(item["output_file"]),
                metadata={
                    "batch_id": batch_id,
                    "sample_id": item["id"],
                    "complexity": item["complexity"],
                    "coverage_focus": item.get("coverage_focus", []),
                },
            )
            result = orchestrator_factory().run_generate_validate_visual_eval_and_repair_loop(
                stage_input=stage_input,
                max_repair_rounds=repair_rounds,
            )
            report_args = SimpleNamespace(
                vue_file=stage_input.vue_file_path,
                ssm_file=None,
                source_file=stage_input.source_file,
                output_file=stage_input.output_file_path,
                max_repair_rounds=repair_rounds,
                include_state=include_state,
            )
            report = build_report(report_args, result.state, item["report_file"])
            write_report(item["report_file"], report)
            sample_result = compact_sample_result(
                sample=item,
                state=result.state,
                output_file=item["output_file"],
                report_file=item["report_file"],
                started_at=started_at,
                elapsed_seconds=time.monotonic() - start_clock,
                max_repair_rounds=repair_rounds,
            )
        except Exception as exc:  # noqa: BLE001 - batch isolation is intentional
            exit_code = 2
            sample_result = {
                "id": item["id"],
                "component_name": item["component_name"],
                "complexity": item["complexity"],
                "coverage_focus": item.get("coverage_focus", []),
                "vue_file": display_path(item["resolved_vue_file"]),
                "output_file": display_path(item["output_file"]),
                "report_file": display_path(item["report_file"]),
                "status": "error",
                "started_at": started_at,
                "finished_at": now_iso(),
                "elapsed_seconds": round(time.monotonic() - start_clock, 3),
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": traceback.format_exc(),
            }

        upsert_result(results, sample_result)
        checkpoint["updated_at"] = now_iso()
        checkpoint["aggregate"] = build_aggregate(config, results)
        write_json_atomic(summary_path, checkpoint)

        if sample_result["status"] == "completed":
            print(
                f"[{item['id']}] completed: "
                f"passed={sample_result['final_passed']} "
                f"repair_rounds={sample_result['repair_rounds']}"
            )
        else:
            print(
                f"[{item['id']}] error: "
                f"{sample_result['error_type']}: {sample_result['error_message']}",
                file=sys.stderr,
            )
            if fail_fast:
                break

    checkpoint["updated_at"] = now_iso()
    checkpoint["aggregate"] = build_aggregate(config, results)
    write_json_atomic(summary_path, checkpoint)
    return checkpoint, exit_code


def main() -> int:
    args = build_parser().parse_args()
    summary, exit_code = execute_batch(
        config_file=args.config_file,
        output_dir=args.output_dir,
        report_dir=args.report_dir,
        summary_file=args.summary_file,
        max_repair_rounds=args.max_repair_rounds,
        sample_ids=args.sample_ids,
        force=args.force,
        dry_run=args.dry_run,
        include_state=args.include_state,
        skip_health_check=args.skip_health_check,
        fail_fast=args.fail_fast,
    )
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"summary_file: {summary.get('summary_file')}")
        print(json.dumps(summary.get("aggregate", {}), ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
