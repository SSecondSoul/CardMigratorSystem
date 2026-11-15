"""Restore SettingsForm prop initialization in a separate Monitoring probe."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration_pipeline.replay_formal_30_v4_remaining_monitoring_syntax_fix import (
    check_candidate,
    replace_exact,
)


SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_remaining_monitoring_syntax_v1_candidate_20261027_211600/candidate.san"
)
SOURCE_SHA256 = "6a9da9e71e8a0695583d5097dd86425dbe5130b77428075ba57ea1e0138c889c"
OUTPUT_DIR = ROOT / (
    "data/experiments/pipeline/manual_fixes/"
    "formal_30_v4_remaining_monitoring_settings_v2"
)
OUTPUT = OUTPUT_DIR / "MonitoringDashboard_repaired.san"
REPORT = OUTPUT_DIR / "repair_report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_candidate(code: str) -> str:
    # Vue SettingsForm.data() copies the incoming settings prop. San initData
    # cannot read props; copy it once from the data store in inited().
    code = replace_exact(
        code,
        """      localSettings: {
        refreshInterval: 5,
        alertThreshold: 80,
        logRetention: '7',
        autoRefresh: true,
        desktopNotifications: false
      }
    };
  },
  handleSubmit() {""",
        """      localSettings: {}
    };
  },
  inited() {
    this.data.set('localSettings', { ...(this.data.get('settings') || {}) });
  },
  handleSubmit() {""",
    )
    return code


def main() -> None:
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("v2 candidate/report already exists; do not overwrite evidence")
    if sha256(SOURCE) != SOURCE_SHA256:
        raise RuntimeError("Frozen Monitoring v1 candidate SHA-256 mismatch")
    candidate = build_candidate(SOURCE.read_text(encoding="utf-8"))
    validation, visual = check_candidate(candidate)
    if not validation.validation_passed:
        raise RuntimeError(f"v2 validation failed: {validation.validation_errors}")
    if not visual.visual_eval_passed:
        raise RuntimeError(f"v2 lightweight visual failed: {visual.visual_eval_errors}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(candidate, encoding="utf-8", newline="")
    report = {
        "sample_id": "MonitoringDashboard",
        "classification": "reused_development_posthoc_settings_initialization_probe",
        "independent_holdout": False,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": SOURCE_SHA256,
        "candidate": OUTPUT.relative_to(ROOT).as_posix(),
        "candidate_sha256": sha256(OUTPUT),
        "scope": "SettingsForm copies its incoming settings prop during San inited, preserving Vue data() semantics",
        "validation_passed": True,
        "san_compile_passed": True,
        "lightweight_visual_passed": True,
        "structure_similarity": visual.structure_similarity,
        "browser_runtime": "pending_user_review",
        "boundary": "This is a post-hoc development candidate; the failed automatic batch remains unchanged.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
