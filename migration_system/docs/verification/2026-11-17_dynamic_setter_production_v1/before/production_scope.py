"""Disclosure for the existing migration chain, not a compatibility engine or waiver."""


def production_scope():
    """Return a fresh server-owned snapshot, persisted with each new request."""
    return {
        'id': 'san-supported-migration-v1',
        'label': '有明确支持范围的 Vue → SSM → San 迁移闭环',
        'target': 'San',
        'deployment': 'trusted_local_single_user',
        'source_profile': 'single_file_javascript_options_api_without_external_imports',
        'exports': ['export default', 'module.exports'],
        'styles': ['css', 'scoped_css'],
        'pipeline': ['preflight', 'extract_ssm', 'generate', 'evaluate',
                     'bounded_repair', 'candidate_retest_and_gate', 'report_and_download'],
        'unsupported_policy': 'report_and_stop_not_pass_not_rewrite_source',
        'preflight_is_full_support_proof': False,
        'full_public_instance_compatibility': False,
        'experimental_public_instance_runtime_enabled': False,
        'dynamic_instance_setter': 'blocked_without_finite_key_waiver',
        'evaluation_scope': 'configured_props_and_actions_not_universal_equivalence',
        'missing_interactions': 'not_run_not_pass',
        'historical_results_reclassified': False,
        'not_required_for_basic_migration': ['langsmith_upload', 'lora_training', 'clip_embeddings'],
    }
