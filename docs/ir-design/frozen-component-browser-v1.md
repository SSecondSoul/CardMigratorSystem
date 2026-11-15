# 真实冻结组件完整页面适配 v1

这是S2开发校准入口，不是新模型批次、全30项回归或生产放行。旧受控评估器v1及其证据不变；新增SFC封装器与独立v2全页截图入口。未修改生成／repair Prompt、迁移规则或组件产物。

## 已覆盖范围

从20261104冻结批次按原顺序每层首项选择VolumeControl、BatchRenamer、AnalyticsDashboard。共5场景10页，保留源／目标完整模板、内联子组件、默认props和CSS。只注入挂载、观察和就绪逻辑；不用模拟DOM，不替换业务方法、加载定时器或表格／图表内容。

封装器仅支持可信CommonJS风格Options API、普通HTML／JS／CSS、显式静态本地依赖图和已固定的Vue2.7.16／San3.15.6。Vue普通scoped样式由compiler-sfc3.5.42转换选择器，配合Vue2原生_scopeId；通过父／子组件实际样式隔离正负控制，不等于完整Vue3编译器兼容。script setup、ESM、预处理器、CSS Modules、deep／slot／v-bind样式、动态require、循环依赖、外部包／资源等明确拒绝，不填空或静默略过。San scoped样式尚不支持。

显式props仅为已有props测试输入，不是新增调用方协议。默认场景props={}，让原组件工厂／默认值自行执行；静态场景视觉相同不证明任意公开键、方法、副作用、通知、异常或交互等价。

## 运行方式

项目根目录执行，不需要local_server、密钥或新依赖；目录必须是新目录，旧证据不允许覆盖。

```powershell
# 只准备页面，不启动浏览器
python -m migration_pipeline.prepare_frozen_component_browser_v1 `
  --prepared-dir data/experiments/analysis/my_new_component_pages

# 启动隔离headless Edge，对准备好的完整页面评估
python -m migration_pipeline.prepare_frozen_component_browser_v1 `
  --prepared-dir data/experiments/analysis/my_new_component_pages `
  --output-dir data/experiments/analysis/my_new_component_capture
```

这个入口绑定本次冻结开发输入与旧实现指纹；若后续代码或人工页已变，不要回退用户文件来绕过预检，应另立新版本和基线。底层v2 CLI：0为所有比较通过，1为评估有效但有差异，2为存在阻断／执行失败；Python包装入口输出报告，**仍必须读取status、eligible、passed，不以包装脚本退出0当迁移通过**。

合成适配层／完整截图控制：

```powershell
python -m migration_pipeline.calibrate_component_page_adapter_v1 `
  --output-dir data/experiments/analysis/my_new_adapter_controls
```

## 捕获策略与限制

1280×800视口、DPR1、固定浅色／zh-CN／Asia/Shanghai／Date／seed；明确ready、字体与两帧等待，然后二次截图。固定html scrollbar-gutter:stable避免全页截图移除滚动条引起宽度变化；这是受控渲染环境，不是修改业务CSS。首轮无固定占位的失败记录及仅改单个环境声明的反事实对照保留。

完整截图只向下扩展，最大400万像素，横向溢出阻断；关键元素必须在完整捕获范围内。源／目标高度不等时保留各自原图和尺寸诊断，不缩放／补边／裁切／编造SSIM及差异图。单页阻断不丢掉其余页结果。实际browser与字体版本／文件指纹记录，但未vendoring；中文／emoji回退字体未逐字形固定。

当前Vue警告通过显式warnHandler记录为“Vue component warning”的console.error并保守阻断；必须与原生异常、San错误和迁移失败分开报告，不能把源基准警告算成目标新缺陷。后续生产接入需正式冻结错误分类与反馈策略，不能据本轮小样例直接套用全量成功率。

每页是新target，但共享本次隔离profile／origin；本轮三个组件无存储操作。**尚未证明有localStorage／IndexedDB／ServiceWorker等组件的逐页存储隔离**，生产接入前需明确策略；也未覆盖运行时祖先应用、SSR、任意外部依赖、交互、拖拽及全量状态空间。本入口不是恶意代码安全沙箱。

## 当前观察与后续

Volume默认／initialVolume60、Batch默认／两文件props共4静态场景像素差0、关键样式相同。Analytics双方7个子组件、30个图点及15条活动已加载且观察字段相同；源重复key产生10条警告，两侧完整页面1326／1625高，存在7项关键矩形差异，因此比较继续阻断；没有将其改为通过或回填旧成绩。

下一步将源基准问题、目标视觉差异和评估设施问题分别归类，选择可解释的反馈字段、存储隔离及状态覆盖策略，再冻结生产评估协议与阈值、接入流水线。不能直接开始独立测试或付费全量复跑；已有公开动态键及通知／异常阶段阻断继续保留。

证据：[REPORT.md](../../data/experiments/analysis/frozen_component_browser_v1_20261115/REPORT.md)。样式语义依据：[Vue Scoped CSS](https://vuejs.org/api/sfc-css-features)、[Vue2完整模板编译API](https://v2.vuejs.org/v2/api/#Vue-compile)，普通选择器跨工具链部分另有本地原生实测，不泛化为所有SFC特性。
