"""Append precise syntax-first capture counts without rewriting frozen evidence."""
from analyze_coverage import read,write_once,hashed,RUNS


def main():
    replay=RUNS/'composed_v8_final_replay_20261120';review=RUNS/'composed_v8_review_20261120'
    assessments=list(replay.glob('*/baseline-assessment.json'))
    captures=list(replay.glob('*/baseline-browser.json'))
    syntax_failed=sum(read(p).get('syntax',{}).get('status')=='fail' for p in assessments)
    note=f'''# v8 捕获范围精确说明

原报告“69 份代码重新静态检查和真实浏览器捕获”描述的是语法优先的整体流程，不应理解为每份都有浏览器截图。精确范围为：

- {len(assessments)} 份有代码产物重新评估。
- {len(captures)} 份基线保存真实浏览器捕获。
- {syntax_failed} 份脚本语法失败，按生产语法优先门停止，没有浏览器捕获。
- TaskManager 无完整代码，不重试未知调用，也没有浏览器捕获。

35/70 的有效离线结果及全部原始证据、哈希、失败不变。本说明追加保存，不覆盖原报告、Notebook 或原始 SHA256SUMS。`analysis_verified.ipynb` 在原 Notebook 前加本说明，供后续阅读使用。
'''
    write_once(review/'CAPTURE_SCOPE.md',note)
    notebook=read(review/'analysis.ipynb')
    notebook['cells'].insert(0,{'cell_type':'markdown','metadata':{},'source':note})
    write_once(review/'analysis_verified.ipynb',notebook)
    write_once(review/'ADDENDUM_SHA256SUMS.txt',''.join(hashed(review/name)+'  '+name+'\n'
        for name in ('CAPTURE_SCOPE.md','analysis_verified.ipynb')))


if __name__=='__main__':main()
