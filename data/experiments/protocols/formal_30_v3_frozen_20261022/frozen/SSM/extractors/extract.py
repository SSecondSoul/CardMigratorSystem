#!/usr/bin/env python3
"""
SSM 提取工具 — CLI 入口

用法：
    python -m SSM.extractors.extract <input.vue> [--output result.json] [--pretty]

    python -m SSM.extractors.extract --stdin < input.vue

    python -m SSM.extractors.extract --dir ./components/ --output-dir ./ssm_output/

输入：
    单个 .vue 文件、stdin 传入的源码、或包含 .vue 文件的目录。

输出：
    符合 SSM Schema v3 的 JSON 文件。
"""

import argparse
import json
import os
import sys

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


from SSM.extractors.factory import SSMFactory


def extract_single(input_file: str, output_file: str, pretty: bool = False):
    """提取单个 .vue 文件。"""
    if not os.path.isfile(input_file):
        print(f"[错误] 文件不存在: {input_file}", file=sys.stderr)
        sys.exit(1)

    factory = SSMFactory()
    result = factory.build_from_file(input_file)

    indent = 2 if pretty else None

    if output_file:
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=indent)
        print(f"[完成] SSM 已输出到: {output_file}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=indent))


def extract_stdin(output_file: str, pretty: bool = False):
    """从标准输入读取源码。"""
    source = sys.stdin.read()
    if not source.strip():
        print("[错误] stdin 为空", file=sys.stderr)
        sys.exit(1)

    factory = SSMFactory()
    result = factory.build(source, source_file="stdin")

    indent = 2 if pretty else None

    if output_file:
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=indent)
        print(f"[完成] SSM 已输出到: {output_file}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=indent))


def extract_dir(input_dir: str, output_dir: str, pretty: bool = False):
    """提取目录下所有 .vue 文件。"""
    if not os.path.isdir(input_dir):
        print(f"[错误] 目录不存在: {input_dir}", file=sys.stderr)
        sys.exit(1)

    vue_files = []
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith(".vue"):
                vue_files.append(os.path.join(root, filename))

    if not vue_files:
        print(f"[警告] 目录中没有找到 .vue 文件: {input_dir}")
        return

    factory = SSMFactory()
    os.makedirs(output_dir, exist_ok=True)

    success = 0
    fail = 0

    for vpath in vue_files:
        try:
            result = factory.build_from_file(vpath)

            rel_path = os.path.relpath(vpath, input_dir)
            out_name = os.path.splitext(rel_path)[0] + ".json"
            out_path = os.path.join(output_dir, out_name)

            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            indent = 2 if pretty else None
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=indent)

            success += 1
            print(f"  [OK] {rel_path} → {out_name}")
        except Exception as e:
            fail += 1
            rel_path = os.path.relpath(vpath, input_dir)
            print(f"  [FAIL] {rel_path}: {e}", file=sys.stderr)

    print(f"\n[完成] 成功 {success} 个, 失败 {fail} 个, 共 {len(vue_files)} 个文件")
    print(f"[输出目录] {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="SSM 提取工具 — 将 Vue SFC 组件提取为 San Source Model",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="输入的 .vue 文件路径（默认使用 --stdin）",
    )
    parser.add_argument(
        "--output", "-o",
        help="输出的 JSON 文件路径（默认输出到 stdout）",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="从标准输入读取源码",
    )
    parser.add_argument(
        "--dir", "-d",
        help="批量提取目录下所有 .vue 文件",
    )
    parser.add_argument(
        "--output-dir",
        help="批量提取时的输出目录（配合 --dir 使用）",
    )
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="输出格式化的 JSON（缩进 2 空格）",
    )

    args = parser.parse_args()

    # 模式判断
    if args.stdin:
        extract_stdin(args.output, args.pretty)
    elif args.dir:
        output_dir = args.output_dir or "./ssm_output"
        extract_dir(args.dir, output_dir, args.pretty)
    elif args.input:
        extract_single(args.input, args.output, args.pretty)
    else:
        # 无参数时尝试从 stdin 读取
        extract_stdin(args.output, args.pretty)


if __name__ == "__main__":
    main()