from pathlib import Path
import zipfile,xml.etree.ElementTree as E,json,copy
HERE=Path(__file__).resolve().parent
SRC=Path(r'C:/Users/soul/Desktop/swu/中期答辩/中期答辩-杨润生（前三节-含数据集构造）-流程动画版.pptx')
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
for k,v in NS.items():E.register_namespace(k,v)
R='http://schemas.openxmlformats.org/package/2006/relationships'
C='http://schemas.openxmlformats.org/package/2006/content-types'
with zipfile.ZipFile(SRC) as z: payload={n:z.read(n) for n in z.namelist()}
with zipfile.ZipFile(HERE/'content.pptx') as z:
 generated=E.fromstring(z.read('ppt/slides/slide1.xml'))
target=E.fromstring(payload['ppt/slides/slide12.xml'])
tree=target.find('p:cSld/p:spTree',NS)
for i,node in enumerate(list(generated.find('p:cSld/p:spTree',NS))[2:],start=100):
 for item in node.findall('.//p:cNvPr',NS):item.set('id',str(i));item.set('name','Validation_'+item.get('name',''))
 tree.append(copy.deepcopy(node))
payload['ppt/slides/slide12.xml']=E.tostring(target,encoding='utf-8',xml_declaration=True)
notes='''讲述建议：本节围绕“行为与约束是否保留、结构是否一致、外观是否还原”三个问题展开。静态语义以源 Vue、SSM 与目标 San 为依据，检查状态、计算属性、事件参数、生命周期和公开方法契约。只证明当前规则支持范围内的约束，不宣称完整语义等价。
结构层同时核对 SSM 与目标模板投影，以及两端实际渲染 DOM。有序 Zhang–Shasha 树编辑距离采用单位插入、删除、重命名成本，相似度为 max(0, 1 - TED/max(Ns,Nt))，Ns/Nt 包含投影根节点。两个结构相似度都须严格大于 0.95，且实际表单控件初值一致。key 身份与混合文本顺序还有独立规则/DOM检查，不能只用模板 TED 推断。
视觉层在相同视口和渲染设置下运行 Vue 与 San。默认视口为1280×900，读取计算样式并截取双端图像。SSIM采用8×8亮度窗口总体方差算法。像素最大RGBA通道差大于10计为差异像素。样式匹配率 C 按节点路径比较颜色、字体、边距、尺寸等属性。UI还原度 = 100×[0.5×SSIM + 0.3×(1-d) + 0.2×C]，其中d为像素差异率。UI还原度须严格大于95%，且d严格小于5%。系统保存Vue/San截图、热图、结构差异与计算样式明细，提供后续修复依据。源基准与目标编译运行另设门控。
表中是两个固定任务的最终评估，不是整体成功率或独立测试集结论。NotificationCard：静态通过，模板TED=0(8/8节点)，DOM TED=0(10/10节点)，UI100%，SSIM1，像素差异0。BudgetThreshold：静态通过，模板TED=0(6/6节点)，DOM TED=1(9/9节点)，相似度8/9=88.89%，UI100%，SSIM1，像素差异0，结构门控未通过。这说明只看截图会遗漏不可见属性或结构差异。
本批次属于开发后重新划分的内部探索性实验，运行仍在继续，不使用其动态汇总作为最终结果。这两个任务均没有配置actions，interaction=not_run，不能根据页面通过推断任意props、全部公开API或完整功能等价。
代码来源（项目根目录 C:/Users/soul/Desktop/swu/毕业设计）：
migration_pipeline/stages/validate.py
migration_system/src/card_migration_system/stages/evaluation.py
migration_system/src/card_migration_system/stages/structure.py
migration_system/browser/metrics.mjs
migration_system/browser/evaluate.mjs
migration_system/src/card_migration_system/application/migrations.py
真实证据：experiment_runs/real_system_experiment70_v3_general_repairs_20261119/samples/001_NotificationCard/report.json；samples/003_budget_threshold/report.json；同批 protocol.json。'''
note=E.Element('{'+NS['p']+'}notes');cs=E.SubElement(note,'{'+NS['p']+'}cSld');st=E.SubElement(cs,'{'+NS['p']+'}spTree')
ng=E.SubElement(st,'{'+NS['p']+'}nvGrpSpPr');E.SubElement(ng,'{'+NS['p']+'}cNvPr',id='1',name='');E.SubElement(ng,'{'+NS['p']+'}cNvGrpSpPr');E.SubElement(ng,'{'+NS['p']+'}nvPr');E.SubElement(st,'{'+NS['p']+'}grpSpPr')
sp=E.SubElement(st,'{'+NS['p']+'}sp');nv=E.SubElement(sp,'{'+NS['p']+'}nvSpPr');E.SubElement(nv,'{'+NS['p']+'}cNvPr',id='2',name='Notes');E.SubElement(nv,'{'+NS['p']+'}cNvSpPr');ph=E.SubElement(nv,'{'+NS['p']+'}nvPr');E.SubElement(ph,'{'+NS['p']+'}ph',type='body',idx='1');E.SubElement(sp,'{'+NS['p']+'}spPr');tx=E.SubElement(sp,'{'+NS['p']+'}txBody');E.SubElement(tx,'{'+NS['a']+'}bodyPr');E.SubElement(tx,'{'+NS['a']+'}lstStyle')
for line in notes.splitlines():
 p=E.SubElement(tx,'{'+NS['a']+'}p');r=E.SubElement(p,'{'+NS['a']+'}r');E.SubElement(r,'{'+NS['a']+'}t').text=line
