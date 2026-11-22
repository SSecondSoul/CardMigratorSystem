from pathlib import Path
import json,subprocess,math,hashlib,re
from datetime import datetime
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION_START
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

B=Path(__file__).parent;R=B.resolve().parents[2];OUT=R/'output/reports';OUT.mkdir(parents=True,exist_ok=True)
E=json.loads((B/'evidence.json').read_text(encoding='utf-8'));S=E['batch_summary']
POP=Path(r'C:/Users/soul/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe')
pdfmetrics.registerFont(TTFont('CJK',r'C:/Windows/Fonts/msyh.ttc'))
NAVY='#183C60';TEAL='#087F8C';GREY='#5F7080';PALE='#EAF2F8';AMBER='#A66621'
def fig(name,w,h,draw):
 p=B/(name+'.pdf');c=canvas.Canvas(str(p),pagesize=(w,h));c.setFillColorRGB(1,1,1);c.rect(0,0,w,h,fill=1,stroke=0);draw(c);c.save()
 subprocess.run([str(POP),'-singlefile','-png','-r','150',str(p),str(B/name)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 return B/(name+'.png')
def lab(c,t,x,y,size=14,color=NAVY,center=False):
 c.setFont('CJK',size);c.setFillColor(color);(c.drawCentredString if center else c.drawString)(x,y,t)
def box(c,t,x,y,w,h=50,color=PALE,size=14):
 c.setFillColor(color);c.setStrokeColor('#CBD9E4');c.roundRect(x,y,w,h,6,fill=1,stroke=1)
 for i,l in enumerate(t.split('\n')):lab(c,l,x+w/2,y+h/2+(len(t.split('\n'))-1)*9-i*18-5,size,center=True)
def arrow(c,x,y,xx,yy,color=TEAL):
 c.setStrokeColor(color);c.setFillColor(color);c.setLineWidth(1.6);c.line(x,y,xx,yy)
 a=math.atan2(yy-y,xx-x);p=c.beginPath();p.moveTo(xx,yy);p.lineTo(xx-8*math.cos(a-.45),yy-8*math.sin(a-.45));p.lineTo(xx-8*math.cos(a+.45),yy-8*math.sin(a+.45));p.close();c.drawPath(p,fill=1,stroke=0)
def flow(c):
 labels=['源代码预检查','提取完整 SSM','组装 Prompt\n模型生成 San','多维校验\n语义／结构／视觉','诊断与停止判断','生成报告\n保存接受版本']
 for i,t in enumerate(labels):box(c,t,12+i*145,151,133,61)
 for i in range(5):arrow(c,145+i*145,182,157+i*145,182)
 for t,x in [('规则或模型修复',320),('候选再校验',490),('接受／回退',660)]:box(c,t,x,40,145,52)
 c.setStrokeColor(TEAL);c.line(659,151,659,115);c.line(659,115,392,115);arrow(c,392,115,392,92)
 arrow(c,465,66,490,66);arrow(c,635,66,660,66);c.line(805,66,862,66);c.line(862,66,862,128);c.line(862,128,673,128);arrow(c,673,128,673,151)
 lab(c,'未通过且仍有修复额度',420,120,12);lab(c,'回到诊断节点',724,104,12);lab(c,'图中对应真实 StateGraph 节点，修复最多 3 轮；源基准阻断或预算用尽也会进入报告',14,15,12,GREY)
f_flow=fig('01-langgraph-flow',900,230,flow)
def split(c):
 cols=[('#087F8C','实验集'),('#6FA6C1','验证集'),('#B9CCDA','测试集')]
 for i,(level,nums) in enumerate([('简单',[24,7,3]),('中等',[23,7,3]),('复杂',[23,6,4])]):
  y=115-i*36;lab(c,level,10,y+8,14);x=80
  for (color,_),n in zip(cols,nums):c.setFillColor(color);c.rect(x,y,n*17,25,fill=1,stroke=0);lab(c,str(n),x+n*17/2,y+7,13,'#FFFFFF' if color!='#B9CCDA' else NAVY,True);x+=n*17
  lab(c,str(sum(nums))+' 个',x+10,y+7,13)
 for i,(col,t) in enumerate(cols):c.setFillColor(col);c.rect(90+i*180,8,13,13,fill=1,stroke=0);lab(c,t,110+i*180,8,12)
f_split=fig('02-dataset-split',750,158,split)
def extract(c):
 for i,t in enumerate(['SFC 分块\n模板／脚本／样式','真实 AST 解析\nVue Compiler + Babel','四维提取器\n模板、脚本、样式','跨块关联\n节点—状态—事件','Schema v3 组装\nJSON 与来源摘要']):
  box(c,t,10+i*175,36,160,67,size=14)
  if i<4:arrow(c,170+i*175,69,185+i*175,69)
 lab(c,'AST 失败保留诊断；正式提取不以正则降级结果冒充成功',12,10,12,GREY)
f_extract=fig('03-extraction',890,120,extract)
def arch(c):
 for t,x,y,w in [('Vue 3 + TypeScript\nVite 工作台',10,132,190),('Flask API\n认证、入队、查询',250,132,190),('独立迁移 Worker\nLangGraph 主图',490,132,190),('Node.js\nVue／San／Puppeteer',730,132,210),('业务数据库\nSQLAlchemy + SQLite／MySQL',130,15,320),('本机图检查点 + 产物文件\nSqliteSaver、San、JSON、PNG',540,15,380)]:box(c,t,x,y,w,66,size=15)
 arrow(c,200,165,250,165);arrow(c,440,165,490,165);arrow(c,680,165,730,165)
 arrow(c,345,132,345,81);arrow(c,585,132,585,81);arrow(c,280,81,280,132);lab(c,'短事务保存任务事实',24,102,12,GREY);lab(c,'文件按路径和 SHA-256 关联',575,102,12,GREY)
f_arch=fig('04-architecture',950,215,arch)
def batch(c):
 for i,(name,k) in enumerate([('简单','simple'),('中等','medium'),('复杂','complex')]):
  a=S['by_complexity'][k];n=a['completed'];passed=a['passed'];y=130-i*39
  lab(c,name,12,y+6,14);c.setFillColor('#E5EBEF');c.rect(85,y,510,24,fill=1,stroke=0);c.setFillColor(TEAL);c.rect(85,y,510*passed/n,24,fill=1,stroke=0)
  lab(c,f'{passed}/{n}  ({100*passed/n:.2f}%)',610,y+5,14)
 lab(c,'按当前配置全部必需检查通过的组件比例；本批 actions 为空，交互未测',85,15,12,GREY)
f_batch=fig('05-batch-results',840,168,batch)
def er(c):
 nodes={'u':(15,175,190,'users\nid PK，账号与角色'),'s':(270,175,230,'source_inputs\nid PK，源码路径／摘要'),'j':(570,175,310,'migration_jobs\nid PK，input_id FK，状态与请求'),'a':(15,35,190,'auth_sessions\nuser_id FK，会话摘要'),'o':(270,35,230,'job_owners / input_owners\n用户与任务／输入所有权'),'f':(570,35,145,'migration_files\njob_id FK'),'c':(735,35,145,'migration_model_calls\njob_id FK')}
 for x,y,w,t in nodes.values():box(c,t,x,y,w,65,size=13)
 arrow(c,500,207,570,207);lab(c,'1 : N',517,216,11)
 arrow(c,110,175,110,100);lab(c,'1 : N',120,132,11)
 arrow(c,205,193,230,193);c.setStrokeColor(TEAL);c.line(230,193,230,67);arrow(c,230,67,270,67)
 arrow(c,500,67,535,67);c.line(535,67,535,207);arrow(c,535,207,570,207)
 arrow(c,385,100,385,175);lab(c,'input_id',392,131,11)
 arrow(c,642,175,642,100);arrow(c,807,175,807,100)
 lab(c,'业务关系示意：所有权关联表实现隔离；图检查点和文件正文不混入上述业务实体',15,8,12,GREY)
f_er=fig('06-database-er',900,252,er)

D=Document();sec=D.sections[0];sec.page_width=Inches(8.5);sec.page_height=Inches(11)
sec.top_margin=Inches(.62);sec.bottom_margin=Inches(.62);sec.left_margin=Inches(.68);sec.right_margin=Inches(.68)
sec.header_distance=Inches(.25);sec.footer_distance=Inches(.25)
for name,font,size in [('Normal','宋体',10.5),('Title','黑体',19),('Heading 1','黑体',15),('Heading 2','黑体',11.5),('Caption','宋体',9)]:
 st=D.styles[name];st.font.name=font;st.font.size=Pt(size);st.font.color.rgb=RGBColor(0,0,0);st.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),font)
 for border in st.element.findall('.//'+qn('w:pBdr')):border.getparent().remove(border)
