import { PNG } from 'pngjs'

// Uniform 8x8-window luminance SSIM. No automatic masking or image resizing.
export function pixels(first, second) {
  const a = PNG.sync.read(first), b = PNG.sync.read(second)
  if (a.width !== b.width || a.height !== b.height) throw new Error('screenshot_size_mismatch')
  const heat = new PNG({width:a.width,height:a.height}); let different=0, sum=0, windows=0
  const lum = (p,i) => .2126*p[i]+.7152*p[i+1]+.0722*p[i+2]
  for(let y=0;y<a.height;y+=8) for(let x=0;x<a.width;x+=8) {
    const av=[],bv=[]
    for(let yy=y;yy<Math.min(y+8,a.height);yy++) for(let xx=x;xx<Math.min(x+8,a.width);xx++) {
      const i=(yy*a.width+xx)*4
      av.push(lum(a.data,i)); bv.push(lum(b.data,i))
      const delta=Math.max(...[0,1,2,3].map(k=>Math.abs(a.data[i+k]-b.data[i+k])))
      if(delta>10) different++
      heat.data[i]=delta>10?255:a.data[i]/4; heat.data[i+1]=delta>10?0:a.data[i+1]/4
      heat.data[i+2]=delta>10?0:a.data[i+2]/4;heat.data[i+3]=255
    }
    const n=av.length, ma=av.reduce((s,v)=>s+v,0)/n, mb=bv.reduce((s,v)=>s+v,0)/n
    const va=av.reduce((s,v)=>s+(v-ma)**2,0)/n, vb=bv.reduce((s,v)=>s+(v-mb)**2,0)/n
    const cov=av.reduce((s,v,i)=>s+(v-ma)*(bv[i]-mb),0)/n
    sum+=((2*ma*mb+6.5025)*(2*cov+58.5225))/((ma*ma+mb*mb+6.5025)*(va+vb+58.5225));windows++
  }
  return {ssim:sum/windows, different_pixel_ratio:different/(a.width*a.height),
    heatmap:PNG.sync.write(heat).toString('base64'),width:a.width,height:a.height,
    algorithm:'luminance_uniform_8x8_population_ssim_v1',channel_threshold:10}
}
