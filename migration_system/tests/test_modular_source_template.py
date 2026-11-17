"""HTML-aware source parsing and bounded failure feedback; no cloud model calls."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from test_modular_system import ModularFixture,PROJECT,SOURCE,SAN
from card_migration_system.adapters.browser import BrowserEvaluator,SourceParseError
from card_migration_system.application.service import ServiceError
from card_migration_system.config import load_settings
from card_migration_system.runtime import profile

FROZEN=PROJECT.parent/'data/experiments/evaluator_calibration/2026-11-17_modular_source_void_elements_preflight_v1/frozen'


def source_sfc(body):
    return '<template>\n<section>'+body+'</section>\n</template>\n<script>module.exports={}</script>'


def node_preflight(source):
    request={'repository':str(PROJECT/'engine'),'project':str(PROJECT),'source':source,'action':'source-preflight'}
    process=subprocess.run(['node',str(PROJECT/'browser/evaluate.mjs')],input=json.dumps(request).encode(),
        capture_output=True,timeout=30,cwd=PROJECT)
    return process.returncode,json.loads(process.stdout)


class SourceTemplateTests(unittest.TestCase):
    def test_input_img_br_hr_and_other_void_elements_support_both_legal_spellings(self):
        for tag,attrs in (('input','type="text" value="a"'),('img','alt="example"'),('br',''),('hr',''),('wbr','')):
            with self.subTest(tag=tag):
                a,result=node_preflight(source_sfc(f'<{tag} {attrs}>'))
                b,closed=node_preflight(source_sfc(f'<{tag} {attrs}/>'))
                self.assertEqual((a,b),(0,0),(result,closed))
                self.assertEqual(result['source']['source_parser'],'vue_compiler_dom_html_v1')
                self.assertEqual(result['source']['tree'],closed['source']['tree'])
                section=result['source']['tree']['children'][0]
                self.assertTrue(section['children'][0]['label'].startswith(tag+'|'))

    def test_void_nodes_are_siblings_and_comment_text_does_not_invent_nodes(self):
        status,result=node_preflight(source_sfc('before<input>middle<img alt="x"><br><!-- <input> --><span>end</span>'))
        self.assertEqual(status,0,result)
        nodes=result['source']['tree']['children'][0]['children']
        self.assertEqual([n['label'].split('|')[0] for n in nodes],['#text:before','input','#text:middle','img','br','span'])

    def test_genuinely_missing_or_mismatched_nonvoid_tags_still_block(self):
        for body in ('<div><span></div>','<div>','<textarea>text','<strong>bad</aside>'):
            with self.subTest(body=body):
                code,result=node_preflight(source_sfc(body))
                self.assertNotEqual(code,0)
                self.assertEqual(result['status'],'blocked')
                self.assertIn(result['error'],('source_template_syntax_error','source_sfc_syntax_error'))
                self.assertTrue(result['diagnostics'])
                self.assertIn('location',result['diagnostics'][0])
                self.assertNotEqual(result['error'],'browser_evaluation_blocked')

    def test_script_syntax_is_reported_separately_without_executing_source(self):
        broken=source_sfc('<input>').replace('module.exports={}','throw Error("MUST_NOT_EXECUTE");module.exports={x:}')
        code,result=node_preflight(broken)
        self.assertNotEqual(code,0)
        self.assertEqual(result['error'],'source_script_syntax_error')
        finding=result['diagnostics'][0]
        self.assertGreater(finding['location']['offset'],broken.index('<script>'))
        self.assertEqual(finding['location_precision'],'exact')
        valid=broken.replace('{x:}','{}')
        self.assertEqual(node_preflight(valid)[0],0)

    def test_UTF16_diagnostic_positions_are_absolute_even_with_emoji(self):
        source=source_sfc('图标😀<input><span>broken')
        _,result=node_preflight(source)
        for finding in result['diagnostics']:
            location=finding['location'];prefix=source.encode('utf-16-le')[:location['offset']*2].decode('utf-16-le')
            self.assertEqual(location['line'],prefix.count('\n')+1)
            self.assertEqual(location['column'],len(prefix.rsplit('\n',1)[-1].encode('utf-16-le'))//2+1)
            self.assertTrue(finding['excerpt'])

    @unittest.skipUnless((FROZEN/'source.vue').is_file(), 'Historical experiment corpus is not part of the standalone distribution')
    def test_frozen_InvoiceLineEditor_preflight_passes_without_altering_original_bytes(self):
        original=(FROZEN/'source.vue').read_bytes()
        self.assertEqual(sha256(original).hexdigest(),'9b50005a20314dd9c1f52db9496c6092d8f2838958955be0fa0350db7c77a8df')
        code,result=node_preflight(original.decode())
        self.assertEqual(code,0,result)
        self.assertEqual(result['status'],'completed')
        self.assertEqual((FROZEN/'source.vue').read_bytes(),original)


class SourceDiagnosticAdapterTests(unittest.TestCase):
    def setUp(self):
        self.settings=load_settings(project_root=PROJECT,environ={})
        self.browser=BrowserEvaluator(self.settings,profile(self.settings))

    def test_real_source_error_crosses_adapter_with_specific_code_and_location(self):
        with self.assertRaises(SourceParseError) as caught:self.browser.preflight(source_sfc('<div>'))
        self.assertIn(caught.exception.code,('source_template_syntax_error','source_sfc_syntax_error'))
        self.assertTrue(caught.exception.diagnostics[0]['location'])

    def test_unknown_browser_errors_remain_generic_and_do_not_echo_raw_stderr(self):
        process=subprocess.CompletedProcess([],2,stdout=json.dumps({'status':'blocked','error':'SECRET_SENTINEL'}).encode(),stderr=b'SECRET_SENTINEL')
        with patch('card_migration_system.adapters.browser.subprocess.run',return_value=process):
            with self.assertRaises(ServiceError) as caught:self.browser.preflight(SOURCE)
        self.assertEqual(caught.exception.code,'browser_evaluation_blocked')
        self.assertNotIn('SECRET_SENTINEL',str(caught.exception))

    def test_invalid_diagnostic_fields_are_discarded_and_location_excerpt_are_source_bound(self):
        source='first\n😀<span>'
        result=SourceParseError('source_template_syntax_error',source,[{'code':'source_template_syntax_error',
            'message':'missing end tag','location':{'offset':9,'line':999,'column':999},
            'excerpt':'FOREIGN_SECRET','secret':'FOREIGN_SECRET','location_precision':'exact'}])
        item=result.diagnostics[0]
        self.assertEqual(item['location'],{'offset':9,'line':2,'column':4})
        self.assertEqual(item['excerpt'],source)
        self.assertNotIn('FOREIGN_SECRET',json.dumps(item))
        fallback=SourceParseError('source_template_syntax_error',source,[{'code':'other','message':'bad'}])
        self.assertNotIn('location',fallback.diagnostics[0])


class SourcePreflightGraphTests(ModularFixture,unittest.TestCase):
    def blocked_source(self):
        source=source_sfc('<input><span>broken')
        self.source=self.base.create_input({'filename':'Broken.vue','source':source})
        settings=load_settings(project_root=PROJECT,environ={})
        self.service.browser=BrowserEvaluator(settings,profile(settings))
        key=self.enqueue();result=self.run_graph(key)
        return source,key,result

    def test_invalid_source_stops_before_generation_and_diagnostics_reach_report_and_failure_file(self):
        source,key,result=self.blocked_source()
        self.assertEqual(result['status'],'blocked')
        self.assertIn(result['stop_reason'],('source_template_syntax_error','source_sfc_syntax_error'))
        self.assertEqual(self.model.calls,0);self.assertEqual(result['model_calls_started'],0)
        self.assertEqual(result['usage']['known_total_tokens'],0)
        self.assertIsNone(result['assessment'])
        diagnostics=result['state']['failure_diagnostics']
        self.assertTrue(diagnostics[0]['location'])
        failure=next(f for f in result['files'] if f['kind']=='failure')
        payload=self.service.cached(key,failure['relative_path'].split(key+'/')[1])
        self.assertEqual(payload['diagnostics'],diagnostics)
        self.assertEqual(payload['source_sha256'],sha256(source.encode()).hexdigest())
        self.assertNotIn('excerpt',json.dumps(payload['trace']))
        self.assertIsNone(self.service.cached(key,'revisions/0.json'))

    def test_built_workbench_displays_actual_blocked_report_line_column_and_escaped_excerpt(self):
        from dataclasses import replace
        from threading import Thread
        from werkzeug.serving import make_server
        from test_modular_workbench import Quiet
        from card_migration_system.interfaces.api.app import create_app
        from card_migration_system.runtime import browser_executable
        _,_,result=self.blocked_source()
        settings=replace(self.settings,project_root=PROJECT)
        app=create_app(settings,write_token='local-test-token-at-least-24-characters')
        server=make_server('127.0.0.1',0,app,request_handler=Quiet)
        app.config['ALLOWED_PORT']=server.server_port
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            request={'url':f'http://127.0.0.1:{server.server_port}/','error_code':result['stop_reason'],
                'executable':browser_executable(profile(settings)['browser'])}
            process=subprocess.run(['node',str(PROJECT/'browser/source-diagnostic-smoke.mjs')],
                input=json.dumps(request).encode(),capture_output=True,timeout=60,cwd=PROJECT)
            self.assertEqual(process.returncode,0,process.stderr.decode()[:1000])
            observed=json.loads(process.stdout)
            self.assertEqual(observed['page_errors'],[])
            for key in ('code_visible','location_visible','zero_model_visible','excerpt_as_text'):
                self.assertTrue(observed[key],observed)
        finally:
            server.shutdown();thread.join(timeout=5);server.server_close();app.extensions['migration_service'].close()


class VoidElementBrowserTests(unittest.TestCase):
    def test_real_browser_renders_and_compares_void_elements_without_source_rewrites(self):
        # Isolate void-element parsing from the separate framework-specific
        # serialization of input.value attributes (no DOM policy relaxation).
        source=source_sfc('<input placeholder="amount"><img alt="example"><br><span>end</span>')
        target=source.replace('module.exports={}',"const san=require('san');module.exports=san.defineComponent({})")
        settings=load_settings(project_root=PROJECT,environ={})
        data=BrowserEvaluator(settings,profile(settings)).evaluate(source,target,{},[])
        self.assertEqual(data['status'],'completed')
        self.assertEqual(data['vue']['errors'],[]);self.assertEqual(data['san']['errors'],[])
        self.assertEqual(data['source_ast']['tree'],data['target_ast']['tree'])
        from card_migration_system.stages.structure import tree_distance,tree_differences
        left=data['vue']['snapshots'][0]['dom'];right=data['san']['snapshots'][0]['dom']
        self.assertEqual(tree_distance(left,right)['distance'],0,tree_differences(left,right))


if __name__=='__main__':unittest.main()
