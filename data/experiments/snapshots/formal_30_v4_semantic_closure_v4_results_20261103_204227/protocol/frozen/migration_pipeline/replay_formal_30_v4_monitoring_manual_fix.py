"""Replay scoped MonitoringDashboard manual findings from its frozen pass."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / (
    "data/experiments/snapshots/"
    "formal_30_v4_deferred_monitoring_dashboard_pass_20261025_124927/"
    "pipeline/complex/MonitoringDashboard_repaired_repaired.san"
)
SOURCE_SHA256 = "0d2970f176ac8416dab6b99e512e17c5dd3e06628e2ed70ff6a7bd54fd898156"
TARGET = ROOT / (
    "data/experiments/pipeline/manual_fixes/formal_30_v4_monitoring_dashboard/"
    "MonitoringDashboard_settings_kpi_logs.san"
)


def replace_once(code: str, old: str, new: str) -> str:
    if code.count(old) != 1:
        raise RuntimeError(f"Expected exactly one occurrence of {old!r}, found {code.count(old)}")
    return code.replace(old, new, 1)


def main() -> None:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("Frozen source SHA-256 changed")
    if TARGET.exists():
        raise FileExistsError(TARGET)
    code = SOURCE.read_text(encoding="utf-8")
    for old, new in (
        ('on-click="showSettings = true"', 'on-click="openSettings"'),
        ('s-if="showSettings" on-click="showSettings = false"',
         's-if="showSettings" on-click="onSettingsOverlayClick($event)"'),
        ('on-click="showSettings = false"', 'on-click="closeSettings"'),
        ('on-save="saveSettings"', 'on-save="saveSettings($event)"'),
        ('on-cancel="showSettings = false"', 'on-cancel="closeSettings"'),
        ('{{ Math.abs(trend) }}%', '{{ formatTrend(trend) }}%'),
        ('{{ log.level.toUpperCase() }}', '{{ formatLogLevel(log.level) }}'),
        ('<form on-submit="handleSubmit" class="settings-form">',
         '<form on-submit="prevent:handleSubmit" class="settings-form">'),
        ('on-click="fire(\'cancel\')" class="cancel-btn"',
         'on-click="cancel" class="cancel-btn"'),
    ):
        code = replace_once(code, old, new)
    code = replace_once(
        code,
        """      icon: ''
    };
  }
});

const realTimeChart""",
        """      icon: ''
    };
  },
  formatTrend(trend) {
    return Math.abs(Number(trend) || 0);
  }
});

const realTimeChart""",
    )
    code = replace_once(
        code,
        """  formatTime(timestamp) {
    const date = new Date(timestamp);
    return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}`;
  }
});

const serviceGrid""",
        """  formatTime(timestamp) {
    const date = new Date(timestamp);
    return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}`;
  },
  formatLogLevel(level) {
    return String(level || '').toUpperCase();
  }
});

const serviceGrid""",
    )
    code = replace_once(
        code,
        """  handleSubmit() {
    this.fire('save', this.data.get('localSettings'));
  }
});

module.exports""",
        """  handleSubmit() {
    this.fire('save', this.data.get('localSettings'));
  },
  cancel() {
    this.fire('cancel');
  }
});

module.exports""",
    )
    code = replace_once(
        code,
        """  saveSettings(settings) {
    this.stopAutoRefresh();""",
        """  openSettings() {
    this.data.set('showSettings', true);
  },
  closeSettings() {
    this.data.set('showSettings', false);
  },
  onSettingsOverlayClick(event) {
    if (event && event.target === event.currentTarget) this.closeSettings();
  },
  saveSettings(settings) {
    this.stopAutoRefresh();""",
    )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(code, encoding="utf-8")
    print(f"candidate: {TARGET.relative_to(ROOT)}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