normal=D.styles['Normal'].paragraph_format;normal.line_spacing=1.18;normal.space_after=Pt(4);normal.first_line_indent=Pt(21)
for n in ['Heading 1','Heading 2']:D.styles[n].paragraph_format.space_before=Pt(7);D.styles[n].paragraph_format.space_after=Pt(5)
hp=sec.header.paragraphs[0];hp.text='硕士研究生中期报告  论文研究进度';hp.style=D.styles['Caption'];hp.alignment=WD_ALIGN_PARAGRAPH.RIGHT
fp=sec.footer.paragraphs[0];fp.alignment=WD_ALIGN_PARAGRAPH.CENTER
for t in ['第 ',None,' 页']:
 if t:fp.add_run(t).font.size=Pt(9)
 else:
  r=fp.add_run();f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),'PAGE');r._r.append(f)
FULL=[]
PAGE_NO=0
def p(t,style=None):
 FULL.append(t);a=D.add_paragraph(t,style);return a
def h(t):p(t,'Heading 2')
def page(t,first=False):
 global PAGE_NO
 PAGE_NO+=1
 current=sec if first else D.add_section(WD_SECTION_START.NEW_PAGE)
 current.footer.is_linked_to_previous=False
 f=current.footer.paragraphs[0];f.clear();f.text=f'第 {PAGE_NO} 页  共 10 页';f.alignment=WD_ALIGN_PARAGRAPH.CENTER;f.paragraph_format.first_line_indent=Pt(0)
 for r in f.runs:r.font.size=Pt(9)
 p(t,'Heading 1')
def caption(t):
 a=p(t,'Caption');a.alignment=WD_ALIGN_PARAGRAPH.CENTER;a.paragraph_format.first_line_indent=Pt(0);a.paragraph_format.space_after=Pt(6)
def picture(path,width=7.1):
 a=D.add_paragraph();a.paragraph_format.first_line_indent=Pt(0);a.paragraph_format.space_after=Pt(3);a.alignment=WD_ALIGN_PARAGRAPH.CENTER;a.add_run().add_picture(str(path),width=Inches(width))
