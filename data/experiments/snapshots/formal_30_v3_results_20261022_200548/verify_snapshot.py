"""Verify every file recorded in this frozen result snapshot."""

import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main():
    failures = []
    checked = 0
    for line in (HERE / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = HERE / relative
        if not path.is_file():
            failures.append(f"missing: {relative}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(f"hash mismatch: {relative}")
        checked += 1
    if failures:
        print("snapshot verification: FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"snapshot verification: PASS ({checked} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
