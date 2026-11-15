"""Prepare isolated full-template pages; leave manual verification to the user."""
import argparse
import base64
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot

PRIOR = ROOT / 'data/experiments/analysis/formal_30_v4_async_watcher_browser_v1_20261113'
V7 = ROOT / 'data/experiments/analysis/formal_30_v4_async_watcher_scope_v7_20261113'
OUTPUT = ROOT / 'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113'
NOTEBOOK = ROOT / 'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
PREFIX_SHA = '1b0104325d129ae243633bbfd129488f6a223f94e61f696cb6b65f4e3d6461fd'
METADATA_SHA = 'da8e8b42bb4344c317ccdf5038310d76529bda61666c53ff805bcc19dbede418'
NAMES = ['tests/manual/taskmanager-v7-vue.html', 'tests/manual/taskmanager-v7-san.html',
         'tests/manual/taskmanager-v7-manual.js', 'tests/manual/taskmanager-v7-README.md',
         'migration_pipeline/prepare_task_manager_v7_manual_acceptance.py']
REGISTRY = 'https://registry.npmjs.org/vue/2.7.16'
TARBALL = 'https://registry.npmjs.org/vue/-/vue-2.7.16.tgz'


def stable(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def inventory():
    old = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
    previous = json.loads((PRIOR / 'live_inventory.json').read_text(encoding='utf-8'))
    for name, expected in {**previous, **old['source_inputs'], **old['application_files_sha256'],
                           **old['selected_application_files_sha256']}.items():
        if digest(ROOT / name) != expected:
            raise RuntimeError('Previous/source/application file changed: ' + name)
    nb = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    if stable(nb['cells'][:74]) != PREFIX_SHA or stable(nb['metadata']) != METADATA_SHA:
        raise RuntimeError('Old Notebook cells/metadata changed')
    return {**previous, **{name: digest(ROOT / name) for name in NAMES}}


def fetch(url, limit):
    request = urllib.request.Request(url, headers={'User-Agent': 'CardMigrator-manual-runtime-preparer/1', 'Accept': 'application/json' if url == REGISTRY else 'application/octet-stream'})
    with urllib.request.urlopen(request, timeout=45) as response:
        if response.url != url:
            raise RuntimeError('Unexpected dependency redirect: ' + response.url)
        data = response.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError('Dependency response too large')
    return data


def official_vue():
    print('Fetching official vue@2.7.16 release metadata...', flush=True)
    metadata_bytes = fetch(REGISTRY, 2_000_000)
    metadata = json.loads(metadata_bytes)
    if (metadata['name'], metadata['version'], metadata['dist']['tarball']) != ('vue', '2.7.16', TARBALL):
        raise RuntimeError('Unexpected official package identity')
    print('Fetching exact tarball and verifying npm SHA-512 integrity...', flush=True)
    archive = fetch(TARBALL, 20_000_000)
    actual = 'sha512-' + base64.b64encode(hashlib.sha512(archive).digest()).decode()
    expected = next(v for v in metadata['dist']['integrity'].split() if v.startswith('sha512-'))
    if not hmac.compare_digest(actual, expected):
        raise RuntimeError('npm tarball integrity mismatch')
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as package:
        for name, output in [('package/dist/vue.js', 'vendor/vue-2.7.16.js'),
                             ('package/LICENSE', 'vendor/LICENSE.vue'),
                             ('package/package.json', 'vendor/package.vue.json')]:
            member = package.getmember(name)
            if not member.isfile() or member.size > 2_000_000:
                raise RuntimeError('Unexpected archive member: ' + name)
            files[output] = package.extractfile(member).read()
    package_info = json.loads(files['vendor/package.vue.json'])
    if (package_info['name'], package_info['version']) != ('vue', '2.7.16'):
        raise RuntimeError('Archive package identity mismatch')
    files['vendor/npm_vue_2_7_16.json'] = metadata_bytes
    return files, {'registry': REGISTRY, 'tarball': TARBALL, 'npm_integrity': expected,
                   'tarball_sha256': hashlib.sha256(archive).hexdigest(),
                   'tarball_integrity_verified': True, 'tarball_retained': False}


CHECKLIST = '''# TaskManager v7 完整界面人工验收（待用户确认）

本轮只准备页面，没有运行浏览器或声明交互通过。不要把过去最小render的110阶段匹配当作本轮人工验收。

## 开始

项目根目录运行 `python -m http.server 8080 --bind 127.0.0.1`。
同时打开 `/tests/manual/taskmanager-v7-vue.html` 和 `/tests/manual/taskmanager-v7-san.html`。
先分别点击“清空本页隔离数据并重新加载”，确保初始状态可比。两页分别保存数据，不共享原应用的 `task_manager_data`。

## 按顺序对照

1. 初始标题、四张统计卡片、趋势百分值、任务优先级/日期/标签、初始列表和空列表样式。
2. 全部/待完成/已完成筛选、数量同步、关键词搜索、完成/取消完成、删除任务后统计同步。
3. 新建任务：描述框没有源码；填写标题/描述/日期/优先级/负责人，选择标签时颜色变化；保存成功，不刷新页面。
4. 编辑任务：原值完整回填、修改可保存；×和取消均关闭；点击弹窗内容不能意外关闭，点击遮罩仅按源Vue行为关闭。
5. 设置：下拉选中后仍显示当前值；勾选框可反复取消/选中；点击内部不关闭；×关闭；变化即时作用。通知文字按源Vue对照，源本来带英文key不自动判为迁移缺陷。
6. 拖拽两条未过滤的任务并比较顺序、拖到末尾；刷新本页后顺序保留。若Vue本身也异常，分别记录，不自动“迁就”一方。
7. 任务详情和评论、主题/紧凑模式、通知关闭、导出按钮（导出会在本机生成文件，按需检查）。
8. 关闭自动保存/开启自动保存及同步间隔的真实行为；观察控制台，不以随机/相对时间的细微数值差异直接判缺陷。

## 可选：一次保存故障

正常项完成后，可分别启用顶部“一次保存故意失败”，然后修改设置或任务。日志应记录 `ManualAcceptanceStorageWriteFailure`，后续保存应恢复；记录是否出现未处理Promise拒绝、设置/后续任务更新是否继续。
这是故障注入，不是真实磁盘损坏。两个页面使用显式全局只报告错误策略，San只为父watcher配置v7入口；不能推广为所有子组件/SSR错误已处理。

## 反馈

请说“TaskManager正常交互通过”及“是否做了可选异常项”。若不通过，发送具体操作、Vue/San差异、首条红色报错及截图（如方便）。等待明确确认后再记录人工结果，不修改原批24/30或宣称生产放行。
'''


def prepare():
    if OUTPUT.exists():
        raise FileExistsError('Never overwrite an existing prepared manual bundle')
    hashes = inventory()
    if verify_snapshot(PRIOR.resolve()) != 8 or verify_snapshot(V7.resolve()) != 10:
        raise RuntimeError('Previous evidence scope changed')
    old = json.loads((PRIOR / 'audit.json').read_text(encoding='utf-8'))
    vue = ROOT / next(p for p in old['source_inputs'] if p.endswith('.vue'))
    san = ROOT / old['candidate_reference']
    for source in [vue, san]:
        text = source.read_text(encoding='utf-8')
        if "storageKey: 'task_manager_data'" not in text:
            raise RuntimeError('Unexpected component storage key')
    files, provenance = official_vue()
    OUTPUT.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        target = OUTPUT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
    asset = lambda path: {'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(path)}
    san_runtime = ROOT / next(p for p in old['source_inputs'] if p.endswith('san.dev.js'))
    manifest = {'schema_version': 1, 'component': 'TaskManager', 'manual_status': 'awaiting_user',
        'props': {}, 'application_error_policy': 'explicit-global-reporting-only-no-source-ancestor-captures',
        'storage_namespace': 'cardmig:taskmanager-async-scope-v7-manual:<framework>:', 'storage_key': 'task_manager_data',
        'frameworks': {'vue': {'version': '2.7.16', 'runtime': asset(OUTPUT / 'vendor/vue-2.7.16.js'), 'component': asset(vue)},
                       'san': {'version': '3.15.6', 'runtime': asset(san_runtime), 'component': asset(san)}}}
    print('Checking script syntax and fixed runtime API only (no browser/server)...', flush=True)
    for script in [ROOT / NAMES[2], OUTPUT / 'vendor/vue-2.7.16.js']:
        subprocess.run(['node', '--check', str(script)], cwd=ROOT, check=True, capture_output=True)
    check = r"const fs=require('fs');const m={exports:{}};new Function('module','exports',fs.readFileSync(process.argv[1],'utf8'))(m,m.exports);process.stdout.write(JSON.stringify({version:m.exports.version,compile:typeof m.exports.compile}));"
    api = json.loads(subprocess.run(['node', '-e', check, str(OUTPUT / 'vendor/vue-2.7.16.js')], cwd=ROOT,
        check=True, capture_output=True, text=True, encoding='utf-8').stdout)
    if api != {'version': '2.7.16', 'compile': 'function'}:
        raise RuntimeError('Not the expected full Vue compiler build')
    status = {'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'manual_status': 'awaiting_user', 'component': 'TaskManager', 'preparation_only': True,
        'official_vue_provenance': provenance, 'vue_full_build_api_check': api,
        'old_inventory_unchanged': 433, 'inventory_count': len(hashes), 'production_runtime_inventory_unchanged': 387,
        'original_pages_unchanged': old['application_files_sha256'],
        'sources_and_candidate_unchanged': True, 'full_parent_and_inline_templates_preserved': True,
        'browser_or_server_started_this_step': False, 'interaction_checked_this_step': False,
        'production_rules_or_prompt_modified': False, 'production_integration_enabled': False,
        'model_requests': 0, 'original_aggregate': old['original_aggregate'], 'original_score_modified': False,
        'prior_notebook_cells': 74, 'prior_notebook_cells_sha256': PREFIX_SHA,
        'prior_notebook_metadata_sha256': METADATA_SHA,
        'boundary': 'Readiness/static checks only. Full UI may expose unresolved defects; wait for user confirmation.'}
    if inventory() != hashes:
        raise RuntimeError('Existing files changed during preparation')
    for name, value in [('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'),
                        ('status.json', json.dumps(status, ensure_ascii=False, indent=2) + '\n'),
                        ('live_inventory.json', json.dumps(hashes, ensure_ascii=False, indent=2) + '\n'),
                        ('MANUAL_CHECKLIST.md', CHECKLIST)]:
        with (OUTPUT / name).open('x', encoding='utf-8') as stream:
            stream.write(value)
    for name in NAMES:
        target = OUTPUT / 'code' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    items = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
    with (OUTPUT / 'SHA256SUMS.txt').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in items) + '\n')
    return verify_snapshot(OUTPUT.resolve())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.prepare == args.check:
        parser.error('Choose exactly one of --prepare or --check')
    count = prepare() if args.prepare else verify_snapshot(OUTPUT.resolve())
    if args.check:
        if inventory() != json.loads((OUTPUT / 'live_inventory.json').read_text(encoding='utf-8')):
            raise RuntimeError('Prepared live files changed')
        manifest = json.loads((OUTPUT / 'manifest.json').read_text(encoding='utf-8'))
        for config in manifest['frameworks'].values():
            for key in ['runtime', 'component']:
                if digest(ROOT / config[key]['path']) != config[key]['sha256']:
                    raise RuntimeError('Asset drift: ' + config[key]['path'])
    print(json.dumps({'prepared_payloads': count, 'manual_status': 'awaiting_user', 'browser_started': False,
        'model_requests': 0, 'production_integration_enabled': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
