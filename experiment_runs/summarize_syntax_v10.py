"""Frozen syntax repair evidence, never extrapolated to a new 70-case success rate."""
from collections import Counter
import ast
import json
from analyze_coverage import ROOT,RUNS,read,write_once,hashed
from replay_general_repairs_v3 import binding

EVIDENCE=RUNS/'composed_v10_syntax_replay_20261120'
TESTS=ROOT/'migration_system/docs/verification/2026-11-20_followup_v10'
OUTPUT=RUNS/'composed_v10_syntax_review_20261120'


def verify(root):
    count=0
    for line in (root/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest,relative=line.split('  ',1)
        if hashed(root/relative)!=digest:raise ValueError('payload_changed:'+relative)
        count+=1
    return count


def main():
    if OUTPUT.exists():raise ValueError('choose_new_immutable_review_directory')
    results=read(EVIDENCE/'results.json');summary=read(EVIDENCE/'summary.json');tests=read(TESTS/'test-results.json')
    protocol=read(EVIDENCE/'protocol.json');red=read(TESTS/'red/result.json')
    standalone_path=ROOT/'migration_system/var/refactor-verification/composed_v10_syntax_20261120.json'
    standalone=read(standalone_path)
    if not tests['successful']:raise ValueError('regressions_not_green')
    if tests['implementation_sha256']!=protocol['implementation_sha256'] or binding()!=protocol['implementation_sha256']:
        raise ValueError('evidence_implementation_mismatch')
    if standalone['status']!='standalone_verified' or standalone['actual_cloud_model_calls']!=0:
        raise ValueError('standalone_verification_required')
    if any(standalone['implementation_sha256'].get(k)!=v for k,v in protocol['implementation_sha256'].items()):
        raise ValueError('standalone_implementation_mismatch')
    files={'replay':verify(EVIDENCE),'regressions':verify(TESTS)}
    # Recheck all cited historical files; never overwrite a prior report.
    for root,entries in ((RUNS/'composed_v9_scope_reassessment_20261120',protocol['reference_files_sha256']),
                         (RUNS,protocol['historical_input_sha256'])):
        for relative,digest in entries.items():
            if hashed(root/relative)!=digest:raise ValueError('historical_file_changed:'+relative)
    summary.update(tests_run=tests['tests_run'],tests_successful=True,red_tests=red['tests_run'],
        red_failures=red['failures'],red_errors=red['errors'],verified_payloads=files,
        historical_real_model_v3_passed=15,historical_first_mixed_passed=12,
        last_full_corpus_offline={'version':'v9','effective_passed':43,'total':70},
        current_full70_passrate='not_measured_no_extrapolation',
        standalone_sha256=hashed(standalone_path),standalone_verified=True,
        complete_passes=[r['component'] for r in results if r['effective_passed']])
    lines=['# v10：三项语法阻断的通用恢复与真实重放','',
        '2026-11-20。仅本机冻结源码、SSM及门禁后的有效代码；无模型调用、云数据库写入、服务重启或付费批次。','',
        '## 结果','',
        f'- 当前实现同版关联回归 {tests["tests_run"]} 项全部通过。修复前冻结 v9 浏览器实现运行相同新增断言：{red["tests_run"]} 项、{red["failures"]} 失败、{red["errors"]} 异常，原日志保留。',
        f'- {summary["syntax_unblocked"]}/3 项从语法阻断恢复到完整检查；真实生产规范化＋静态＋新浏览器捕获＋候选门禁后，完整配置检查通过 {summary["effective_passed"]}/3。',
        '- 完整通过：'+('、'.join(summary['complete_passes']) or '无；语法恢复不等于迁移通过')+'。',
        '- 其余具体失败见下方逐项记录，未删除新暴露的错误或降低阈值。',
        '- 未重测其余67项，不给出当前版本70项通过率。上一轮完整离线v9仍43/70；真实v3模型仍15/70；首次混合配置结果仍12/70，历史均不改写。','',
        '独立目录系统验证也通过：真实内部AST、持久化LangGraph、API／前端／下载及浏览器均实际执行；模型明确为记录响应替身，云模型调用0、原数据库未更新。','',
        '## 通用规则与边界','',
        '1. 依据源码注册组件图和完整解析，删除组件选项边界唯一多余闭合符；不进入函数体猜括号，不接受未知子组件／不可信San入口。',
        '2. Vue循环别名、集合、key及标签作用域匹配后，把错误HTML形式的trackby及键并入San的s-for内部；保留真正源属性，错键／错集合／多重声明不猜。',
        '3. 对单一标量表达式及有限完整方法建立源码AST参考，只补缺失闭合符，要求完整目标脚本解析和导出父方法AST一致；不替换整个方法，不整体规则生成。',
        '4. 完整方法闭合只接纳普通声明状态／已知调用及未遮蔽原生引用。局部覆盖Math、Object、module、require、San来源不可信、业务运算／常量／键不同、赋值返回值不同均拒绝。',
        '生成仍是完整SSM＋模型；未加入整组件确定性生成、公开实例代理或组件名白名单，生成／修复Prompt未改动。本轮只修复目标语法层，后续语义缺陷不借此放行。','',
        '## 逐项真实检查','',
        '诊断代码可重叠，运行失败也会连带影响结构／控件结果；代码数量不是人工独立缺陷数。代表性交互未配置时仍为not_run，不改写为通过。','']
    for row in results:
        lines.extend(['### '+row['component'],'',
            '- 完整检查：'+('通过' if row['effective_passed'] else '未通过')+'；候选提案 '+str(len(row['steps']))+' 次。',
            '- 保留诊断：'+('、'.join(row['effective_codes']) or '无')+'。',
            '- 门禁：'+('；'.join(str(s['number'])+': '+s['gate']['reason']+('（接受）' if s['gate']['accepted'] else '（拒绝并保留父版本）') for s in row['steps']) or '无新候选')+'。',''])
    lines.extend(['## 后续未闭合问题','',
        '继续区分真实生成缺陷与验证器误报。对watch回调不能仅按同名方法放行：已有产物出现源中不存在的观察器及额外业务clamp；需修复真实效果和注册时机。定时器私有句柄也不能凭下划线直接视为安全。',
        '数组验证仍需区分只复制容器后重排并写回、与浅复制后修改共享记录／嵌套对象；尚未在本版本放宽该检查。剩余DOM、默认值、响应依赖等沿用v9清单，本次不宣称全部问题完成。','',
        'TaskManager仍为未知模型结果且没有完整有效产物；不自动重试、不算通过。','',
        '## 证据','',
        '- ../composed_v10_syntax_replay_20261120/：实现、父产物、提案、门禁、原始新截图及全部诊断。',
        '- migration_system/docs/verification/2026-11-20_followup_v10/：旧实现RED、同版完整关联回归、源码快照及哈希。',
        '- 原历史与v9引用文件前后哈希校验通过。',''])
    write_once(OUTPUT/'summary.json',summary);write_once(OUTPUT/'results.json',results)
    write_once(OUTPUT/'standalone.json',standalone)
    write_once(OUTPUT/'REPORT.md','\n'.join(lines))
    nb={'nbformat':4,'nbformat_minor':5,'metadata':{},'cells':[
        {'id':'v10-syntax-summary','cell_type':'markdown','metadata':{},'source':'\n'.join(lines)},
        {'id':'v10-syntax-results','cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
         'source':"import json\nfrom pathlib import Path\nname='composed_v10_syntax_review_20261120'\nbase=next(p for root in [Path.cwd(),*Path.cwd().parents] for p in [root,root/'experiment_runs'/name] if p.name==name and (p/'summary.json').exists())\nsummary=json.loads((base/'summary.json').read_text(encoding='utf-8'))\nsummary"},
        {'id':'v10-syntax-details','cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
         'source':"results=json.loads((base/'results.json').read_text(encoding='utf-8'))\n[(r['component'],r['effective_passed'],r['effective_codes']) for r in results]"}]}
    for cell in nb['cells']:
        if cell['cell_type']=='code':ast.parse(cell['source'])
    write_once(OUTPUT/'analysis.ipynb',nb)
    write_once(OUTPUT/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(OUTPUT).as_posix()+'\n' for p in sorted(OUTPUT.rglob('*')) if p.is_file()))
    print(json.dumps(summary,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
