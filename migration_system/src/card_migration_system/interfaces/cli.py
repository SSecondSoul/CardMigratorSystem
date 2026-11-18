"""Read-only checks and explicit development database/API/worker commands."""
import argparse
import json
import os
import secrets
from pathlib import Path
import sys

from .. import __version__
from ..config import ConfigurationError, load_settings
from ..contracts import ContractBindingError, load_p1_contracts


def check_scaffold(*, project_root=None, config_file=None, environ=None):
    settings = load_settings(project_root=project_root, config_file=config_file, environ=environ)
    from ..adapters.engine import verify_engine
    engine=verify_engine(settings.engine_root)
    binding = load_p1_contracts(settings.repository_root)
    return {
        "package_version": __version__, "status": "scaffold_verified",
        "production_ready": False, "model_calls": 0, "services_started": False,
        "configuration": settings.public_summary(), "contracts": binding.public_summary(),
        "engine": engine,
        "capabilities": {
            "frontend": "real_migration_workbench",
            "ssm_extraction": "internal_AST_extractor_with_diagnostic_fallback_boundary",
            "san_generation": "internal_pinned_experimental_prompt_Qwen_or_local_LoRA",
            "modular_migration": "real_graph_api_worker_evaluation_repair_code_external_configuration_pending",
            **{name: "local_persistent_system_not_unrestricted_production" for name in (
                "http_api", "business_database", "worker", "langgraph_execution")},
            "langsmith_tracing": "opt_in_metadata_only_export_implemented_live_credentials_pending",
            "puppeteer_evaluation": "real_isolated_context_ast_dom_screenshot_ssim_styles_actions",
            "lora_training": "offline_dataset_peft_training_and_adapter_inference_implemented_resources_pending"},
    }