def source(t):
 a=p('实现与证据依据：'+t);a.paragraph_format.first_line_indent=Pt(0);a.paragraph_format.space_before=Pt(4)
 for r in a.runs:r.font.size=Pt(8);r.font.color.rgb=RGBColor.from_string('596A79')
def table(head,rows,widths=None):
 t=D.add_table(rows=1,cols=len(head));t.style='Table Grid';t.autofit=False
 for i,x in enumerate(head):t.rows[0].cells[i].text=x
 for row in rows:
  for c,x in zip(t.add_row().cells,row):c.text=str(x)
 if widths:
  for row in t.rows:
   for c,w in zip(row.cells,widths):c.width=Inches(w)
 for ri,row in enumerate(t.rows):
  pr=row._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');pr.append(cant)
  if ri==0:repeat=OxmlElement('w:tblHeader');pr.append(repeat)
  for c in row.cells:
   tcPr=c._tc.get_or_add_tcPr();mar=OxmlElement('w:tcMar')
   for side,v in [('top','50'),('bottom','50'),('left','65'),('right','65')]:
    el=OxmlElement('w:'+side);el.set(qn('w:w'),v);el.set(qn('w:type'),'dxa');mar.append(el)
   tcPr.append(mar)
   if ri==0:sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'EAF2F8');tcPr.append(sh)
   for a in c.paragraphs:
    a.paragraph_format.first_line_indent=Pt(0);a.paragraph_format.space_after=Pt(0);a.paragraph_format.line_spacing=1.05
    for r in a.runs:r.font.size=Pt(9);r.bold=ri==0
 FULL.append('；'.join(head)+'\n'+'\n'.join('；'.join(map(str,r)) for r in rows))
 return t
def mr(t):
 r=OxmlElement('m:r');v=OxmlElement('m:t');v.text=t;r.append(v);return r
def frac(a,b):
 f=OxmlElement('m:f');n=OxmlElement('m:num');d=OxmlElement('m:den');n.append(mr(a));d.append(mr(b));f.extend([n,d]);return f
def eq(parts,num):
 # The first-party DOCX canvas renderer currently drops OMML. Use a structured,
 # high-resolution equation figure with real fraction bars for portable output.
 tokens=[]
 for x in parts:
  if isinstance(x,str):tokens.append(x)
  else:tokens.append((''.join(x.find(qn('m:num')).itertext()),''.join(x.find(qn('m:den')).itertext())))
 def chunks(t):
  result=[];last=0
  for hit in re.finditer(r'_\{([^}]+)\}',t):
   result.append((t[last:hit.start()],False));result.append((hit.group(1),True));last=hit.end()
  result.append((t[last:],False));return result
 def width(t,sz):return sum(pdfmetrics.stringWidth(a,'CJK',sz*.7 if sub else sz) for a,sub in chunks(t))
 def drawtext(c,t,x,y,sz):
  for a,sub in chunks(t):
   lab(c,a,x,y-sz*.26 if sub else y,sz*.7 if sub else sz,'#000000');x+=pdfmetrics.stringWidth(a,'CJK',sz*.7 if sub else sz)
 widths=[width(x,18) if isinstance(x,str) else max(width(x[0],15),width(x[1],15))+14 for x in tokens]
 w=sum(widths)+65
 def draw(c):
  xx=8
  for x,ww in zip(tokens,widths):
   if isinstance(x,str):drawtext(c,x,xx,27,18)
   else:
    drawtext(c,x[0],xx+(ww-width(x[0],15))/2,43,15);drawtext(c,x[1],xx+(ww-width(x[1],15))/2,13,15)
    c.setStrokeColor('#000000');c.setLineWidth(.8);c.line(xx+3,36,xx+ww-3,36)
   xx+=ww
  lab(c,'('+str(num)+')',xx+12,27,15,'#000000')
 image=fig('formula-'+str(num),w,67,draw);picture(image,min(6.9,w/90))
 FULL.append('公式 '+str(num))
def code(t):
 a=p(t);a.paragraph_format.first_line_indent=Pt(0);a.paragraph_format.line_spacing=1.0
 for r in a.runs:r.font.name='Consolas';r.font.size=Pt(8.5)

# 1
page('论文研究进度',True)
p('基于大模型的搜索场景Web技术栈自动迁移系统','Title')
p('本研究围绕Vue组件到San组件的自动迁移，落实开题报告中的结构化语义表示、多阶段校验和环境反馈修复路线。目前已形成独立运行的迁移系统，覆盖源码输入、预检查、SSM提取、Prompt构建、大模型生成、质量评估、修复复测和报告归档。本文以2026年11月19日保存的代码、数据清单和运行产物为依据，分别说明方法实现、系统设计与阶段性结果。')
h('1 研究任务与总体执行流程')
p('迁移对象不仅包含页面标签，还包含状态、计算属性、事件参数、条件与循环、作用域样式等关联。直接翻译文本容易遗漏这些关系，因此系统先构造SSM，再约束模型输出完整San单文件组件，并让生成结果进入真实编译和浏览器环境接受检查。生成成功、程序运行和质量通过采用不同状态记录。')
picture(f_flow);caption('图1  LangGraph迁移主图与有界修复回路')
p('图1对应graph/migration.py中的StateGraph。preflight检查源文件及运行前提，extract_ssm生成中间表示，generate产生revision 0，evaluate输出分维度评估，diagnose决定进入report或repair。修复候选先经过candidate_retest，再由candidate_gate接受或回退，之后重新诊断。候选生成模块本身没有决定“通过”的权限。')
table(['状态信息','用途与持久化方式'],[['migration_id、request_sha256','绑定任务身份与请求，防止恢复时串用输入'],['current、candidate及其evaluation','分别保存接受版本、候选版本与对应评估'],['round、stop_reason、decisions','记录轮次、停止原因与逐轮接受／回退理由']],[2.4,4.7])
p('LangGraph使用本机SQLite检查点实现阶段恢复，业务数据库记录任务事实；两者职责分离。任务恢复时检查请求摘要、实现指纹及运行配置，未知模型调用不会自动重发。LangSmith仅作为显式开启的追踪能力，不参与改变质量判定。')
picture(f_arch,6.9);caption('图2  前端 API Worker与存储分层架构')
source('开题报告主要研究内容；graph/migration.py；application/migrations.py；observability/traces.py。')

