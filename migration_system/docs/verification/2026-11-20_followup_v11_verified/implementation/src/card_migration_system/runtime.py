"""Runtime integration profile. Secrets are read by the worker, never the API UI."""
from copy import deepcopy
import importlib.util
import os
from pathlib import Path
import shutil
import tomllib

from .application.service import ServiceError
from .adapters.qwen_transport import valid_endpoint


def profile(settings):
    path = settings.project_root / 'configs/system.toml'
    if not path.is_file():
        raise ServiceError('system_profile_missing', 503)
    value = tomllib.loads(path.read_text(encoding='utf-8'))
    if set(value) != {'schema_version', 'model', 'browser', 'tracing', 'learning'} or value['schema_version'] != 1:
        raise ServiceError('invalid_system_profile', 503)
    model, browser, trace, learning = (value[n] for n in ('model', 'browser', 'tracing', 'learning'))
    allowed={
        'model':{'backend','model','endpoint','api_key_env','network_enabled','timeout_seconds','max_output_tokens','max_calls','usage_stop_tokens'},
        'browser':{'executable','enabled','width','height','settle_ms'},
        'tracing':{'enabled','api_key_env','project','endpoint'},
        'learning':{'few_shot_manifest','few_shot_count','base_model_path','adapter_path','embedding_model_path'}}
    for name,keys in allowed.items():
        if type(value[name]) is not dict or set(value[name])!=keys:raise ServiceError('unknown_runtime_fields_secrets_must_use_environment',503)
    for env_name in (model['api_key_env'],trace['api_key_env']):
        import re
        if type(env_name) is not str or not re.fullmatch('[A-Z][A-Z0-9_]{1,79}',env_name):raise ServiceError('invalid_secret_environment_name',503)
    if type(model['model']) is not str or not model['model'].strip() or len(model['model'])>100:raise ServiceError('invalid_model_name',503)
    if model['backend'] not in ('qwen', 'local_lora'):
        raise ServiceError('unsupported_model_backend', 503)
    valid_endpoint(model['endpoint'])
    for key, low, high in (('max_output_tokens', 256, 32768), ('max_calls', 1, 4),
                           ('timeout_seconds', 1, 600), ('usage_stop_tokens', 1, 10000000)):
        if type(model.get(key)) is not int or not low <= model[key] <= high:
            raise ServiceError('invalid_model_budget', 503)
    if type(model.get('network_enabled')) is not bool or type(trace.get('enabled')) is not bool or type(browser.get('enabled')) is not bool:
        raise ServiceError('invalid_runtime_switch', 503)
    if trace['endpoint'] not in ('https://api.smith.langchain.com', 'https://eu.api.smith.langchain.com'):
        raise ServiceError('unsupported_tracing_endpoint', 503)
    for key, low, high in (('width', 320, 1920), ('height', 240, 1600), ('settle_ms', 0, 5000)):
        if type(browser.get(key)) is not int or not low <= browser[key] <= high:
            raise ServiceError('invalid_browser_profile', 503)
    if type(learning.get('few_shot_count')) is not int or not 0 <= learning['few_shot_count'] <= 5:
        raise ServiceError('invalid_few_shot_count', 503)
    return deepcopy(value)


def readiness(settings):
    value = profile(settings)
    model, browser, trace, learning = (value[n] for n in ('model', 'browser', 'tracing', 'learning'))
    pending = []
    if model['backend'] == 'qwen':
        if not model['network_enabled']: pending.append('model_network_disabled')
        if not os.environ.get(model['api_key_env']): pending.append('model_api_key_missing')
    else:
        if not learning['base_model_path'] or not Path(learning['base_model_path']).is_dir(): pending.append('local_base_model_missing')
        if not learning['adapter_path'] or not Path(learning['adapter_path']).is_dir(): pending.append('lora_adapter_missing')
        if importlib.util.find_spec('peft') is None: pending.append('training_dependencies_missing')
    if not shutil.which('node'): pending.append('node_missing')
    if not (settings.project_root / 'browser/node_modules/puppeteer-core').is_dir(): pending.append('browser_dependencies_missing')
    if not browser['enabled']: pending.append('browser_disabled')
    if not browser_executable(browser): pending.append('browser_executable_missing')
    if trace['enabled'] and not os.environ.get(trace['api_key_env']): pending.append('langsmith_key_missing')
    return {'mode': 'migration', 'ready': not pending, 'pending': pending,
            'backend': model['backend'], 'model': model['model'], 'network_enabled': model['network_enabled'],
            'langsmith_enabled': trace['enabled'], 'few_shot_count': learning['few_shot_count'],
            'max_repair_rounds': 3, 'max_calls': model['max_calls'], 'production_ready': False,
            'scope': 'local_single_user_component_migration', 'quality_claim': 'measured_per_run_not_guaranteed'}


def browser_executable(browser):
    explicit = browser.get('executable') or os.environ.get('CARDMIG_BROWSER_EXECUTABLE', '')
    if explicit:
        return str(Path(explicit).resolve()) if Path(explicit).is_file() else None
    for root in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
        for suffix in ('Microsoft/Edge/Application/msedge.exe', 'Google/Chrome/Application/chrome.exe'):
            candidate = Path(os.environ.get(root, '__absent__')) / suffix
            if candidate.is_file(): return str(candidate)
    for binary in ('chromium', 'chromium-browser', 'google-chrome'):
        if shutil.which(binary): return shutil.which(binary)
    return None
