const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');
const pptx = new pptxgen();
pptx.layout='LAYOUT_WIDE'; pptx.author='杨润生'; pptx.subject='毕业论文初稿框架汇报';
pptx.title='基于大模型的搜索场景Web技术栈自动迁移系统';
pptx.company='西南大学'; pptx.lang='zh-CN';
pptx.theme={headFontFace:'Microsoft YaHei',bodyFontFace:'Microsoft YaHei',lang:'zh-CN'};
const C={navy:'14283F',blue:'2176D2',teal:'008F91',ink:'20354B',muted:'61758A',bg:'F4F7FB',white:'FFFFFF',line:'DFE7F0',orange:'C57A28'};
const slides=[];
function text(s,t,x,y,w,h,size=18,color=C.ink,bold=false){s.addText(t,{x,y,w,h,fontSize:size,color,bold,fontFace:'Microsoft YaHei',margin:0,breakLine:false,vertAlign:'mid',fit:'shrink'});}
function base(title,tag='项目介绍'){
 const s=pptx.addSlide(); s.background={color:C.bg};
 s.addShape(pptx.ShapeType.rect,{x:0,y:0,w:13.333,h:.12,fill:{color:C.teal},line:{color:C.teal}});
 text(s,tag.toUpperCase(),.6,.35,11,.25,11,C.teal,true); text(s,title,.6,.86,12.1,.7,28,C.navy,true);
 s.addShape(pptx.ShapeType.line,{x:.6,y:6.98,w:12.1,h:0,line:{color:C.line,width:1}});
 text(s,'西南大学  ·  杨润生  /  论文初稿框架汇报',.6,7.08,10,.2,9,C.muted);
 text(s,String(slides.length+1).padStart(2,'0'),12,7.04,.7,.3,11,C.muted);
 return s;
}
function note(s,t,source=''){s.addNotes(t+(source?'\n材料依据：'+source:''));}
function cards(title,items,takeaway,notes,tag='项目介绍',source=''){
 const s=base(title,tag); const n=items.length; const gap=.22; const w=(12.1-gap*(n-1))/n;
 items.forEach((a,i)=>{let x=.6+i*(w+gap); s.addShape(pptx.ShapeType.roundRect,{x,y:1.95,w,h:3.73,rectRadius:.12,fill:{color:C.white},line:{color:C.line,width:1}}); text(s,'0'+(i+1),x+.25,2.18,w-.5,.4,19,C.teal,true);text(s,a[0],x+.25,2.83,w-.5,.6,21,C.navy,true);text(s,a[1],x+.25,3.55,w-.5,1.77,17,C.muted);});
 text(s,takeaway,.65,6.03,12,.57,18,C.blue,true);note(s,notes,source);slides.push({title,items,takeaway,notes,source});return s;
}
let s=base('基于大模型的搜索场景\nWeb技术栈自动迁移系统','硕士学位论文 · 初稿框架汇报');
text(s,'以 Vue → San 组件迁移为验证场景',.65,2.55,11, .65,25,C.teal,true);
text(s,'项目介绍  /  技术路线  /  阶段进展  /  论文框架',.65,3.62,11,.5,20,C.muted);
text(s,'汇报人：杨润生    校内导师：陈武    校外导师：祖明',.65,5.32,12,.45,17);
text(s,'西南大学 · 电子信息    |    2026年10月26日',.65,5.91,12,.4,16,C.muted);
note(s,'本次主要汇报项目研究定位、已完成的技术工作，以及初稿拟采用的章节结构。题目沿用选题报告。汇报建议控制在10—12分钟。','docs/paper/专业学位硕士研究生选题报告4.docx');slides.push({title:'封面',notes:'开场：汇报研究定位、技术工作与论文初稿结构。'});
cards('研究背景：迁移需要同时保留结构、状态与交互',[
 ['业务需求','搜索卡片及页面组件需要适配统一技术栈；迁移过程中要保持内容、样式和交互的一致性。'],
 ['核心困难','模板、脚本、样式相互关联；属性绑定、响应式更新和事件机制在 Vue 与 San 中存在差异。'],
 ['研究切入','用结构化表示组织源组件语义，再通过可执行检查与反馈修复降低迁移偏差。']
],'研究目标：建立可检查、可迭代、可追溯的组件迁移流程。','这里强调组件迁移的工程需求。搜索场景是应用背景，当前仓库的验证对象是分层Vue组件；不将组件级实验直接外推为整页搜索系统上线效果。','项目介绍','开题报告；SSM/README.md');
cards('项目定位与边界',[
 ['输入与输出','输入：Vue 单文件组件\n中间：SSM 结构化表示\n输出：San 组件及迁移报告'],
 ['当前验证范围','覆盖模板、状态、事件和样式提取；采用简单／中等／复杂组件进行分层评估。'],
 ['当前能力边界','重点验证组件级迁移。全量交互等价、真实搜索业务集成及性能收益仍需补充证据。']
],'以 Vue → San 的实证研究支撑“Web 技术栈自动迁移”这一论文主题。','说明论文题目较宽，而当前实验聚焦明确的源框架与目标框架。搜索场景适配约束应在需求章节说明，真实业务验证作为待补充工作。','项目介绍','local_server/README.md；migration_pipeline/batch_configs/formal_30_v3.json');
cards('拟回答的三个研究问题',[
 ['RQ1 · 如何表达','如何保留模板、逻辑、样式及跨块关联，使大模型获得足够完整的迁移上下文？'],
 ['RQ2 · 如何纠错','如何将静态规则、编译与 DOM 差异转成可操作反馈，支持多轮修复和终止？'],
 ['RQ3 · 如何验证','如何区分自动检查、交互验证与迁移成本，并判断方法在不同复杂度下的适用边界？']
],'研究主线：语义表示 → 反馈驱动迁移 → 分层实验验证。','三个问题对应论文第三、四、五章。它们是初稿组织的研究问题，不能把已有工程实现直接表述为已获证明的学术创新。','研究设计');
s=base('技术路线：SSM 驱动的生成—校验—修复闭环','技术路线');
const stages=[['Vue 组件','template / script / style'],['SSM 提取','AST 解析与语义关联'],['模型生成','SSM → San'],['校验评估','规则 / 编译 / DOM'],['输出报告','代码 / 指标 / 历史']];
stages.forEach((v,i)=>{let x=.6+i*2.46;s.addShape(pptx.ShapeType.roundRect,{x,y:2.25,w:2.23,h:1.55,fill:{color:i===1?C.teal:C.white},line:{color:C.line}});text(s,v[0],x+.12,2.48,1.99,.42,20,i===1?C.white:C.navy,true);text(s,v[1],x+.12,3.06,1.99,.43,12,i===1?C.white:C.muted);if(i<4)text(s,'→',x+2.25,2.77,.22,.35,17,C.teal,true);});
text(s,'未通过 → 差异报告 → 模型修复 → 再校验',3.1,4.35,8,.6,22,C.blue,true);
text(s,'停止条件：检查通过 / 达到修复上限 / 连续无进展',1.05,5.28,11.2,.5,19,C.muted);
text(s,'当前采用 Python 编排器；LangGraph 为开题规划中的后续集成方向。',.65,6.12,12,.45,16,C.teal,true);
note(s,'生成模型核心输入为SSM。当前MigrationPipelineOrchestrator已实现阶段调用与循环控制，但没有据此宣称已完成LangGraph集成。默认最大修复轮数为3。','migration_pipeline/orchestrator.py；migration_pipeline/README.md');slides.push({title:'技术路线',notes:'依次解释输入、SSM、模型生成、规则与DOM评估、反馈修复。当前是Python编排器，LangGraph尚属后续集成。'});
cards('核心方法一：用 SSM 组织组件迁移语义',[
 ['模板与逻辑','DOM 树、指令、插槽\nprops / data / computed\nmethods / watch / 生命周期'],
 ['跨块关联','binding_graph：数据绑定\nevent_model：事件关系\nstyle_model：样式关联'],
 ['生成约束','保留状态初值及方法上下文；通过迁移提示与生成契约约束 San 输出，减少信息丢失。']
],'实现链路：Vue / Babel AST → Node 解析桥 → Python 组装 → SSM JSON。','SSM在选题报告中解释为Structured Semantic Model，仓库README又使用San Source Model，初稿需统一术语。建议正文统一为结构化语义模型，并交代实现命名。解析优先真实AST，回退路径另行说明限制。','技术路线','SSM/README.md；SSM/schema/v3.py；SSM/extractors/relation_builder.py');
cards('核心方法二：把检查结果转为修复反馈',[
 ['静态与编译','检查 San 语法、属性默认值、数据访问、动态绑定与事件映射；输出定位信息和错误码。'],
 ['渲染与 DOM','比较初始渲染的结构、文本及关键属性；结构相似度默认阈值为 0.95。'],
 ['反馈与终止','将差异写入修复提示；复检修复结果，记录轮数、Token 和停止原因，识别无进展循环。']
],'当前自动通过主要反映规则、编译与初始 DOM 检查；交互和像素评估须分别报告。','不要把visual_eval模块名等同于完整像素视觉验证。当前核心调用为Vue/San渲染与DOM比较。像素级指标、浏览器全量交互与性能评估应作为补充实验。','技术路线','migration_pipeline/stages/validate.py；stages/visual_eval.py；orchestrator.py');
s=base('阶段结果：冻结留出集暴露了复杂组件瓶颈','阶段进展');
[['30','配置样本'],['18 / 30','总体自动通过'],['2 → 18','初次 → 修复后通过']].forEach((a,i)=>{let x=.65+i*4.08;text(s,a[0],x,1.95,3.8,.7,35,C.blue,true);text(s,a[1],x,2.72,3.8,.4,16,C.muted);});
const rows=[['简单','10 / 10',1],['中等','7 / 10',.7],['复杂','1 / 10',.1]];
rows.forEach((a,i)=>{let y=3.55+i*.65;text(s,a[0],.7,y,1,.35,17);s.addShape(pptx.ShapeType.rect,{x:2,y:y+.03,w:8,h:.27,fill:{color:C.line},line:{color:C.line}});s.addShape(pptx.ShapeType.rect,{x:2,y:y+.03,w:8*a[2],h:.27,fill:{color:i===2?C.orange:C.teal},line:{color:i===2?C.orange:C.teal}});text(s,a[1],10.3,y,2.2,.35,17,C.navy,true);});
text(s,'formal_30_v3：27 个完成，9 个未通过，3 个生成超时；完成样本通过率为 18/27（66.67%）。',.7,5.76,12,.5,15,C.muted);
text(s,'结论：修复闭环有实用价值；复杂组件仍是主要限制，尚不能据此作因果归因。',.7,6.35,12,.4,17,C.blue,true);
note(s,'总体分母包含配置的全部30个样本，自动通过率60%。复杂组10个中1个通过、6个失败、3个执行错误。初次2个通过，16个经修复后通过，属于同一流水线前后描述，不替代严格消融。该批次执行前冻结，后续使用其中失败样本进行开发时不可继续称为未见测试。','data/experiments/analysis/formal_30_v3_20261022/REPORT.md');slides.push({title:'冻结留出集结果',notes:'30个配置样本中18个通过，总体60%；27个完成的样本中18个通过，为66.67%。复杂组仅1/10，另有3个超时。初次2个通过，修复后18个通过，暂不作因果结论。'});
cards('后续回归结果与证据边界',[
 ['开发回归','v4 对 v3 中 12 个失败或超时案例复用改进；终态自动检查 12/12 通过，累计终态修复 17 轮。'],
 ['交互抽查','v3 已通过样本中，7 个代表组件经人工浏览器验证均通过；属于定向抽查，未覆盖全批次。'],
 ['论文写作口径','v4 为内部回归，不能作为独立泛化成绩；12 个案例的自动交互评估字段均未记录通过结果。']
],'保留冻结测试结果，将失败分析与开发回归单独呈现。','v4的12/12说明对已知问题的回归修复能力，不代表新留出集100%通过。v3的7/7人工验证来自报告记录，本次没有重新执行这些检查。v4终态Token不包含此前全部重跑开销。','阶段进展','formal_30_v4_development_closeout_20261025/summary.json；formal_30_v3_20261022/REPORT.md');
cards('论文总体框架：六章形成完整论证链',[
 ['第 1—2 章 · 问题基础','第1章 绪论\n研究背景、研究现状、问题与贡献\n\n第2章 相关技术与需求分析\nVue/San 差异、AST、LLM、迁移需求'],
 ['第 3—4 章 · 核心方法','第3章 结构化语义模型设计与提取\nSSM 规范、AST 提取、关联与契约\n\n第4章 多阶段自校正迁移系统\n生成、校验、反馈修复与工程实现'],
 ['第 5—6 章 · 证据结论','第5章 实验设计与结果分析\n数据集、对比消融、成本、失败分析\n\n第6章 总结与展望\n研究结论、局限与后续方向']
],'章节关系：为什么迁移 → 如何表示 → 如何迁移 → 效果如何 → 结论边界。','这是建议初稿目录，不是仓库已存在的完整论文。第3和第4章为主体方法章节，第5章承担验证贡献的任务。','论文框架');
cards('第 3 章：结构化语义模型设计与自动提取',[
 ['3.1—3.2 · 模型定义','3.1 建模目标与设计原则\n3.2 模板、逻辑、样式及关联模型\n\n回答：迁移必须保留哪些信息？'],
 ['3.3—3.4 · 提取方法','3.3 AST 驱动的多块解析\n3.4 数据绑定与事件关系构建\n\n回答：如何可靠地提取这些信息？'],
 ['3.5—3.6 · 约束与验证','3.5 生成契约与语义完整性\n3.6 代表性样例及提取质量分析\n\n产出：模型定义、算法、字段实例。']
],'建议图表：SSM 总体结构图、提取流程图、Vue→SSM 实例、语法覆盖与缺失分析表。','第3章需要给出形式化程度适当的字段定义，并用完整状态初值、computed依赖和事件参数的案例解释设计依据。提取质量需要单独评价，不能仅通过生成成功与否间接判断。','论文框架','SSM/schema/v3.py；SSM/extractors/');
cards('第 4 章：多阶段自校正迁移系统设计与实现',[
 ['4.1—4.2 · 系统与生成','4.1 系统架构与状态流转\n4.2 SSM 驱动的提示构造与代码生成\n\n说明接口、输入输出和模型配置。'],
 ['4.3—4.4 · 检查与修复','4.3 静态、编译及 DOM 一致性检查\n4.4 错误反馈与迭代修复策略\n\n说明错误分类、修复规则与终止。'],
 ['4.5—4.6 · 工程与案例','4.5 批量执行、检查点与结果追溯\n4.6 典型迁移案例及本章小结\n\n展示从初次失败到修复的证据链。']
],'建议图表：系统架构图、修复循环状态图、错误分类表、典型案例逐轮变化表。','以实际代码为准描述Python编排器。LangGraph、LangSmith、LoRA在开题中属于技术规划，当前不作为已完成模块写入实现成果。后续是否引入应由实验需要决定。','论文框架','migration_pipeline/；local_server/');
cards('第 5 章：实验设计与结果分析',[
 ['5.1—5.2 · 实验协议','数据来源与复杂度分层\n开发集、冻结测试与回归集边界\n模型、Prompt、轮数与运行环境\n\n以全部配置样本为主分母。'],
 ['5.3—5.4 · 效果与贡献','对比：直接源码生成 vs SSM\n消融：无修复 vs 完整闭环\n按复杂度报告通过与失败分布\n\n统一模型、预算和评估器。'],
 ['5.5—5.6 · 成本与局限','轮数、耗时、Token、人工干预\n交互案例与失败类型归因\n数据规模、评估覆盖与外部效度\n\n区分已有结果与待补实验。']
],'计划新增的对比与消融需在冻结新样本上执行；v3/v4 主要用于已有证据与失败分析。','本页属于实验计划。避免把不同批次不同样本的指标差直接当作方法增益。增加直接源码生成、SSM无修复、SSM完整闭环的公平比较；若评估器变更，需另建协议并保留历史结果。','论文框架');
cards('初稿形成计划与本次讨论重点',[
 ['已有材料可先成稿','第3章：SSM 规范与提取实现\n第4章：迁移闭环与工程设计\n第5章：已有批次结果与失败案例\n\n先完成图表与证据索引。'],
 ['建议四周推进','第1周：细化目录与第1—2章\n第2周：完成第3—4章初稿\n第3周：补对比、消融与交互实验\n第4周：形成第5—6章并统一全文'],
 ['希望确认的重点','题目与组件级验证范围是否匹配？\nSSM 与自校正能否构成论文主线？\n对比基线和评估指标是否充分？\n搜索场景案例还需补到什么程度？']
],'本次目标：确定研究边界、六章结构与补充实验方案，形成可执行的初稿写作路径。','四周为建议安排，不是既有承诺。当前应优先保证论文论证完整、对比公平和结论边界清楚。请导师重点指导题目范围、方法章节以及实验证据是否足够。','后续安排');
cards('附录：关键证据与口径核对',[
 ['题目与设计','选题报告：专业学位硕士研究生选题报告4.docx\n\n实现依据：SSM/、local_server/、migration_pipeline/'],
 ['冻结测试证据','formal_30_v3_20261022/REPORT.md\n\n30配置 / 27完成 / 18通过\n7个代表样本人工验证通过'],
 ['开发回归证据','formal_30_v4_development_closeout_20261025/summary.json\n\n12例复用开发回归全部自动通过\n非独立留出集；交互尚未完整验证']
],'材料统计截止：2026年10月25日；PPT 整理日期：2026年10月26日。','主讲可跳过此页。所有指标来自项目本地保存的报告，没有重新运行模型实验。统一术语时须处理SSM名称差异。','附录');
async function main(){
 await pptx.writeFile({fileName:path.join(__dirname,'项目初稿框架汇报.pptx')});
 fs.writeFileSync(path.join(__dirname,'汇报讲稿与材料说明.md'),'# 项目初稿框架汇报\n\n建议时长：10—12分钟；末页为备查附录。PPT中的正文、流程图和数据条均可编辑。\n\n'+slides.map((a,i)=>`## ${i+1}. ${a.title}\n\n${a.items?a.items.map(v=>'**'+v[0]+'**：'+v[1].replace(/\n/g,'；')).join('\n\n')+'\n\n':''}${a.takeaway||''}\n\n讲解提示：${a.notes}\n\n${a.source?'材料依据：'+a.source:''}`).join('\n\n')+'\n\n说明：第5章的新增对比与消融、四周写作安排均为建议计划。历史实验结果来自仓库报告，本次未重跑模型。现有自动检查通过不等同于全量交互等价。\n','utf8');
 console.log('Created '+slides.length+' slides.');
}
main();
