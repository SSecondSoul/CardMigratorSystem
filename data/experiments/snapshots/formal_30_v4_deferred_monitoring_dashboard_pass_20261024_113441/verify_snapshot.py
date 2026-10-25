"""Verify every file recorded in this frozen snapshot."""

import hashlib
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main() -> None:
    failures = []
    checked = 0
    for line in (HERE / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        path = HERE / relative
        if not path.is_file():
            failures.append(f"missing: {relative}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(f"hash mismatch: {relative}")
        checked += 1
    if failures:
        raise SystemExit("snapshot verification failed: " + "; ".join(failures))
    print(f"snapshot verification passed: {checked} files")


if __name__ == "__main__":
    main()
