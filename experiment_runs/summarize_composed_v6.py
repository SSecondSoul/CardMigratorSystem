"""Freeze the repair investigation and its unresolved coverage, not a pass claim."""
from collections import Counter
from pathlib import Path
import json
from analyze_coverage import read,write_once,hashed,RUNS

ROOT=Path(__file__).resolve().parents[1]
REPLAY=RUNS/'composed_v6_final_replay_20261119'
OUTPUT=RUNS/'composed_v6_review_20261119'


def main():
    summary=read(REPLAY/'summary.json');rows=read(REPLAY/'results.json')
    if len(rows)!=70 or summary['statuses'].get('replay_error'):raise ValueError('review_requires_complete_successful_replay')
    pairs=read(RUNS/'analysis_v3_vs_first70_20261119/pairs.json')
    old={p['component']:p['new'] for p in pairs}
    remaining=[];codes=Counter();new_passes=[];lost_passes=[]
    for row in rows:
        previous=old[row['component']]
        if row['effective_passed'] and not previous['passed']:new_passes.append(row['component'])
        if previous['passed'] and not row['effective_passed']:lost_passes.append(row['component'])
        if row['effective_passed']:continue
        if row.get('gate'):
            assessment=row['after'] if row['gate']['accepted'] else row['before']
            findings=assessment.get('diagnostics',[])
        else:
            report=read(RUNS/previous['report']);findings=(report.get('assessment') or {}).get('diagnostics',[])
        found=sorted({d['code'] for d in findings}) or [previous['stop_reason']]
        codes.update(found)
        remaining.append({'component':row['component'],'complexity':previous['complexity'],'codes':found,
                          'gate':row.get('gate'),'historical_report':previous['report'],
                          'offline_result':str((REPLAY/previous['sample_id']/'result.json').relative_to(RUNS))})
    verdict={**summary,'fresh_generation_passed':15,'fresh_generation_total':70,
             'offline_new_passes':new_passes,'historical_passes_lost_offline':lost_passes,
             'remaining_count':len(remaining),'remaining_codes_by_components':dict(codes.most_common()),
             'all_issues_resolved':not remaining,'model_unknown_retry_performed':False,
             'interpretation':'offline_existing_code_repair_compatibility_NOT_new_model_generation_success'}
    all_codes=sorted({code for p in pairs for version in ('old','new')
                      for code in p[version]['ever_evaluated_codes']+p[version]['final_diagnostic_codes']})
    coverage=[]
    for code in all_codes:
        if code.startswith(('model_','provider_')):
            layer='模型传输／账本／预算';mechanism='保留收据、未知调用不重试；不是代码缺陷的自动放行规则'
        elif 'syntax' in code or 'directive' in code or 's_for' in code:
            layer='模板／脚本语法';mechanism='真实解析定位＋源匹配属性、循环、闭合修复；未知表达式不猜测'
        elif any(x in code for x in ('dom_','template_structure','control_')):
            layer='模板与实际 DOM／控件';mechanism='实际原生 value/class 反射＋严格 DOM 与 live 控件检查；回退诊断谱系尚待补齐'
        elif any(x in code for x in ('computed','reactive','render_dependency','render_call')):
            layer='computed／响应式依赖';mechanism='源函数体一致的 getter 及消费者原子修复；未知别名、捕获和复杂子组件仍拒绝'
        elif any(x in code for x in ('dynamic_assignment','method_interface','record_','state_mutation','array_transaction')):
            layer='方法与状态变更';mechanism='完整调用体、标准闭包与普通 data 键证明；跨方法动态键流、未知 this owner 不放行'
        elif any(x in code for x in ('event','class_binding','filter_method','component_registration')):
            layer='事件／组件／类名';mechanism='复用源匹配事件、注册、类名和参数规则；模型输出在同一候选内复核'
        else:
            layer='初始化／生命周期／环境';mechanism='复用默认值、启动阶段、watch 与运行时规则；动态初始化和复杂生命周期仍需独立证明'
        coverage.append({'code':code,'layer':layer,'mechanism':mechanism,'remaining_components':codes[code],
                         'status':'未闭合，保留失败' if codes[code] else '本批有效父版本未再观测，不代表普遍消除'})
    lines=['# 通用修复 v6：两轮根因与真实离线验证','',
      '## 结果口径','',
      f'真实新生成批次仍为 **15/70**。本次只读冻结源码与模型产物，模型调用为 0；离线候选有效通过 {summary["effective_passed"]}/70，不可改写为新的真实模型通过率。',
      f'新增离线通过：{"、".join(new_passes) or "无"}。历史通过回退：{"、".join(lost_passes) or "无"}。',
      f'仍未解决 {len(remaining)} 项；没有将未通过改为人工通过。','',
      '## 根因与落实位置','',
      '- **修复入口遗漏**：模板解析通过便提前返回，源匹配的 getter／事件修饰符修复没有执行。现覆盖可解析模板，并完成有界后续属性修复；采用 HTML namespace/void-element 解析，避免 input 与 SVG 定位混乱。',
      '- **规则与模型衔接断层**：模型输出未经规则复核就进入候选门，恢复默认值等工作被推迟到下一轮甚至预算耗尽。现同一提案内最多 3 次语法→最新静态检查→既有规则；原始输出、逐步哈希另存，最终仍复测和回退。',
      '- **computed 依赖组断裂**：只搬 getter 不改其消费者，或把 reduce 的新建局部累加器误当外部状态修改。现只搬完整源函数体翻译一致的 getter，连同已知源消费者的零参数误调用原子改为值读取；未知调用、参数、依赖缺失仍拒绝。',
      '- **完整调用体修复过窄**：本地记录复制／时间戳被全局闭包白名单误拒。现允许已知 Date/Object/Array 标准引用，并保留源码／目标同名遮蔽检查；不放行未知键和 this owner。',
      '- **原生 DOM 表示差异无法直接由模型模板修复**：受限非空普通 data 的 input :value 使用原生 defaultValue 反射；字符串条件 class 使用原生 className 反射。实际修复 value/class 属性，不删除 DOM 差异。对 v-model、nullable props、未知键、SVG 等仍保守拒绝；模板投影只合并同表达式的实现别名，CSS 属性观察仍严格。','',
      '## 尚未闭合的部分','',
      'remaining.json 逐项保留：真实缺失节点／控件、初始化时序、未知动态键流、内联组件与复杂 getter、语法与事件契约、候选门中新显现诊断。不能把这一轮修订叫作“全部问题彻底修复”。',
      'TaskManager 的模型传输结果未知仍单独保留；未再次调用，已知 Tokens 不代表其实际费用为零。','',
      '## 证据','',
      '- 两轮逐项及全部修复轮次：../analysis_v3_vs_first70_20261119/。',
      '- 本次全部 70 项离线规则与真实浏览器候选门：../composed_v6_final_replay_20261119/。',
      '- 规则／浏览器／编排回归：migration_system/docs/verification/2026-11-19_general_repairs_v1/test-results-composed_v6_verified.json。',
      '- 部分中断的预检目录保留 INTERRUPTED 标记，不混入本轮完整结果。','']
    write_once(OUTPUT/'summary.json',verdict);write_once(OUTPUT/'remaining.json',remaining)
    write_once(OUTPUT/'coverage.json',coverage)
    write_once(OUTPUT/'REPORT.md','\n'.join(lines))
    write_once(OUTPUT/'analysis.ipynb',{'nbformat':4,'nbformat_minor':5,'metadata':{},'cells':[
      {'cell_type':'markdown','metadata':{},'source':'\n'.join(lines)},
      {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
       'source':"import json\nfrom pathlib import Path\nsummary=json.loads(Path('summary.json').read_text(encoding='utf-8'))\nsummary"},
      {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],
       'source':"remaining=json.loads(Path('remaining.json').read_text(encoding='utf-8'))\nremaining"}]})
    write_once(OUTPUT/'SHA256SUMS.txt',''.join(hashed(p)+'  '+p.relative_to(OUTPUT).as_posix()+'\n' for p in sorted(OUTPUT.rglob('*')) if p.is_file()))
    print(json.dumps(verdict,ensure_ascii=True))


if __name__=='__main__':main()
