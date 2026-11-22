import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL,fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const mod=require.resolve('@oai/artifact-tool',{paths:['C:/Users/soul/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules']});
const {Presentation,PresentationFile}=await import(pathToFileURL(mod).href);
const p=Presentation.create({slideSize:{width:1280,height:720}});
const s=p.slides.add();
function text(name,t,x,y,w,h,size=19,color='#183C60',bold=false){
 const a=s.shapes.add({geometry:'textbox',name,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 a.text=t;a.text.style={fontFamily:'微软雅黑',fontSize:size,color,bold};a.text.insets=0;return a;
}
text('summary','已实现静态语义、双层结构与统一渲染校验，输出分维度结果和差异证据',83,177,1110,30,21,'#657A8C');
const xs=[84,466,848], cw=346;
const headers=['01  语义一致性','02  结构一致性','03  视觉一致性'];
headers.forEach((h,i)=>text('heading-'+i,h,xs[i],224,cw,32,24,'#356DA5',true));
text('semantic','核对状态、计算属性与事件参数\n检查生命周期及公开方法契约\n输出错误代码、位置和修复建议',84,270,cw,90,20);
text('semantic-gate','通过条件：静态检查错误为 0',84,369,cw,30,19,'#356DA5',true);
text('structure','SSM／San 模板与渲染后 DOM\n采用有序树编辑距离（TED）\n相似度 = 1 − TED / max(Ns, Nt)',466,270,cw,90,20);
text('structure-gate','双层相似度 >95%，控件初值一致',466,369,cw,30,18.5,'#356DA5',true);
text('visual','固定视口与渲染条件，双端截图\n结合 SSIM、像素差异与计算样式\n保存差异热图及样式属性明细',848,270,cw,90,20);
text('visual-gate','UI >95%，且像素差异率 <5%',848,369,cw,30,19,'#356DA5',true);
text('case-heading','真实运行案例：视觉相同的组件仍可能存在结构偏差',84,427,1110,30,23,'#183C60',true);
const values=[['组件','静态语义','模板结构','DOM 结构','UI 还原度','像素差异','综合判定'],['NotificationCard','通过','100%','100%','100%','0%','通过'],['BudgetThreshold','通过','100%','88.89%','100%','0%','未通过']];
const tab=s.tables.add({rows:3,columns:7,left:84,top:470,width:1110,height:111,columnWidths:[244,138,145,145,145,145,148],values});
tab.borders.assign({fill:'#D5E3EE',width:0.8,style:'solid'});
for(let r=0;r<3;r++)for(let c=0;c<7;c++){
 const cell=tab.getCell(r,c);cell.fill=r===0?'#E9F2F8':'#FFFFFF';
 cell.text.style={fontFamily:'微软雅黑',fontSize:r===0?19:18,color:'#183C60',bold:r===0};
}
tab.getCell(2,3).fill='#FFF2CE';tab.getCell(2,3).text.style={fontFamily:'微软雅黑',fontSize:18,color:'#A56823',bold:true};
tab.getCell(2,6).text.style={fontFamily:'微软雅黑',fontSize:18,color:'#A56823',bold:true};
text('case-interpretation','各维度分别判定，全部必需项通过后才接受当前结果。像素或 UI 得分不能替代语义与结构检查。',84,596,1110,29,19,'#356DA5');
text('scope','案例取自 2026-11-19 内部探索性运行的最终评估；两例均未配置代表性交互，不据此推断完整功能等价。',84,634,1105,30,15.5,'#657A8C');
await (await PresentationFile.exportPptx(p)).save(fileURLToPath(new URL('./content.pptx',import.meta.url)));
console.log('content exported');