#2
page('2 数据集构建与复杂度分级')
p('数据准备由存量组件整理和脚本化成对构造组成。新增组件先定义功能规格，包括数据模型、状态变化、工作流、模板骨架、组件通信和迁移关注点，再由同一规格分别生成Vue和San参考版本。例如音量控制器规定“当前音量、静音前音量、静音／恢复”状态及change事件，使两端实现围绕同一行为设计。数据集参考San用于核对，不能直接作为本轮模型生成结果。')
p('构造后检查模块导出、San模板解析、初始化及computed求值、残留Vue语法、未替换生成宏、CSS块一致性与评分元信息，并通过归一化模板骨架和模板token的Jaccard相似度识别重复或高度相似组件。此类检查提高数据可用性，但不能代替完整的双端交互等价验证，参考代码仍可能存在缺陷。')
table(['维度','1分参考','2分参考','3分参考'],[['T 模板','≤10节点；≤3层；≤2指令','11–30节点；4–5层；3–5指令','≥31节点；≥6层；≥6指令'],['D 数据逻辑','data≤3；无computed；方法≤2','data 4–8；computed 1–2；方法3–5','data≥9；computed≥3；方法≥6'],['I 交互','≤1事件；无钩子','2–4事件；1钩子','≥5事件；≥2钩子'],['S 样式','≤5类；无动态类／scoped','6–15类；1–2动态类；scoped','≥16类；≥3动态类；主题变化'],['C 通信','props≤2；无emit／子组件','props 3–5；emit 1–2；子组件≤1','props≥6；emit≥3；子组件≥2']],[.8,2.1,2.1,2.1])
eq(['K = T + D + I + S + C，  5 ≤ K ≤ 15'],1)
p('式（1）按五维各1–3分求和，5–8分为简单、9–12分为中等、13–15分为复杂。该表是项目人工规格分级的参考标准，不是由当前运行耗时反推的难度，也未实现逐项阈值的统一自动打分。各项不完全落在同一档时，应结合规格和现有评分记录复核。')
picture(f_split,6.75);caption('图3  100个组件的复杂度分层与70／20／10划分')
p('划分以组件组为单位，保证Vue与参考San进入同一集合。prepare_split.py按种子20261118及最大余数分配整数名额，简单／中等／复杂分别为34／33／33个；实验、验证、测试分别为70／20／10个，并检查精确重复源码不跨集合。清单明确independent_holdout=false，已知历史开发组件优先归入实验集，因此这轮划分属于开发后的内部探索性评价，不能据此声称独立泛化能力。')
source('scripts/generate_dataset_batch_20260902.js、validate_dataset_batch_20260902.js；docs/cardComplexityDimensions.md；experiment_dataset/manifest.json、prepare_split.py。')

#3
page('3 SSM结构设计与跨块语义关联')
p('开题报告将SSM定义为连接源组件与目标框架的中间表示。当前实现采用Schema v3，除模板、脚本、样式的原始抽取结果外，还组织binding_graph、event_model、style_model以及san_generation_contract，分别服务数据依赖、事件行为、样式特征和生成约束。其目标是保存迁移需要的语义关系，而非只给源代码换一种文本格式。')
table(['核心维度','主要内容','在迁移和校验中的作用'],[['模板结构树','node_id、父子路径、source_tag／san_tag、静态属性、动态绑定、条件／循环、插槽及子组件引用','为模板生成、节点定位和结构投影提供依据'],['数据绑定图','data、props、computed、methods及模板表达式依赖，状态与节点的关联','避免遗漏初值、计算依赖和响应式读写'],['事件交互表','事件名、修饰符、处理函数、参数表达式及自定义事件关系','约束on-event映射、参数和emit／fire行为'],['样式特征集','静态／动态class、内联style、CSS规则与scoped信息','保留样式来源，辅助定位布局与类绑定差异']],[1.15,3.0,2.95])
h('3.1 节点身份和关系表示')
p('模板节点记录标签、路径及父节点，使事件或动态属性能够回到具体位置。同一字段可能同时出现在文本、按钮禁用条件和计算属性中，关系构建器在模板提取与脚本分析后统一关联。以计数组件为例，count的初值、文本插值、increment中的写入以及按钮click事件应在中间表示中建立联系，不能只保留按钮标签而丢失状态变化。')
code('关系示意（为说明模型含义而简写，非完整SSM产物）\ncount（data，初值0） → 文本插值 {{count}}\nbutton 的 click → increment() → count += 1\n.counter / button → scoped CSS规则\n实际产物根字段：template、script、binding_graph、event_model、\nstyle_model、styles、sub_components、san_generation_contract 等。')
h('3.2 源语义与目标语法的分工')
p('source_tag和源表达式保留源码信息，san_tag、san_equivalent等迁移提示提供目标表达线索。SSM不直接执行组件，也不能单凭字段齐全证明任意Vue语法已被完整支持。对循环key、混合文本次序、复杂动态键和公开方法契约等问题，系统仍依赖独立静态规则与实际DOM观察补充验证。')
p('Schema与实现均随任务绑定摘要保存，便于解释同一源文件在不同版本下的差异。工程中保留metadata和源文件SHA-256，并将SSM、生成约束、目标代码和评估证据关联，避免将旧任务结果错误地解释为新实现的效果。当前尚不把SSM覆盖所有Vue语法或框架无关语义完备性作为已验证结论。')
source('engine/SSM/schema/v3.py；engine/SSM/extractors/factory.py、relation_builder.py；封存任务artifacts/ssm.json。')

