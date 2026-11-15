"""Prepare a reusable v7 manual case using already-frozen local assets only.

No server/browser/model/test execution; never overwrite an existing bundle.
"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT / 'data/experiments/manual_followups/task_manager_async_scope_v7_prepared_20261113'
CLOSURE = ROOT / 'data/experiments/analysis/formal_30_v4_class_binding_closure_v1_20261113'
OUTPUT = ROOT / 'data/experiments/manual_followups/task_manager_v7_class_binding_prepared_20261114'
CASE_ID = 'task-manager-v7-class-v1'
NEW_FILES = ['tests/manual/v7-acceptance.html', 'tests/manual/v7-acceptance.js',
             'tests/manual/v7-acceptance-config.json', 'tests/manual/v7-acceptance-README.md',
             'migration_pipeline/prepare_v7_acceptance.py']
OLD_FILES = ['tests/manual/vue-test-runner.html', 'tests/manual/san-test-runner.html',
             'tests/manual/taskmanager-v7-vue.html', 'tests/manual/taskmanager-v7-san.html',
             'tests/manual/taskmanager-v7-manual.js', 'tests/manual/taskmanager-v7-README.md']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_bundle(folder):
    for line in (folder / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        path = (folder / name).resolve()
        if not path.is_relative_to(folder.resolve()) or sha(path) != expected:
            raise RuntimeError('Frozen evidence mismatch: ' + name)


def write_json(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2); stream.write('\n')


CHECKLIST = '''# TaskManager · v7 + class 绑定修复 v1：人工验收清单

本轮只建立验收入口，没有启动页面或执行交互测试，状态为 awaiting_user。
San 使用 class 闭环规则派生的候选，不再加载默认始终暗黑的旧候选。
保留完整父模板、内联子组件、原 CSS 和业务计时器，不用最小 render 替代界面。

## 打开

项目根目录启动 `python -m http.server 8080 --bind 127.0.0.1`。
打开 `/tests/manual/v7-acceptance.html?case=task-manager-v7-class-v1&framework=san`，
点击“打开 Vue 对照页”，或使用顶部框架选择器。
先分别点击“清空本页隔离数据并重新加载”；该命名空间与原应用、旧 v7 页面及另一框架互不覆盖。

## 按顺序核对（先不要启用保存故障）

1. 清空隔离数据后的默认主题与 Vue 一致，不应仅因 isDarkMode=false 却固定出现 dark-theme。
2. 连续切换明暗主题、紧凑模式；四种组合都检查，再切回原状，观察样式是否及时跟随。
3. 标题、统计卡片、变化百分值、优先级、日期、标签和列表初始内容；筛选、搜索、完成/取消、删除后统计同步。
4. 设置弹窗内部点击不意外关闭；下拉值可见，勾选框可反复选中/取消；×和遮罩行为按源 Vue 对照。
5. 新建/编辑：描述框没有源码，原值完整回填，标签颜色随选择变化；提交不刷新，×和取消能关闭。
6. 未过滤列表中拖拽排序、拖到末尾；刷新当前框架页面后数据/顺序保留；对比 Vue，不把源端异常自动算成迁移正确。
7. 详情、评论、通知关闭和导出（下载操作按需手工检查）。记录控制台第一条红色报错。

## 可选异常项

正常交互检查后，按需分别启用“一次保存故意失败”，再修改任务/设置。
记录 ManualAcceptanceStorageWriteFailure、后续更新和保存能否继续、有无未处理拒绝。
错误会记录且继续输出到 Console，不吞掉或改写为“成功”。

## 边界与反馈

v7-parent-watch-report-only 是显式实验配置：无源祖先捕获钩子、全局只报告错误；不是生产接入或任意组件都等价的证明。
只代理脚本词法作用域的 localStorage；不是拦截 window.localStorage、IndexedDB 或任意全局 API 的通用沙箱。
既有 watcher 动态键、异步调度及异常策略校验仍保持阻断，不因本页能加载而解除。

请反馈“TaskManager正常交互通过／不通过”并说明是否执行可选异常项。
未得到明确确认，不记录人工通过，也不修改原批 24/30 成绩。
'''


def prepare():
    if OUTPUT.exists():
        raise FileExistsError('Never overwrite a prepared acceptance bundle')
    original = {name: sha(ROOT / name) for name in OLD_FILES}
    verify_bundle(PRIOR); verify_bundle(CLOSURE)
    old_manifest = json.loads((PRIOR / 'manifest.json').read_text(encoding='utf-8'))
    closure = json.loads((CLOSURE / 'audit.json').read_text(encoding='utf-8'))
    for config in old_manifest['frameworks'].values():
        for kind in ['runtime', 'component']:
            if sha(ROOT / config[kind]['path']) != config[kind]['sha256']:
                raise RuntimeError('Prior asset drift: ' + config[kind]['path'])
    candidate = CLOSURE / 'TaskManager_class_binding_offline.san'
    # Read-only identity checks, not a new component validation or UI test.
    if not closure['validation_after']['validation_passed'] and closure['model_requests'] == 0:
        pass
    else:
        raise RuntimeError('Unexpected evidence boundary for this experimental candidate')
    text = candidate.read_text(encoding='utf-8')
    if '__watcherScope_v7Configure' not in text or 'task-manager {{ isDarkMode ?' not in text:
        raise RuntimeError('Not the expected v7 + class-derived candidate')
    config = json.loads((ROOT / 'tests/manual/v7-acceptance-config.json').read_text(encoding='utf-8'))
    case = next(c for c in config['cases'] if c['id'] == CASE_ID)
    if case['manifest'] != (OUTPUT / 'manifest.json').relative_to(ROOT).as_posix():
        raise RuntimeError('Registry/manifest path mismatch')
    frameworks = json.loads(json.dumps(old_manifest['frameworks']))
    frameworks['san']['component'] = {'path': candidate.relative_to(ROOT).as_posix(), 'sha256': sha(candidate)}
    manifest = {
        'schema_version': 1, 'case_id': CASE_ID, 'component': 'TaskManager', 'component_tag': 'task-manager',
        'manual_status': 'awaiting_user', 'props': {}, 'frameworks': frameworks,
        'san_adapter': 'v7-parent-watch-report-only',
        'application_error_policy': old_manifest['application_error_policy'],
        'storage_namespace': 'cardmig:v7-acceptance:' + CASE_ID + ':<framework>:',
        'storage_keys': ['task_manager_data'],
        'checklist': (OUTPUT / 'MANUAL_CHECKLIST.md').relative_to(ROOT).as_posix(),
        'source_evidence': CLOSURE.relative_to(ROOT).as_posix(),
        'boundary': '开发人工验收，未接入生产、未人工确认通过。class 已做离线规则验证；watcher 调度、动态键及异常策略仍未获生产放行。显式全局只报告策略，不推断祖先错误捕获。'
    }
    status = {
        'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'manual_status': 'awaiting_user', 'case_id': CASE_ID, 'preparation_only': True,
        'original_files_sha256': original, 'new_files_sha256': {name: sha(ROOT / name) for name in NEW_FILES},
        'sources': {asset['path']: asset['sha256'] for f in frameworks.values() for asset in [f['runtime'], f['component']]},
        'candidate_reference': frameworks['san']['component'],
        'production_validation_passed': False,
        'remaining_validation_codes': sorted({e['code'] for e in closure['validation_after']['validation_errors']}),
        'browser_started': False, 'server_started': False, 'test_commands_executed': False,
        'interaction_verified': False, 'model_requests': 0, 'original_scores_modified': False,
        'original_aggregate': closure['original_aggregate']
    }
    OUTPUT.mkdir(parents=True, exist_ok=False)
    write_json(OUTPUT / 'manifest.json', manifest); write_json(OUTPUT / 'status.json', status)
    with (OUTPUT / 'MANUAL_CHECKLIST.md').open('x', encoding='utf-8') as stream: stream.write(CHECKLIST)
    for name in NEW_FILES:
        target = OUTPUT / 'code' / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    if original != {name: sha(ROOT / name) for name in OLD_FILES}:
        raise RuntimeError('An existing manual file changed during preparation')
    items = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
    with (OUTPUT / 'SHA256SUMS.txt').open('x', encoding='utf-8') as stream:
        stream.write('\n'.join(sha(p) + '  ' + p.relative_to(OUTPUT).as_posix() for p in items) + '\n')
    print(json.dumps({'prepared': OUTPUT.relative_to(ROOT).as_posix(), 'payloads': len(items),
        'manual_status': 'awaiting_user', 'original_files_unchanged': len(original),
        'model_requests': 0, 'browser_started': False, 'tests_run': False}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--prepare', action='store_true')
    if not parser.parse_args().prepare: parser.error('Use --prepare to create the new local bundle')
    prepare()