cm=E.SubElement(note,'{'+NS['p']+'}clrMapOvr');E.SubElement(cm,'{'+NS['a']+'}masterClrMapping')
relskey='ppt/slides/_rels/slide12.xml.rels';rels=E.fromstring(payload[relskey])
existing=next((x for x in rels if x.get('Type','').endswith('/notesSlide')),None)
if existing is None:
 E.SubElement(rels,'{'+R+'}Relationship',Id='rIdValidationNotes',Type=NS['r']+'/notesSlide',Target='../notesSlides/notesSlideValidation.xml')
 payload[relskey]=E.tostring(rels,encoding='utf-8',xml_declaration=True)
 notepath='ppt/notesSlides/notesSlideValidation.xml'
 nr=E.Element('{'+R+'}Relationships');E.SubElement(nr,'{'+R+'}Relationship',Id='rId1',Type=NS['r']+'/notesMaster',Target='../notesMasters/notesMaster1.xml');E.SubElement(nr,'{'+R+'}Relationship',Id='rId2',Type=NS['r']+'/slide',Target='../slides/slide12.xml')
 payload['ppt/notesSlides/_rels/notesSlideValidation.xml.rels']=E.tostring(nr,encoding='utf-8',xml_declaration=True)
 ct=E.fromstring(payload['[Content_Types].xml']);E.SubElement(ct,'{'+C+'}Override',PartName='/'+notepath,ContentType='application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml');payload['[Content_Types].xml']=E.tostring(ct,encoding='utf-8',xml_declaration=True)
else:notepath='ppt/'+existing.get('Target').replace('../','')
payload[notepath]=E.tostring(note,encoding='utf-8',xml_declaration=True)
with zipfile.ZipFile(HERE/'candidate.pptx','w',zipfile.ZIP_DEFLATED) as z:
 for n,b in payload.items():z.writestr(n,b)
with zipfile.ZipFile(SRC) as z:
 changed=[n for n in z.namelist() if payload[n]!=z.read(n)]
 print(json.dumps({'changed_parts':changed,'unchanged_slides':[i for i in range(1,15) if payload[f'ppt/slides/slide{i}.xml']==z.read(f'ppt/slides/slide{i}.xml')]},ensure_ascii=False))
