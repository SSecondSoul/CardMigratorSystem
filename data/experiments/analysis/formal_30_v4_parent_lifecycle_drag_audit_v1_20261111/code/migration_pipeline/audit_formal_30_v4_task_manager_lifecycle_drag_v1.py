"""Read-only frozen parent lifecycle/drag audit; no production normalization or LLM."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import platform
import subprocess
import sys
from datetime import datetime, timezone, timedelta

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot
from migration_pipeline.stages.validate import ValidateStage, ValidateStageInput

BASE = ROOT / 'data/experiments/analysis/formal_30_v4_source_child_initialization_closure_v1_20261111'
RAW = ROOT / 'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'
OUTPUT = ROOT / 'data/experiments/analysis/formal_30_v4_parent_lifecycle_drag_audit_v1_20261111'
SAN = BASE / 'TaskManager_source_child_initialization_offline.san'
VUE = RAW / 'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'
JAVASCRIPT = ROOT / 'migration_pipeline/audit_formal_30_v4_task_manager_lifecycle_drag_v1.cjs'
TEST = 'tests/test_task_manager_lifecycle_drag_audit.py'
NOTEBOOK = ROOT / 'notebooks/02-migration-experiments/2026-11-04_formal_30_v4_full_regression_v2.ipynb'
MANUAL = ['tests/manual/vue-test-runner.html', 'tests/manual/san-test-runner.html']


def inventory():
    previous = json.loads((BASE / 'live_inventory.json').read_text(encoding='utf-8'))
    changed = [name for name, sha in previous.items() if digest(ROOT / name) != sha]
    if changed:
        raise RuntimeError('Audit must not change production runtime: ' + str(changed))
    return previous


def runtime():
    proc = subprocess.run(['node', str(JAVASCRIPT)], cwd=ROOT,
        input=json.dumps({'code': SAN.read_text(encoding='utf-8'), 'vue': VUE.read_text(encoding='utf-8')}),
        text=True, encoding='utf-8', capture_output=True, timeout=30)
    if proc.returncode:
        raise RuntimeError('Diagnostic Node harness failed: ' + proc.stderr)
    result = json.loads(proc.stdout)
    if proc.stderr.strip():
        raise RuntimeError('Unexpected San runtime warning/error: ' + proc.stderr)
    return result


def diagnose():
    verified = {'child_initialization': verify_snapshot(BASE.resolve()), 'raw': verify_snapshot(RAW.resolve())}
    hashes = inventory()
    state = json.loads((RAW / 'repair_reports/complex/TaskManager_repair_history.json').read_text(encoding='utf-8'))['state']
    validation = ValidateStage().run(ValidateStageInput(generated_code=SAN.read_text(encoding='utf-8'),
        ssm=state['ssm'], vue_file_path=str(VUE))).to_state_update()
    result = runtime()
    if result['sanVersion'] != '3.15.6':
        raise RuntimeError('This audit requires the recorded installed San 3.15.6')
    if validation['validation_errors']:
        raise RuntimeError('Expected the already frozen candidate with zero current static errors')
    if not all(r['order'] == r['sourceExpectedOrder'] for r in result['drag']):
        raise RuntimeError('Unexpected source move-order mismatch: review diagnostic harness')
    inventory()
    if hashes != inventory():
        raise RuntimeError('Runtime inventory drift')
    return {
        'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification': 'read_only_development_diagnostic_not_a_repair_or_new_batch',
        'source_verified_files': verified, 'model_requests': 0,
        'inputs': {str(p.relative_to(ROOT).as_posix()): digest(p) for p in [SAN, VUE]},
        'runtime_inventory_count': len(hashes), 'validation': validation,
        'environment': {'python_version': platform.python_version(), 'python_executable': sys.executable,
            'node_version': result['nodeVersion'], 'san_version': result['sanVersion'],
            'manual_san_version_not_executed': '3.15.3'},
        'observations': result,
        'harness_development_notes': [
            'First harness incorrectly assumed export default; frozen Vue uses module.exports. Fixed diagnostic AST root selection.',
            'Second harness directly required San unbundled parser internals and hit CommonJS circular dependency; switched to installed san.dev bundle with one in-memory internal listener export. No package file modified.',
            'Parent wrapper template assigned to exported constructor as normal SFC loading would; no DOM attach executed.'
        ],
        'findings': [
            {'id': 'PARENT_WATCH_REGISTRATION_AFTER_INITIALIZATION', 'category': 'remaining_risk',
             'status': 'san_runtime_reproduced_source_order_static_only',
             'evidence': 'All four directly invoked attached hooks register tasks/settings after loadInitialData; no startup watcher callback/save.',
             'boundary': 'Source declarative watch precedes mounted, but Vue async/batching/effect ordering not executed. No automatic hook move justified yet.'},
            {'id': 'NATIVE_DRAG_TRANSFER_SIDE_EFFECTS_MISSING', 'category': 'production_defect',
             'status': 'frozen_source_method_and_san_handler_reproduced_unfixed',
             'evidence': 'Source sets text/plain and effectAllowed=move before emit; target emits index but sets neither.',
             'boundary': 'Browser-dependent native drag impact not exercised; synthetic custom event chain does pass.'},
            {'id': 'SAN_DEEP_WATCH_NOT_VUE_DEEP_WATCH', 'category': 'remaining_risk',
             'status': 'installed_san_runtime_reproduced_unfixed',
             'evidence': 'San watch accepts two arguments; third deep option ignored. Nested data.set/splice observed, raw object mutation/same-reference set not observed.',
             'boundary': 'No general Vue watcher compatibility or full component acceptance claim.'}
        ],
        'original_score': {'passed': 24, 'configured': 30, 'failed': 6, 'execution_errors': 0, 'total_tokens': 1821544},
        'manual_page_sha256': {p: digest(ROOT / p) for p in MANUAL},
        'production_runtime_modified': False, 'canonical_san_modified': False,
        'prompt_or_rules_modified': False, 'manual_acceptance_inherited': False,
        'full_suite_reexecuted': False, 'prior_full_suite_reference': {'passed': 614, 'elapsed_seconds': 999.702,
            'path': str((BASE / 'unit_tests.txt').relative_to(ROOT).as_posix())}
    }


def report(data):
    return f'''# TaskManager 父生命周期与完整拖放声明链诊断（2026-11-11）

本轮只读检查上层子组件初始化冻结候选；不是修复完成、不是新批次或独立测试。原成绩仍为 24/30、6 失败、0 执行异常、1,821,544 tokens。0 模型请求；不改生产规则/Prompt、canonical San、人工页或旧冻结包，不 commit/push。

## 已复现与尚未证明

1. 父 attached 先 loadInitialData/startAutoSync/通知，后注册 tasks/settings 监听。空存储、已存数据、关闭自动保存、损坏 JSON 四个场景直接运行真实 San 应用钩子，初始化的监听回调与保存次数均为 0；统计显式 updateStatistics 正常，后续嵌套编辑/设置替换可以触发监听，disposed 清除模拟 interval 并保存。源 Vue 使用声明式 deep watch（在 mounted 之前建立），但本机未执行 Vue runtime 的异步监听队列，不能把预期保存次数/计时器顺序冒充已证实；不能简单把 San 注册移到初始化前，San 同步监听可能在恢复 settings 之前就保存、重启 timer，需单独证明源顺序与副作用。

2. Vue TaskItem.onDragStart(e) 有 dataTransfer.setData('text/plain',index) 和 effectAllowed='move'，目标缺失这两项。提取冻结源函数用相同模拟事件执行，源写入且发出索引；目标实际 San 声明监听器只发索引。这不是本轮引入的回归，且当前静态验证仍 0 错误，说明现有源 DOM/数组事务规则没有覆盖该事件体副作用。浏览器是否因此阻止原生拖拽尚未执行，不能宣称在所有浏览器必现。

3. San 3.15.6 watch 两个形参，第三参数 deep/immediate 无效。真实 San 观察证明嵌套 data.set 与 data.splice 触发根监听；直接修改 data.get 返回对象、再同引用 set 不触发。不能认为已有 {{deep:true}} 等价 Vue 深监听，也不把源直接突变一律安全。

## 已通过的局部检查

解析冻结目标父/子模板，使用已安装 San 的 getEventListener 和 Component.fire 实际解释声明，模拟 dragstart→子自定义事件→父索引→drop-on/列表 drop→moveTask→dragend。6 场景（向下/向上、列表末尾、自身、取消、禁用）列表顺序均与提取的源 moveTask 函数一致，元素身份保留，原数组不被改坏；drop.stop 与 dragover.prevent 确认执行。过滤后的索引正确到达父方法，结束后拖拽索引清空。这里手工绑定真实声明并注入合成事件，不运行 DOM attach/浏览器原生手势，不能替代交互验收。

## 验证与边界

新增诊断测试 {data['diagnostic_tests']['passed']}/{data['diagnostic_tests']['passed']}，{data['diagnostic_tests']['elapsed_seconds']} 秒，无跳过；完整 614 项不是本轮重跑，引用上轮冻结日志（999.702 秒），两者不合并为新全套通过。生产运行清单 {data['runtime_inventory_count']} 项逐项保持一致；本轮使用的 Node 模块与 San bundle 另保存哈希。本次 Python {data['environment']['python_version']}、Node {data['environment']['node_version']}、San 3.15.6；不是假定历史 cardmig/Python 3.10/Node 20 环境一致。浏览器页 San 仍为 3.15.3，不声称前者验证过。

诊断脚本开发的两次失败不隐去：首次错误假定源 export default，实际为 CommonJS module.exports；随后直接加载 San 未打包 parser 内部模块触发循环依赖。均为测试装置错误，未作生产规则更改；最终读取实际安装 san.dev bundle，只在内存导出原有 getEventListener 函数，函数体/依赖包原字节不改，给导出父构造器配置 SFC 外层模板后再实例化。不把这两次失败计为组件新缺陷或修复回归。

未重跑 30 样本/轻量 DOM，不增加“已通过数”，不继承人工确认。TripItineraryPlanner 外部渲染辅助依赖风险保持上层记录，不豁免。Notebook 只追加证据，不覆盖历史。

## 下一步

先为原生事件方法体建立基于完整源 AST 的有边界规则（保留 guard、dataTransfer 操作、参数、emit 次序），同步验证器/候选保护/正反例；用本冻结输入验证，不靠 Prompt 文字宣称闭环。父监听注册另需覆盖异步批次、恢复存储、自动保存关闭、计时器创建/取消、销毁清理的源运行 oracle；未证明前 fail closed，不自动搬动。两项完成后再讨论完整调度器/30 项离线回放与人工验收，暂不付费复跑。
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence', action='store_true')
    args = parser.parse_args()
    if args.write_evidence and OUTPUT.exists():
        raise FileExistsError('Never overwrite frozen audit evidence')
    before = inventory()
    data = diagnose()
    if args.write_evidence:
        proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
            '-p', 'test_task_manager_lifecycle_drag_audit.py', '-v'], cwd=ROOT,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, capture_output=True, text=True, encoding='utf-8')
        log = proc.stdout + proc.stderr
        match = re.search(r'Ran (\d+) tests in ([\d.]+)s', log)
        if proc.returncode or not match or '\nOK' not in log or 'skipped=' in log:
            raise RuntimeError('Diagnostic tests failed:\n' + log)
        if before != inventory():
            raise RuntimeError('Production files changed during audit')
        data['diagnostic_tests'] = {'passed': int(match[1]), 'failed': 0, 'elapsed_seconds': float(match[2])}
        OUTPUT.mkdir(parents=True)
        for path in [Path(__file__).resolve(), JAVASCRIPT, ROOT / TEST]:
            dest = OUTPUT / 'code' / path.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        for name, value in [('audit.json', data), ('live_inventory.json', before)]:
            (OUTPUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (OUTPUT / 'diagnostic_tests.txt').write_text(log, encoding='utf-8')
        (OUTPUT / 'REPORT.md').write_text(report(data), encoding='utf-8')
        payloads = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT / 'SHA256SUMS.txt').write_text('\n'.join(
            f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in payloads) + '\n', encoding='utf-8')
        verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'model_requests': 0, 'static_errors': len(data['validation']['validation_errors']),
        'drag_cases': len(data['observations']['drag']), 'findings': [f['id'] for f in data['findings']],
        'production_files_changed': False, 'evidence_written': args.write_evidence,
        'diagnostic_tests': data.get('diagnostic_tests')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