#4
page('4 源代码预检查与SSM自动提取')
p('预检查安排在模型生成前，用于尽早发现源文件或环境本身的问题。浏览器侧先解析Vue单文件结构、模板和脚本，识别语法错误及当前运行方式不支持的输入，再检查模型配置等运行前提。输入格式、运行环境和模型结果错误分开记录，可减少对无效输入的付费调用，也便于判断失败应由用户修改源码还是由系统继续修复。')
table(['检查层次','当前实现','结果处理'],[['SFC与模板','Vue Compiler解析分块与模板，保留错误位置和片段','语法错误停止并保存源诊断'],['脚本与依赖','Babel解析；当前浏览器入口针对JS Options API，外部import等受限','不将受限输入伪装成可执行组件'],['契约与运行前提','检查来源契约、模型后端、网络开关和配置；动态setter放行后仍须完整评估','源码放行不等于语义通过'],['提取完整性','校验源码摘要、提取器指纹、输出状态及容量；AST失败保留阻断状态','正式链路不接受正则降级冒充AST成功']],[1.1,3.55,2.45])
picture(f_extract);caption('图4  源文件解析 四维提取及跨块组装流程')
p('图4中的SSMExtractor经短生命周期Python宿主调用Node AST桥接器。桥接器使用@vue/compiler-sfc与@babel/parser获取真实语法树，再由SSMFactory中的TemplateExtractor、ScriptExtractor、StyleExtractor及RelationBuilder组装Schema v3。Python宿主通过独立进程隔离模块缓存，核对文件和源码摘要，并设置超时及输出大小限制。')
h('4.1 提取信息与可核验产物')
p('模板提取处理节点、指令、表达式和子组件引用；脚本提取处理导入、导出、选项、状态与方法；样式提取保留CSS及动态类／样式来源。关系构建步骤将表达式依赖连接回脚本声明和模板节点。最终ssm.json同时保存提取状态、来源摘要、实现绑定、限制说明与SSM正文。原始Vue文件不因迁移而被改写。')
h('4.2 预检查与目标校验的边界')
p('源组件在预检查中合法，只说明可以进入当前处理链。模型输出的San仍需经过San自身模板解析、脚本语法和真实浏览器运行；例如源端合法的computed调用在目标模板中可能属于非法表达式。目标语法失败时，后续语义与视觉检查会标明暂缓，不能把未运行的项目当作通过。修复语法后再开展完整检查，才能获得可比较的质量结果。')
source('application/migrations.py的preflight与extract；adapters/ssm_worker.py、ssm_bridge.cjs；browser/evaluate.mjs、source-contracts.mjs；stages/syntax.py。')

#5
page('5 Prompt构造 大模型调用与San产物保存')
p('初始生成将完整SSM作为语义来源，由既有Prompt构造器生成请求，并通过上下文整理减少重复表达。请求包含角色指令、SSM内容、目标San约束、输出要求与选定的few-shot对。共享San契约同时用于初始生成和修复，明确状态读写、默认值、事件、生命周期、父子组件及DOM保留要求，避免各阶段使用相互冲突的规则。')
table(['Prompt部分','组织内容','设计目的'],[['系统指令','迁移角色、San单文件输出及共享契约','约束格式与目标框架用法'],['少样本对','以user提供示例SSM，以assistant提供对应San','展示语义到目标写法的映射'],['当前任务','当前SSM及迁移规则，不将测试参考San作为答案输入','保留组件专属语义并控制泄漏'],['输出要求','完整template、script和style，不要解释性文本','便于自动解析、复测与归档']],[1.15,3.6,2.35])
p('示例选择仅接受train条目，排除当前source_group、相同源码摘要和显式排除组，再校验示例SSM及San内容哈希。该措施可防止明确的同组与精确重复示例混入，但无法单独证明语义近似组件从未进入开发过程，数据集独立性仍需单独审计。系统保留direct、ssm_no_repair与ssm策略，为后续对照和消融实验提供统一入口。')
h('5.1 模型调用与响应核验')
p('当前配置采用Qwen-Plus，通过HTTPS兼容接口调用，temperature为0、关闭流式输出，并设置单次输出上限和超时。后端在发送前记录调用序号与请求摘要，收到响应后保存收据。只有单一候选、finish_reason为stop、模型身份正确、内容非空且包含三个SFC分块时，响应才可作为候选代码；这些格式检查不代表San语法或功能已经通过。')
eq(['N_{call} ≤ 1 + R，  0 ≤ R ≤ 3'],2)
eq(['T_{known} = Σ_{i} (T_{prompt,i} + T_{completion,i})'],3)
p('式（2）表示一次初始生成加最多三轮修复的调用上限，规则直接产出候选时不消耗该轮模型调用。式（3）累加有合法收据的输入与输出Token，缺失收据必须标为不完整。当前配置的131072 Token停止线依据已返回用量检查，属于软停止机制，不是预付费或硬计费上限；网络结果未知时不自动重发，避免重复收费。')
h('5.2 San代码与版本链')
p('初始响应首先写为revisions/0.san，其JSON元数据记录版本号、父版本、来源和文件摘要。每轮修复保存独立的n.san及n.json，不覆盖原响应。最终下载使用候选门当前接受的版本，并与报告中的final_artifact及SHA-256关联。失败任务可能仍有可查看的候选文件，不能把“已有San文件”直接称为迁移成功。')
p('开题报告中的LoRA路线目前已有指令数据构建、训练和加载模块，但没有实际训练权重与效果实验，因此本阶段的迁移结果主要来自提示约束、少样本示例及真实校验反馈，不能归因于微调提升。')
source('prompts/migration.py、san_contract.py；stages/generate.py；adapters/model.py；configs/system.toml；training/README.md。')

