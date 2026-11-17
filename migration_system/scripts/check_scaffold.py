"""Source-checkout entry point; uses only the new src package, not the old root."""
from pathlib import Path
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from card_migration_system.interfaces.cli import main

    raise SystemExit(main(["check", *sys.argv[1:]]))
