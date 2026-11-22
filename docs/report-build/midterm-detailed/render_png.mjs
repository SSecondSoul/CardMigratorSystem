import fs from'node:fs/promises';import path from'node:path';import{createRequire}from'node:module';import{pathToFileURL}from'node:url';
const r=createRequire(import.meta.url),base='C:/Users/soul/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const mp=r.resolve('@oai/artifact-tool',{paths:[base]});const m=await import(pathToFileURL(mp));
const {Canvas}=r(r.resolve('skia-canvas',{paths:[path.dirname(mp)]}));
const d=await m.DocumentFile.importDocx(await fs.readFile(process.argv[2]));
const dummy=new Canvas(816,1056),ctx=dummy.getContext('2d');
const pages=m.layoutDocumentPages(d,ctx);console.log('PAGECOUNT',pages.length,'images',d.images.items.length);
const images=await m.preloadDocumentImageBitmaps(d,pages);console.log('BITMAPS',images.size);
await fs.mkdir(process.argv[3],{recursive:true});
for(let i=0;i<pages.length;i++){
 const cv=new Canvas(pages[i].widthPx,pages[i].heightPx),cx=cv.getContext('2d');cx.fillStyle='white';cx.fillRect(0,0,cv.width,cv.height);
 m.drawDocumentToCtx(d,cx,{pageIndex:i,clear:false,drawPageOutline:false,imageBitmaps:images});
 await fs.writeFile(path.join(process.argv[3],`page-${i+1}.png`),await cv.png);console.log('PAGE',i+1);
}
