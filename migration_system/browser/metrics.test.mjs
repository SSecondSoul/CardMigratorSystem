import test from 'node:test'
import assert from 'node:assert/strict'
import { PNG } from 'pngjs'
import { pixels } from './metrics.mjs'
const picture=(n)=>{const p=new PNG({width:16,height:16});p.data.fill(n);for(let i=3;i<p.data.length;i+=4)p.data[i]=255;return PNG.sync.write(p)}
test('identical images are 1 / 0, known difference is not hidden',()=>{const a=picture(255), b=picture(0);assert.equal(pixels(a,a).ssim,1);assert.equal(pixels(a,a).different_pixel_ratio,0);assert.equal(pixels(a,b).different_pixel_ratio,1);assert.ok(pixels(a,b).ssim<.01)})
