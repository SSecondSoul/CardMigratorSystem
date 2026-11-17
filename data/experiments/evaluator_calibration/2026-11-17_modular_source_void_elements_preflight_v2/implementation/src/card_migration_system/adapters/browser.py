"""Fresh Puppeteer contexts; no public website or user browser session is controlled."""
import json
from pathlib import Path
import subprocess
from .ssm import _environment
from ..application.service import ServiceError
from ..runtime import browser_executable

SOURCE_PARSE_CODES={'source_sfc_syntax_error','source_template_syntax_error','source_script_syntax_error'}


class SourceParseError(ServiceError):
    """Bounded source diagnostics for local reports, never raw browser stderr."""
    def __init__(self,code,source,diagnostics):
        super().__init__(code)
        self.diagnostics=[]
        encoded=source.encode('utf-16-le')
        for item in diagnostics[:16] if type(diagnostics) is list else []:
            if type(item) is not dict or item.get('code')!=code or type(item.get('message')) is not str:continue
            location=item.get('location')
            offset=location.get('offset') if type(location) is dict else None
            if type(offset) is not int or not 0<=offset<=len(encoded)//2:continue
            try:prefix=encoded[:offset*2].decode('utf-16-le')
            except UnicodeDecodeError:continue
            at=len(prefix)
            self.diagnostics.append({'code':code,'message':item['message'][:800],
                'location':{'offset':offset,'line':prefix.count('\n')+1,
                    'column':len(prefix.rsplit('\n',1)[-1].encode('utf-16-le'))//2+1},
                'location_precision':item.get('location_precision') if item.get('location_precision') in
                    ('exact','block_start','document_start') else 'document_start',
                'excerpt':source[max(0,at-70):at+170]})
        if not self.diagnostics:
            self.diagnostics=[{'code':code,'message':'源 Vue 解析失败；解析器未提供有效位置，请检查下载的源文件。'}]


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
                if code in SOURCE_PARSE_CODES:raise SourceParseError(code,source,result.get('diagnostics',[]))
                raise ServiceError(code if code in known else 'browser_evaluation_blocked')
            return result
        except ServiceError:raise
        except (OSError,ValueError,subprocess.TimeoutExpired):raise ServiceError('browser_unavailable') from None
