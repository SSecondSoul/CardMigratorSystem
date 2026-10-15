import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from migration_pipeline import GenerateStage, GenerateStageInput


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run migration_pipeline generate stage to produce San code.",
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
        help="Optional target path for the generated .san file.",
    )
    parser.add_argument(
        "--source-file",
        default="",
        help="Optional logical source file name passed to generation service.",
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
        "--disable-node-bridge",
        action="store_true",
        help="Disable Node bridge when building SSM from Vue input.",
    )
    return parser


def load_json_file(file_path: str) -> dict:
    return json.loads(Path(file_path).read_text(encoding="utf-8"))


def main() -> int:
    args = build_parser().parse_args()
    metadata = load_json_file(args.metadata_file) if args.metadata_file else {}
    ssm = load_json_file(args.ssm_file) if args.ssm_file else None

    stage_input = GenerateStageInput(
        vue_file_path=args.vue_file,
        ssm=ssm,
        source_file=args.source_file,
        instruction=args.instruction,
        output_file_path=args.output_file,
        use_node_bridge=not args.disable_node_bridge,
        metadata=metadata,
    )
    result = GenerateStage().run(stage_input)

    print(f"source_file: {result.source_file}")
    print(f"saved_file_path: {result.saved_file_path}")
    print(f"provider: {result.provider}")
    print(f"model: {result.model}")
    print(f"usage: {json.dumps(result.usage, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
