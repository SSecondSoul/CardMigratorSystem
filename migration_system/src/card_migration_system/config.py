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
    """Locate this self-contained system checkout, never its parent repository."""
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
    auth_mode: str = 'local'
    public_origin: str = ''

    @property
    def engine_root(self) -> Path:
        """Internal validated engine. repository_root is a compatibility field."""
        return self.repository_root

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
            "auth_mode": self.auth_mode, "public_origin": self.public_origin,
            "project_root": str(self.project_root),
            "engine_root": str(self.engine_root),
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
    repository = project / 'engine'
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
    _keys(app, ("mode", "host", "port", "auth_mode", "public_origin"), "app")
    _keys(paths, ("runtime_dir", "artifact_dir"), "paths")
    env = os.environ if environ is None else environ
    mode = env.get("CARDMIG_SYSTEM_MODE", app.get("mode"))
    host = env.get("CARDMIG_SYSTEM_HOST", app.get("host"))
    port = env.get("CARDMIG_SYSTEM_PORT", app.get("port"))
    auth_mode = env.get('CARDMIG_AUTH_MODE', app.get('auth_mode','local'))
    origin = env.get('CARDMIG_PUBLIC_ORIGIN',app.get('public_origin',''))
    if auth_mode not in ('local','multi_user'):
        raise ConfigurationError('Invalid authentication mode')
    if origin and auth_mode!='multi_user':
        raise ConfigurationError('Public origin requires multi_user authentication')
    from urllib.parse import urlsplit
    address=urlsplit(origin) if type(origin) is str else None
    if not address or origin and (address.scheme!='https' or not address.hostname or address.username or address.password or address.path or address.query or address.fragment):
        raise ConfigurationError('Public origin must be an exact HTTPS origin without a path')
    if "CARDMIG_SYSTEM_PORT" in env:
        if type(port) is not str or not re.fullmatch(r"[0-9]{1,5}", port):
            raise ConfigurationError("Invalid CARDMIG_SYSTEM_PORT")
        port = int(port)
    if mode != "development_stub":
        raise ConfigurationError("P2a only supports development_stub configuration, not real execution")
    if host not in ("127.0.0.1", "::1") and not (auth_mode=='multi_user' and origin and host=='0.0.0.0'):
        raise ConfigurationError("Only explicit loopback hosts are supported")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ConfigurationError("Port must be an integer in 1..65535")
    for key in ("runtime_dir", "artifact_dir"):
        if type(paths.get(key)) is not str or not paths[key].strip():
            raise ConfigurationError(f"{key} must be an explicit nonblank path")
    runtime = _inside(project / paths["runtime_dir"], project / "var", "Runtime")
    artifacts = _inside(project / paths["artifact_dir"], project / 'var/artifacts', "Artifact")
    if runtime == artifacts or runtime.is_relative_to(artifacts) or artifacts.is_relative_to(runtime):
        raise ConfigurationError("Runtime and evidence directories must differ")
    return Settings(project, repository, runtime, artifacts, host, port, mode, auth_mode, origin)
