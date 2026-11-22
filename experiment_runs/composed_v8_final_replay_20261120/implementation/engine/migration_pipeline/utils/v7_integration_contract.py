"""Explicit application scope for the first v7 integration investigation.

This validates declarations, NOT function purity, source equivalence, ancestry at
runtime or production admission. Existing semantic validators remain mandatory.
"""
from copy import deepcopy


V7_APPLICATION_SCOPE = {
    'schema_version': 1,
    'environment': 'browser',
    'ancestor_policy': 'no-source-ancestor-error-capture',
    'global_error_policy': 'report-only',
    'handler_scheduling': 'synchronous',
    'tracking_policy': 'no-reactive-reads-or-writes',
    'san_adapter': 'v7-parent-watch-report-only',
    'framework_versions': {'vue': '2.7.16', 'san': '3.15.6'},
}
MANIFEST_ERROR_POLICY = 'explicit-global-reporting-only-no-source-ancestor-captures'


def evaluate_v7_application_scope(declaration: dict, manifest: dict) -> dict:
    """Exact opt-in; no permissive defaults and no inferred ancestor mapping."""
    problems = []
    if not isinstance(declaration, dict):
        problems.append('application_scope_declaration_required')
    else:
        if set(declaration) != set(V7_APPLICATION_SCOPE):
            problems.append('unknown_or_missing_application_scope_fields')
        for key, expected in V7_APPLICATION_SCOPE.items():
            actual = declaration.get(key)
            if type(actual) is not type(expected) or actual != expected:
                problems.append('unsupported_application_scope:' + key)
    if not isinstance(manifest, dict):
        problems.append('acceptance_manifest_required')
    else:
        if manifest.get('san_adapter') != V7_APPLICATION_SCOPE['san_adapter']:
            problems.append('manifest_adapter_mismatch')
        if manifest.get('application_error_policy') != MANIFEST_ERROR_POLICY:
            problems.append('manifest_error_policy_mismatch')
        frameworks = manifest.get('frameworks')
        if not isinstance(frameworks, dict):
            frameworks = {}
        for framework, version in V7_APPLICATION_SCOPE['framework_versions'].items():
            config = frameworks.get(framework)
            if not isinstance(config, dict) or config.get('version') != version:
                problems.append('manifest_runtime_version_mismatch:' + framework)
    return {
        'contract': 'v7_limited_browser_application_scope_v1',
        'application_scope_accepted': not problems,
        'blocking_reasons': problems,
        'supported_declaration': deepcopy(V7_APPLICATION_SCOPE),
        'production_eligible': False,
        'source_equivalence_proven': False,
        'runtime_callback_purity_proven': False,
        'boundary': 'Declaration acceptance is only a prerequisite. It never clears source watcher diagnostics, '
                    'proves callback purity or deployment, or substitutes for production validation and regression gates.',
    }
