"""Pinned real Vue watcher scheduler vs retained San; diagnosis only, zero model calls."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile

from migration_pipeline.analyze_formal_30_v4_full_regression import ROOT, digest, verify_snapshot

BASE = ROOT/'data/experiments/analysis/formal_30_v4_source_native_drag_closure_v1_20261111'
RAW = ROOT/'data/experiments/snapshots/formal_30_v4_full_regression_v2_results_20261104_214821'
OUTPUT = ROOT/'data/experiments/analysis/formal_30_v4_parent_watch_oracle_v1_20261111'
VENDOR = ROOT/'data/experiments/runtime_dependencies/vue_2_7_16'
JAVASCRIPT = ROOT/'migration_pipeline/audit_formal_30_v4_parent_watch_oracle_v1.cjs'
SAN = BASE/'TaskManager_source_native_drag_offline.san'
VUE = RAW/'protocol/frozen/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue'
VUE_RUNTIME = VENDOR/'package/dist/vue.runtime.common.dev.js'
SAN_RUNTIME = ROOT/'node_modules/san/dist/san.dev.js'
VENDOR_NAMES = ['vue-2.7.16.tgz', 'package/dist/vue.runtime.common.dev.js', 'package/LICENSE', 'package/package.json', 'PROVENANCE.json']
CODE_NAMES = ['migration_pipeline/audit_formal_30_v4_parent_watch_oracle_v1.py',
    'migration_pipeline/audit_formal_30_v4_parent_watch_oracle_v1.cjs', 'tests/test_parent_watch_oracle_audit.py',
    'migration_pipeline/utils/inline_identifier_recovery.cjs']
MANUAL = ['tests/manual/vue-test-runner.html', 'tests/manual/san-test-runner.html']


def inventory():
    previous = json.loads((BASE/'live_inventory.json').read_text(encoding='utf-8'))
    changed = [name for name, sha in previous.items() if digest(ROOT/name) != sha]
    if changed:
        raise RuntimeError('Read-only oracle must not change production files: '+str(changed))
    return previous


def verify_vendor():
    provenance = json.loads((VENDOR/'PROVENANCE.json').read_text(encoding='utf-8'))
    archive = (VENDOR/'vue-2.7.16.tgz').read_bytes()
    integrity = 'sha512-'+base64.b64encode(hashlib.sha512(archive).digest()).decode('ascii')
    if integrity != provenance['official_dist_integrity'] or hashlib.sha1(archive).hexdigest() != provenance['official_dist_shasum']:
        raise RuntimeError('Official npm dist integrity mismatch')
    with tarfile.open(VENDOR/'vue-2.7.16.tgz', 'r:gz') as package:
        for name in provenance['extracted_members']:
            if name not in VENDOR_NAMES or package.extractfile(name).read() != (VENDOR/name).read_bytes():
                raise RuntimeError('Extracted runtime differs from official tar member: '+name)
    if digest(VUE_RUNTIME) != provenance['runtime_sha256']:
        raise RuntimeError('Pinned Vue runtime digest mismatch')
    if json.loads((VENDOR/'package/package.json').read_text(encoding='utf-8'))['version'] != '2.7.16':
        raise RuntimeError('Unexpected runtime version')
    return {name:digest(VENDOR/name) for name in VENDOR_NAMES}


def runtime():
    payload = {'code':SAN.read_text(encoding='utf-8'), 'vue':VUE.read_text(encoding='utf-8'),
        'vueRuntime':VUE_RUNTIME.read_bytes().decode('utf-8'), 'sanRuntime':SAN_RUNTIME.read_bytes().decode('utf-8')}
    proc = subprocess.run(['node', str(JAVASCRIPT)], cwd=ROOT, input=json.dumps(payload),
        text=True, encoding='utf-8', capture_output=True, timeout=40)
    if proc.returncode or proc.stderr.strip():
        raise RuntimeError('Headless oracle failed: '+proc.stderr)
    return json.loads(proc.stdout)


def phase(row, name):
    return next(p for p in row['phases'] if p['name'] == name)


def metrics(row, *names):
    events = [e for name in names for e in phase(row, name)['events']]
    return {'watch_callbacks':[e['field'] for e in events if e['kind']=='watch-callback'],
        'writes':[e['value'] for e in events if e['kind']=='storage-write'],
        'interval_starts':[e['delay'] for e in events if e['kind']=='interval-start'],
        'interval_clears':sum(e['kind']=='interval-clear' for e in events)}


def summarize(result):
    summary = []
    for name in result['scenarios']:
        group = {r['variant']:r for r in result['runs'] if r['scenario']==name}
        summary.append({'scenario':name,'variants':{variant:{
            'construction_registrations':[e['field'] for e in row['constructionEvents'] if e['kind']=='watch-register'],
            'startup':metrics(row,'mount_sync','mount_tick'),
            'nested_twice':metrics(row,'nested_twice_sync','nested_twice_tick'),
            'settings_before_tasks':metrics(row,'settings_before_tasks_sync','settings_before_tasks_tick'),
            'destroy_before_flush':metrics(row,'destroy_before_flush_sync','destroy_before_flush_tick'),
            'stored_settings_after_mount':(phase(row,'mount_tick')['state']['stored'] or {}).get('settings'),
            'final_active_intervals':phase(row,'post_destroy_change_tick')['state']['activeIntervalDelays']
        } for variant,row in group.items()}})
    return summary


def diagnose():
    verified = {'native_drag_closure':verify_snapshot(BASE.resolve()),'raw':verify_snapshot(RAW.resolve())}
    before = inventory(); vendor = verify_vendor(); result = runtime()
    if len(result['runs'])!=15 or any(len(r['phases'])!=18 for r in result['runs']):
        raise RuntimeError('Expected 5 scenarios x 3 variants x 18 phase snapshots')
    if digest(VUE_RUNTIME)!=result['vueRuntimeSha256'] or digest(SAN_RUNTIME)!=result['sanRuntimeSha256']:
        raise RuntimeError('Executed runtime bytes differ from recorded files')
    if inventory()!=before or verify_vendor()!=vendor:
        raise RuntimeError('Inputs changed while diagnosing')
    return {'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'classification':'headless_real_vue_watch_oracle_reused_development_not_repair_or_new_batch',
        'source_verified_files':verified,'production_inventory_count':len(before),
        'inputs':{str(p.relative_to(ROOT).as_posix()):digest(p) for p in [SAN,VUE,VUE_RUNTIME,SAN_RUNTIME]},
        'vendor_sha256':vendor,'observations':result,'summary':summarize(result),
        'manual_page_sha256':{name:digest(ROOT/name) for name in MANUAL},
        'environment':{'python_version':platform.python_version(),'node_version':result['nodeVersion'],
            'vue_version':'2.7.16','san_version':json.loads((ROOT/'node_modules/san/package.json').read_text(encoding='utf-8'))['version']},
        'production_rule_or_prompt_modified':False,'canonical_san_or_manual_page_modified':False,
        'model_requests':0,'new_batch_score_or_manual_acceptance_claimed':False,
        'original_score':{'passed':24,'configured':30,'failed':6,'execution_errors':0,'total_tokens':1821544},
        'full_suite_reexecuted':False,'prior_full_suite_reference':{'passed':644,'elapsed_seconds':1140.378,
            'path':str((BASE/'unit_tests.txt').relative_to(ROOT).as_posix())},
        'findings':[{'id':'PARENT_WATCH_SCHEDULING_NOT_LANDED','category':'production_defect',
            'component':'TaskManager','framework':'san','status':'runtime_reproduced_unfixed',
            'symptoms':['Startup effects omitted by late registration','Same-turn changes not coalesced',
                'Different callback/save/timer ordering','Extra immediate effects before destruction'],
            'evidence_upgrade':'Earlier remaining risk now reproduced against pinned actual Vue runtime, not only source-derived assumptions.'},
            {'id':'NAIVE_EARLY_REGISTRATION_UNSAFE','category':'remaining_risk',
             'status':'counterfactual_runtime_failure_not_applied_to_production',
             'symptoms':['Saved autoSave=false overwritten with default autoSave=true and interval=60 before settings restore'],
             'not_counted_as_applied_repair_regression':True}],
        'acquisition_notes':['No cached Vue2 runtime was available.',
            'Sandbox npm metadata request failed EACCES; no project dependency or lock was changed.',
            'Authorized direct official npm metadata/tarball fetch succeeded; sha512 and sha1 checked before selective extraction; no install scripts.',
            'Official source/guide consulted for initWatch and async queue; measurements use actual bundled runtime, not a hand-written Vue queue.']}


def report(data):
    table = []
    for row in data['summary']:
        v = row['variants']; count = lambda name:len(v[name]['startup']['writes'])
        table.append(f"| {row['scenario']} | {count('vue_source')} | {count('san_current')} | {count('san_naive_early')} |")
    return f'''# 父监听时序真实 Vue 对照（2026-11-11）

本轮只建立运行 oracle，不改生产规则/Prompt、canonical San 或测试页。0 模型请求；原批次仍 24/30、6失败、0执行异常、1,821,544 tokens。不是新批次、独立测试或人工验收。

隔离获取官方 Vue2.7.16 npm 发布包，核对官方 dist sha512/sha1；只提取 runtime、LICENSE、package.json，不安装依赖、不运行脚本、不改项目 package/lock/node_modules。完整包、精确运行时字节与来源记录同时冻结。Vue2页只锁 vue@2，未证明浏览器实际补丁版本；本 oracle 不替代该页面。官方说明参见 [异步更新队列](https://v2.vuejs.org/v2/guide/reactivity.html#Async-Update-Queue)、[固定版 initWatch](https://raw.githubusercontent.com/vuejs/vue/v2.7.16/src/core/instance/state.ts)、[固定版 scheduler](https://raw.githubusercontent.com/vuejs/vue/v2.7.16/src/core/observer/scheduler.ts)。

## 实测方法

5存储场景×3版本（源Vue、当前San、只在内存提前注册的San）=15次执行，每次18个同步/nextTick阶段，共270份状态/事件快照。实际 Vue 根构造、响应式深监听、默认 async 队列、$mount→mounted 与 $destroy→beforeDestroy；render替为无子组件的空根VNode，Node无DOM patch，不声称测试源模板。San实际构造/inited/内建watch/nextTick/native dispose；attached应用钩子直接调用，无完整DOM attach。独立vm沙箱，固定Date，模拟localStorage/应用interval/timeout；真实框架Promise队列，不用自写Vue调度器。通知3000ms回调与周期同步未触发，不说所有timer都清理。

## 初始化保存次数

| 存储场景 | 源Vue | 当前San | 仅提前注册San |
| --- | ---: | ---: | ---: |
{chr(10).join(table)}

源在构造期注册tasks/settings，mounted同步加载完成后异步监听；当前San加载后才注册，初始化效果漏掉。同轮两次任务标题修改，源只运行一次tasks监听，San运行两次；先改settings两次再改tasks，源仍按声明次序tasks→settings各一次，San为settings→settings→tasks，保存中间态且重复重启interval。已保存30秒设置时，源先由mounted启动一次、再由settings watcher清理重启一次，这是源实际行为，不擅自“优化掉”。

仅提前注册不是合格修复：恢复数据原为autoSave=false/30秒，San tasks同步回调先按默认autoSave=true/60秒写回存储，settings恢复后不再保存，磁盘模拟状态停在错误默认设置。该对照只改内存AST，未应用生产，不计为已实施修复回归。

销毁前改设置：源$destroy前尚未执行待排watcher，beforeDestroy只保存一次；San立即监听先保存并建interval，再disposed保存并清理，共2次保存。真实框架销毁后再改数据均无监听/保存，活动interval归零；仍有源本来未取消的通知timeout，本轮不触发它，也不谎称全timer无泄漏。

将此前父监听remaining_risk升级为1类已复现迁移缺陷（调度/时机语义缺口，多个症状不重复计数）。不是原生drag规则或工厂规则失效，也不是本轮引入。没有浏览器/子组件事件或原始30批次复跑；不更新分数。

## 验证与下一步

诊断测试 {data['diagnostic_tests']['passed']}/{data['diagnostic_tests']['passed']}，0失败/0跳过，{data['diagnostic_tests']['elapsed_seconds']}秒；不是完整644项重跑（引用上轮1140.378秒日志，不拼接成绩）。现有{data['production_inventory_count']}项生产清单原字节不变。先前网络沙箱拒绝与官方直接获取步骤保留在audit.json；没有用“没拿到运行时”阻塞后伪造Vue队列。

后续规则必须同时证明：首次注册早于源初始化、每实例每字段去重、按源注册顺序批处理、回调读取执行时最新值、清空本轮pending后处理回调中新变更、销毁使待排任务无效、同源持久化/计时器副作用。源码若使用sync/immediate、未知路径/额外effects或不能证明闭合依赖，需拒绝自动改写。不能只移动watch，也不能只加Promise或任意防抖。再同步验证器/候选保护/回归，使用本冻结oracle验收，完成前不付费复跑。
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-evidence',action='store_true');args=parser.parse_args()
    if args.write_evidence and OUTPUT.exists():raise FileExistsError('Never overwrite frozen oracle evidence')
    hashes=inventory(); vendor=verify_vendor(); code_hashes={name:digest(ROOT/name) for name in CODE_NAMES}
    data=diagnose()
    if args.write_evidence:
        proc=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_parent_watch_oracle_audit.py','-v'],
            cwd=ROOT,env={**os.environ,'PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8')
        log=proc.stdout+proc.stderr;match=re.search(r'Ran (\d+) tests in ([\d.]+)s',log)
        if proc.returncode or not match or '\nOK' not in log or 'skipped=' in log:raise RuntimeError('Diagnostic tests failed:\n'+log)
        if inventory()!=hashes or verify_vendor()!=vendor or any(digest(ROOT/name)!=sha for name,sha in code_hashes.items()):
            raise RuntimeError('Inputs/code changed during final audit')
        data['diagnostic_tests']={'passed':int(match[1]),'failed':0,'elapsed_seconds':float(match[2])}
        OUTPUT.mkdir(parents=True)
        for name in CODE_NAMES:
            dest=OUTPUT/'code'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
        for name in VENDOR_NAMES:
            dest=OUTPUT/'vendor'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(VENDOR/name,dest)
        for name,value in [('audit.json',data),('live_inventory.json',hashes)]:
            (OUTPUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'REPORT.md').write_text(report(data),encoding='utf-8');(OUTPUT/'diagnostic_tests.txt').write_text(log,encoding='utf-8')
        files=sorted(p for p in OUTPUT.rglob('*') if p.is_file())
        (OUTPUT/'SHA256SUMS.txt').write_text('\n'.join(f'{digest(p)}  {p.relative_to(OUTPUT).as_posix()}' for p in files)+'\n',encoding='utf-8')
        verify_snapshot(OUTPUT.resolve())
    print(json.dumps({'scenarios':5,'variants':3,'runs':15,'phase_snapshots':270,
        'model_requests':0,'production_rules_changed':False,'evidence_written':args.write_evidence,'tests':data.get('diagnostic_tests')}))


if __name__=='__main__':main()
