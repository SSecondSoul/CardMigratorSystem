"""Pure metric/contract tests; browser evidence tests read the separately run calibration.
No hidden browser launches or dependency installation during unittest discovery.
"""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'data/experiments/analysis/controlled_browser_pixel_v1_20261115'


def node(code):
    proc = subprocess.run(['node', '-'], input=code, cwd=ROOT, capture_output=True,
                          text=True, encoding='utf-8', timeout=30)
    if proc.returncode:
        raise AssertionError(proc.stderr)
    return json.loads(proc.stdout)


class PixelMetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = node(r"""
const m=require('./migration_pipeline/utils/browser_pixel_metrics_v1.cjs');
const e=require('./migration_pipeline/run_controlled_browser_pixel_v1.cjs');
const image=(w,h,r,g,b)=>({width:w,height:h,rgba:Buffer.from(Array.from({length:w*h},()=>[r,g,b,255]).flat())});
const a=image(16,16,100,100,100),b=image(16,16,110,110,110),black=image(16,16,0,0,0),white=image(16,16,255,255,255);
const clean=result=>{delete result.diff;return result;};
const rejects=fn=>{try{fn();return false;}catch(_e){return true;}};
const png=m.encodePNG(a.width,a.height,a.rgba),decoded=m.decodePNG(png),corrupt=Buffer.from(png);corrupt[corrupt.length-1]^=1;
const one=image(16,16,100,100,100);one.rgba[0]=101;
const transparent=image(16,16,100,100,100);transparent.rgba[3]=0;
console.log(JSON.stringify({identical:clean(m.compareRGBA(a,a)),uniform:clean(m.compareRGBA(a,b)),
 extreme:clean(m.compareRGBA(black,white)),one:clean(m.compareRGBA(a,one)),tolerance:clean(m.compareRGBA(a,one,{pixelTolerance:1})),
 codec:decoded.width===16&&decoded.height===16&&decoded.rgba.equals(a.rgba),crc:rejects(()=>m.decodePNG(corrupt)),
 size:rejects(()=>m.compareRGBA(a,image(17,16,0,0,0))),small:rejects(()=>m.compareRGBA(image(8,8,0,0,0),image(8,8,0,0,0))),
 alpha:rejects(()=>m.compareRGBA(a,transparent)),nan:rejects(()=>m.compareRGBA(a,a,{pixelTolerance:NaN})),
 contract:rejects(()=>e.validate({})),noThresholds:rejects(()=>e.validate({pages:[{name:'a',html:'x',selectors:{x:'#x'}}],pairs:[{source:'a',target:'a'}]})),
 styles:e.styleDifferences({title:{rect:{x:1},color:'red'}},{title:{rect:{x:2},color:'blue'}}),
 missing:e.styleDifferences({a:{rect:{}}},{}),env:e.ENV}));
""")

    def test_identical_pixels(self):
        self.assertEqual(self.values['identical']['changedPixels'], 0)
        self.assertAlmostEqual(self.values['identical']['ssim'], 1, places=10)

    def test_uniform_ssim_analytic_formula(self):
        expected = (2 * 100 * 110 + 6.5025) / (100 ** 2 + 110 ** 2 + 6.5025)
        self.assertAlmostEqual(self.values['uniform']['ssim'], expected, places=9)
        self.assertEqual(self.values['uniform']['rgbMeanAbsoluteError'], 10)

    def test_extreme_color_full_image_difference(self):
        self.assertEqual(self.values['extreme']['changedPixelRatio'], 1)
        self.assertEqual(self.values['extreme']['rgbMeanAbsoluteError'], 255)
        self.assertLess(self.values['extreme']['ssim'], .001)

    def test_single_pixel_denominator(self):
        self.assertEqual(self.values['one']['changedPixels'], 1)
        self.assertEqual(self.values['one']['changedPixelRatio'], 1 / 256)
        self.assertEqual(self.values['one']['rgbMeanAbsoluteError'], 1 / 768)

    def test_tolerance_does_not_change_raw_error(self):
        self.assertEqual(self.values['tolerance']['changedPixels'], 0)
        self.assertEqual(self.values['tolerance']['rgbMeanAbsoluteError'], 1 / 768)

    def test_png_roundtrip(self):
        self.assertTrue(self.values['codec'])

    def test_corrupt_png_rejected(self):
        self.assertTrue(self.values['crc'])

    def test_sizes_never_rescaled(self):
        self.assertTrue(self.values['size'])

    def test_ssim_undersized_image_rejected(self):
        self.assertTrue(self.values['small'])

    def test_transparency_not_silently_ignored(self):
        self.assertTrue(self.values['alpha'])

    def test_nonfinite_tolerance_rejected(self):
        self.assertTrue(self.values['nan'])

    def test_explicit_inputs_required(self):
        self.assertTrue(self.values['contract'])
        self.assertTrue(self.values['noThresholds'])

    def test_key_style_and_rect_comparison(self):
        self.assertEqual({r['property'] for r in self.values['styles']}, {'rect', 'color'})
        self.assertEqual(self.values['missing'][0]['property'], 'mapping')

    def test_fixed_protocol_not_os_dark_theme(self):
        env = self.values['env']
        self.assertEqual((env['width'], env['height'], env['deviceScaleFactor']), (640, 480, 1))
        self.assertEqual(env['theme'], 'light')
        self.assertEqual(env['timezone'], 'Asia/Shanghai')


class IndependentMetricReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = node(r"""
const m=require('./migration_pipeline/utils/browser_pixel_metrics_v1.cjs'),z=require('zlib');
function chunk(type,data){const t=Buffer.from(type),n=Buffer.alloc(4),c=Buffer.alloc(4);n.writeUInt32BE(data.length);c.writeUInt32BE(m.crc32(Buffer.concat([t,data])));return Buffer.concat([n,t,data,c]);}
const header=channels=>{const b=Buffer.alloc(13);b.writeUInt32BE(16);b.writeUInt32BE(16,4);b[8]=8;b[9]=channels===4?6:2;return b;};
const codec=[];
for(const channels of [3,4])for(let filter=0;filter<5;filter++){
 const stride=16*channels,raw=Buffer.from(Array.from({length:16*stride},(_,i)=>i%channels===3?255:(i*17+31)%256)),rows=Buffer.alloc(16*(stride+1));
 for(let y=0;y<16;y++){rows[y*(stride+1)]=filter;for(let x=0;x<stride;x++){
  const i=y*stride+x,a=x>=channels?raw[i-channels]:0,b=y?raw[i-stride]:0,c=y&&x>=channels?raw[i-stride-channels]:0,p=a+b-c;
  const distances=[Math.abs(p-a),Math.abs(p-b),Math.abs(p-c)],paeth=distances[0]<=distances[1]&&distances[0]<=distances[2]?a:distances[1]<=distances[2]?b:c;
  rows[y*(stride+1)+1+x]=(raw[i]-[0,a,b,Math.floor((a+b)/2),paeth][filter]+256)%256;
 }}
 const png=Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',header(channels)),chunk('IDAT',z.deflateSync(rows)),chunk('IEND',Buffer.alloc(0))]);
 const out=m.decodePNG(png);let same=true;for(let i=0;i<256;i++)for(let c=0;c<4;c++)if(out.rgba[4*i+c]!== (c===3&&channels===3?255:raw[channels*i+c]))same=false;
 codec.push({channels,filter,same});
}
const a=Float64Array.from({length:256},(_,i)=>(i*17+i%16*3)%256),b=Float64Array.from(a,(v,i)=>Math.max(0,Math.min(255,v+(i%5-2)*9)));
const k=Array.from({length:11},(_,i)=>Math.exp(-((i-5)**2)/4.5)),total=k.reduce((a,b)=>a+b);for(let i=0;i<11;i++)k[i]/=total;
let reference=0,n=0;
for(let y=0;y<6;y++)for(let x=0;x<6;x++){
 let u=0,v=0,aa=0,bb=0,ab=0;
 for(let j=0;j<11;j++)for(let i=0;i<11;i++){const w=k[i]*k[j],p=a[(y+j)*16+x+i],q=b[(y+j)*16+x+i];u+=w*p;v+=w*q;aa+=w*p*p;bb+=w*q*q;ab+=w*p*q;}
 reference+=((2*u*v+6.5025)*(2*(ab-u*v)+58.5225))/((u*u+v*v+6.5025)*(Math.max(0,aa-u*u)+Math.max(0,bb-v*v)+58.5225));n++;
}
console.log(JSON.stringify({codec,ssim:m.ssim(a,b,16,16),reverse:m.ssim(b,a,16,16),reference:reference/n}));
""")

    def test_all_five_png_filters_rgb_and_rgba(self):
        self.assertEqual(len(self.values['codec']), 10)
        self.assertTrue(all(row['same'] for row in self.values['codec']))

    def test_ssim_against_independent_direct_two_dimensional_reference(self):
        self.assertAlmostEqual(self.values['ssim'], self.values['reference'], places=12)

    def test_ssim_symmetry(self):
        self.assertAlmostEqual(self.values['ssim'], self.values['reverse'], places=12)


class RecordedBrowserCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Missing browser evidence is a failure, not a skip or a migration pass.
        cls.summary = json.loads((EVIDENCE / 'run2/calibration.json').read_text(encoding='utf-8'))
        cls.result = json.loads((EVIDENCE / 'run2/result.json').read_text(encoding='utf-8'))

    def test_all_nine_calibration_controls(self):
        self.assertTrue(self.summary['calibrationPassed'])
        self.assertEqual(len(self.summary['checks']), 9)
        self.assertTrue(all(self.summary['checks'].values()))

    def test_native_runtime_fixtures_are_not_component_acceptance(self):
        self.assertFalse(self.summary['componentPassClaimed'])
        self.assertFalse(self.result['boundary']['componentCompiler'])
        self.assertFalse(self.result['boundary']['productionIntegrated'])
        self.assertFalse(self.summary['productionThresholdsSelected'])

    def test_saved_screenshots_and_diff_images(self):
        self.assertEqual(len(self.result['captures']), 9)
        for name in self.result['captures']:
            for suffix in ['.png', '-repeat.png']:
                self.assertTrue((EVIDENCE / 'run2' / (name + suffix)).is_file())
        for pair in self.result['comparisons']:
            self.assertTrue((EVIDENCE / 'run2' / pair['diff']).is_file())

    def test_errors_network_and_instability_not_passed(self):
        captures = self.result['captures']
        self.assertFalse(captures['runtime_error']['clean'])
        self.assertFalse(captures['blocked_network']['clean'])
        self.assertFalse(captures['unstable']['stable'])
        self.assertFalse(self.result['passed'])

    def test_repeat_run_determinism_for_eight_nonmoving_pages(self):
        other = json.loads((EVIDENCE / 'repeat/result.json').read_text(encoding='utf-8'))
        for name, capture in self.result['captures'].items():
            if name != 'unstable':
                self.assertEqual(capture['screenshotSha256'], other['captures'][name]['screenshotSha256'])
                self.assertEqual(capture['styles'], other['captures'][name]['styles'])
        self.assertEqual(self.result['browser'], other['browser'])


class RecordedFailClosedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = json.loads((EVIDENCE / 'failure_modes/failure_modes.json').read_text(encoding='utf-8'))

    def test_missing_browser_not_skipped_as_pass(self):
        self.assertTrue(self.values['checks']['missing_browser']['checkPassed'])

    def test_readiness_not_assumed(self):
        self.assertTrue(self.values['checks']['not_ready']['checkPassed'])

    def test_missing_selector_not_silently_omitted(self):
        self.assertTrue(self.values['checks']['missing_selector']['checkPassed'])

    def test_no_silent_crop_of_overflow(self):
        self.assertTrue(self.values['checks']['overflow']['checkPassed'])

    def test_existing_evidence_never_overwritten(self):
        self.assertTrue(self.values['checks']['overwrite']['checkPassed'])


if __name__ == '__main__':
    unittest.main()
