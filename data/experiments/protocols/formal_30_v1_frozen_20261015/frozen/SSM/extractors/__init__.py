# SSM Extractors Package
from SSM.schema import DEFAULT_SCHEMA_VERSION, get_default_schema_module_path, resolve_schema_module

from .factory import DEFAULT_SCHEMA_MODULE, SSMFactory, build_ssm
from .vue_parser import VueSFCParser, parse_vue_sfc
from .template_extractor import TemplateExtractor, extract_template
from .script_extractor import ScriptExtractor, extract_script
from .style_extractor import StyleExtractor, extract_styles, extract_template_classes
from .relation_builder import RelationBuilder, build_relations
