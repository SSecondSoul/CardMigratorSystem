import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const require=createRequire(import.meta.url);
const mod=require.resolve('@oai/artifact-tool',{paths:['C:/Users/soul/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules']});
const {FileBlob,PresentationFile}=await import(pathToFileURL(mod).href);
const source='C:/Users/soul/Desktop/swu/中期答辩/中期答辩-杨润生（前三节-含数据集构造）-流程动画版.pptx';
const p=await PresentationFile.importPptx(await FileBlob.load(source));
console.log('slides',p.slides.items.length);
for(const i of [10,11]){
 await fs.writeFile(new URL(`./before-${i+1}.png`,import.meta.url),new Uint8Array(await (await p.export({slide:p.slides.items[i],format:'png',scale:1})).arrayBuffer()));
}
console.log('rendered');
