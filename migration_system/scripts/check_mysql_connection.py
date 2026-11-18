"""Read-only MySQL inspection; credentials never come from CLI arguments."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from card_migration_system.persistence.mysql_connection import main

if __name__ == '__main__':
    raise SystemExit(main())
