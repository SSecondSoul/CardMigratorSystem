"""Verify the frozen protocol and optionally its live inputs/runtime."""

import argparse
import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    failures = []
    entries = []
    for line in (HERE / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        entries.append((expected, relative))
        frozen = HERE / relative
        if not frozen.is_file():
            failures.append(f"missing protocol file: {relative}")
        elif digest(frozen) != expected:
            failures.append(f"protocol checksum mismatch: {relative}")
        if args.live and relative.startswith("frozen/"):
            live_relative = relative[len("frozen/"):]
            live = ROOT / live_relative
            if not live.is_file():
                failures.append(f"missing live file: {live_relative}")
            elif digest(live) != expected:
                failures.append(f"live file differs from frozen baseline: {live_relative}")
    if failures:
        print("protocol verification: FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"protocol verification: PASS ({len(entries)} checksums, live={args.live})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
