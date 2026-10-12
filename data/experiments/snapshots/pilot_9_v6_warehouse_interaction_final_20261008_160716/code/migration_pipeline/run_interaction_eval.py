import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from migration_pipeline.utils.interaction_eval import evaluate_interaction_scenario


DEFAULT_CONFIG_FILE = (
    PROJECT_ROOT
    / "migration_pipeline"
    / "interaction_configs"
    / "pilot_9_v6_data_pagination.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate Vue/San interaction scenarios without calling a model.",
    )
    parser.add_argument(
        "--config-file",
        default=str(DEFAULT_CONFIG_FILE),
        help="Standalone interaction evaluation JSON config.",
    )
    parser.add_argument("--report-file", help="Override the report path from the config.")
    return parser


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def config_fingerprint(config: dict[str, Any]) -> str:
    canonical = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    for field in ("evaluation_id", "vue_file", "san_file", "report_file"):
        if not isinstance(config.get(field), str) or not config[field]:
            raise ValueError(f"{field} must be a non-empty string")
    scenarios = config.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("scenarios must be a non-empty list")
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict) or not isinstance(scenario.get("steps"), list):
            raise ValueError(f"scenarios[{index}] must contain a steps list")
    fixed_now_ms = config.get("fixed_now_ms", 1_700_000_000_000)
    if not isinstance(fixed_now_ms, int) or isinstance(fixed_now_ms, bool):
        raise ValueError("fixed_now_ms must be an integer timestamp in milliseconds")
    return config


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def main() -> int:
    args = build_parser().parse_args()
    config_path = resolve_project_path(args.config_file)
    config = load_config(config_path)
    vue_file = resolve_project_path(config["vue_file"])
    san_file = resolve_project_path(config["san_file"])
    report_file = resolve_project_path(args.report_file or config["report_file"])

    for source in (vue_file, san_file):
        if not source.is_file():
            raise FileNotFoundError(source)

    result = evaluate_interaction_scenario(
        vue_file_path=vue_file,
        san_file_path=san_file,
        scenarios=config["scenarios"],
        fixed_now_ms=config.get("fixed_now_ms", 1_700_000_000_000),
    )
    report = {
        "evaluation_id": config["evaluation_id"],
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "config_file": display_path(config_path),
        "config_sha256": config_fingerprint(config),
        "vue_file": display_path(vue_file),
        "san_file": display_path(san_file),
        "fixed_now_ms": config.get("fixed_now_ms", 1_700_000_000_000),
        "model_called": False,
        "result": asdict(result),
    }
    write_json_atomic(report_file, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
