"""Read-only exception and dynamic-key boundary oracle; no model calls or production fixes."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot

BASE = ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_closure_v1_20261111'
ORACLE = ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_oracle_v1_20261111'
RAW = ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'
SAN = BASE/'TaskManager_parent_async_watch_offline.san'
VUE = RAW/'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'
VUE_RUNTIME = ORACLE/'vendor/package/dist/vue.runtime.common.dev.js'
SAN_RUNTIME = ROOT/'node_modules/san/dist/san.dev.js'
OUTPUT = ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_boundaries_v1_20261111'
CODE_NAMES = ['migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.py',
    'migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs',
    'tests/test_parent_watch_boundaries_audit.py']
MANUAL = ['tests/manual/vue-test-runner.html', 'tests/manual/san-test-runner.html']


def inventory():
    expected = json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    changed = [name for name, sha in expected.items() if digest(ROOT/name) != sha]
    if changed:
        raise RuntimeError('Diagnostic must not change existing production/runtime files: '+str(changed))
    return expected


def runtime():
    prior = json.loads((ORACLE/'audit.json').read_text(encoding='utf-8'))
    if digest(SAN_RUNTIME) != prior['inputs'][SAN_RUNTIME.relative_to(ROOT).as_posix()]:
        raise RuntimeError('San runtime changed')
    payload = {'code':SAN.read_text(encoding='utf-8'), 'vue':VUE.read_text(encoding='utf-8'),
        'vueRuntime':VUE_RUNTIME.read_bytes().decode('utf-8'), 'sanRuntime':SAN_RUNTIME.read_bytes().decode('utf-8')}
    script = ROOT/'migration_pipeline/audit_formal_30_v4_parent_watch_boundaries_v1.cjs'
    proc = subprocess.run(['node',str(script)], cwd=ROOT, input=json.dumps(payload),
        text=True, encoding='utf-8', capture_output=True, check=True, timeout=40)
    if proc.stderr.strip():
        raise RuntimeError(proc.stderr)
    return json.loads(proc.stdout)


def summarize(result):
    rows = []
    for scenario in result['scenarios']:
        pairs = [p for p in result['pairs'] if p['scenario'] == scenario]
        rows.append({'scenario':scenario, 'state_mismatch_phases':[p['phase'] for p in pairs if not p['stateEqual']],
            'business_effect_mismatch_phases':[p['phase'] for p in pairs if not p['businessEffectsEqual']],
            'error_channels':{r['variant']:[e['channel'] for e in r['errors']]
                for r in result['runs'] if r['scenario'] == scenario}})
    return rows


def diagnose():
    verified = {name:verify_snapshot(path.resolve()) for name,path in [('parent_watch_closure',BASE),('source_oracle',ORACLE),('raw',RAW)]}
    hashes = inventory()
    result = runtime()
    if len(result['runs']) != 18 or len(result['pairs']) != 90 or any(len(r['phases']) != 10 for r in result['runs']):
        raise RuntimeError('Expected 9 scenarios x 2 variants x 10 snapshots')
    if not result['hostPrototypeCleanBefore'] or not result['hostPrototypeCleanAfter'] or not result['rejectionListenerCountRestored']:
        raise RuntimeError('Diagnostic leaked process/prototype state')
    if inventory() != hashes:
        raise RuntimeError('Production changed during diagnosis')
    return {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'unproven_parent_watch_boundaries_diagnostic_reused_development_not_repair',
        'source_verified_files':verified, 'production_inventory_count':len(hashes),
        'inputs':{p.relative_to(ROOT).as_posix():digest(p) for p in [SAN,VUE,VUE_RUNTIME,SAN_RUNTIME]},
        'manual_page_sha256':{name:digest(ROOT/name) for name in MANUAL},
        'observations':result, 'summary':summarize(result),
        'production_rule_or_prompt_modified':False, 'canonical_san_or_manual_page_modified':False,
        'model_requests':0, 'full_suite_reexecuted':False, 'new_batch_score_or_manual_acceptance_claimed':False,
        'prior_full_suite_reference':{'passed':672, 'elapsed_seconds':1238.068,
            'path':(BASE/'unit_tests.txt').relative_to(ROOT).as_posix()},
        'findings':[
            {'id':'PARENT_WATCH_EXCEPTION_POLICY_NOT_CLOSED','category':'remaining_risk','component':'TaskManager',
             'framework':'san','status':'runtime_reproduced_not_fixed',
             'scope':'Explicitly unproven exception branch of frozen normal-flow derivative, not a newly observed UI defect.',
             'evidence':['write_failure_captured','write_failure_headless_default']},
            {'id':'PARENT_WATCH_DYNAMIC_KEY_SHAPE_NOT_CLOSED','category':'remaining_risk','component':'TaskManager',
             'framework':'san','status':'runtime_reproduced_not_fixed',
             'scope':'Unknown/new/inherited/prototype keys outside previous proven existing-key contract.',
             'evidence':['new_key','new_undefined_key','inherited_key','prototype_key']}],
        'original_score':{'passed':24,'configured':30,'failed':6,'execution_errors':0,'total_tokens':1821544}}


def report(data):
    table = []
    for r in data['summary']:
        table.append('| '+r['scenario']+' | '+(', '.join(r['state_mismatch_phases']) or '无')+' | '
            +(', '.join(r['business_effect_mismatch_phases']) or '无')+' |')
    return f'''# 父监听异常与动态键边界诊断 v1（2026-11-11）

本轮只诊断上一轮明确未证明的分支，不修改生产规则/Prompt、canonical San 或测试页；0 模型请求。保留上轮正常流程修复及其 672/672 完整测试证据，不撤销它，也不扩大为异常/任意键均等价。原始批次仍为24/30、6失败、0执行异常、1,821,544 tokens，不是新批次或独立测试。

冻结源 Vue2.7.16 与上轮派生 San（San3.15.6）原字节不变。9 场景×2框架×10同步/观察阶段=18次运行、180份快照、90组对照。源业务方法、San代码均不改写；只在隔离 localStorage 中让一次 setItem 抛错。默认采用显式 Vue config.errorHandler 记录错误；另有 Node 无自定义 handler 对照，不把该配置说成浏览器默认策略。宿主监听 unhandledRejection 仅收集结果、保持进程继续，不给被测 Promise 加 catch，不替换原生调度器；最终移除监听。两个 setImmediate 只观察原生 Promise 队列与拒绝通知，不执行模拟的应用timer。无浏览器/DOM attach/真实存储；Vue用空根render，San直接调用attached、真实headless dispose。

| 场景 | 状态不同的阶段 | 业务效果不同的阶段 |
| --- | --- | --- |
{chr(10).join(table)}

动态键检查区分初始/恢复时已有的响应式键、事后新增普通键、同值undefined的新键、继承键及__proto__。同时记录 ownEnumerableKeys、ownUndefined、是否自有__proto__、原型身份与继承标记，避免 JSON.stringify 忽略undefined/原型而造成假等价。原型输入仅进入独立vm中的settings对象；宿主与沙箱Object.prototype都未改动。

上轮队列try/finally能复位，但不等于桥接Vue错误处理与继续剩余watcher的策略。未知键直接赋值、整个对象克隆、同值保护也不能无条件等价。本轮保存成功/失败的每次存储尝试、业务方法调用、timer启动/清理及恢复阶段，不能只比较最后画面或最终内存。异常路由单列，不过滤成“正常通过”。

具体观测：显式捕获策略下第一次保存抛错后，源tasks回调中止，但settings回调继续保存并启动30秒timer；目标整个flush中止，settings当轮未运行。下轮目标可再次工作，说明finally复位有效，却不能据此称错误策略相同。Node默认无自定义handler时，源本轮抛错且后续监听队列不再运行，目标finally复位后可恢复；因此也不能无条件“catch后继续”假装对齐两种策略。后续timer事件ID差异来自此前缺失启动，不是独立缺陷。

已有声明键和恢复对象中已存在的额外键作为三个控制场景，状态及业务效果全匹配。事后新增普通/继承键在源中无响应式通知，目标整对象替换则额外保存/启动timer；新增undefined时源会创建自有属性，而目标Object.is保护直接跳过，连属性形状都不同。__proto__在源中修改局部settings原型，在目标spread中变成自有键，既有形状差异也有效果差异。不把新增属性“修成响应式”，也不以只序列化JSON隐藏这些差别。

诊断测试 {data['diagnostic_tests']['passed']}/{data['diagnostic_tests']['passed']}，0失败/0跳过，{data['diagnostic_tests']['elapsed_seconds']}秒。现有382项清单原字节未变；本轮未重新运行完整672项，不能拼接成新的完整套件成绩。两项边界仍待工程化，不计为新的整批生产缺陷率，不继承人工通过。后续先确定可证明的错误策略/调用键范围，再实现规则、验证器、拒绝保护和对照回归；不得直接吞异常、假造Vue2新增属性通知或默认整组件已通过。
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-evidence',action='store_true')
    args = parser.parse_args()
    if args.write_evidence and OUTPUT.exists():
        raise FileExistsError('Never overwrite frozen diagnostic evidence')
    before = inventory()
    code_hashes = {name:digest(ROOT/name) for name in CODE_NAMES}
    data = diagnose()
    if args.write_evidence:
        proc = subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_parent_watch_boundaries_audit.py','-v'],
            cwd=ROOT,env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
        log = proc.stdout+proc.stderr
        match = re.search(r'Ran (\d+) tests in ([\d.]+)s',log)
        if proc.returncode or not match or '\nOK' not in log or 'skipped=' in log:
            raise RuntimeError('Diagnostic tests failed:\n'+log)
        if inventory() != before or any(digest(ROOT/name) != sha for name,sha in code_hashes.items()):
            raise RuntimeError('Code or inputs changed during final diagnostic')
        data['diagnostic_tests'] = {'passed':int(match[1]),'failed':0,'elapsed_seconds':float(match[2])}
        OUTPUT.mkdir(parents=True)
        for name in CODE_NAMES:
            target = OUTPUT/'code'/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,target)
        for name,value in [('audit.json',data),('live_inventory.json',before)]:
            (OUTPUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'REPORT.md').write_text(report(data),encoding='utf-8')
        (OUTPUT/'diagnostic_tests.txt').write_text(log,encoding='utf-8')
        files = sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT/'SHA256SUMS.txt').write_text('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n',encoding='utf-8')
        verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'summary':data['summary'],'model_requests':0,'production_rules_changed':False,
        'evidence_written':args.write_evidence,'tests':data.get('diagnostic_tests')},ensure_ascii=False))


if __name__ == '__main__':
    main()
