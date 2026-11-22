"""Disclosure for the existing migration chain, not a compatibility engine or waiver."""


def production_scope():
    """Return a fresh server-owned snapshot, persisted with each new request."""
    return {
        'id': 'san-supported-migration-v4',
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
        'runtime_admission': 'not_enabled_in_production',
        'dynamic_instance_setter': 'admitted_to_existing_model_pipeline_without_source_rewrite',
        'dynamic_assignment_contract': 'source_internal_declared_state_assignment_v1',
        'dynamic_assignment_limitations': 'not_arbitrary_external_public_key_equivalence',
        'generation_policy': 'model_generation_with_existing_validation_and_bounded_repair',
        'source_ast_rule_generation_enabled': False,
        'evaluation_scope': 'configured_props_and_actions_not_universal_equivalence',
        'missing_interactions': 'not_run_not_pass',
        'historical_results_reclassified': False,
        'not_required_for_basic_migration': ['langsmith_upload', 'lora_training', 'clip_embeddings'],
    }