#6
page('6 语义校验与双层结构一致性校验')
p('语义校验检查源Vue的可识别约束是否在San中落地，重点包括props默认值、状态访问、computed与方法命名空间、事件参数和载荷、循环与修饰符、生命周期和watcher阶段、公开方法接口。当前内置规则基于源／目标AST及SSM开展有限证明，不能将正则匹配或某个方法名存在视为完整语义保持。无法证明的情况保留诊断，交给后续修复或判定失败。')
table(['校验对象','代表性关注点','证据'],[['数据与方法','初值、data.get／set、computed读取、内部动态写入的调用体','源／目标AST和逐方法契约记录'],['事件与时序','on-event、原生事件参数、fire载荷、mounted／attached与watch注册顺序','错误码、位置、来源约束及修复建议'],['目标运行','San真实模板解析、编译、浏览器错误／警告及资源阻断','语法诊断、浏览器日志、源基准状态']],[1.2,3.5,2.4])
h('6.1 模板投影与真实DOM双层比对')
p('结构层首先将SSM模板树和目标San模板转成统一的有序带标签树。标签包含节点名、规范化属性、绑定和文本信息，保留子节点顺序。随后对两端浏览器捕获的渲染DOM再次计算距离，并核对表单控件的真实初始值。结构检查因此既观察编译前的语义结构，也观察编译后的实际界面，避免只比较字符串或只依赖截图。')
eq(['S_{tree} = max(0, 1 − ',frac('TED(T_{s}, T_{t})','max(N_{s}, N_{t})'),')'],4)
p('式（4）中的TED采用Zhang–Shasha有序树编辑距离，插入、删除和标签重命名成本均为1；Ns、Nt为树节点数。模板和DOM分别得到结构相似度，两个值都须严格大于0.95，且初始控件状态一致。DOM比较同时保存原始与有限规范化后的距离及变更证据，不以有效值相同为由随意忽略HTML属性缺失。')
table(['真实任务最终接受版本','模板相似度','DOM相似度','UI还原度','配置检查结论'],[['NotificationCard revision 2','100%','100%','100%','通过'],['BudgetThreshold revision 1','100%','88.89%','100%','未通过']],[2.65,1.05,1.1,1.05,1.25])
p('BudgetThreshold的DOM两端均有9个计数节点，TED为1，按式（4）得到1−1/9=88.89%。它的像素与样式可以相同，但HTML结构或属性仍存在偏差，因此保留结构失败。该反例说明，视觉一致不能替代结构正确。模板投影也有边界：循环key身份、混合文本次序和完整脚本逻辑分别由其他规则或真实DOM补充核查，TED本身不能证明任意功能等价。')
source('engine/migration_pipeline/stages/validate.py；stages/structure.py、dom_comparison.py、evaluation.py；封存批次001与003任务report.json。')

