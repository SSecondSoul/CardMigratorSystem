"""Fresh Puppeteer contexts; no public website or user browser session is controlled."""
import json
from pathlib import Path
import subprocess
from .ssm import _environment
from ..application.service import ServiceError
from ..runtime import browser_executable


class BrowserEvaluator:
    def __init__(self,settings,profile): self.settings,self.profile=settings,profile

    def syntax(self,source,code,*,normalize=False):
        from .syntax import target_syntax
        return target_syntax(self.settings,source,code,normalize=normalize)

    def preflight(self,source):
        return self.evaluate(source,'',{},[],action='source-preflight')

    def evaluate(self,source,code,props,actions,*,action='evaluate'):
        browser=self.profile['browser'];executable=browser_executable(browser)
        if not browser['enabled']:raise ServiceError('browser_disabled')
        if not executable:raise ServiceError('browser_executable_missing')
        request={'repository':str(self.settings.repository_root),'project':str(self.settings.project_root),
            'source':source,'code':code,'props':props,'actions':actions,'browser':browser,'executable':executable,'action':action}
        try:
            proc=subprocess.run(['node',str(self.settings.project_root/'browser/evaluate.mjs')],
                input=json.dumps(request).encode(),capture_output=True,timeout=90,env=_environment(),
                cwd=self.settings.project_root)
            if len(proc.stdout)>40*1024*1024:raise ServiceError('browser_evidence_too_large')
            result=json.loads(proc.stdout)
            if result.get('status') not in ('completed','target_compile_failed'):
                known={'unsupported_source_sfc','external_source_dependencies_unsupported','source_style_preprocessor_unsupported',
                       'source_css_compile_failed','style_capacity_exceeded','dom_node_limit'}
                code=result.get('error')
                raise ServiceError(code if code in known else 'browser_evaluation_blocked')
            return result
        except ServiceError:raise
        except (OSError,ValueError,subprocess.TimeoutExpired):raise ServiceError('browser_unavailable') from None
