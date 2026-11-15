"""Source-oracle diagnosis contracts; discovery never launches Edge/model."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/experiments/analysis/analytics_source_oracle_audit_v1_20261115'

class AnalyticsSourceOracleUnitTests(unittest.TestCase):
    def test_prepared_scripts_parse_and_variants_are_controls(self):
        body="const assert=require('assert');const p=require('./migration_pipeline/audit_analytics_source_oracle_v1.cjs').prepare('not-created');assert.equal(p.input.pages.length,12);assert.equal(p.input.pairs.length,6);assert(p.binding.boundary.namespaceVariantIsMechanismControlNotSourceCorrection);assert.equal(p.binding.keySites.grid.line,148);assert.equal(p.binding.keySites.points.line,173);assert(p.binding.fullPages.observerOnlyScaffoldChanged);"
        p=subprocess.run(['node','-e',body],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(p.returncode,0,p.stderr)

    def test_first_failed_attempt_is_retained(self):
        f=json.loads((BASE/'failed_implementation.json').read_text(encoding='utf-8'))
        seal=BASE/'native/SHA256SUMS.txt'
        self.assertEqual(hashlib.sha256(seal.read_bytes()).hexdigest(),f['seal_sha256'])
        for line in seal.read_text(encoding='utf-8').splitlines():
            h,p=line.split('  ',1)
            self.assertEqual(hashlib.sha256((seal.parent/p).read_bytes()).hexdigest(),h)
        r=json.loads((seal.parent/'result.json').read_text(encoding='utf-8'))
        self.assertFalse(r['nativeRegistry']['complete'])
        self.assertEqual(r['captures']['analytics_default_vue']['status'],'blocked')
        self.assertEqual(r['captures']['trend_1_original']['status'],'blocked')
        self.assertEqual(hashlib.sha256(f['frozen_source'].encode()).hexdigest(),f['sha256'])

    def test_fixed_fixture_selector_does_not_require_positive_area_polyline(self):
        p=json.loads((BASE/'native_retry/input.json').read_text(encoding='utf-8'))
        pages=[p for p in p['pages'] if p['name'].startswith('trend_1_')]
        self.assertEqual(len(pages),2)
        self.assertTrue(all('polyline' not in p['selectors'] and p['selectors']['legend']=='.chart-legend' for p in pages))


class AnalyticsSourceOracleRecordedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from migration_pipeline import check_analytics_source_oracle_v1 as audit
        cls.audit=audit
        cls.result=audit.read(audit.BASE/'native_retry/result.json')

    def altered(self,fn):
        r=copy.deepcopy(self.result);fn(r)
        for c in r['captures'].values():
            for k in ['styles','extent','componentEvidence','environment']:
                c['repeatObservation'][k]=copy.deepcopy(c[k])
        with self.assertRaises(AssertionError): self.audit.audit_native(r)

    def test_actual_native_diagnosis(self):
        a=self.audit.audit_native(self.result)
        self.assertEqual(a['source_oracle_status'],'blocked_duplicate_sibling_keys')
        self.assertEqual(a['interaction_scenarios_executed'],0)
        self.assertEqual(a['total_native_diagnostics'],42)

    def test_protected_old_files_and_scores(self):
        self.assertEqual(self.audit.audit_protected()['protected'],100)

    def test_five_point_overlap_observed_in_full_source(self):
        e=self.result['captures']['analytics_default_vue']['componentEvidence']['keyAudit']
        self.assertEqual(e['duplicateKeys'],[1,2,3,4,5])
        self.assertEqual(e['gridGroups']+e['pointGroups'],35)

    def test_boundary_one_and_two_points(self):
        a=self.audit.audit_native(self.result)['mechanism_controls']
        self.assertEqual((a[0]['overlap_keys'],a[0]['original_warnings']),([],0))
        self.assertEqual((a[1]['overlap_keys'],a[1]['original_warnings']),([1],2))

    def test_forged_overall_pass_rejected(self):
        self.altered(lambda r:r.update(passed=True,status='evaluated'))

    def test_unknown_owner_rejected(self):
        self.altered(lambda r:r['nativeRegistry']['events'][0].update(attribution='unverified'))

    def test_removed_warning_rejected(self):
        self.altered(lambda r:r['nativeRegistry']['events'].pop(0))

    def test_cleared_source_overlap_rejected(self):
        self.altered(lambda r:r['captures']['analytics_default_vue']['componentEvidence']['keyAudit'].update(duplicateKeys=[]))

    def test_warning_waiver_on_unchanged_pixels_rejected(self):
        self.altered(lambda r:r['comparisons'][2].update(passed=True,eligible=True))

    def test_mechanism_namespace_forgery_rejected(self):
        self.altered(lambda r:r['captures']['trend_7_namespaced']['componentEvidence']['keyAudit'].update(duplicateKeys=[1]))

    def test_lost_layout_difference_rejected(self):
        self.altered(lambda r:r['comparisons'][0].update(styleChanges=[]))

    def test_modified_picture_pin_rejected(self):
        self.altered(lambda r:r['captures']['analytics_default_vue'].update(screenshotSha256='0'*64))

    def test_reused_native_identity_rejected(self):
        self.altered(lambda r:r['nativeRegistry']['entries'][1].update(sessionId=r['nativeRegistry']['entries'][0]['sessionId']))

if __name__=='__main__': unittest.main()