#7
page('7 视觉一致性指标与差异定位')
p('视觉评估在固定视口、运行资源和稳定等待条件下分别渲染Vue与San，保存两端PNG、DOM快照和逐节点计算样式。当前默认视口为1280×900，评估不自动缩放截图或掩盖动态区域；图片尺寸不同直接报错。源端错误、警告、资源阻断或证据溢出进入源基准判定，避免把源运行失败当作目标迁移错误。')
eq(['SSIM(x,y) = ',frac('(2μ_{x}μ_{y} + C_{1})(2σ_{xy} + C_{2})','(μ_{x}² + μ_{y}² + C_{1})(σ_{x}² + σ_{y}² + C_{2})')],5)
p('式（5）在每个8×8亮度窗口计算并求平均。μ表示均值，σ²表示总体方差，σxy为协方差；当前实现C1=6.5025、C2=58.5225。RGBA像素转亮度时采用0.2126R+0.7152G+0.0722B。SSIM观察局部结构相似性，不等同于差异像素占比。')
eq(['d = ',frac('Σ_{p} 1[max_{k} |I_{k}(p) − J_{k}(p)| > 10]','W × H'),'，  C_{style} = ',frac('n_{match}','n_{compare}')],6)
eq(['UI = 100 × [0.5 × SSIM + 0.3 × (1 − d) + 0.2 × C_{style}]'],7)
p('式（6）将任一RGBA通道差超过10的像素计为不同像素，W、H为视口宽高；nmatch与ncompare分别为匹配与比较的样式属性数。Cstyle沿节点索引路径比较颜色、背景、字体、边距、尺寸、display和position等属性。式（7）是当前实现的加权工程评分，权重未通过独立感知实验校准。视觉通过要求UI/100>0.95且d<0.05，不能只看一个综合分数。')
case=R/'experiment_runs/real_system_experiment70_v3_general_repairs_20261119/samples/003_budget_threshold/artifacts/evaluations/1'
imgs=D.add_table(rows=1,cols=3)
for cell,name,label in zip(imgs.rows[0].cells,['vue.png','san.png','heatmap.png'],['Vue源界面','San候选界面','像素差异热图']):
 a=cell.paragraphs[0];a.paragraph_format.first_line_indent=Pt(0);a.add_run(label).bold=True
 a=cell.add_paragraph();a.paragraph_format.first_line_indent=Pt(0);shape=a.add_run().add_picture(str(case/name),width=Inches(2.25))
 # Crop only the document viewport, preserving the complete original PNG bytes.
 shape.height=Inches(2.25*220/800)
 fill=shape._inline.find('.//'+qn('pic:blipFill'));crop=OxmlElement('a:srcRect')
 for key,value in [('l','18750'),('r','18750'),('t','0'),('b','75556')]:crop.set(key,value)
 fill.insert(1,crop)
caption('图5  BudgetThreshold组件区域局部放大  文档内保留原始完整截图')
p('图5对应BudgetThreshold接受版本1：SSIM=1、像素差异率d=0、UI=100%。此时截图完全一致，热图仍展示暗化底图，不代表出现差异；第6节的DOM距离却未通过。因此报告保留视觉与结构的独立结论，并通过节点路径和样式属性明细定位问题。对于配置动作后的代表性交互，另比较DOM、样式及控件实际状态；本批未配置动作，不据此推断交互正确。')
source('browser/metrics.mjs、evaluate.mjs；stages/structure.py的compare_styles；evaluation.py；003任务evaluations/1原始PNG与report.json。')

#8
page('8 规则模型修复 再校验及阶段性实验数据')
p('修复阶段优先执行有来源依据的确定性规则，包括目标语法、Vue残留语法、方法选项、默认值、事件和动态赋值等。语法失败时先走语法规范化路径；普通语义阶段使用现有规则计划。规则没有产生变化，或同一父版本下完全相同的规则候选已被拒绝时，再将当前代码、相关SSM、分类诊断、样式差异及拒绝反馈送入模型，要求最小修改并输出完整San文件。')
p('candidate_retest与初始evaluate共用评估器和原阈值。一般门控先拒绝源阻断、已通过维度退步或新增错误码，再按“通过维度数、负诊断数、模板相似度、DOM相似度、UI分数”的字典序比较是否严格改进。另有明确的语法解阻分支：语法修复后首次显露的语义错误不直接视为退步，但候选接受仍不等于迁移通过。')
table(['NotificationCard版本','语法','静态语义','模板／DOM','UI还原度','门控'],[['revision 0','失败','失败','暂缓','暂缓','初始生成'],['revision 1','通过','失败','87.5%／70%','99.49%','语法解阻，接受'],['revision 2','通过','通过','100%／100%','100%','严格改进，接受']],[1.5,.65,.8,1.5,1.0,1.65])
p('BudgetThreshold则在接受revision 1后，第二、三轮候选均未取得严格改进而被拒绝，最终保留结构失败；系统没有为了提高通过率降低阈值，也没有以最后生成文件覆盖已接受版本。这两类过程共同验证了修复、复测、接受和回退路径。')
picture(f_batch,6.85);caption('图6  本次封存70项真实模型批次的配置检查结果')
eq(['P_{config} = ',frac('N_{pass}','N_{completed}'),' = 15 / 70 = 21.43%'],8)
p(f'截至本次封存，批次已结束，简单13/24、中等1/23、复杂1/23，共15/70通过当前配置必需检查，55项未通过。已开始模型调用{S["model_calls"]}次，已知Token共{S["known_total_tokens"]:,}。式（8）是严格多维门控下的配置检查通过率，不是单纯编译运行率，也不是完整功能等价率。批次actions为空，人工验收未执行；数据来自内部探索性集合，不能替代开题目标的独立验证。')
p('现有结果表明主流程已可执行，但复杂组件正确性仍是主要瓶颈。下一步需按失败类型补齐条件分支、默认值、computed依赖、公开方法及多级事件等问题，再冻结新版本开展对照／消融与代表性交互实验。工程回归测试通过、旧产物离线规则重放与新模型端到端结果采用不同口径，不合并计算成功率。')
source('stages/repair.py、evaluation.py；001与003任务evaluations及decisions；real_system_experiment70_v3_general_repairs_20261119/summary.json，本次保存于'+E['captured_at']+'。')

