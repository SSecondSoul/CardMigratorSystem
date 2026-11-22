import importlib
from types import ModuleType

DEFAULT_SCHEMA_VERSION = "v3"
SCHEMA_MODULES = {
    "v1": "SSM.schema.v1",
    "v2": "SSM.schema.v2",
    "v3": "SSM.schema.v3",
}


def resolve_schema_module(schema: str | ModuleType | None = None) -> ModuleType:
    if isinstance(schema, ModuleType):
        return schema

    target = schema or DEFAULT_SCHEMA_VERSION
    module_path = SCHEMA_MODULES.get(target, target)
    return importlib.import_module(module_path)


def get_default_schema_module_path() -> str:
    return SCHEMA_MODULES[DEFAULT_SCHEMA_VERSION]
