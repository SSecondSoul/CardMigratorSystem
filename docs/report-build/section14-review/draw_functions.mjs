import fs from'node:fs/promises';import{createRequire}from'node:module';import{fileURLToPath}from'node:url';
const r=createRequire(import.meta.url),sharp=r(r.resolve('sharp',{paths:['C:/Users/soul/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules']}));
const items=[['任务创建','上传源码与填写任务'],['迁移运行','查看进度与自动修复'],['结果查看','检查差异与修复记录'],['文件与历史记录','下载结果与查找任务'],['账号管理','管理本人或受邀账号'],['运行状态查看','查看服务与模型信息']];
const text=(s,x,y,size=24)=>`<text x="${x}" y="${y}" text-anchor="middle" font-family="SimSun,宋体,serif" font-size="${size}" fill="black">${s}</text>`;
let s='<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="405"><rect width="1000" height="405" fill="white"/><g fill="none" stroke="black" stroke-width="1.8"><rect x="350" y="10" width="300" height="60"/><path d="M500 70V100H177V120M500 100H823V120M500 100V120M500 85H15V250H823V275M177 250V275M500 250V275"/></g>'+text('组件迁移系统',500,50,28);
for(let i=0;i<items.length;i++){const x=27+i%3*323,y=i<3?120:275;s+=`<rect x="${x}" y="${y}" width="300" height="105" fill="white" stroke="black" stroke-width="1.8"/>`+text(items[i][0],x+150,y+37,26)+text(items[i][1],x+150,y+79,22)}
s+='</svg>';
await fs.writeFile(new URL('./section14-functions.svg',import.meta.url),s);
await sharp(Buffer.from(s),{density:200}).png().toFile(fileURLToPath(new URL('./section14-functions.png',import.meta.url)));
await fs.copyFile(new URL('./section14-functions.png',import.meta.url),new URL('../../paper/中期报告续写/14_系统功能划分_对齐原稿.png',import.meta.url));
