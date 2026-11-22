"""Fresh Puppeteer contexts; no public website or user browser session is controlled."""
import json
from hashlib import sha256
from pathlib import Path
import subprocess
from .ssm import _environment
from ..application.service import ServiceError
from ..runtime import browser_executable

SOURCE_PARSE_CODES={'source_sfc_syntax_error','source_template_syntax_error','source_script_syntax_error'}


def _default_recovery_binding(settings,request,result,*,initialization=False):
    """Prove the WHOLE proposal is exactly one named source-bound repair.

    Parsing only, no source execution/model/network. A missing witness refuses
    refinement. This is not a template hash with expressions erased: the
    normalized hash covers every byte of template, script and CSS. It cannot
    authorize a changed wrapper, binding, branch, method or style.
    """
    try:
        if initialization and ('props' not in request['source'] or 'inited' not in request['code']):return None
        helper=settings.repository_root/('migration_pipeline/utils/bounded_semantics.cjs' if initialization
                                          else 'migration_pipeline/utils/parent_prop_semantics.cjs')
        payload={'vue':request['source'],'code':request['code'],'repair':True}
        if initialization:payload['action']='source_data_initialization_only'
        proc=subprocess.run(['node',str(helper)],input=json.dumps(payload).encode(),
            capture_output=True,timeout=10,env=_environment(),cwd=settings.repository_root)
        if proc.returncode or len(proc.stdout)>12*1024*1024:return None
        value=json.loads(proc.stdout);normalized=value.get('code');changes=value.get('changes')
        allowed=({'restored_source_pure_prop_data_initialization_phase'} if initialization
                 else {'restored_source_parent_prop_schema','restored_source_parent_prop_defaults'})
        if value.get('error') or not isinstance(normalized,str) or not isinstance(changes,list) or set(changes)-allowed:return None
        digest=lambda text:sha256(text.encode()).hexdigest()
        files={str(p.relative_to(settings.project_root)):sha256(p.read_bytes()).hexdigest()
               for p in sorted((settings.project_root/'browser').glob('*.mjs'))}
        # The source capture, input scope, browser and both pinned runtimes must
        # agree across evaluations. No historical witness is synthesized.
        files['pure_data_initialization_rule' if initialization else 'prop_default_rule']=sha256(helper.read_bytes()).hexdigest()
        if initialization:
            files['engine_manifest']=sha256((settings.repository_root/'MANIFEST.json').read_bytes()).hexdigest()
            for p in sorted((settings.repository_root/'migration_pipeline/utils').glob('*.cjs')):
                files['engine_helper:'+p.name]=sha256(p.read_bytes()).hexdigest()
        for label,p in [('vue',settings.project_root/'frontend/node_modules/vue/dist/vue.global.js'),
                        ('san',settings.repository_root/'node_modules/san/dist/san.dev.js')]:
            files[label]=sha256(p.read_bytes()).hexdigest()
        sides=[result['vue'],result['san']]
        complete=not request['actions'] and all(not s['warnings'] and not s['blocked_requests']
            and not s['evidence_overflow'] and s.get('evidence_limits',{}).get('complete') is True for s in sides)
        return {'contract':('source_pure_data_initialization_runtime_recovery_v1' if initialization
                            else 'source_prop_defaults_runtime_recovery_v1'),'complete':complete,
                'code_sha256':digest(request['code']),'normalized_sha256':digest(normalized),'changes':changes,
                'input_sha256':digest(json.dumps({k:request[k] for k in ('source','props','actions','browser')},sort_keys=True)),
                'runtime_sha256':digest(json.dumps(files,sort_keys=True)+result.get('browser_version',''))}
    except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired):return None


class SourceDiagnosticError(ServiceError):
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
            self.diagnostics=[{'code':code,'message':'源预检查未通过；未提供有效位置，请检查下载的源文件及当前支持范围。'}]


class SourceParseError(SourceDiagnosticError):
    """Source syntax errors, distinct from unsupported semantic contracts."""


class SourceContractError(SourceDiagnosticError):
    """Valid source, but its retained public contract is not implemented."""


class BrowserEvaluator:
    def __init__(self,settings,profile): self.settings,self.profile=settings,profile

    def syntax(self,source,code,*,normalize=False):
        from .syntax import target_syntax
        return target_syntax(self.settings,source,code,normalize=normalize)

    def preflight(self,source):
        return self.evaluate(source,'',{},[],action='source-preflight')

    def source_contracts(self,source):
        return self.evaluate(source,'',{},[],action='source-contracts')

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
                if code=='source_dynamic_key_contract_unsupported':raise SourceContractError(code,source,result.get('diagnostics',[]))
                raise ServiceError(code if code in known else 'browser_evaluation_blocked')
            if action=='evaluate' and result.get('status')=='completed':
                result['default_recovery_binding']=_default_recovery_binding(self.settings,request,result)
                result['initialization_recovery_binding']=_default_recovery_binding(self.settings,request,result,initialization=True)
            return result
        except ServiceError:raise
        except (OSError,ValueError,subprocess.TimeoutExpired):raise ServiceError('browser_unavailable') from None