def main(argv=None):
    from .system_cli import COMMANDS, main as system_main
    raw = sys.argv[1:] if argv is None else argv
    from .accounts_cli import COMMANDS as AUTH_COMMANDS, main as auth_main
    if raw and raw[0] in AUTH_COMMANDS:return auth_main(raw)
    if raw and raw[0]=='worker':
        return system_main(['migration-worker',*raw[1:]])
    if raw and raw[0] in COMMANDS:
        return system_main(raw)
    parser = argparse.ArgumentParser(description="Development vertical slice; not a production migration runner")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="read-only configuration and pinned-contract verification")
    check.add_argument("--project-root", type=Path)
    check.add_argument("--config", type=Path)
    for name in ("init-db", "serve", "development-worker", "backup", "verify-backup", "restore", "extract-ssm",
                 "extract-ssm-graph", "resume-ssm-extraction", "ssm-extraction-report", "generation-preview",
                 "prepare-generation", "generation-report", "generation-budget-review", "prepare-generation-approval",
                 "generation-approval-report", "approve-generation-plan", "revoke-generation-plan"):
        command = commands.add_parser(name)
        command.add_argument("--project-root", type=Path)
        command.add_argument("--config", type=Path)
        if name == "development-worker":
            command.add_argument("--once", action="store_true")
        if name in ("backup", "verify-backup", "restore"):
            command.add_argument("--backup-id", required=name != "backup")
        if name in ("extract-ssm", "extract-ssm-graph"):
            source = command.add_mutually_exclusive_group(required=True)
            source.add_argument("--input-id")
            source.add_argument("--run-id")
        if name in ('resume-ssm-extraction', 'ssm-extraction-report'):
            command.add_argument('--extraction-id', required=True)
        if name == 'generation-report':
            command.add_argument('--generation-id', required=True)
        if name in ('generation-approval-report', 'approve-generation-plan', 'revoke-generation-plan'):
            command.add_argument('--approval-id', required=True)
        if name in ('approve-generation-plan', 'revoke-generation-plan'):
            command.add_argument('--expected-request-sha256', required=True)
        if name == 'approve-generation-plan':
            command.add_argument('--confirm-single-call', action='store_true', required=True)
        if name in ('generation-preview', 'prepare-generation', 'generation-budget-review', 'prepare-generation-approval'):
            command.add_argument('--extraction-id', required=True)
            command.add_argument('--provider', required=True)
            command.add_argument('--model', required=True)
            command.add_argument('--max-output-tokens', type=int, default=8192)
            command.add_argument('--max-total-tokens', type=int, default=32768)
            command.add_argument('--timeout-seconds', type=int, default=240)
            if name in ('prepare-generation', 'prepare-generation-approval'):
                command.add_argument('--idempotency-key', required=True)
            if name == 'prepare-generation-approval':
                command.add_argument('--expires-in', type=int, default=900)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            result = check_scaffold(project_root=args.project_root, config_file=args.config)
        else:
            settings = load_settings(project_root=args.project_root, config_file=args.config)
            load_p1_contracts(settings.repository_root)
            if args.command in ('generation-budget-review', 'prepare-generation-approval', 'generation-approval-report',
                                'approve-generation-plan', 'revoke-generation-plan'):
                from ..application.generation_approvals import GenerationApprovalService
                from ..application.service import Service
                service = Service(settings)
                try:
                    approvals = GenerationApprovalService(service)
                    if args.command in ('generation-budget-review', 'prepare-generation-approval'):
                        options = dict(provider=args.provider, model=args.model, max_output_tokens=args.max_output_tokens,
                            max_total_tokens=args.max_total_tokens, timeout_seconds=args.timeout_seconds)
                        if args.command == 'generation-budget-review':
                            result = approvals.preview(args.extraction_id, **options)
                        else:
                            key = approvals.create(args.extraction_id, args.idempotency_key, expires_in=args.expires_in, **options)
                            result = approvals.report(key)
                    elif args.command == 'approve-generation-plan':
                        result = approvals.approve(args.approval_id, expected_request_sha256=args.expected_request_sha256,
                            confirm_single_call=args.confirm_single_call)
                    elif args.command == 'revoke-generation-plan':
                        result = approvals.revoke(args.approval_id, expected_request_sha256=args.expected_request_sha256)
                    else:
                        result = approvals.report(args.approval_id)
                    # Do not print full messages, source, endpoint credentials or raw code.
                    result = {name: result[name] for name in result if name not in ('request', 'files', 'created_at')}
                finally:
                    service.close()
            elif args.command in ('prepare-generation', 'generation-report'):
                from ..application.generations import GenerationService
                from ..application.service import Service
                from ..persistence.runtime_lock import execution_guard
                service = Service(settings)
                try:
                    ledger = GenerationService(service)
                    if args.command == 'prepare-generation':
                        with execution_guard(settings.runtime_dir):
                            key = ledger.create(args.extraction_id, args.idempotency_key, provider=args.provider,
                                model=args.model, max_output_tokens=args.max_output_tokens,
                                max_total_tokens=args.max_total_tokens, timeout_seconds=args.timeout_seconds)
                        from ..graph.generation import summary
                        result = summary(ledger.report(key))
                    else:
                        result = ledger.report(args.generation_id)
                finally:
                    service.close()
            elif args.command == 'generation-preview':
                from ..application.generation_preview import generation_preview
                result = generation_preview(settings, args.extraction_id, provider=args.provider, model=args.model,
                    max_output_tokens=args.max_output_tokens, max_total_tokens=args.max_total_tokens,
                    timeout_seconds=args.timeout_seconds)
            elif args.command == "extract-ssm":
                from ..stages.extract import extract_registered_input
                result = extract_registered_input(settings, input_id=args.input_id, run_id=args.run_id)
            elif args.command in ('extract-ssm-graph', 'resume-ssm-extraction', 'ssm-extraction-report'):
                from ..application.service import Service
                from ..application.extractions import ExtractionService
                from ..graph.extraction import execute_extraction
                service = Service(settings)
                try:
                    if args.command == 'ssm-extraction-report':
                        result = ExtractionService(service).report(args.extraction_id)
                    elif args.command == 'resume-ssm-extraction':
                        result = execute_extraction(service, extraction_id=args.extraction_id)
                    else:
                        result = execute_extraction(service, input_id=args.input_id, run_id=args.run_id)
                finally:
                    service.close()
            elif args.command == "init-db":
                from ..persistence.database import initialize
                initialize(settings)
                result = {"status": "database_initialized", "production_ready": False}
            elif args.command in ("backup", "verify-backup", "restore"):
                from ..persistence.backup import create_backup, verify_backup, restore_backup
                action = {"backup": create_backup, "verify-backup": verify_backup, "restore": restore_backup}[args.command]
                result = action(settings, backup_id=args.backup_id)
            elif args.command == "serve":
                if settings.host not in ('127.0.0.1','::1') or settings.public_origin:
                    raise ValueError('Use a production WSGI server and HTTPS reverse proxy for non-loopback deployments')
                from werkzeug.serving import make_server
                from .api.app import create_app
                app = create_app(settings, write_token=os.environ.get("CARDMIG_SYSTEM_WRITE_TOKEN") or secrets.token_urlsafe(32))
                try:
                    with make_server(settings.host, settings.port, app) as server:
                        server.serve_forever()
                finally:
                    app.extensions["migration_service"].close()
                return 0
            else:
                from ..application.service import Service
                from ..workers.runner import run_worker
                service = Service(settings)
                try:
                    result = run_worker(service, once=args.once)
                finally:
                    service.close()
    except (ConfigurationError, ContractBindingError, ValueError) as error:
        print(json.dumps({"status": "blocked", "error": str(error), "production_ready": False}), file=sys.stderr)
        return 2
    # ASCII JSON remains lossless across Windows console encodings.
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 2 if result.get('status') == 'blocked' else 0
