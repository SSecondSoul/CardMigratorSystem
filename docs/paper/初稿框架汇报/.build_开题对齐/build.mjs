import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {Presentation, PresentationFile} from '@oai/artifact-tool';

const build=path.dirname(fileURLToPath(import.meta.url));
const workspace=path.resolve(build,'..');
const out=path.join(workspace,'开题对齐优化版');
const skill='C:/Users/soul/.codex/plugins/cache/openai-primary-runtime/presentations/26.1025.11240/skills/presentations';
const py='C:/Users/soul/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const refP='C:/Users/soul/Desktop/swu/开题答辩-杨润生（第三版）(1).pptx';
const refD='C:/Users/soul/Desktop/swu/专业学位硕士研究生选题报告(1).docx';
const C={bg:'#F5F7FA',white:'#FFFFFF',ink:'#182F48',muted:'#53677D',blue:'#1C669E',teal:'#007F80'};
const font='Microsoft YaHei';
const p=Presentation.create({slideSize:{width:1280,height:720}});
const record=[];
function txt(s,t,x,y,w,h,size=25,color=C.ink,bold=false){
 const o=s.shapes.add({geometry:'textbox',name:'text-'+s.shapes.items.length,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0,style:'solid'}});
 o.text=t;o.text.style={fontSize:size,typeface:font,color,bold,verticalAlignment:'top',wrap:'square',autoFit:'none',insets:0};return o;
}
function base(title,section='项目介绍'){
 const s=p.slides.add();s.background.fill=C.bg;
 txt(s,section,64,30,1100,28,17,C.teal,true);
 txt(s,title,64,85,1150,72,39,C.ink,true);
 txt(s,'杨润生  /  论文初稿框架汇报',64,680,1000,20,13,C.muted);
 txt(s,String(p.slides.items.length).padStart(2,'0'),1170,676,50,25,16,C.muted);
 return s;
}
function notes(s,t,source='开题答辩第4、10、12—15页及选题报告研究内容'){
 s.speakerNotes.text=t+'\n\n材料依据：'+source+'\n来源文件：'+refP+'\n'+refD;
}
function columns(title,groups,summary,note,section='项目介绍',source){
 const s=base(title,section);const gap=48;const w=(1152-gap*(groups.length-1))/groups.length;
 groups.forEach((g,i)=>{const x=64+i*(w+gap);txt(s,g[0],x,207,w,64,28,C.blue,true);txt(s,g[1],x,292,w,250,25,C.muted);});
 if(summary)txt(s,summary,64,591,1150,57,24,C.teal,true);
 notes(s,note,source);record.push({title,groups,summary,note});return s;
}
function rows(title,entries,summary,note,section='论文框架',source){
 const s=base(title,section);const step=430/entries.length;
 entries.forEach((r,i)=>{const y=190+i*step;txt(s,r[0],64,y,496,step-10,25,C.blue,true);txt(s,r[1],594,y,618,step-10,23,C.muted);});
 txt(s,summary,64,625,1150,38,21,C.teal,true);notes(s,note,source);record.push({title,groups:entries,summary,note});return s;
}
let s=p.slides.add();s.background.fill=C.ink;
txt(s,'硕士学位论文初稿框架汇报',64,69,1100,40,24,'#87DBD4',true);
txt(s,'基于大模型的搜索场景\nWeb技术栈自动迁移系统',64,180,1148,180,54,C.white,true);
txt(s,'项目介绍与论文框架',64,408,1100,50,32,'#87DBD4');
txt(s,'汇报人：杨润生\n指导教师：陈武、祖明',64,526,1100,75,25,C.white);
txt(s,'西南大学    2026年10月27日',64,642,1100,30,21,'#B4C2D1');
notes(s,'本次汇报以开题答辩的研究定位为基础，介绍搜索场景组件迁移的需求、核心技术设计，以及论文六章的二级目录。课题题目沿用较新的开题答辩PPT。早期报告题目为卡片组件自动迁移系统，其中Card IR与答辩SSM属于同一中间表示研究方向，正文统一使用SSM。','开题答辩第1、4、10、15页，选题报告研究目的');record.push({title:'封面',note:'以开题研究定位为基础，汇报项目介绍和论文初稿框架。'});