#9
page('9 功能设计 前端界面与后端技术栈')
p('系统功能围绕“创建迁移、观察执行、理解差异、获取代码”组织。用户上传Vue源码并填写任务及运行配置，服务端登记后由Worker执行；界面显示阶段、最终检查结论和逐轮修复证据，提供San与报告下载。账号模块支持登录、任务所有权隔离和额度；开发夹具与真实迁移记录分开，避免混入实验统计。')
picture(R/'migration_system/var/workbench-ui-user-simplified-01/desktop-viewport.png',7.05);caption('图7  已实现工作台的本地验证截图  数据来自冻结任务临时副本')
p('图7取自已有本地前端验证，使用冻结任务的临时数据库副本，未更新用户业务库。侧栏提供新建和历史任务，中部以阶段图与最近任务组织上下文，详情将视觉与结构合并在“质量评估”，并提供代码和修复记录。橙色检查未通过、未测试等状态独立显示。前端展示后端的分维度结论，不根据单一UI分数自行判定成功。当前实现还保留“产物与验收”入口，用于查看产物和独立记录人工反馈；该批次没有实际人工验收结果。')
table(['层次','技术或模块','具体职责'],[['前端','Vue 3、TypeScript、Vite、vue-tsc','组件化界面、类型检查、构建与响应式状态'],['HTTP后端','Python 3.12+、Flask','认证、入队、报告查询、文件下载及错误响应'],['编排与执行','LangGraph、独立Worker','检查点、条件路由、模型阶段与有界迭代'],['持久化','SQLAlchemy、Alembic、SQLite／MySQL','业务实体、短事务、版本演进与多用户记录'],['解析和渲染','Node.js、Vue Compiler、Babel、San、Puppeteer','真实AST、San语法、双端运行与截图']],[.8,2.45,3.85])
p('Flask接口只负责请求与查询，不在HTTP请求中等待整个模型闭环。Worker通过持久化任务领取执行，Node子进程处理AST和浏览器工作。界面刷新不会丢失任务；账号切换会卸载旧工作台，服务端按所有权限制查询和下载。当前面向可信受邀源码运行，隔离的浏览器边界不能被表述为已完成面向任意恶意源码的公网安全沙箱。')
source('frontend/package.json、src/App.vue及MigrationWorkbench.vue；pyproject.toml；interfaces/api/；var/workbench-ui-user-simplified-01/report.json。')

#10
page('10 数据库设计 实现边界与后续研究')
p('数据库采用“业务事实、图检查点、产物正文”分离设计。业务库记录用户、输入、任务、调用和文件索引，SqliteSaver保存LangGraph执行位置，San／SSM／截图／原始评估保存为文件并由路径与SHA-256校验关联。系统支持SQLite和MySQL，使用Alembic推进结构版本，当前HEAD为0008_multi_user。云库已完成34表核验及应用账号接入检查，但不将既有部署检查直接等同于生产级并发和备份恢复验收。')
picture(f_er,6.95);caption('图8  当前主链核心实体关系  省略开发历史与独立登记链路')
table(['实体','关键字段与约束','设计说明'],[['source_inputs','id、filename、relative_path、sha256','源码文件索引与内容身份'],['migration_jobs','input_id FK；idempotency_key唯一；request、binding、state JSON','任务、配置、实现指纹与停止原因'],['migration_files','relative_path PK；job_id FK；sha256、kind','每一产物绑定任务和内容摘要'],['migration_model_calls','job_id FK；(job_id,ordinal)唯一；receipt、status','调用账本与已知用量，防止重复重发'],['users／auth_sessions','用户名规范化唯一；token_sha256唯一；user_id FK','账号、角色和可撤销会话'],['input_owners／job_owners','输入／任务主键及user_id外键','将归属与冻结业务记录分离'],['额度与审计','user_limits、user_usage_daily、audit_logs等','约束任务／调用额度，保留操作事实']],[1.6,3.05,2.45])
p('图8中的输入到任务是一对多，任务到文件与模型调用也是一对多；用户通过所有权关联表访问输入和任务。幂等键相同而请求摘要不同会拒绝，调用序号唯一约束防止重复登记。大JSON与文件设置大小边界，日志与结构化记录分别保存。历史tasks／runs等开发链路与当前migration_jobs分开，主链评估与候选明细通过文件索引和任务state保存，历史开发结果与本轮实验统计也分别管理。')
p('本阶段完成了SSM、生成、分维度校验、修复复测和Web系统的可执行实现，但封存70项批次只有21.43%通过严格配置门控，说明工程闭环已建立而迁移准确性目标尚未达到。后续将补充交互与人工干预记录，冻结评价规则，分别开展direct、ssm_no_repair和ssm对照，报告成功率、像素差异、Token及耗时分布。LoRA、视觉嵌入辅助指标及人工效率对比尚无完整实证结果，不写为已取得提升。')
source('persistence/migrations.py、accounts.py、schema_v1.py、database.py；migrations/versions/0008_multi_user.py；docs/deployment/MYSQL_CLOUD_ACTIVATION.md；开题报告预期目标。')

D.core_properties.title='中期报告论文研究进度详细版';D.core_properties.subject='Vue到San自动迁移系统的实现与阶段性实验';D.core_properties.author='杨润生'
target=OUT/'中期报告_论文研究进度_详细版_20261119.docx';D.save(target)
(B/'fulltext.txt').write_text('\n\n'.join(FULL),encoding='utf-8')
print('OUTPUT',target,'characters',sum(len(x) for x in FULL),'paragraphs',len(D.paragraphs),'tables',len(D.tables))
