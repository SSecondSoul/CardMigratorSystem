"""Freeze, queue, export and summarize real-system development experiments.

The existing cloud Worker owns model calls and migration routing. This runner
never imports a fake model, alters quotas, replays unknown calls, or repairs code.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / 'migration_system'
RUNS = Path(__file__).resolve().parent
sys.path.insert(0, str(SYSTEM / 'src'))

TERMINAL = {'finished', 'failed', 'blocked', 'review_required', 'cancelled'}
INFRASTRUCTURE_STOPS = {
    'model_api_key_missing', 'model_network_disabled', 'model_response_unknown_no_automatic_retry',
    'model_usage_unknown_requires_review', 'migration_binding_drift', 'migration_runtime_profile_drift',
    'provider_http_error', 'model_output_incomplete', 'invalid_model_response',
}
DEFAULT_BATCH = 'real_system_experiment70_v1_20261118'


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def inside(path, root):
    path = path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('path_escapes_expected_root')
    return path


def write_once(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(content)
    except FileExistsError:
        if path.read_bytes() != content:
            raise ValueError('immutable_file_differs:' + path.name)


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def log(event, **values):
    print(json.dumps({'at': now(), 'event': event, **values}, ensure_ascii=True), flush=True)


def batch_dir(name):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,55}', name):
        raise ValueError('invalid_batch_id')
    return inside(RUNS / name, RUNS)


def load_samples(dataset):
    raw = read_json(dataset / 'experiment/manifest.json')
    samples = raw['samples']
    if raw['subset'] != 'experiment' or raw['count'] != 70 or len(samples) != 70:
        raise ValueError('expected_experiment_70_only')
    if len({s['id'] for s in samples}) != 70:
        raise ValueError('duplicate_sample_id')
    if Counter(s['complexity'] for s in samples) != {'simple': 24, 'medium': 23, 'complex': 23}:
        raise ValueError('complexity_counts_differ')
    for sample in samples:
        if sample['subset'] != 'experiment':
            raise ValueError('non_experiment_sample')
        source = inside(dataset / sample['vue_file'], dataset / 'experiment')
        if file_hash(source) != sample['vue_sha256']:
            raise ValueError('source_hash_mismatch:' + sample['id'])
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,100}\.vue', source.name):
            raise ValueError('invalid_vue_filename')
    return samples


def imports():
    from card_migration_system.config import load_settings
    from card_migration_system.application.service import Service
    from card_migration_system.application.migrations import MigrationService, binding
    from card_migration_system.runtime import profile
    from card_migration_system.reporting.identity import digest
    return load_settings, Service, MigrationService, binding, profile, digest


def select_samples(samples, sample_ids=None):
    if sample_ids is None:
        return samples
    wanted = set(sample_ids)
    if not wanted or len(wanted) != len(sample_ids) or wanted - {s['id'] for s in samples}:
        raise ValueError('invalid_or_duplicate_experiment_sample_selection')
    # Freeze dataset order, not the order supplied on the command line.
    return [s for s in samples if s['id'] in wanted]


def prepare(folder, *, sample_ids=None):
    if folder.exists():
        raise ValueError('batch_already_exists_use_resume_not_prepare')
    load_settings, _, _, binding, profile, digest = imports()
    settings = load_settings(config_file='configs/mysql_multi_user.local.toml')
    runtime = profile(settings)
    pool = load_samples(ROOT / 'experiment_dataset')
    samples = select_samples(pool, sample_ids)
    excluded = sorted({s['component_name'] for s in pool} | {s['id'] for s in pool})
    frozen_binding = binding(settings)
    protocol = {
        'schema_version': 1, 'batch_id': folder.name, 'created_at': now(), 'subset': 'experiment',
        'configured': len(samples), 'complexity_counts': dict(Counter(s['complexity'] for s in samples)),
        'sample_selection': 'all_experiment_70' if sample_ids is None else 'explicit_development_probe',
        'excluded_example_groups': excluded,
        'system_config': 'configs/mysql_multi_user.local.toml', 'database_backend': settings.database_backend,
        'strategy': 'ssm', 'max_repair_rounds': 3, 'props': {}, 'actions': [],
        'thresholds': {'structure': .95, 'ui': .95, 'pixel_difference': .05},
        'interaction_status_without_scenarios': 'not_run_not_a_pass',
        'runtime_profile': runtime, 'binding': frozen_binding, 'binding_digest': digest(frozen_binding),
        'max_calls_per_sample': min(4, runtime['model']['max_calls']),
        'max_calls_whole_batch': len(samples) * min(4, runtime['model']['max_calls']),
        'billing_cap': 'not_guaranteed_existing_per_job_soft_usage_stop_unchanged',
        'execution': 'sequential_submission_to_existing_real_cloud_worker',
        'owner_mode': 'trusted_local_cli_experiment_unowned_as_existing_batch_cli_not_user_quota_bypass',
        'old_jobs_reused': False, 'reference_san_used_as_input': False,
        'validation_and_test_executed': False,
        'input_manifest_sha256': file_hash(ROOT / 'experiment_dataset/experiment/manifest.json'),
        'dataset_evidence_class': read_json(ROOT / 'experiment_dataset/manifest.json').get('evidence_class'),
        'source_group_policy': 'component_name; all 70 names and IDs excluded from few-shot selection',
        'model_temperature': 0, 'manual_status': 'not_performed',
        'repair_policy': 'freeze_full_baseline_then_group_failures_no_mid_batch_prompt_rule_changes',
    }
    folder.mkdir(parents=True)
    planned = []
    snapshot = {}
    for index, sample in enumerate(samples):
        safe = re.sub(r'[^A-Za-z0-9_-]', '_', sample['id'])
        slug = f'{index+1:03d}_{safe}'
        source = ROOT / 'experiment_dataset' / sample['vue_file']
        relative = 'inputs/' + slug + '/' + source.name
        write_once(folder / relative, source.read_bytes())
        planned.append({**sample, 'slug': slug, 'frozen_vue': relative,
                        'group': sample['component_name'],
                        'idempotency_key': folder.name + '_' + sha256(sample['id'].encode()).hexdigest()[:16]})
    # Freeze the actual internal implementation, prompts, locks and few-shot manifest.
    selected = []
    for directory in ('src/card_migration_system', 'browser', 'engine'):
        selected.extend(p for p in (SYSTEM / directory).rglob('*')
                        if p.is_file() and not {'node_modules', '__pycache__', '.git'} & set(p.parts)
                        and p.suffix in ('.py', '.cjs', '.mjs', '.js', '.json', '.toml', '.lock'))
    selected += [SYSTEM / name for name in ('configs/system.toml', 'requirements.lock', 'requirements-mysql.lock', 'pyproject.toml')]
    few_shot = Path(runtime['learning']['few_shot_manifest'])
    if not few_shot.is_absolute():
        few_shot = SYSTEM / few_shot
    selected.append(inside(few_shot, SYSTEM))
    for path in sorted(set(selected)):
        relative = 'implementation/' + path.relative_to(SYSTEM).as_posix()
        write_once(folder / relative, path.read_bytes())
        snapshot[relative] = file_hash(path)
    write_once(folder / 'dataset_manifest.json', (ROOT / 'experiment_dataset/experiment/manifest.json').read_bytes())
    write_once(folder / 'protocol.json', encode(protocol))
    write_once(folder / 'samples.json', encode(planned))
    write_once(folder / 'implementation_sha256.json', encode(snapshot))
    atomic(folder / 'checkpoint.json', encode({'batch_id': folder.name, 'status': 'prepared', 'jobs': {}, 'results': {}}))
    summary(folder)
    log('prepared', batch_id=folder.name, configured=len(samples), implementation_files=len(snapshot), model_calls_triggered=0)


def category(code):
    if any(k in code for k in ('source_baseline', 'source_browser', 'unsupported_source', 'external_source')):
        return '源基准或支持范围'
    if any(k in code for k in ('syntax', 'parse', 'render_failed', 'render_error', 'compile', 'browser_error')):
        return '语法或编译运行'
    if any(k in code for k in ('prop', 'method', 'reactive', 'mutation', 'lifecycle', 'binding', 'event', 'computed')):
        return '静态语义或响应式'
    if any(k in code for k in ('template', 'dom', 'structure', 'control')):
        return '结构或控件状态'
    if any(k in code for k in ('visual', 'style', 'pixel', 'ssim')):
        return '视觉或样式'
    if any(k in code for k in ('model', 'provider', 'usage', 'key_missing')):
        return '模型或调用预算'
    return '其他待诊断'


def summary(folder):
    samples = read_json(folder / 'samples.json')
    checkpoint = read_json(folder / 'checkpoint.json')
    rows = []
    groups = {}
    for sample in samples:
        row = {'sample_id': sample['id'], 'component': sample['component_name'], 'complexity': sample['complexity'],
               'migration_id': checkpoint['jobs'].get(sample['id'], {}).get('migration_id', ''),
               'status': checkpoint['jobs'].get(sample['id'], {}).get('status', 'pending'), 'stop_reason': '', 'passed': False, 'model_calls': 0, 'total_tokens': 0,
               'repair_rounds': 0, 'error_codes': [], **checkpoint['results'].get(sample['id'], {})}
        rows.append(row)
        if row['status'] not in TERMINAL or row['passed']:
            continue
        for code in row['error_codes'] or [row['stop_reason'] or 'no_diagnostic_recorded']:
            group = groups.setdefault(code, {'code': code, 'category': category(code), 'samples': []})
            group['samples'].append({'sample_id': sample['id'], 'component': sample['component_name'],
                                     'report': 'samples/' + sample['slug'] + '/report.json'})
    completed = [r for r in rows if r['status'] in TERMINAL]
    passed = sum(r['passed'] for r in completed)
    result = {'batch_id': folder.name, 'updated_at': now(), 'run_status': checkpoint['status'],
              'configured': len(rows), 'completed': len(completed), 'passed': passed,
              'not_passed': len(completed) - passed, 'pending': len(rows) - len(completed),
              'pass_rate_all_configured': passed / len(rows),
              'pass_rate_completed': passed / len(completed) if completed else None,
              'model_calls': sum(r['model_calls'] for r in completed), 'known_total_tokens': sum(r['total_tokens'] for r in completed),
              'by_complexity': {}, 'pause_reason': checkpoint.get('pause_reason'),
              'manual_checks': 'not_run', 'interaction': 'not_run_no_actions_configured'}
    result['active_sample'] = checkpoint.get('active_sample')
    result['active_migration_id'] = checkpoint.get('active_migration_id')
    for complexity in ('simple', 'medium', 'complex'):
        items = [r for r in rows if r['complexity'] == complexity]
        done = [r for r in items if r['status'] in TERMINAL]
        result['by_complexity'][complexity] = {'configured': len(items), 'completed': len(done),
                                             'passed': sum(r['passed'] for r in done)}
    atomic(folder / 'summary.json', encode(result))
    atomic(folder / 'failure_groups.json', encode(sorted(groups.values(), key=lambda g: (-len(g['samples']), g['code']))))
    stream = io.StringIO(newline='')
    fields = ['sample_id', 'component', 'complexity', 'migration_id', 'status', 'stop_reason', 'passed',
              'initial_passed', 'repair_rounds', 'model_calls', 'total_tokens', 'elapsed_seconds',
              'static', 'compile_runtime', 'structure', 'visual', 'interaction', 'source_baseline',
              'structure_similarity', 'dom_similarity', 'ui_restoration', 'ssim', 'pixel_difference', 'error_codes']
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore');writer.writeheader()
    writer.writerows({**row, 'error_codes': ';'.join(row['error_codes'])} for row in rows)
    atomic(folder / 'sample_results.csv', ('\ufeff' + stream.getvalue()).encode('utf-8'))
    text = [f'# {folder.name} 实验结果', '', f'状态：{checkpoint["status"]}。已完成 {len(completed)}/{len(rows)}，通过 {passed}，未通过 {len(completed)-passed}，待运行 {len(rows)-len(completed)}。',
            '', '仅统计本批新任务，不复用网页历史结果；未运行交互场景和人工验收。原始报告、候选、截图和收据保持不变。', '',
            '## 失败归类与下一轮通用修复', '', '以下按每种错误涉及的样本数统计，同一样本可以涉及多类错误，不等同于独立缺陷数。', '']
    for group in sorted(groups.values(), key=lambda g: -len(g['samples'])):
        text.append(f'- {group["category"]} / `{group["code"]}`：{len(group["samples"])} 个样本（' + '、'.join(s['component'] for s in group['samples']) + '）。')
    text += ['', '整批完成前不修改迁移实现。完成后逐组检查源 Vue、初始 San、各修复候选和评估证据，区分迁移缺陷、评估误报和环境问题；先用冻结失败产物验证通用修复，再建立 v2 批次回归，不覆盖本批结果。', '']
    atomic(folder / 'FAILURE_REPORT.md', '\n'.join(text).encode('utf-8'))
    return result


def assert_frozen(folder, settings):
    _, _, _, binding, profile, digest = imports()
    protocol = read_json(folder / 'protocol.json')
    if binding(settings) != protocol['binding'] or profile(settings) != protocol['runtime_profile']:
        raise ValueError('system_or_profile_changed_stop_batch_create_new_version')
    for sample in read_json(folder / 'samples.json'):
        if file_hash(inside(folder / sample['frozen_vue'], folder / 'inputs')) != sample['vue_sha256']:
            raise ValueError('frozen_input_changed')
    return digest(protocol['binding'])


def worker_available(base, expected):
    from sqlalchemy import select
    from card_migration_system.persistence.database import transaction
    from card_migration_system.persistence.worker_health import WorkerHealth
    with transaction(base.engine) as session:
        workers = session.scalars(select(WorkerHealth).where(WorkerHealth.state == 'migration_worker',
                                                           WorkerHealth.last_seen > time.time() - 35)).all()
    return any(worker.binding_sha256 == expected for worker in workers)


def export_sample(folder, sample, service, key):
    report = service.report(key)
    job = service.job(key)
    if report['status'] not in TERMINAL:
        raise ValueError('cannot_export_nonterminal_as_final')
    output = folder / 'samples' / sample['slug']
    for file in report['files']:
        relative = file['relative_path']
        prefix = 'migrations/' + key + '/'
        if not relative.startswith(prefix):
            raise ValueError('cross_job_file_reference')
        destination = inside(output / 'artifacts' / relative[len(prefix):], output / 'artifacts')
        write_once(destination, service.read_file(key, relative))
    write_once(output / 'report.json', encode(report))
    index = {p.relative_to(output).as_posix(): file_hash(p) for p in output.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt'}
    write_once(output / 'SHA256SUMS.txt', ''.join(h + '  ' + p + '\n' for p, h in sorted(index.items())).encode())
    assessment = report.get('assessment') or {}
    initial_path = output / 'artifacts/evaluations/0.json'
    initial = read_json(initial_path) if initial_path.exists() else {}
    codes = sorted({item.get('code', 'diagnostic_without_code') for item in assessment.get('diagnostics', [])})
    codes += [item.get('code', 'source_diagnostic') for item in report['state'].get('failure_diagnostics', [])]
    return {'status': report['status'], 'stop_reason': report['stop_reason'],
            'passed': report['status'] == 'finished' and assessment.get('passed') is True,
            'initial_passed': initial.get('passed'), 'repair_rounds': report['state'].get('round', 0),
            'model_calls': report['model_calls_started'], 'total_tokens': report['usage']['known_total_tokens'],
            'unknown_calls': report['unknown_calls'], 'usage_complete': report['usage']['complete'],
            'elapsed_seconds': round(job.updated_at - job.created_at, 3),
            **assessment.get('dimensions', {}),
            'structure_similarity': assessment.get('structure_ted', {}).get('similarity'),
            'dom_similarity': assessment.get('dom_ted', {}).get('similarity'),
            'ui_restoration': assessment.get('ui_restoration'), 'ssim': assessment.get('ssim'),
            'pixel_difference': assessment.get('different_pixel_ratio'), 'error_codes': sorted(set(codes))}


def run(folder, *, poll=10):
    from sqlalchemy import select
    from card_migration_system.persistence.database import transaction
    from card_migration_system.persistence.migrations import MigrationJob
    from card_migration_system.persistence.runtime_lock import execution_guard, RuntimeBusyError
    load_settings, Service, MigrationService, _, _, _ = imports()
    protocol = read_json(folder / 'protocol.json')
    settings = load_settings(config_file=protocol['system_config'])
    expected = assert_frozen(folder, settings)
    base = Service(settings);service = MigrationService(base)
    try:
        with execution_guard(folder):
            checkpoint = read_json(folder / 'checkpoint.json')
            checkpoint.update(status='running', pause_reason=None)
            atomic(folder / 'checkpoint.json', encode(checkpoint))
            samples = read_json(folder / 'samples.json')
            excluded = protocol.get('excluded_example_groups', sorted({s['group'] for s in samples} | {s['id'] for s in samples}))
            try:
                for sample in samples:
                    if sample['id'] in checkpoint['results']:
                        continue
                    if (folder / 'STOP').exists():
                        raise ValueError('stop_marker_requested_no_new_jobs')
                    assert_frozen(folder, settings)
                    if not worker_available(base, expected):
                        raise ValueError('matching_real_worker_not_online_no_new_job_submitted')
                    record = checkpoint['jobs'].setdefault(sample['id'], {})
                    with transaction(base.engine) as session:
                        existing = session.scalar(select(MigrationJob).where(MigrationJob.idempotency_key == sample['idempotency_key']))
                    if existing:
                        key = existing.id
                        if existing.request['source_sha256'] != sample['vue_sha256'] or existing.binding != protocol['binding']:
                            raise ValueError('existing_batch_job_identity_differs')
                    else:
                        if not record.get('input_id'):
                            source = (folder / sample['frozen_vue']).read_bytes().decode('utf-8')
                            record['input_id'] = base.create_input({'filename': Path(sample['vue_file']).name, 'source': source})['input_id']
                            atomic(folder / 'checkpoint.json', encode(checkpoint))
                        payload = {'input_id': record['input_id'], 'name': folder.name + ' / ' + sample['component_name'],
                                   'trusted_source': True, 'confirm_model_calls': True, 'strategy': 'ssm',
                                   'source_group': sample['group'], 'excluded_example_groups': excluded,
                                   'max_repair_rounds': 3, 'props': {}, 'actions': []}
                        key = service.create(payload, sample['idempotency_key'])['migration_id']
                    record.update(migration_id=key)
                    checkpoint.update(active_sample=sample['id'], active_migration_id=key)
                    atomic(folder / 'checkpoint.json', encode(checkpoint));summary(folder)
                    log('sample_queued_or_resumed', sample=sample['id'], migration_id=key)
                    started = time.monotonic();last_state = None;worker_absent = None
                    while True:
                        job = service.job(key)
                        state = (job.status, job.stage)
                        if state != last_state:
                            record.update(status=job.status, stage=job.stage)
                            atomic(folder / 'checkpoint.json', encode(checkpoint));summary(folder)
                            log('sample_stage', sample=sample['id'], status=job.status, stage=job.stage)
                            last_state = state
                        if job.status in TERMINAL:
                            # A terminal row can precede the graph's final file
                            # registration. Export only after the Worker releases
                            # its execution guard, preserving the complete bundle.
                            try:
                                with execution_guard(settings.runtime_dir):
                                    assert_frozen(folder, settings)
                                    result = export_sample(folder, sample, service, key)
                            except RuntimeBusyError:
                                pass
                            else:
                                break
                        if time.monotonic() - started > 3600:
                            raise ValueError('sample_wait_timeout_original_job_kept_no_resubmit')
                        if worker_available(base, expected):
                            worker_absent = None
                        elif worker_absent is None:
                            worker_absent = time.monotonic()
                        elif time.monotonic() - worker_absent > 120:
                            raise ValueError('worker_offline_original_job_kept_no_resubmit')
                        time.sleep(poll)
                    checkpoint['results'][sample['id']] = result
                    checkpoint.update(active_sample=None, active_migration_id=None)
                    atomic(folder / 'checkpoint.json', encode(checkpoint))
                    totals = summary(folder)
                    log('sample_collected', sample=sample['id'], status=result['status'], stop_reason=result['stop_reason'],
                        completed=totals['completed'], passed=totals['passed'], tokens=result['total_tokens'])
                    if result['unknown_calls'] or not result['usage_complete'] or result['stop_reason'] in INFRASTRUCTURE_STOPS:
                        raise ValueError('review_required_before_next_model_call:' + result['stop_reason'])
                checkpoint['status'] = 'completed'
            except Exception as error:
                checkpoint.update(status='paused', pause_reason=getattr(error, 'code', str(error) if isinstance(error, ValueError) else type(error).__name__))
                log('batch_paused', reason=checkpoint['pause_reason'])
            finally:
                atomic(folder / 'checkpoint.json', encode(checkpoint));summary(folder)
            return 0 if checkpoint['status'] == 'completed' else 2
    finally:
        base.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'status'])
    parser.add_argument('--batch', default=DEFAULT_BATCH)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--samples', nargs='+', help='prepare only: exact experiment IDs for a separate development probe')
    args = parser.parse_args();folder = batch_dir(args.batch)
    if args.samples and args.command != 'prepare':
        parser.error('--samples is only allowed when preparing a new batch')
    if args.command == 'prepare':
        prepare(folder, sample_ids=args.samples);return 0
    if args.command == 'status':
        print(json.dumps(read_json(folder / 'summary.json'), ensure_ascii=True, indent=2));return 0
    if not args.execute:
        log('execution_not_enabled', note='pass --execute to queue real model jobs');return 0
    return run(folder)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        log('runner_stopped', error=getattr(error, 'code', str(error) if isinstance(error, ValueError) else type(error).__name__))
        raise SystemExit(2)