columns('研究背景与课题定位',[
 ['技术栈演进需求','历史组件需要随前端框架演进持续迁移。\n\n理解旧代码、重写逻辑和核验页面表现，需要投入较多工程成本。'],
 ['搜索场景的约束','迁移需保证信息准确与页面稳定。\n\n结果卡片还需符合组件复用要求，\n并适配样式体系与视觉规范。']
],'本课题以 Vue 到 San 的组件迁移为技术验证场景。','项目介绍应先交代搜索场景和卡片组件的关系。搜索场景是应用背景，组件迁移是当前可执行、可评估的研究单元。避免将合成组件数据直接表述为已经在真实搜索业务上线。','项目介绍','开题答辩第4页，选题报告研究目的与意义');
rows('搜索场景下的迁移需求',[
 ['内容与结构','保留标题、摘要、图片及组件层次等信息表达'],
 ['状态与交互','保留数据初值、动态绑定、事件参数及状态更新'],
 ['组件依赖约束','在目标系统的组件选型与复用要求下完成适配'],
 ['样式 Token 与视觉规范','考虑颜色、字体、边距、尺寸及样式映射关系']
],'研究范围围绕局部组件，需求同时考虑组件所在的系统环境。','依赖约束与样式Token来自开题答辩的搜索场景扩展维度。此处作为需求与模型设计内容呈现，并不宣称仓库已经完成企业组件库映射或完整Token映射系统。','项目介绍','开题答辩第4、10页');
columns('研究目标与总体思路',[
 ['语义信息如何组织','构建结构化语义模型 SSM。\n\n描述组件结构，关联数据、事件和样式，为模型生成提供语义输入。'],
 ['迁移质量如何保证','组织代码生成与结构校验，通过 UI 评估和差异修复迭代优化。\n\n同时评价结构、视觉与功能的一致性。']
],'方法采用静态分析提供确定性信息，大模型承担代码生成与复杂修复。','这里总结开题主线，不展示当前批次进度。研究目标中的高保真是待实验支持的目标，不转换为已经实现的量化结论。','研究设计','开题答辩第4、10页，选题报告研究目标');
rows('研究内容与技术任务',[
 ['结构化语义模型','设计 SSM，自动提取模板、数据、事件与样式语义'],
 ['多阶段迁移流程','构建生成、校验、评估、修复的反馈循环'],
 ['UI 还原度评估','结合 DOM、关键样式与像素差异形成诊断'],
 ['质量指标与实验验证','从迁移质量、自动化程度及成本评价整体方案']
],'四项研究内容分别对应模型设计、迁移方法和实验论证。','按照开题报告研究内容组织，并保留答辩中对视觉评估的强调。论文不以工具列表作为主线，而以这些研究任务组织技术和证据。','研究设计','开题答辩第10、12—15页，选题报告第2部分');
rows('SSM 的四维结构设计',[
 ['模板结构树','描述 DOM 层次、条件与循环、子组件引用及插槽'],
 ['数据绑定图','关联 props、data、computed 与模板中的使用位置'],
 ['事件交互表','记录事件监听、处理函数、参数及自定义事件触发'],
 ['样式特征集','组织静态类名、动态样式、作用域样式及视觉特征']
],'搜索场景扩展信息包括组件依赖约束与样式 Token 映射。','统一使用答辩中的结构化语义模型SSM术语。早期报告称Card IR，当前Schema内部又命名San Source Model，论文应在术语说明中明确概念和实现命名关系。四维结构强调不同信息之间的关联。','核心技术','开题答辩第10、15页，选题报告Card IR设计');
columns('AST 驱动的语义提取',[
 ['Node 侧语法解析','Vue compiler-sfc 拆分组件代码块，compiler-dom 解析模板结构。\n\nBabel parser 与 traverse 提取声明、方法、表达式和依赖信息。'],
 ['Python 侧模型组装','模板、脚本和样式提取器消费解析结果。\n\n关系构建器形成 binding_graph、event_model、style_model 及生成约束。']
],'以 AST 分析为主路径，保留关键表达式和方法上下文。','本页结合开题计划与仓库实际提取链路。不要把静态提取描述为所有动态行为都可完全还原。研究重点是可保留的语义以及生成所需的上下文信息。','核心技术','开题答辩第15页，SSM/README.md，SSM/extractors/');
rows('多阶段自校正迁移流程',[
 ['代码生成','模型读取 SSM 与目标框架约束，生成初始 San 组件'],
 ['结构校验','检查迁移规则、编译结果及结构和关键属性保留'],
 ['UI 评估','比较初始渲染，并按视觉评估方案形成差异信息'],
 ['差异修复','将诊断反馈给修复环节，生成修订版本并重新检查']
],'迭代控制采用通过、修复轮数上限与无进展停止等条件。','开题提出规则快速修复与模型复杂修复的混合策略。当前仓库主要通过规则诊断和提示约束配合模型修复实现闭环。完整目标AST与源SSM等价检查属于设计方向，当前校验实现需按规则、编译和DOM范围说明。','核心技术','开题答辩第13页，migration_pipeline/orchestrator.py，stages/');
columns('视觉差异驱动的 UI 还原度评估',[
 ['结构与样式层','比较归一化 DOM，识别节点、文本及关键属性差异。\n\n在浏览器环境中比较颜色、字体、边距与尺寸等计算样式。'],
 ['图像层','在固定视口、字体和输入数据下渲染 Vue 与 San。\n\n通过截图的像素差异、SSIM 及热力图辅助定位视觉偏差。']
],'开题评估方案同时考虑 DOM 与图像，差异报告用于指导后续修复。','这是开题完整视觉评估路线。当前主流水线的自动检查以初始DOM比较为主，截图、像素分析与综合分数应按实际接入和实验覆盖单独报告。像素差异率与SSIM分别定义，不能将SSIM直接称为像素差异率。','核心技术','开题答辩第14页，选题报告视觉评估方案，migration_pipeline/stages/visual_eval.py');
columns('流程编排与大模型适配',[
 ['阶段编排与可观测性','开题设计：LangGraph 管理阶段节点与条件流转，LangSmith 记录调用链。\n\n当前实现：Python 编排器维护共享状态、轮次、报告及检查点。'],
 ['生成提示与模型适配','当前采用外部模型接口与 SSM 约束提示。\n\n开题提出少样本示例和 LoRA 适配，可作为后续方案比较或扩展方向。']
],'编排层负责执行控制，模型层负责生成与复杂修复。','本页保留答辩中Agent框架与模型优化内容，但没有将LangGraph、LangSmith和LoRA写成已完成模块。参考多轮反馈的思想不代表项目进行了强化学习训练。','技术方案','开题答辩第12页，local_server/README.md，migration_pipeline/README.md');
rows('迁移质量评价与实验设计',[
 ['结构与功能','编译运行通过率、结构保留、状态与事件场景验证'],
 ['UI 还原度','DOM 一致性、样式误差、像素差异率及 SSIM'],
 ['自动化程度与成本','人工介入比例、修改量、耗时、Token 与修复轮数'],
 ['对比与消融','零样本与示例提示基线，SSM、校验、视觉及修复模块分析']
],'按复杂度分层，以统一模型、预算与评估协议比较各方案。','本页描述实验设计。原开题报告中的30—50个组件、85%成功率等属于预期，不作为本次结果。UI还原度需要分别给出各指标定义。新增对比和消融实验应实际执行后再形成结论。','研究设计','选题报告2.3、2.4与预期目标，开题答辩第13—15页');
columns('研究特色与论文论证重点',[
 ['面向 UI 的语义表示','围绕模板、数据、事件与样式组织组件信息。\n\n论证重点：语义保留程度及对生成的帮助。'],
 ['环境反馈参与迁移','将结构检查与视觉差异转为可定位的修复信息。\n\n论证重点：检查与修复模块对质量和成本的影响。'],
 ['场景约束下的应用','关注搜索组件的复用、依赖及样式一致性要求。\n\n论证重点：方法的适用范围及业务适配价值。']
],'研究特色需要通过表示实例、模块对比和迁移案例逐项支撑。','沿用开题研究特色，但不重复“填补空白”等未经文献核验的绝对判断。静态分析与生成式AI的融合贯穿方法，不额外包装为独立量化成果。','研究特色','开题答辩第10页，选题报告研究特色');
rows('论文总体框架与开题研究内容的对应',[
 ['第1章  绪论','解释研究背景、研究现状、研究问题与目标'],
 ['第2章  相关技术与需求分析','明确框架差异、搜索场景约束及迁移需求'],
 ['第3章  SSM 设计与自动提取','展开结构化中间表示研究'],
 ['第4章  自校正迁移方法与系统实现','展开生成、结构校验、视觉评估与修复'],
 ['第5章  实验设计与结果分析','验证各模块作用、质量表现与迁移成本'],
 ['第6章  总结与展望','归纳研究结论与后续扩展方向']
],'第3、4章为方法主体，第5章围绕开题研究问题提供实验证据。','六章结构是本次初稿建议。保持技术重点版对技术介绍的侧重，并将开题中的视觉、场景约束与实验设计纳入对应章节。','论文框架','开题答辩第10—15页，选题报告主要研究内容');
rows('第1章  绪论',[
 ['1.1 研究背景与意义','前端技术栈演进、搜索场景迁移需求及应用价值'],
 ['1.2 国内外研究现状','规则与学习迁移、中间表示、Agent 与视觉验证'],
 ['1.3 研究问题与研究目标','语义表示、自校正流程及迁移质量的评价问题'],
 ['1.4 主要研究内容与技术路线','明确 SSM、迁移闭环、UI 评估与实验任务'],
 ['1.5 研究特色与论文组织','说明拟论证的研究特色及各章节的关系']
],'本章图表：研究脉络梳理表、研究问题表、总体技术路线图。','本章以开题答辩的搜索场景题目为准，吸收早期报告的卡片组件研究落点。相关工作正式写作时核查原始文献，不直接继承开题材料中所有数字及绝对性判断。');
rows('第2章  相关技术与搜索场景迁移需求',[
 ['2.1 Vue 与 San 组件机制','模板语法、响应式状态、事件、组件与生命周期'],
 ['2.2 AST 与结构化中间表示','SFC 分析、脚本解析、树结构与语义关联'],
 ['2.3 大模型与迁移 Agent 技术','提示构造、工具调用、状态编排与反馈执行'],
 ['2.4 搜索场景的业务约束','内容、组件依赖、组件复用及样式 Token 规范'],
 ['2.5 系统需求与质量要求','提取、生成、检查、修复及稳定性和追溯要求'],
 ['2.6 本章小结','形成后续模型与系统设计的需求依据']
],'本章图表：框架机制对照表、场景约束表、系统需求清单。','本章将搜索场景从背景落到需求。明确哪些是目标系统的约束，哪些在当前组件级实验中可以实际验证。');
rows('第3章  结构化语义模型设计与自动提取',[
 ['3.1 SSM 建模目标与总体设计','定义表示边界、分层结构、字段与统一术语'],
 ['3.2 四维语义模型设计','模板结构树、数据绑定图、事件表与样式特征'],
 ['3.3 搜索场景扩展与生成契约','组织组件依赖、Token 映射及目标框架约束'],
 ['3.4 AST 驱动的自动提取方法','描述模板、脚本、样式解析及 Node/Python 协作'],
 ['3.5 关联构建与表达能力验证','分析跨块依赖、关键语法覆盖及语义保留'],
 ['3.6 实例分析与本章小结','用完整组件展示 Vue 与 SSM 的对应关系']
],'本章图表：SSM 模型图、字段表、提取算法、关联实例及覆盖表。','模型主干以现有SSM实现为基础，场景扩展按设计和实现情况区分。正文首次出现时说明早期Card IR称谓与SSM的关系，后文保持统一。');
rows('第4章  多阶段自校正迁移方法与系统实现',[
 ['4.1 系统架构与流程状态设计','模块职责、服务接口、共享状态与阶段流转'],
 ['4.2 基于 SSM 的代码生成','提示组织、目标约束、示例策略与模型接口'],
 ['4.3 结构一致性与编译校验','描述校验规则、结构比较及统一差异报告'],
 ['4.4 视觉差异与 UI 还原度评估','DOM、计算样式、截图像素及指标定义'],
 ['4.5 差异反馈与自修复策略','规则与模型修复、复检、预算和停止条件'],
 ['4.6 工程实现与本章小结','编排实现、批量执行、报告与典型迁移过程']
],'本章图表：系统架构图、闭环流程图、视觉评估流程与修复案例。','4.4保留开题核心视觉路线，依据完成范围给出实际实现和实验覆盖。LangGraph等开题技术若尚未集成，应放在设计选择或扩展讨论，不能替代当前Python编排实现说明。');
rows('第5章  实验设计与结果分析',[
 ['5.1 研究问题与实验目标','将表示、检查、视觉反馈与修复作用转为假设'],
 ['5.2 数据集与实验环境','组件类型、复杂度、划分、黄金版本与运行设置'],
 ['5.3 指标定义与对比方案','定义质量、视觉、人工干预和成本，设置基线'],
 ['5.4 整体结果与分层评价','分析编译运行、结构、视觉及交互表现'],
 ['5.5 消融实验与成本分析','分析 SSM、校验、视觉、修复及提示策略影响'],
 ['5.6 案例分析、有效性讨论与小结','选取代表组件讨论适用范围与结论依据']
],'本章图表：协议与数据分布表、对比及消融图、视觉案例和成本表。','黄金版本只统计实际提供并验证的样本，不根据开题预期假定全量具备。统一模型与评估预算，区分未见测试、开发回归和人工代表性核验。');
rows('第6章  总结与展望',[
 ['6.1 研究工作总结','归纳 SSM、迁移闭环、视觉评估及系统实现'],
 ['6.2 主要研究结论','逐项回应研究问题，并明确实验支持范围'],
 ['6.3 应用价值与研究局限','讨论搜索组件适配价值与数据、验证覆盖范围'],
 ['6.4 后续研究方向','真实场景约束、更广组件类型及模型适配扩展']
],'本章以实验结论收束全文，进一步讨论搜索场景中的推广条件。','展望可包括LangGraph可观测性、LoRA与更丰富浏览器验证，但不把它们预先写成确定有效的成果。');
columns('初稿写作的内容组织',[
 ['项目介绍','以搜索场景需求说明研究价值。\n\n以 SSM 和自校正迁移解释技术方法。\n\n以视觉评估补全 UI 迁移的质量要求。'],
 ['论文框架','第3章解释语义如何表达与提取。\n\n第4章解释迁移如何执行与纠错。\n\n第5章用统一实验回答方法是否有效。']
],'汇报讨论重点：研究定位、方法章节安排与实验论证是否充分。','结束时请导师重点指导论文主线与章节分工。本版不展开批次实验进度，将时间留给项目定位与论文结构。','汇报讨论');

await fs.mkdir(out,{recursive:true});
await fs.mkdir(path.join(build,'previews'),{recursive:true});
for(let i=0;i<p.slides.items.length;i++){
 const png=await p.export({slide:p.slides.items[i],format:'png',scale:1});
 await fs.writeFile(path.join(build,'previews',String(i+1).padStart(2,'0')+'.png'),new Uint8Array(await png.arrayBuffer()));
 console.log('Rendered '+(i+1));
}
await (await PresentationFile.exportPptx(p)).save(path.join(build,'candidate.pptx'));
await fs.writeFile(path.join(build,'content.json'),JSON.stringify(record,null,2));
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const result=await finalizePresentation({workspaceDir:workspace,candidatePath:path.join(build,'candidate.pptx'),finalPath:path.join(out,'项目介绍与论文框架_开题对齐优化版.pptx'),pythonExecutable:py,integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,receiptPath:path.join(build,'validation-'+Date.now()+'.json')});
console.log(JSON.stringify(result));



