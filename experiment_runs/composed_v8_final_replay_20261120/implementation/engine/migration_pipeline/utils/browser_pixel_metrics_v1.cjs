/* Dependency-free PNG RGB/RGBA8 codec and explicitly defined visual metrics.
 * SSIM: valid 11x11 Gaussian (sigma 1.5), population moments, BT.601 luma,
 * L=255 K1=.01 K2=.03. No resize, registration, mask or contrast correction.
 */
'use strict';
const zlib=require('zlib');
const signature=Buffer.from([137,80,78,71,13,10,26,10]);
function crc32(bytes){let c=0xffffffff;for(const v of bytes){c^=v;for(let k=0;k<8;k++)c=(c>>>1)^((c&1)?0xedb88320:0);}return (c^0xffffffff)>>>0;}
function chunk(type,data){const t=Buffer.from(type),n=Buffer.alloc(4),crc=Buffer.alloc(4);n.writeUInt32BE(data.length);crc.writeUInt32BE(crc32(Buffer.concat([t,data])));return Buffer.concat([n,t,data,crc]);}
function encodePNG(width,height,rgba){
  if(!Number.isInteger(width)||!Number.isInteger(height)||width<1||height<1||width*height>4000000||rgba.length!==width*height*4)throw Error('Invalid RGBA dimensions');
  const header=Buffer.alloc(13);header.writeUInt32BE(width);header.writeUInt32BE(height,4);header[8]=8;header[9]=6;
  const rows=Buffer.alloc(height*(width*4+1));for(let y=0;y<height;y++)Buffer.from(rgba.buffer,rgba.byteOffset+y*width*4,width*4).copy(rows,y*(width*4+1)+1);
  return Buffer.concat([signature,chunk('IHDR',header),chunk('IDAT',zlib.deflateSync(rows)),chunk('IEND',Buffer.alloc(0))]);
}
function decodePNG(png){
  if(!png.subarray(0,8).equals(signature))throw Error('Invalid PNG signature');
  let offset=8,width,height,channels,ended=false,seenData=false;const data=[];
  while(offset<png.length){
    if(offset+12>png.length)throw Error('Truncated PNG');const n=png.readUInt32BE(offset),end=offset+12+n;
    if(end>png.length)throw Error('Truncated PNG chunk');const type=png.toString('ascii',offset+4,offset+8),body=png.subarray(offset+8,offset+8+n);
    if(crc32(png.subarray(offset+4,offset+8+n))!==png.readUInt32BE(offset+8+n))throw Error('PNG CRC mismatch');
    if(type==='IHDR'){
      if(width!==undefined||offset!==8||n!==13)throw Error('Invalid PNG header');width=body.readUInt32BE();height=body.readUInt32BE(4);
      if(!width||!height||width*height>4000000||body[8]!==8||![2,6].includes(body[9])||body[10]||body[11]||body[12])throw Error('Unsupported PNG format (RGB/RGBA8 non-interlaced only)');
      channels=body[9]===6?4:3;
    }else if(type==='IDAT'){if(!channels)throw Error('Missing PNG header');data.push(body);seenData=true;}
    else if(type==='IEND'){if(n||!seenData)throw Error('Invalid PNG end');ended=true;offset=end;break;}
    else if(type==='tRNS'||(type[0]===type[0].toUpperCase()&&type!=='PLTE'))throw Error('Unsupported PNG chunk '+type);
    offset=end;
  }
  if(!ended||offset!==png.length)throw Error('PNG end/trailing data invalid');const stride=width*channels;
  const packed=zlib.inflateSync(Buffer.concat(data),{maxOutputLength:height*(stride+1)});
  if(packed.length!==height*(stride+1))throw Error('PNG scanline size mismatch');const raw=Buffer.alloc(height*stride);
  const paeth=(a,b,c)=>{const p=a+b-c,pa=Math.abs(p-a),pb=Math.abs(p-b),pc=Math.abs(p-c);return pa<=pb&&pa<=pc?a:pb<=pc?b:c;};
  for(let y=0;y<height;y++){
    const filter=packed[y*(stride+1)];if(filter>4)throw Error('Unsupported PNG filter');
    for(let x=0;x<stride;x++){
      const i=y*stride+x,a=x>=channels?raw[i-channels]:0,b=y?raw[i-stride]:0,c=y&&x>=channels?raw[i-stride-channels]:0;
      raw[i]=(packed[y*(stride+1)+1+x]+[0,a,b,Math.floor((a+b)/2),paeth(a,b,c)][filter])&255;
    }
  }
  const rgba=Buffer.alloc(width*height*4);for(let i=0;i<width*height;i++){for(let c=0;c<3;c++)rgba[i*4+c]=raw[i*channels+c];rgba[i*4+3]=channels===4?raw[i*4+3]:255;}
  return {width,height,rgba};
}
function ssim(a,b,width,height){
  if(width<11||height<11)throw Error('SSIM needs at least 11x11 pixels');
  const kernel=Array.from({length:11},(_,i)=>Math.exp(-((i-5)**2)/(2*1.5**2))),sum=kernel.reduce((x,y)=>x+y);
  for(let i=0;i<11;i++)kernel[i]/=sum;
  const w=width-10,h=height-10;
  function blur(input){
    const horizontal=new Float64Array(w*height),out=new Float64Array(w*h);
    for(let y=0;y<height;y++)for(let x=0;x<w;x++){let v=0;for(let k=0;k<11;k++)v+=kernel[k]*input[y*width+x+k];horizontal[y*w+x]=v;}
    for(let y=0;y<h;y++)for(let x=0;x<w;x++){let v=0;for(let k=0;k<11;k++)v+=kernel[k]*horizontal[(y+k)*w+x];out[y*w+x]=v;}return out;
  }
  const aa=Float64Array.from(a,v=>v*v),bb=Float64Array.from(b,v=>v*v),ab=Float64Array.from(a,(v,i)=>v*b[i]);
  const ma=blur(a),mb=blur(b),va=blur(aa),vb=blur(bb),cov=blur(ab);let score=0;
  for(let i=0;i<ma.length;i++){
    const x=ma[i],y=mb[i],vx=Math.max(0,va[i]-x*x),vy=Math.max(0,vb[i]-y*y),xy=cov[i]-x*y;
    score+=((2*x*y+6.5025)*(2*xy+58.5225))/((x*x+y*y+6.5025)*(vx+vy+58.5225));
  }return score/ma.length;
}
function compareRGBA(a,b,{pixelTolerance=0}={}){
  if(!Number.isInteger(pixelTolerance)||pixelTolerance<0||pixelTolerance>255)throw Error('Invalid pixel tolerance');
  if(a.width!==b.width||a.height!==b.height)throw Error('Image size mismatch; never auto-resize');
  const n=a.width*a.height;if(a.rgba.length!==n*4||b.rgba.length!==n*4)throw Error('Invalid pixel buffer');
  const la=new Float64Array(n),lb=new Float64Array(n),diff=Buffer.alloc(n*4);let changed=0,absolute=0,maxDelta=0;
  for(let i=0;i<n;i++){
    let delta=0;for(let c=0;c<4;c++){
      if(c===3&&(a.rgba[i*4+c]!==255||b.rgba[i*4+c]!==255))throw Error('Only opaque screenshots supported');
      const d=Math.abs(a.rgba[i*4+c]-b.rgba[i*4+c]);delta=Math.max(delta,d);if(c<3)absolute+=d;
    }
    maxDelta=Math.max(maxDelta,delta);if(delta>pixelTolerance){changed++;diff[i*4]=255;diff[i*4+1]=255-delta;}
    diff[i*4+3]=255;
    la[i]=.299*a.rgba[i*4]+.587*a.rgba[i*4+1]+.114*a.rgba[i*4+2];lb[i]=.299*b.rgba[i*4]+.587*b.rgba[i*4+1]+.114*b.rgba[i*4+2];
  }
  return {width:a.width,height:a.height,totalPixels:n,changedPixels:changed,changedPixelRatio:changed/n,
    rgbMeanAbsoluteError:absolute/(3*n),maxChannelDelta:maxDelta,ssim:ssim(la,lb,a.width,a.height),diff};
}
module.exports={crc32,encodePNG,decodePNG,compareRGBA,ssim};
