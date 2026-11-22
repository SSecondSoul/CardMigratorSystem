"""Read-only, pinned P1 loader. Does not execute migration_pipeline/__init__.py.

Trusted repository compatibility, not a sandbox for hostile Python producers.
All three source texts are verified before executing any of them. Execution uses
those exact verified strings, avoiding a second path read by an import loader.
"""
from dataclasses import dataclass, field
from hashlib import sha256
from importlib.machinery import ModuleSpec
from importlib.resources import files
import json
from pathlib import Path
import re
import sys
from threading import RLock
from types import ModuleType


class ContractBindingError(ValueError):
    pass


_LOCK = RLock()
_NAMES = ("__init__.py", "v1.py", "legacy.py")


def _manifest():
    payload = json.loads(files(__package__).joinpath("p1_contracts_pin.json").read_text(encoding="utf-8"))
    if (type(payload) is not dict or set(payload) != {
            "schema_version", "binding_id", "relative_directory", "normalization", "files"}
            or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
            or payload["relative_directory"] != "migration_pipeline/contracts"
            or payload["normalization"] != "utf8_lf_no_other_changes"
            or type(payload["binding_id"]) is not str
            or type(payload["files"]) is not dict or set(payload["files"]) != set(_NAMES)):
        raise ContractBindingError("Unsupported P1 binding manifest")
    if any(type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value)
           for value in payload["files"].values()):
        raise ContractBindingError("Invalid P1 source fingerprint")
    return payload


@dataclass(frozen=True)
class LegacyContractBinding:
    binding_id: str
    manifest_sha256: str
    source_directory: Path
    source_sha256: tuple[tuple[str, str], ...]
    contracts: ModuleType = field(repr=False, compare=False)

    def public_summary(self):
        return {
            "binding_id": self.binding_id, "manifest_sha256": self.manifest_sha256,
            "source_directory": str(self.source_directory),
            "source_sha256": dict(self.source_sha256),
            "normalization": "utf8_lf_no_other_changes",
            "scope": "pinned_contracts_only_not_pipeline_admission",
        }


def load_p1_contracts(repository_root: Path | str) -> LegacyContractBinding:
    manifest = _manifest()
    repository = Path(repository_root).resolve()
    directory = repository / manifest["relative_directory"]
    sources = {}
    for name in _NAMES:
        path = (directory / name).resolve()
        if not path.is_relative_to(repository):
            raise ContractBindingError("P1 source escapes repository")
        try:
            raw = path.read_bytes()
            source = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        except (OSError, UnicodeError) as error:
            raise ContractBindingError(f"Cannot read pinned P1 source: {name}") from error
        if sha256(source.encode("utf-8")).hexdigest() != manifest["files"][name]:
            raise ContractBindingError(f"P1 source drift detected: {name}; explicit re-integration required")
        sources[name] = source
    manifest_hash = sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    location_hash = sha256(str(repository).encode("utf-8")).hexdigest()
    namespace = f"card_migration_system._p1_{manifest_hash}_{location_hash}"
    with _LOCK:
        if namespace not in sys.modules:
            package = ModuleType(namespace)
            package.__package__ = namespace
            package.__path__ = []
            package.__spec__ = ModuleSpec(namespace, loader=None, is_package=True)
            package.__file__ = str(directory / "__init__.py")
            created = [namespace]
            sys.modules[namespace] = package
            try:
                for name in ("v1", "legacy"):
                    qualified = f"{namespace}.{name}"
                    module = ModuleType(qualified)
                    module.__package__ = namespace
                    module.__file__ = str(directory / f"{name}.py")
                    module.__spec__ = ModuleSpec(qualified, loader=None)
                    sys.modules[qualified] = module
                    created.append(qualified)
                    setattr(package, name, module)
                    exec(compile(sources[f"{name}.py"], module.__file__, "exec"), module.__dict__)
                exec(compile(sources["__init__.py"], package.__file__, "exec"), package.__dict__)
            except Exception:
                for name in reversed(created):
                    sys.modules.pop(name, None)
                raise
        package = sys.modules[namespace]
    return LegacyContractBinding(manifest["binding_id"], manifest_hash, directory.resolve(),
                                 tuple(sorted(manifest["files"].items())), package)
