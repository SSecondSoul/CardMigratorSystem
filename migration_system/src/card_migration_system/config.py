"""P2a local configuration. Parsing is read-only and confers no execution permission."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import tomllib
from typing import Mapping


class ConfigurationError(ValueError):
    pass


def source_project_root() -> Path:
    """Source checkout convenience, not an installed-wheel deployment locator."""
    return Path(__file__).resolve().parents[2]


def _inside(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ConfigurationError(f"{label} escapes its allowed directory")
    return resolved


def _keys(value, allowed, label):
    if type(value) is not dict or set(value) - set(allowed):
        raise ConfigurationError(f"Unsupported {label} fields")


@dataclass(frozen=True)
class Settings:
    project_root: Path
    repository_root: Path
    runtime_dir: Path
    artifact_dir: Path
    host: str
    port: int
    mode: str

    @property
    def business_database(self) -> Path:
        return self.runtime_dir / "business.sqlite3"

    @property
    def graph_database(self) -> Path:
        return self.runtime_dir / "langgraph.sqlite3"

    def public_summary(self) -> dict:
        # Explicit allowlist: never dump os.environ, model credentials or raw TOML.
        return {
            "mode": self.mode, "host": self.host, "port": self.port,
            "project_root": str(self.project_root),
            "runtime_dir": str(self.runtime_dir), "artifact_dir": str(self.artifact_dir),
            "business_database": str(self.business_database),
            "graph_database": str(self.graph_database),
        }


def load_settings(*, project_root: Path | str | None = None,
                  config_file: Path | str | None = None,
                  environ: Mapping[str, str] | None = None) -> Settings:
    project = Path(project_root).resolve() if project_root is not None else source_project_root()
    if not project.is_dir():
        raise ConfigurationError("Project root must exist")
    repository = project.parent
    config = Path(config_file) if config_file is not None else Path("configs/development.toml")
    config = _inside(config if config.is_absolute() else project / config, project, "Config")
    try:
        with config.open("rb") as stream:
            data = stream.read(65537)
        if len(data) > 65536:
            raise ConfigurationError("Configuration exceeds 64 KiB")
        payload = tomllib.loads(data.decode("utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError("Cannot read valid UTF-8 TOML configuration") from error
    _keys(payload, ("schema_version", "app", "paths"), "top-level")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        raise ConfigurationError("Unsupported configuration schema")
    app, paths = payload.get("app"), payload.get("paths")
    _keys(app, ("mode", "host", "port"), "app")
    _keys(paths, ("runtime_dir", "artifact_dir"), "paths")
    env = os.environ if environ is None else environ
    mode = env.get("CARDMIG_SYSTEM_MODE", app.get("mode"))
    host = env.get("CARDMIG_SYSTEM_HOST", app.get("host"))
    port = env.get("CARDMIG_SYSTEM_PORT", app.get("port"))
    if "CARDMIG_SYSTEM_PORT" in env:
        if type(port) is not str or not re.fullmatch(r"[0-9]{1,5}", port):
            raise ConfigurationError("Invalid CARDMIG_SYSTEM_PORT")
        port = int(port)
    if mode != "development_stub":
        raise ConfigurationError("P2a only supports development_stub configuration, not real execution")
    if host not in ("127.0.0.1", "::1"):
        raise ConfigurationError("Only explicit loopback hosts are supported")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ConfigurationError("Port must be an integer in 1..65535")
    for key in ("runtime_dir", "artifact_dir"):
        if type(paths.get(key)) is not str or not paths[key].strip():
            raise ConfigurationError(f"{key} must be an explicit nonblank path")
    runtime = _inside(project / paths["runtime_dir"], project / "var", "Runtime")
    artifacts = _inside(project / paths["artifact_dir"],
                        repository / "data/experiments/migration_system", "Artifact")
    if runtime == artifacts:
        raise ConfigurationError("Runtime and evidence directories must differ")
    return Settings(project, repository, runtime, artifacts, host, port, mode)
