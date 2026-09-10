const fs = require('fs');
const path = require('path');
const buildComplexImplementation = require('./dataset_batch_20260907_complex');

const root = path.resolve(__dirname, '..');
const dataRoot = path.join(root, 'data', 'datasets');
const createdDate = '2026-09-07';
const designFile = path.join(dataRoot, 'features', 'design_matrix_2026-09-07_batch_39.json');

const levelDirs = { simple: '01_simple', medium: '02_medium', complex: '03_complex' };
const baseScores = {
  simple: { template: 1, data_logic: 1, interaction: 1, styling: 2, communication: 1 },
  medium: { template: 2, data_logic: 2, interaction: 2, styling: 2, communication: 2 },
  complex: { template: 3, data_logic: 3, interaction: 3, styling: 2, communication: 2 }
};

function kebab(name) {
  return name.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
}

function snake(name) {
  return kebab(name).replace(/-/g, '_');
}

function spec(level, name, label, model, workflow, structure, stateChange, communication, migrationFocus, pattern, accent, score = {}) {
  return {
    level, name, label, model, workflow, structure, stateChange, communication, migrationFocus, pattern, accent,
    score: Object.assign({}, baseScores[level], score)
  };
}

const specs = [
  spec('simple', 'ClipboardSnippet', '代码片段复制器', '只读代码文本、复制状态与短时反馈', '点击复制并显示已复制状态', '代码预览、复制按钮和反馈标签', '复制动作切换瞬时状态并触发事件', '2 个 props，发出 copy', '文本 prop、剪贴板替代行为、定时复位与 emit/fire', 'copy-feedback', '#2563eb', { interaction: 2, communication: 2 }),
  spec('simple', 'StarRatingInput', '星级评分输入', '最大星数、当前评分与悬停评分', '悬停预览并点击确认评分', '星形按钮行和当前评分说明', 'hover 与 click 分别改变预览值和持久值', '2 个 props，发出 change', '循环按钮、鼠标事件、动态 class 和数值边界', 'hover-rating', '#d97706', { template: 2, interaction: 2 }),
  spec('simple', 'PriceStepper', '价格步进器', '单价、数量、上下限与派生合计', '增减商品数量并查看合计', '商品信息、步进按钮和价格输出', '数量受边界约束并驱动金额', '3 个 props，发出 change', '数字 prop、disabled 边界和金额 computed', 'bounded-stepper', '#059669', { communication: 2 }),
  spec('simple', 'ReadingProgressCard', '阅读进度卡', '总页数、当前页与完成状态', '逐页前进、后退并跳到结尾', '标题、页码、进度条和导航按钮', '页码变化同步百分比与完成文案', '2 个 props，无事件输出', '动态 style、边界按钮和派生状态', 'page-progress', '#7c3aed', { data_logic: 2 }),
  spec('simple', 'OtpCodeInput', '验证码输入器', '固定长度验证码字符串和提交状态', '输入数字、清空并验证长度', '数字输入、位数计数和验证按钮', '过滤非数字并限制最大长度', '1 个 prop，发出 complete', '输入清洗、动态属性、条件状态和事件载荷', 'otp-validation', '#dc2626', { data_logic: 2, communication: 2 }),
  spec('simple', 'ThemePreviewToggle', '主题预览开关', 'light/dark 主题与跟随系统标记', '切换明暗主题并恢复默认', '主题化预览卡和两个控制按钮', '主题状态驱动容器 class 和展示文本', '1 个 prop，发出 change', '动态 class、主题状态机和 emit/fire', 'theme-toggle', '#334155', { interaction: 2, communication: 2 }),
  spec('simple', 'StockReservationBadge', '库存预留徽章', '可用库存、已预留数与库存等级', '预留一件或释放一件', '库存徽章、数量说明和双按钮', '预留量改变剩余库存及告警等级', '2 个 props，无事件输出', '边界运算、动态 class 与条件禁用', 'stock-reservation', '#0f766e', { data_logic: 2 }),
  spec('simple', 'TipSplitCalculator', '小费分摊计算器', '账单、小费比例、人数与人均金额', '录入金额、循环切换小费并调整人数', '三个数值控件和人均结果区', '多个输入共同驱动派生金额', '1 个 prop，无事件输出', '数值输入、比例循环和格式化 computed', 'tip-split', '#0891b2', { data_logic: 2, interaction: 2 }),
  spec('simple', 'ColorContrastBadge', '色彩对比徽章', '前景色、背景色与可读性阈值', '交换前景背景并查看对比评级', '双色样本、交换按钮和评级徽章', '颜色互换后重新计算近似亮度差', '2 个 props，无事件输出', '样式字符串、颜色计算和动态 class', 'contrast-check', '#9333ea', { data_logic: 2 }),
  spec('simple', 'SessionTimeoutNotice', '会话超时提示', '剩余秒数、警告阈值与暂停状态', '倒计时、暂停/继续并延长会话', '倒计时数字、状态提示和操作按钮', '生命周期定时器递减并在阈值变色', '2 个 props，发出 expire', 'attached/disposed、定时器、动态 class 和事件', 'session-countdown', '#b91c1c', { interaction: 2, communication: 2 }),
  spec('simple', 'TemperatureDial', '温度调节盘', '温度值、舒适区间和冷热状态', '拖动温度并恢复推荐值', '温度读数、range 和状态文字', '数值变化驱动冷热标签及刻度位置', '3 个 props，发出 change', 'range 输入、动态 style、区间 computed', 'temperature-range', '#ea580c', { data_logic: 2, communication: 2 }),
  spec('simple', 'FileDropIndicator', '文件拖放指示器', '允许扩展名、拖入状态与文件名', '拖入区域、选择模拟文件并清除', '虚线投放区、文件状态和清除按钮', 'drag 状态与文件是否接受形成三态', '1 个数组 prop，发出 select', 'drag 事件、条件渲染、数组匹配', 'drop-state', '#0369a1', { template: 2, interaction: 2 }),
  spec('simple', 'BookmarkToggleCard', '书签切换卡', '文章标题与收藏布尔状态', '收藏或取消收藏文章', '文章标题、图标按钮和状态文案', '布尔切换改变图标、按钮样式和文案', '2 个 props，发出 change', '布尔 prop 初始化、动态 class 和 emit/fire', 'bookmark-toggle', '#be185d', { communication: 2 }),

  spec('medium', 'ProductFilterPanel', '商品组合筛选器', '商品列表、分类、价格区间、库存和关键词', '组合筛选、排序并清空条件', '多条件工具栏、结果卡片网格和空状态', '多个筛选字段共同驱动排序结果', '2 个 props，发出 select', '组合 computed、表单绑定、列表与空状态', 'multi-filter-grid', '#2563eb'),
  spec('medium', 'HabitWeekTracker', '周习惯追踪表', '习惯列表、七日二维完成矩阵与周目标', '逐格打卡、切换习惯并重置一周', '习惯行、星期列、统计栏和进度条', '二维单元格切换驱动行与全局完成率', '2 个 props，发出 change', '嵌套循环、对象键更新、动态 class/style', 'weekly-matrix', '#16a34a', { template: 3 }),
  spec('medium', 'InvoiceLineEditor', '发票行编辑器', '发票行、税率、折扣和金额汇总', '增删行、编辑数量单价并应用折扣', '可编辑表格、添加栏和汇总区', '行级输入实时重算小计、税额和应付额', '2 个 props，发出 change', '动态表格、深层不可变更新和金额聚合', 'invoice-editor', '#0f766e'),
  spec('medium', 'KanbanColumnBoard', '轻量看板列', '三列任务、当前选择与移动历史', '选择任务并左右移动或新增', '三列看板、卡片列表和新增表单', '任务状态迁移改变分组并记录操作', '2 个 props，发出 move/add', '分组 computed、多列循环和状态迁移', 'kanban-columns', '#7c3aed', { template: 3 }),
  spec('medium', 'MeetingPollScheduler', '会议时间投票器', '候选时间、参与者、投票集合和当前身份', '切换参与者、勾选时间并推荐最佳项', '参与者选择、时间卡列表和推荐摘要', '嵌套投票集合变化重算票数与领先项', '2 个 props，发出 vote/confirm', '集合更新、派生排名、动态 class 与多事件', 'availability-poll', '#0369a1'),
  spec('medium', 'ExpenseSplitLedger', '费用分摊账本', '成员、费用条目、付款人和均摊余额', '添加支出、删除条目并计算谁应补给谁', '支出表单、明细列表和结算摘要', '账目变化驱动成员净余额', '2 个 props，发出 change', '表单提交、对象聚合、正负余额样式', 'expense-ledger', '#c2410c'),
  spec('medium', 'ImageCropControls', '图片裁剪参数面板', '裁剪矩形、宽高比锁定与画布尺寸', '调整 x/y/宽高、锁定比例并重置', '数字控制网格、比例开关和裁剪预览', '参数变化同步预览框 style 并约束边界', '2 个对象 props，发出 change', '对象表单、动态 style、watch 与边界修正', 'crop-controls', '#db2777'),
  spec('medium', 'CourseModuleAccordion', '课程模块手风琴', '模块、课时完成状态和展开集合', '展开模块、标记课时完成并筛选未完成', '模块折叠列表、课时清单和总进度', '嵌套完成状态改变模块与课程统计', '2 个 props，发出 progress', '嵌套循环、条件区域、集合展开状态', 'nested-accordion', '#4f46e5', { template: 3 }),
  spec('medium', 'DeliveryRouteTimeline', '配送路线时间轴', '停靠点、到达时间、状态和延误分钟', '推进站点状态、增加延误并选中详情', '纵向时间轴、站点节点和详情面板', '状态机推进并传播后续预计时间', '2 个 props，发出 status', '时间列表、状态传播、动态 class', 'route-timeline', '#0284c7'),
  spec('medium', 'FormRulePlayground', '表单规则演练器', '用户名、邮箱、年龄字段和可切换校验规则', '输入表单、启停规则并提交', '规则开关区、表单区和错误摘要', '字段与启用规则共同产生错误集合', '2 个 props，发出 submit', '多字段校验、checkbox、错误列表与提交', 'validation-playground', '#dc2626'),
  spec('medium', 'DataPaginationTable', '数据分页表格', '记录列表、页码、每页数和排序键', '排序、翻页、更改每页数并选择记录', '工具栏、数据表、页码控制和选择摘要', '排序与分页共同决定当前切片', '2 个 props，发出 select/page', '分页 computed、表格排序和多事件', 'paginated-table', '#475569'),
  spec('medium', 'ColorPaletteBuilder', '配色方案生成器', '颜色列表、当前草稿、命名和锁定状态', '新增颜色、锁定、删除并复制色板', '颜色输入栏、色块列表和预览带', '色板数组变化同步预览渐变与可操作状态', '2 个 props，发出 change/export', '颜色输入、列表编辑、动态 style 和导出', 'palette-builder', '#9333ea'),
  spec('medium', 'AudioSegmentMarker', '音频片段标注器', '总时长、播放头、区间标记和草稿标签', '移动播放头、添加区间、选择并删除标记', '时间轴、区间条、标记列表和新增表单', '播放位置和区间集合驱动百分比样式', '2 个 props，发出 markers-change', 'range、动态区间 style、表单与列表选择', 'segment-marker', '#be185d'),

  spec('complex', 'WorkflowDiagramEditor', '工作流图编辑器', '节点、连接、选中节点、草稿位置和执行日志', '新增/移动节点、连线、校验、模拟执行和撤销', '工具栏、二维画布、节点属性面板和日志栏', '图结构编辑形成可撤销快照并驱动验证结果', '4 个 props，发出 graph-change/run/save', '图数据、动态定位、撤销栈和多阶段执行', 'workflow-graph', '#7c3aed'),
  spec('complex', 'PolicyRuleComposer', '访问策略编排器', '资源、主体、动作、嵌套规则组和测试上下文', '组合 AND/OR 规则、嵌套条件、模拟判定并发布', '规则树编辑区、上下文表单和判定面板', '规则树更新递归求值并记录测试历史', '4 个 props，发出 test/publish/change', '递归数据、规则树、条件编辑和求值器', 'policy-tree', '#b45309'),
  spec('complex', 'FleetDispatchConsole', '车队调度控制台', '车辆、订单、地理区、分配关系和里程估计', '筛选订单、选择车辆、批量派单、返仓和重排', '订单队列、车辆地图式面板、调度侧栏和统计条', '分配事务同步车辆容量、订单状态和路线负载', '4 个 props，发出 dispatch/return/save', '主从选择、容量约束、批量事务与动态位置', 'fleet-dispatch', '#0369a1'),
  spec('complex', 'ClinicalTriageBoard', '临床分诊看板', '患者、生命体征、分诊级别、床位和处置事件', '录入体征、自动分级、分配床位、升级与出院', '分诊队列、患者详情、体征表单和床位面板', '体征规则重算优先级并驱动队列排序与审计', '5 个 props，发出 triage/assign/discharge', '医疗状态机、规则聚合、审计时间线', 'clinical-triage', '#dc2626'),
  spec('complex', 'DependencyReleasePlanner', '依赖发布规划器', '服务版本、依赖边、环境、阻塞原因和发布波次', '选择版本、检测环依赖、编排波次、批准并回滚', '依赖矩阵、波次泳道、阻塞面板和变更历史', '依赖图与审批状态共同决定可发布集合', '4 个 props，发出 plan/approve/rollback', '图拓扑、矩阵、分组波次和回滚', 'release-dependency', '#4f46e5'),
  spec('complex', 'EnergyLoadScheduler', '能源负载排程器', '设备、24 小时时段、功率上限、费率和排程块', '拖动式调整时段、启停设备、平衡峰值并比较成本', '小时刻度矩阵、设备行、负载图和成本侧栏', '二维排程变化重算峰值、超限时段和总成本', '4 个 props，发出 schedule/optimize', '二维矩阵、动态宽度、约束优化与派生图表', 'energy-schedule', '#059669'),
  spec('complex', 'AuctionControlRoom', '竞拍控制室', '拍品、出价序列、竞买人、倒计时和风控标记', '切换拍品、提交出价、延时、暂停、成交或流拍', '拍品导航、实时出价区、控制台和审计记录', '出价与计时器共同驱动领先者和拍卖状态机', '4 个 props，发出 bid/close/flag', '定时器、排序队列、状态机和风险事件', 'auction-room', '#be123c'),
  spec('complex', 'ResearchAnnotationStudio', '研究语料标注台', '文档、文本跨度、标签体系、标注者和冲突集合', '选择文本跨度、创建/编辑标注、仲裁冲突并提交', '文档阅读区、标签工具栏、标注列表和冲突面板', '跨度集合更新生成重叠冲突与一致性统计', '5 个 props，发出 annotate/resolve/submit', '文本跨度、重叠检测、主从标注和仲裁', 'annotation-studio', '#9333ea'),
  spec('complex', 'ProcurementBidMatrix', '采购投标矩阵', '供应商、评价维度、权重、报价、评分和评审状态', '编辑权重与评分、归一化报价、锁定评委并选定供应商', '供应商评分矩阵、权重工具栏、排名和评审日志', '二维评分与价格归一化实时影响加权排名', '5 个 props，发出 score/lock/award', '动态矩阵、加权聚合、锁定状态和排名', 'procurement-matrix', '#0f766e'),
  spec('complex', 'WarehousePickingWave', '仓库拣选波次台', '订单、库位、拣选任务、波次、人员和异常', '组建波次、分配人员、逐项拣货、报缺并完成复核', '订单池、波次任务树、人员栏和异常抽屉', '任务进度聚合到订单与波次并生成异常补货', '5 个 props，发出 assign/pick/exception/complete', '任务树、批量选择、多级进度与异常流', 'picking-wave', '#ea580c'),
  spec('complex', 'SubscriptionRevenueModeler', '订阅收入建模器', '套餐、客户分群、月度增长、流失、折扣和情景', '调参、保存情景、比较预测曲线并恢复基线', '参数面板、月度预测表、情景列表和对比摘要', '参数变化生成时间序列并计算 MRR、ARR 与留存', '4 个 props，发出 scenario/export', '时间序列模拟、情景快照、对比和数值聚合', 'revenue-modeler', '#0891b2'),
  spec('complex', 'ApiContractWorkbench', 'API 契约工作台', '端点、参数、响应 schema、样例请求和校验问题', '编辑端点、切换方法、增删字段、校验并生成样例', '端点导航、契约编辑矩阵、请求预览和问题面板', '嵌套 schema 更新触发校验与样例重建', '5 个 props，发出 validate/generate/save', '嵌套对象编辑、动态字段、校验器和代码预览', 'api-contract', '#2563eb'),
  spec('complex', 'CrisisCommunicationHub', '危机沟通中心', '事件、受众、消息版本、渠道、审批人和发送记录', '起草消息、按受众预览、审批、分渠道发送并撤回', '事件头、受众栏、编辑器、渠道面板和发送时间线', '版本审批状态约束发送，渠道结果形成审计记录', '5 个 props，发出 approve/send/revoke', '多阶段发布、版本、渠道状态和审计', 'crisis-comms', '#b91c1c')
];

function writeJson(file, value) {
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n', 'utf8');
}

function validateDesign() {
  const manifest = JSON.parse(fs.readFileSync(path.join(dataRoot, 'dataset_manifest.json'), 'utf8'));
  const existingNames = new Set(manifest.components
    .filter(item => item.created_date !== createdDate)
    .map(item => path.basename(item.path.replace(/\/$/, ''))));
  const names = new Set();
  const signatures = new Set();
  const errors = [];

  for (const level of Object.keys(levelDirs)) {
    const count = specs.filter(item => item.level === level).length;
    if (count !== 13) errors.push(`${level}: expected 13 specs, found ${count}`);
  }
  for (const item of specs) {
    if (names.has(item.name)) errors.push(`${item.name}: duplicate batch name`);
    if (existingNames.has(item.name)) errors.push(`${item.name}: conflicts with existing component directory`);
    names.add(item.name);
    const signature = [item.model, item.workflow, item.structure].join('|');
    if (signatures.has(signature)) errors.push(`${item.name}: duplicate design signature`);
    signatures.add(signature);
    const total = Object.values(item.score).reduce((sum, value) => sum + value, 0);
    const ranges = { simple: [5, 8], medium: [9, 12], complex: [13, 15] };
    const [low, high] = ranges[item.level];
    if (total < low || total > high) errors.push(`${item.name}: invalid score ${total} for ${item.level}`);
  }
  if (specs.length !== 39) errors.push(`expected 39 specs, found ${specs.length}`);
  return errors;
}

function designMatrix() {
  return {
    created_date: createdDate,
    batch_size: specs.length,
    diversity_rule: '任意两个候选至少有两个设计维度存在实质差异，且至少一项来自数据模型、核心工作流或模板结构。',
    components: specs.map(item => ({
      component_name: item.name,
      display_name: item.label,
      level: item.level,
      data_model: item.model,
      core_workflow: item.workflow,
      template_structure: item.structure,
      state_change: item.stateChange,
      communication: item.communication,
      migration_focus: item.migrationFocus,
      interaction_pattern: item.pattern
    }))
  };
}

function commonCss(item, extra) {
  const rootClass = kebab(item.name);
  return `
.${rootClass}{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.${rootClass} *{box-sizing:border-box}
.${rootClass} h2,.${rootClass} h3,.${rootClass} p{margin-top:0}
.${rootClass} button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.${rootClass} button.primary{border-color:${item.accent};background:${item.accent};color:#fff}
.${rootClass} button:disabled{opacity:.45;cursor:not-allowed}
.${rootClass} input,.${rootClass} select,.${rootClass} textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.${rootClass} .muted{color:#71808e;font-size:12px}
.${rootClass} .toolbar,.${rootClass} .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
${extra}`;
}

function simpleImplementation(item) {
  const implementations = {
    ClipboardSnippet: {
      props: { code: ['string', 'npm run validate'], language: ['string', 'shell'] },
      state: { copied: false }, computed: [],
      methods: [['copy', '', "this.setValue('copied', true); this.emitEvent('copy', this.code); clearTimeout(this._timer); this._timer = setTimeout(() => this.setValue('copied', false), 1200);"]],
      template: `<section class="clipboard-snippet"><header><span>{{ language }}</span><button @click="copy">{{ copied ? '已复制' : '复制' }}</button></header><pre>{{ code }}</pre><small v-if="copied">内容已放入剪贴板队列</small></section>`,
      css: 'header{display:flex;justify-content:space-between}pre{padding:14px;background:#0f172a;color:#e2e8f0;overflow:auto}small{color:#15803d}'
    },
    StarRatingInput: {
      props: { maxStars: ['number', 5], initialRating: ['number', 3] }, state: { rating: 3, hoverRating: 0 },
      inited: "this.setValue('rating', this.initialRating);", computed: [['starValues', "return Array.from({ length: this.maxStars }, (_, index) => index + 1);"], ['displayRating', "return this.hoverRating || this.rating;"]],
      methods: [['preview', 'value', "this.setValue('hoverRating', value);"], ['clearPreview', '', "this.setValue('hoverRating', 0);"], ['choose', 'value', "this.setValue('rating', value); this.emitEvent('change', value);"]],
      template: `<section class="star-rating-input"><h2>服务评分</h2><div @mouseleave="clearPreview"><button v-for="star in starValues" :key="star" :class="star <= displayRating ? 'active' : ''" @mouseenter="preview(star)" @click="choose(star)">★</button></div><p>{{ displayRating }} / {{ maxStars }} 星</p></section>`,
      sanTemplate: `<section class="star-rating-input"><h2>服务评分</h2><div on-mouseleave="clearPreview"><button s-for="star in starValues trackby star" class="{{ star <= displayRating ? 'active' : '' }}" on-mouseenter="preview(star)" on-click="choose(star)">★</button></div><p>{{ displayRating }} / {{ maxStars }} 星</p></section>`,
      css: '.star-rating-input div{display:flex;gap:6px}.star-rating-input div button{border:0;font-size:28px;color:#cbd5e1}.star-rating-input div button.active{color:#d97706}'
    },
    PriceStepper: {
      props: { unitPrice: ['number', 36], min: ['number', 1], max: ['number', 8] }, state: { quantity: 1 },
      computed: [['total', "return (this.unitPrice * this.quantity).toFixed(2);"]],
      methods: [['change', 'delta', "const next = Math.max(this.min, Math.min(this.max, this.quantity + delta)); this.setValue('quantity', next); this.emitEvent('change', next);"]],
      template: `<section class="price-stepper"><div><h2>手冲咖啡豆</h2><span>¥{{ unitPrice }} / 袋</span></div><div class="step"><button @click="change(-1)" :disabled="quantity <= min">−</button><strong>{{ quantity }}</strong><button @click="change(1)" :disabled="quantity >= max">＋</button></div><output>合计 ¥{{ total }}</output></section>`,
      css: '.price-stepper{display:grid;grid-template-columns:1fr auto;gap:12px}.step{display:flex;align-items:center;gap:10px}.price-stepper output{grid-column:1/-1;padding:12px;background:#ecfdf5;font-size:20px}'
    },
    ReadingProgressCard: {
      props: { title: ['string', '迁移系统设计'], totalPages: ['number', 12] }, state: { currentPage: 1 },
      computed: [['percent', "return Math.round(this.currentPage / this.totalPages * 100);"], ['barStyle', "return 'width:' + this.percent + '%';"]],
      methods: [['go', 'delta', "this.setValue('currentPage', Math.max(1, Math.min(this.totalPages, this.currentPage + delta)));"], ['finish', '', "this.setValue('currentPage', this.totalPages);"]],
      template: `<section class="reading-progress-card"><h2>{{ title }}</h2><p>第 {{ currentPage }} / {{ totalPages }} 页 · {{ percent }}%</p><div class="bar"><span :style="barStyle"></span></div><div class="actions"><button @click="go(-1)" :disabled="currentPage === 1">上一页</button><button @click="go(1)" :disabled="currentPage === totalPages">下一页</button><button class="primary" @click="finish">读完</button></div></section>`,
      css: '.bar{height:9px;margin:14px 0;background:#e5e7eb}.bar span{display:block;height:100%;background:#7c3aed}'
    },
    OtpCodeInput: {
      props: { length: ['number', 6] }, state: { code: '', submitted: false }, computed: [['remaining', "return Math.max(0, this.length - this.code.length);"], ['complete', "return this.code.length === this.length;"]],
      methods: [['updateCode', 'event', "this.setValue('code', event.target.value.replace(/\\D/g, '').slice(0, this.length)); this.setValue('submitted', false);"], ['clear', '', "this.setValue('code', ''); this.setValue('submitted', false);"], ['verify', '', "if (!this.complete) return; this.setValue('submitted', true); this.emitEvent('complete', this.code);"]],
      template: `<section class="otp-code-input"><h2>输入验证码</h2><input inputmode="numeric" :maxlength="length" :value="code" @input="updateCode" placeholder="仅输入数字"><p>{{ complete ? '验证码长度正确' : '还需 ' + remaining + ' 位' }}</p><div class="actions"><button @click="clear">清空</button><button class="primary" @click="verify" :disabled="!complete">验证</button></div><strong v-if="submitted">已提交验证</strong></section>`,
      css: '.otp-code-input input{width:100%;font-size:24px;letter-spacing:8px}.otp-code-input>strong{display:block;margin-top:10px;color:#15803d}'
    },
    ThemePreviewToggle: {
      props: { initialTheme: ['string', 'light'] }, state: { theme: 'light' }, inited: "this.setValue('theme', this.initialTheme);", computed: [['themeLabel', "return this.theme === 'dark' ? '深色主题' : '浅色主题';"]],
      methods: [['toggle', '', "const next = this.theme === 'dark' ? 'light' : 'dark'; this.setValue('theme', next); this.emitEvent('change', next);"], ['reset', '', "this.setValue('theme', this.initialTheme);"]],
      template: `<section :class="'theme-preview-toggle ' + theme"><div class="preview"><h2>{{ themeLabel }}</h2><p>正文与控件将共同切换主题。</p></div><div class="actions"><button class="primary" @click="toggle">切换主题</button><button @click="reset">恢复默认</button></div></section>`,
      css: '.theme-preview-toggle.dark{background:#111827;color:#f8fafc}.preview{padding:16px;border:1px dashed currentColor}.theme-preview-toggle .actions{margin-top:12px}'
    },
    StockReservationBadge: {
      props: { available: ['number', 12], warningAt: ['number', 3] }, state: { reserved: 0 }, computed: [['remaining', "return this.available - this.reserved;"], ['level', "return this.remaining === 0 ? 'empty' : this.remaining <= this.warningAt ? 'low' : 'ok';"]],
      methods: [['reserve', '', "this.setValue('reserved', Math.min(this.available, this.reserved + 1));"], ['release', '', "this.setValue('reserved', Math.max(0, this.reserved - 1));"]],
      template: `<section :class="'stock-reservation-badge ' + level"><h2>演示设备库存</h2><strong>可用 {{ remaining }}</strong><span>已预留 {{ reserved }}</span><div class="actions"><button @click="release" :disabled="reserved === 0">释放</button><button class="primary" @click="reserve" :disabled="remaining === 0">预留一件</button></div></section>`,
      css: '.stock-reservation-badge>strong{display:block;font-size:32px}.stock-reservation-badge.low>strong{color:#d97706}.stock-reservation-badge.empty>strong{color:#dc2626}.stock-reservation-badge .actions{margin-top:12px}'
    },
    TipSplitCalculator: {
      props: { initialBill: ['number', 268] }, state: { bill: 268, tipRate: 10, people: 2 }, inited: "this.setValue('bill', this.initialBill);", computed: [['perPerson', "return ((this.bill * (1 + this.tipRate / 100)) / this.people).toFixed(2);"], ['total', "return (this.bill * (1 + this.tipRate / 100)).toFixed(2);"]],
      methods: [['updateBill', 'event', "this.setValue('bill', Math.max(0, Number(event.target.value) || 0));"], ['cycleTip', '', "const rates = [0, 10, 15, 20]; const index = rates.indexOf(this.tipRate); this.setValue('tipRate', rates[(index + 1) % rates.length]);"], ['changePeople', 'delta', "this.setValue('people', Math.max(1, this.people + delta));"]],
      template: `<section class="tip-split-calculator"><h2>聚餐分摊</h2><label>账单<input type="number" :value="bill" @input="updateBill"></label><button @click="cycleTip">小费 {{ tipRate }}%</button><div class="people"><button @click="changePeople(-1)">−</button><span>{{ people }} 人</span><button @click="changePeople(1)">＋</button></div><output>总计 ¥{{ total }} · 每人 ¥{{ perPerson }}</output></section>`,
      css: '.tip-split-calculator{display:grid;grid-template-columns:1fr auto;gap:10px}.tip-split-calculator label{display:grid}.people{display:flex;align-items:center;gap:8px}.tip-split-calculator output{grid-column:1/-1;padding:14px;background:#ecfeff}'
    },
    ColorContrastBadge: {
      props: { foreground: ['string', '#172554'], background: ['string', '#dbeafe'] }, state: { swapped: false }, computed: [['front', "return this.swapped ? this.background : this.foreground;"], ['back', "return this.swapped ? this.foreground : this.background;"], ['sampleStyle', "return 'color:' + this.front + ';background:' + this.back;"], ['rating', "const a = parseInt(this.front.slice(1), 16); const b = parseInt(this.back.slice(1), 16); return Math.abs(a - b) > 5000000 ? '对比明显' : '建议复核';"]],
      methods: [['swap', '', "this.setValue('swapped', !this.swapped);"]],
      template: `<section class="color-contrast-badge"><h2>色彩可读性</h2><div class="sample" :style="sampleStyle">Aa 示例文本</div><p :class="rating === '对比明显' ? 'good' : 'warn'">{{ rating }}</p><button class="primary" @click="swap">交换前景与背景</button></section>`,
      css: '.sample{padding:24px;text-align:center;font-size:26px}.good{color:#15803d}.warn{color:#b45309}'
    },
    SessionTimeoutNotice: {
      props: { initialSeconds: ['number', 15], warningAt: ['number', 5] }, state: { remaining: 15, paused: false }, inited: "this.setValue('remaining', this.initialSeconds);", attached: "this._timer = setInterval(() => this.tick(), 1000);", disposed: "clearInterval(this._timer);", computed: [['stateClass', "return this.remaining === 0 ? 'expired' : this.remaining <= this.warningAt ? 'warning' : 'active';"]],
      methods: [['tick', '', "if (this.paused || this.remaining <= 0) return; const next = this.remaining - 1; this.setValue('remaining', next); if (next === 0) this.emitEvent('expire');"], ['togglePause', '', "this.setValue('paused', !this.paused);"], ['extend', '', "this.setValue('remaining', this.initialSeconds); this.setValue('paused', false);"]],
      template: `<section :class="'session-timeout-notice ' + stateClass"><h2>{{ remaining ? '会话剩余 ' + remaining + ' 秒' : '会话已过期' }}</h2><p>{{ paused ? '计时已暂停' : '请及时保存当前工作' }}</p><div class="actions"><button @click="togglePause" :disabled="remaining === 0">{{ paused ? '继续' : '暂停' }}</button><button class="primary" @click="extend">延长会话</button></div></section>`,
      css: '.session-timeout-notice.warning{border-color:#d97706;background:#fffbeb}.session-timeout-notice.expired{border-color:#dc2626;background:#fef2f2}'
    },
    TemperatureDial: {
      props: { min: ['number', 16], max: ['number', 30], recommended: ['number', 24] }, state: { value: 24 }, inited: "this.setValue('value', this.recommended);", computed: [['comfort', "return this.value < 20 ? '偏冷' : this.value > 26 ? '偏热' : '舒适';"], ['fillStyle', "return 'width:' + Math.round((this.value - this.min) / (this.max - this.min) * 100) + '%';"]],
      methods: [['update', 'event', "const value = Number(event.target.value); this.setValue('value', value); this.emitEvent('change', value);"], ['reset', '', "this.setValue('value', this.recommended);"]],
      template: `<section class="temperature-dial"><header><h2>室内温度</h2><strong>{{ value }}°C</strong></header><input type="range" :min="min" :max="max" :value="value" @input="update"><div class="scale"><span :style="fillStyle"></span></div><p>{{ comfort }}</p><button @click="reset">恢复推荐温度</button></section>`,
      css: '.temperature-dial header{display:flex;justify-content:space-between}.temperature-dial input{width:100%}.scale{height:7px;background:#e5e7eb}.scale span{display:block;height:100%;background:#ea580c}'
    },
    FileDropIndicator: {
      props: { extensions: ['array', ['png', 'jpg', 'webp']] }, state: { dragging: false, fileName: '', accepted: false }, computed: [['hint', "return this.fileName ? (this.accepted ? '文件可用' : '格式不支持') : '拖入图片文件';"]],
      methods: [['enter', '', "this.setValue('dragging', true);"], ['leave', '', "this.setValue('dragging', false);"], ['selectDemo', '', "this.setValue('fileName', 'cover.png'); this.setValue('accepted', this.extensions.indexOf('png') >= 0); this.emitEvent('select', { name: 'cover.png', accepted: this.accepted });"], ['clear', '', "this.setValue('fileName', ''); this.setValue('accepted', false);"]],
      template: `<section class="file-drop-indicator"><h2>上传封面</h2><div :class="'drop-zone ' + (dragging ? 'dragging' : '')" @dragenter="enter" @dragleave="leave"><strong>{{ hint }}</strong><span v-if="fileName">{{ fileName }}</span></div><div class="actions"><button class="primary" @click="selectDemo">选择示例文件</button><button @click="clear" :disabled="!fileName">清除</button></div></section>`,
      sanTemplate: `<section class="file-drop-indicator"><h2>上传封面</h2><div class="{{ 'drop-zone ' + (dragging ? 'dragging' : '') }}" on-dragenter="enter" on-dragleave="leave"><strong>{{ hint }}</strong><span s-if="fileName">{{ fileName }}</span></div><div class="actions"><button class="primary" on-click="selectDemo">选择示例文件</button><button on-click="clear" disabled="{{ !fileName }}">清除</button></div></section>`,
      css: '.drop-zone{display:grid;place-items:center;min-height:140px;border:2px dashed #94a3b8}.drop-zone.dragging{border-color:#0369a1;background:#e0f2fe}.drop-zone span{display:block}'
    },
    BookmarkToggleCard: {
      props: { title: ['string', 'Vue 到 San 的迁移笔记'], initialBookmarked: ['bool', false] }, state: { bookmarked: false }, inited: "this.setValue('bookmarked', this.initialBookmarked);", computed: [],
      methods: [['toggle', '', "const next = !this.bookmarked; this.setValue('bookmarked', next); this.emitEvent('change', next);"]],
      template: `<article :class="'bookmark-toggle-card ' + (bookmarked ? 'saved' : '')"><div><span>研究资料</span><h2>{{ title }}</h2><p>{{ bookmarked ? '已加入稍后阅读' : '尚未收藏' }}</p></div><button @click="toggle">{{ bookmarked ? '★ 取消收藏' : '☆ 收藏' }}</button></article>`,
      css: '.bookmark-toggle-card{display:flex;justify-content:space-between;align-items:center}.bookmark-toggle-card.saved{border-color:#be185d;background:#fdf2f8}'
    }
  };
  return implementations[item.name];
}

function mediumImplementation(item) {
  const implementations = {
    ProductFilterPanel: {
      props: { products: ['array', [{ id: 1, name: '机械键盘', category: '外设', price: 499, stock: 8 }, { id: 2, name: '显示器支架', category: '办公', price: 269, stock: 0 }, { id: 3, name: '降噪耳机', category: '音频', price: 899, stock: 4 }, { id: 4, name: '桌面灯', category: '办公', price: 159, stock: 12 }]], categories: ['array', ['外设', '办公', '音频']] },
      state: { query: '', category: 'all', maxPrice: 1000, inStockOnly: false, sort: 'name', selectedId: null },
      computed: [['visibleProducts', "const q = this.query.toLowerCase(); return this.products.filter(item => item.name.toLowerCase().indexOf(q) >= 0 && (this.category === 'all' || item.category === this.category) && item.price <= this.maxPrice && (!this.inStockOnly || item.stock > 0)).slice().sort((a, b) => this.sort === 'price' ? a.price - b.price : a.name.localeCompare(b.name, 'zh-CN'));"], ['resultCount', "return this.visibleProducts.length;"]],
      methods: [['updateQuery', 'event', "this.setValue('query', event.target.value);"], ['updateCategory', 'event', "this.setValue('category', event.target.value);"], ['updatePrice', 'event', "this.setValue('maxPrice', Number(event.target.value) || 0);"], ['toggleStock', 'event', "this.setValue('inStockOnly', event.target.checked);"], ['updateSort', 'event', "this.setValue('sort', event.target.value);"], ['select', 'id', "this.setValue('selectedId', id); this.emitEvent('select', id);"], ['clear', '', "this.setValue('query', ''); this.setValue('category', 'all'); this.setValue('maxPrice', 1000); this.setValue('inStockOnly', false);"]],
      template: `<section class="product-filter-panel"><header><h2>商品筛选</h2><strong>{{ resultCount }} 项</strong></header><div class="filters"><input :value="query" @input="updateQuery" placeholder="搜索商品"><select :value="category" @change="updateCategory"><option value="all">全部分类</option><option v-for="item in categories" :key="item" :value="item">{{ item }}</option></select><label>最高 ¥{{ maxPrice }}<input type="range" min="100" max="1000" step="50" :value="maxPrice" @input="updatePrice"></label><label><input type="checkbox" :checked="inStockOnly" @change="toggleStock"> 仅看有货</label><select :value="sort" @change="updateSort"><option value="name">按名称</option><option value="price">按价格</option></select><button @click="clear">清空</button></div><div class="products"><button v-for="product in visibleProducts" :key="product.id" :class="product.id === selectedId ? 'selected' : ''" @click="select(product.id)"><strong>{{ product.name }}</strong><span>¥{{ product.price }} · 库存 {{ product.stock }}</span></button></div><p v-if="!visibleProducts.length" class="empty">无匹配商品</p></section>`,
      css: 'header{display:flex;justify-content:space-between}.filters{display:flex;gap:8px;flex-wrap:wrap}.filters label{display:flex;align-items:center;gap:6px}.products{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-top:14px}.products button{text-align:left}.products button span{display:block}.products button.selected{background:#dbeafe;border-color:#2563eb}.empty{text-align:center}'
    },
    HabitWeekTracker: {
      props: { habits: ['array', [{ id: 'read', name: '阅读', goal: 5 }, { id: 'walk', name: '步行', goal: 7 }, { id: 'sleep', name: '早睡', goal: 4 }]], dayLabels: ['array', ['一', '二', '三', '四', '五', '六', '日']] }, state: { records: {}, selectedHabit: 'read' },
      inited: "const records = {}; this.habits.forEach(habit => records[habit.id] = [false, false, false, false, false, false, false]); this.setValue('records', records); this.setValue('selectedHabit', this.habits[0] ? this.habits[0].id : '');",
      computed: [['totalDone', "return Object.keys(this.records).reduce((sum, key) => sum + this.records[key].filter(Boolean).length, 0);"], ['percent', "const total = this.habits.length * this.dayLabels.length || 1; return Math.round(this.totalDone / total * 100);"], ['barStyle', "return 'width:' + this.percent + '%';"]],
      methods: [['toggle', 'habitId, index', "const records = Object.assign({}, this.records); const row = records[habitId].slice(); row[index] = !row[index]; records[habitId] = row; this.setValue('records', records); this.emitEvent('change', records);"], ['selectHabit', 'id', "this.setValue('selectedHabit', id);"], ['resetWeek', '', "const records = {}; this.habits.forEach(habit => records[habit.id] = this.dayLabels.map(() => false)); this.setValue('records', records);"], ['isDone', 'habitId, index, records', "return !!(records[habitId] && records[habitId][index]);"], ['rowCount', 'habitId, records', "return records[habitId] ? records[habitId].filter(Boolean).length : 0;"]],
      template: `<section class="habit-week-tracker"><header><h2>本周习惯</h2><button @click="resetWeek">重置</button></header><div class="week-head"><span></span><b v-for="day in dayLabels" :key="day">{{ day }}</b><span>完成</span></div><div v-for="habit in habits" :key="habit.id" :class="'habit-row ' + (habit.id === selectedHabit ? 'active' : '')" @click="selectHabit(habit.id)"><strong>{{ habit.name }}</strong><button v-for="day, index in dayLabels" :key="day" :class="isDone(habit.id, index, records) ? 'done' : ''" @click.stop="toggle(habit.id, index)">✓</button><span>{{ rowCount(habit.id, records) }}/{{ habit.goal }}</span></div><div class="progress"><span :style="barStyle"></span></div><p>总完成率 {{ percent }}%</p></section>`,
      sanTemplate: `<section class="habit-week-tracker"><header><h2>本周习惯</h2><button on-click="resetWeek">重置</button></header><div class="week-head"><span></span><b s-for="day in dayLabels">{{ day }}</b><span>完成</span></div><div s-for="habit in habits" class="{{ 'habit-row ' + (habit.id === selectedHabit ? 'active' : '') }}" on-click="selectHabit(habit.id)"><strong>{{ habit.name }}</strong><button s-for="day, index in dayLabels" class="{{ isDone(habit.id, index, records) ? 'done' : '' }}" on-click="toggle(habit.id, index)">✓</button><span>{{ rowCount(habit.id, records) }}/{{ habit.goal }}</span></div><div class="progress"><span style="{{ barStyle }}"></span></div><p>总完成率 {{ percent }}%</p></section>`,
      css: 'header{display:flex;justify-content:space-between}.week-head,.habit-row{display:grid;grid-template-columns:90px repeat(7,1fr) 55px;gap:5px;align-items:center}.week-head{text-align:center}.habit-row{padding:7px;border-left:3px solid transparent}.habit-row.active{border-color:#16a34a;background:#f0fdf4}.habit-row button.done{background:#16a34a;color:#fff}.progress{height:7px;background:#e5e7eb}.progress span{display:block;height:100%;background:#16a34a}'
    },
    InvoiceLineEditor: {
      props: { initialLines: ['array', [{ id: 1, description: '设计服务', quantity: 2, price: 800 }, { id: 2, description: '部署支持', quantity: 1, price: 500 }]], taxRate: ['number', 6] }, state: { lines: [], discount: 0, draft: '', nextId: 10 }, inited: "this.setValue('lines', this.initialLines.map(item => Object.assign({}, item)));", computed: [['subtotal', "return this.lines.reduce((sum, item) => sum + item.quantity * item.price, 0);"], ['tax', "return this.subtotal * this.taxRate / 100;"], ['payable', "return Math.max(0, this.subtotal + this.tax - this.discount);"]],
      methods: [['updateLine', 'id, field, event', "const value = field === 'description' ? event.target.value : Math.max(0, Number(event.target.value) || 0); this.setValue('lines', this.lines.map(item => item.id === id ? Object.assign({}, item, { [field]: value }) : item)); this.notify();"], ['updateDraft', 'event', "this.setValue('draft', event.target.value);"], ['addLine', '', "const text = this.draft.trim(); if (!text) return; this.setValue('lines', this.lines.concat({ id: this.nextId, description: text, quantity: 1, price: 0 })); this.setValue('nextId', this.nextId + 1); this.setValue('draft', ''); this.notify();"], ['removeLine', 'id', "this.setValue('lines', this.lines.filter(item => item.id !== id)); this.notify();"], ['updateDiscount', 'event', "this.setValue('discount', Math.max(0, Number(event.target.value) || 0)); this.notify();"], ['notify', '', "this.emitEvent('change', { lines: this.lines, discount: this.discount });"]],
      template: `<section class="invoice-line-editor"><h2>服务发票</h2><table><thead><tr><th>项目</th><th>数量</th><th>单价</th><th>小计</th><th></th></tr></thead><tbody><tr v-for="line in lines" :key="line.id"><td><input :value="line.description" @input="updateLine(line.id, 'description', $event)"></td><td><input type="number" :value="line.quantity" @input="updateLine(line.id, 'quantity', $event)"></td><td><input type="number" :value="line.price" @input="updateLine(line.id, 'price', $event)"></td><td>¥{{ line.quantity * line.price }}</td><td><button @click="removeLine(line.id)">删除</button></td></tr></tbody></table><div class="add-row"><input :value="draft" @input="updateDraft" placeholder="新增项目"><button @click="addLine">添加行</button></div><aside><label>折扣<input type="number" :value="discount" @input="updateDiscount"></label><span>未税 ¥{{ subtotal }}</span><span>税额 ¥{{ tax }}</span><strong>应付 ¥{{ payable }}</strong></aside></section>`,
      css: 'table{width:100%;border-collapse:collapse}th,td{padding:7px;border-bottom:1px solid #e2e8f0}td input{width:100%}.add-row{display:flex;gap:8px;margin:10px 0}.add-row input{flex:1}aside{display:flex;justify-content:flex-end;align-items:center;gap:14px;padding:12px;background:#ecfdf5}aside label{display:flex;align-items:center;gap:5px}aside input{width:80px}'
    },
    KanbanColumnBoard: {
      props: { initialTasks: ['array', [{ id: 1, title: '需求拆解', status: 'todo' }, { id: 2, title: '组件实现', status: 'doing' }, { id: 3, title: '人工复核', status: 'done' }]], columns: ['array', [{ id: 'todo', label: '待处理' }, { id: 'doing', label: '进行中' }, { id: 'done', label: '已完成' }]] }, state: { tasks: [], selectedId: null, draft: '', nextId: 10 }, inited: "this.setValue('tasks', this.initialTasks.map(item => Object.assign({}, item)));", computed: [['boardColumns', "return this.columns.map(column => { const tasks = this.tasks.filter(item => item.status === column.id); return Object.assign({}, column, { tasks, count: tasks.length }); });"], ['selectedTask', "return this.tasks.find(item => item.id === this.selectedId) || null;"]],
      methods: [['select', 'id', "this.setValue('selectedId', id);"], ['move', 'delta', "const task = this.selectedTask; if (!task) return; const index = this.columns.findIndex(item => item.id === task.status); const target = this.columns[index + delta]; if (!target) return; this.setValue('tasks', this.tasks.map(item => item.id === task.id ? Object.assign({}, item, { status: target.id }) : item)); this.emitEvent('move', { id: task.id, status: target.id });"], ['updateDraft', 'event', "this.setValue('draft', event.target.value);"], ['add', 'event', "event.preventDefault(); const title = this.draft.trim(); if (!title) return; const task = { id: this.nextId, title, status: 'todo' }; this.setValue('tasks', this.tasks.concat(task)); this.setValue('nextId', this.nextId + 1); this.setValue('draft', ''); this.emitEvent('add', task);"]],
      template: `<section class="kanban-column-board"><header><h2>内容制作看板</h2><div class="actions"><button @click="move(-1)" :disabled="!selectedTask">← 左移</button><button @click="move(1)" :disabled="!selectedTask">右移 →</button></div></header><div class="board"><article v-for="column in boardColumns" :key="column.id"><h3>{{ column.label }} · {{ column.count }}</h3><button v-for="task in column.tasks" :key="task.id" :class="task.id === selectedId ? 'selected' : ''" @click="select(task.id)">{{ task.title }}</button></article></div><form @submit="add"><input :value="draft" @input="updateDraft" placeholder="新增待处理任务"><button class="primary" type="submit">添加</button></form></section>`,
      sanTemplate: `<section class="kanban-column-board"><header><h2>内容制作看板</h2><div class="actions"><button on-click="move(-1)" disabled="{{ !selectedTask }}">← 左移</button><button on-click="move(1)" disabled="{{ !selectedTask }}">右移 →</button></div></header><div class="board"><article s-for="column in boardColumns trackby column.id"><h3>{{ column.label }} · {{ column.count }}</h3><button s-for="task in column.tasks trackby task.id" class="{{ task.id === selectedId ? 'selected' : '' }}" on-click="select(task.id)">{{ task.title }}</button></article></div><form on-submit="add"><input value="{{ draft }}" on-input="updateDraft" placeholder="新增待处理任务"><button class="primary" type="submit">添加</button></form></section>`,
      css: 'header{display:flex;justify-content:space-between}.board{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.board article{min-height:190px;padding:10px;background:#f8fafc}.board article>button{display:block;width:100%;margin:6px 0;text-align:left}.board button.selected{background:#ede9fe;border-color:#7c3aed}form{display:flex;gap:8px;margin-top:12px}form input{flex:1}'
    },
    MeetingPollScheduler: {
      props: { participants: ['array', ['林晓', '周宁', '陈雨']], slots: ['array', [{ id: 1, label: '周二 10:00' }, { id: 2, label: '周三 14:00' }, { id: 3, label: '周五 16:00' }]] }, state: { participant: '林晓', votes: {}, confirmedId: null }, inited: "const votes = {}; this.slots.forEach(slot => votes[slot.id] = []); this.setValue('votes', votes); this.setValue('participant', this.participants[0] || '');", computed: [['bestId', "const votes = this.votes || {}; const rows = this.slots.slice().sort((a, b) => ((votes[b.id] || []).length - (votes[a.id] || []).length)); return rows[0] ? rows[0].id : null;"]],
      methods: [['updateParticipant', 'event', "this.setValue('participant', event.target.value);"], ['toggleVote', 'slotId', "const votes = Object.assign({}, this.votes); const list = votes[slotId].slice(); const index = list.indexOf(this.participant); votes[slotId] = index >= 0 ? list.filter(name => name !== this.participant) : list.concat(this.participant); this.setValue('votes', votes); this.emitEvent('vote', { slotId, participants: votes[slotId] });"], ['hasVote', 'slotId, participant, votes', "return votes[slotId].indexOf(participant) >= 0;"], ['voteCount', 'slotId, votes', "return votes[slotId].length;"], ['confirm', 'id', "this.setValue('confirmedId', id); this.emitEvent('confirm', id);"]],
      template: `<section class="meeting-poll-scheduler"><header><h2>会议时间投票</h2><select :value="participant" @change="updateParticipant"><option v-for="name in participants" :key="name" :value="name">{{ name }}</option></select></header><div class="slots"><article v-for="slot in slots" :key="slot.id" :class="slot.id === bestId ? 'best' : ''"><strong>{{ slot.label }}</strong><span>{{ voteCount(slot.id, votes) }} 票</span><button :class="hasVote(slot.id, participant, votes) ? 'selected' : ''" @click="toggleVote(slot.id)">{{ hasVote(slot.id, participant, votes) ? '取消可参加' : '我可参加' }}</button><button @click="confirm(slot.id)">确定此时间</button></article></div><p v-if="confirmedId">已确定候选 #{{ confirmedId }}</p></section>`,
      css: 'header{display:flex;justify-content:space-between}.slots{display:grid;gap:8px}.slots article{display:grid;grid-template-columns:1fr 55px auto auto;gap:8px;align-items:center;padding:10px;border:1px solid #e2e8f0}.slots article.best{border-color:#0369a1;background:#f0f9ff}.slots button.selected{background:#dbeafe}'
    },
    ExpenseSplitLedger: {
      props: { members: ['array', ['林晓', '周宁', '陈雨']], initialEntries: ['array', [{ id: 1, payer: '林晓', amount: 180, note: '晚餐' }]] }, state: { entries: [], payer: '林晓', amount: 0, note: '', nextId: 10 }, inited: "this.setValue('entries', this.initialEntries.map(item => Object.assign({}, item))); this.setValue('payer', this.members[0] || '');", computed: [['total', "return this.entries.reduce((sum, item) => sum + item.amount, 0);"], ['balances', "const share = this.total / (this.members.length || 1); return this.members.map(name => ({ name, balance: this.entries.filter(item => item.payer === name).reduce((sum, item) => sum + item.amount, 0) - share }));"]],
      methods: [['updatePayer', 'event', "this.setValue('payer', event.target.value);"], ['updateAmount', 'event', "this.setValue('amount', Number(event.target.value) || 0);"], ['updateNote', 'event', "this.setValue('note', event.target.value);"], ['add', 'event', "event.preventDefault(); if (this.amount <= 0 || !this.note.trim()) return; this.setValue('entries', this.entries.concat({ id: this.nextId, payer: this.payer, amount: this.amount, note: this.note.trim() })); this.setValue('nextId', this.nextId + 1); this.setValue('amount', 0); this.setValue('note', ''); this.notify();"], ['remove', 'id', "this.setValue('entries', this.entries.filter(item => item.id !== id)); this.notify();"], ['notify', '', "this.emitEvent('change', this.entries.slice());"], ['balanceText', 'value', "return value >= 0 ? '应收 ¥' + value.toFixed(2) : '应补 ¥' + Math.abs(value).toFixed(2);"]],
      template: `<section class="expense-split-ledger"><h2>旅行费用分摊</h2><form @submit="add"><select :value="payer" @change="updatePayer"><option v-for="name in members" :key="name" :value="name">{{ name }}</option></select><input type="number" :value="amount" @input="updateAmount" placeholder="金额"><input :value="note" @input="updateNote" placeholder="用途"><button class="primary" type="submit">记一笔</button></form><ul><li v-for="entry in entries" :key="entry.id"><span>{{ entry.payer }} 支付 {{ entry.note }}</span><strong>¥{{ entry.amount }}</strong><button @click="remove(entry.id)">删除</button></li></ul><div class="balances"><span v-for="row in balances" :key="row.name" :class="row.balance >= 0 ? 'positive' : 'negative'">{{ row.name }}：{{ balanceText(row.balance) }}</span></div></section>`,
      css: 'form{display:grid;grid-template-columns:120px 100px 1fr auto;gap:8px}ul{padding:0;list-style:none}li{display:grid;grid-template-columns:1fr 90px auto;gap:8px;padding:8px;border-bottom:1px solid #e2e8f0}.balances{display:flex;gap:8px;flex-wrap:wrap}.balances span{padding:8px;background:#f8fafc}.positive{color:#15803d}.negative{color:#b91c1c}'
    },
    ImageCropControls: {
      props: { canvas: ['object', { width: 640, height: 360 }], initialCrop: ['object', { x: 10, y: 10, width: 45, height: 55 }] }, state: { crop: {}, locked: false }, inited: "this.setValue('crop', Object.assign({}, this.initialCrop));", computed: [['cropStyle', "return 'left:' + this.crop.x + '%;top:' + this.crop.y + '%;width:' + this.crop.width + '%;height:' + this.crop.height + '%';"]], watch: [['locked', "if (this.locked) this.setValue('crop', Object.assign({}, this.crop, { height: Math.round(this.crop.width * this.canvas.width / this.canvas.height) }));"]],
      methods: [['update', 'field, event', "let value = Math.max(0, Math.min(100, Number(event.target.value) || 0)); const crop = Object.assign({}, this.crop, { [field]: value }); if (this.locked && field === 'width') crop.height = Math.min(100, Math.round(value * this.canvas.width / this.canvas.height)); this.setValue('crop', crop); this.emitEvent('change', crop);"], ['toggleLock', 'event', "this.setValue('locked', event.target.checked);"], ['reset', '', "this.setValue('crop', Object.assign({}, this.initialCrop));"]],
      template: `<section class="image-crop-controls"><h2>裁剪参数</h2><div class="crop-layout"><div class="canvas"><div class="crop-box" :style="cropStyle"></div></div><div class="controls"><label v-for="field in ['x','y','width','height']" :key="field">{{ field }}<input type="number" :value="crop[field]" @input="update(field, $event)"></label><label><input type="checkbox" :checked="locked" @change="toggleLock"> 锁定宽高比</label><button @click="reset">重置</button></div></div></section>`,
      sanTemplate: `<section class="image-crop-controls"><h2>裁剪参数</h2><div class="crop-layout"><div class="canvas"><div class="crop-box" style="{{ cropStyle }}"></div></div><div class="controls"><label s-for="field in fields">{{ field }}<input type="number" value="{{ crop[field] }}" on-input="update(field, $event)"></label><label><input type="checkbox" checked="{{ locked }}" on-change="toggleLock"> 锁定宽高比</label><button on-click="reset">重置</button></div></div></section>`,
      sanState: { fields: ['x', 'y', 'width', 'height'] },
      css: '.crop-layout{display:grid;grid-template-columns:1fr 190px;gap:14px}.canvas{position:relative;aspect-ratio:16/9;background:linear-gradient(135deg,#dbeafe,#fce7f3);overflow:hidden}.crop-box{position:absolute;border:3px solid #db2777;background:#fff4}.controls{display:grid;gap:7px}.controls label{display:grid;grid-template-columns:55px 1fr;align-items:center}'
    },
    CourseModuleAccordion: {
      props: { modules: ['array', [{ id: 1, title: '模板迁移', lessons: [{ id: 11, title: '指令转换' }, { id: 12, title: '循环与条件' }] }, { id: 2, title: '脚本迁移', lessons: [{ id: 21, title: '响应式数据' }, { id: 22, title: '生命周期' }] }]], initiallyOpen: ['number', 1] }, state: { openIds: [], completedIds: [], unfinishedOnly: false }, inited: "this.setValue('openIds', [this.initiallyOpen]);", computed: [['totalLessons', "return this.modules.reduce((sum, module) => sum + module.lessons.length, 0);"], ['progress', "return Math.round(this.completedIds.length / (this.totalLessons || 1) * 100);"]],
      methods: [['toggleModule', 'id', "const open = this.openIds; this.setValue('openIds', open.indexOf(id) >= 0 ? open.filter(item => item !== id) : open.concat(id));"], ['isOpen', 'id, openIds', "return openIds.indexOf(id) >= 0;"], ['toggleLesson', 'id', "const completed = this.completedIds; this.setValue('completedIds', completed.indexOf(id) >= 0 ? completed.filter(item => item !== id) : completed.concat(id)); this.emitEvent('progress', this.completedIds);"], ['isCompleted', 'id, completedIds', "return completedIds.indexOf(id) >= 0;"], ['toggleFilter', 'event', "this.setValue('unfinishedOnly', event.target.checked);"], ['visibleLessons', 'lessons, completedIds, unfinishedOnly', "return unfinishedOnly ? lessons.filter(item => completedIds.indexOf(item.id) < 0) : lessons;"]],
      template: `<section class="course-module-accordion"><header><h2>课程进度 {{ progress }}%</h2><label><input type="checkbox" :checked="unfinishedOnly" @change="toggleFilter"> 仅未完成</label></header><article v-for="module in modules" :key="module.id"><button class="module-head" @click="toggleModule(module.id)"><strong>{{ module.title }}</strong><span>{{ isOpen(module.id, openIds) ? '收起' : '展开' }}</span></button><div v-if="isOpen(module.id, openIds)" class="lessons"><label v-for="lesson in visibleLessons(module.lessons, completedIds, unfinishedOnly)" :key="lesson.id" :class="isCompleted(lesson.id, completedIds) ? 'done' : ''"><input type="checkbox" :checked="isCompleted(lesson.id, completedIds)" @change="toggleLesson(lesson.id)"> {{ lesson.title }}</label></div></article></section>`,
      css: 'header{display:flex;justify-content:space-between}.course-module-accordion article{border:1px solid #e2e8f0}.module-head{display:flex;width:100%;justify-content:space-between;border:0}.lessons{display:grid;padding:10px}.lessons label{padding:7px}.lessons label.done{text-decoration:line-through;color:#64748b}'
    },
    DeliveryRouteTimeline: {
      props: { routeName: ['string', '城西配送线'], initialStops: ['array', [{ id: 1, name: '分拨中心', eta: 0, status: 'done' }, { id: 2, name: '大学城', eta: 25, status: 'active' }, { id: 3, name: '科技园', eta: 55, status: 'waiting' }]] }, state: { stops: [], selectedId: 2, delay: 0 }, inited: "this.setValue('stops', this.initialStops.map(item => Object.assign({}, item)));", computed: [['completedCount', "return this.stops.filter(item => item.status === 'done').length;"], ['selectedStop', "return this.stops.find(item => item.id === this.selectedId) || null;"]],
      methods: [['select', 'id', "this.setValue('selectedId', id);"], ['advance', '', "const index = this.stops.findIndex(item => item.status === 'active'); if (index < 0) return; const next = this.stops.map((item, i) => Object.assign({}, item, { status: i === index ? 'done' : i === index + 1 ? 'active' : item.status })); this.setValue('stops', next); this.emitEvent('status', next);"], ['updateDelay', 'event', "this.setValue('delay', Number(event.target.value) || 0);"], ['applyDelay', '', "const selected = this.selectedStop; if (!selected || !this.delay) return; this.setValue('stops', this.stops.map(item => item.eta >= selected.eta ? Object.assign({}, item, { eta: item.eta + this.delay }) : item)); this.setValue('delay', 0);"]],
      template: `<section class="delivery-route-timeline"><header><h2>{{ routeName }}</h2><span>完成 {{ completedCount }}/{{ stops.length }}</span></header><div class="route-layout"><ol><li v-for="stop in stops" :key="stop.id" :class="stop.status" @click="select(stop.id)"><i></i><div><strong>{{ stop.name }}</strong><span>预计 +{{ stop.eta }} 分钟</span></div></li></ol><aside v-if="selectedStop"><h3>{{ selectedStop.name }}</h3><label>增加延误<input type="number" :value="delay" @input="updateDelay"></label><button @click="applyDelay">应用延误</button><button class="primary" @click="advance">到达并前往下一站</button></aside></div></section>`,
      css: 'header{display:flex;justify-content:space-between}.route-layout{display:grid;grid-template-columns:1fr 220px;gap:16px}ol{padding:0;list-style:none}li{display:flex;gap:10px;padding:11px;border-left:4px solid #cbd5e1}li i{width:13px;height:13px;border-radius:50%;background:#cbd5e1}li.done{border-color:#16a34a}li.active{border-color:#0284c7;background:#f0f9ff}li span{display:block}aside{display:grid;gap:9px;padding:12px;background:#f8fafc}aside label{display:grid}'
    },
    FormRulePlayground: {
      props: { rules: ['array', [{ id: 'email', label: '邮箱格式' }, { id: 'adult', label: '年龄不少于 18' }, { id: 'name', label: '用户名不少于 3 位' }]], title: ['string', '账号规则测试'] }, state: { form: { name: '', email: '', age: 18 }, enabled: ['email', 'adult', 'name'], submitted: false }, computed: [['errors', "const errors = []; if (this.enabled.indexOf('name') >= 0 && this.form.name.trim().length < 3) errors.push('用户名至少 3 位'); if (this.enabled.indexOf('email') >= 0 && this.form.email.indexOf('@') < 0) errors.push('邮箱格式无效'); if (this.enabled.indexOf('adult') >= 0 && Number(this.form.age) < 18) errors.push('年龄必须不少于 18'); return errors;"], ['valid', "return this.errors.length === 0;"]],
      methods: [['updateField', 'field, event', "this.setValue('form', Object.assign({}, this.form, { [field]: event.target.value })); this.setValue('submitted', false);"], ['toggleRule', 'id', "const list = this.enabled; this.setValue('enabled', list.indexOf(id) >= 0 ? list.filter(item => item !== id) : list.concat(id));"], ['isEnabled', 'id, enabled', "return enabled.indexOf(id) >= 0;"], ['submit', 'event', "event.preventDefault(); this.setValue('submitted', true); if (this.valid) this.emitEvent('submit', Object.assign({}, this.form));"]],
      template: `<section class="form-rule-playground"><h2>{{ title }}</h2><div class="rule-strip"><label v-for="rule in rules" :key="rule.id"><input type="checkbox" :checked="isEnabled(rule.id, enabled)" @change="toggleRule(rule.id)"> {{ rule.label }}</label></div><form @submit="submit"><input :value="form.name" @input="updateField('name', $event)" placeholder="用户名"><input :value="form.email" @input="updateField('email', $event)" placeholder="邮箱"><input type="number" :value="form.age" @input="updateField('age', $event)" placeholder="年龄"><button class="primary" type="submit">验证并提交</button></form><ul v-if="submitted && errors.length"><li v-for="error in errors" :key="error">{{ error }}</li></ul><p v-if="submitted && valid" class="success">表单通过全部启用规则</p></section>`,
      css: '.rule-strip{display:flex;gap:10px;flex-wrap:wrap;padding:10px;background:#f8fafc}form{display:grid;grid-template-columns:1fr 1fr 100px auto;gap:8px;margin-top:12px}ul{color:#b91c1c}.success{color:#15803d}'
    },
    DataPaginationTable: {
      props: { rows: ['array', Array.from({ length: 12 }, (_, index) => ({ id: index + 1, name: `样本-${index + 1}`, score: 60 + (index * 7) % 38 }))], initialPageSize: ['number', 4] }, state: { page: 1, pageSize: 4, sortKey: 'id', selectedId: null }, inited: "this.setValue('pageSize', this.initialPageSize);", computed: [['sortedRows', "return this.rows.slice().sort((a, b) => this.sortKey === 'score' ? b.score - a.score : a.id - b.id);"], ['pageCount', "return Math.max(1, Math.ceil(this.sortedRows.length / this.pageSize));"], ['pageRows', "const start = (this.page - 1) * this.pageSize; return this.sortedRows.slice(start, start + this.pageSize);"], ['selectedRow', "return this.rows.find(item => item.id === this.selectedId) || null;"]],
      methods: [['setSort', 'key', "this.setValue('sortKey', key); this.setValue('page', 1);"], ['go', 'delta', "const next = Math.max(1, Math.min(this.pageCount, this.page + delta)); this.setValue('page', next); this.emitEvent('page', next);"], ['updatePageSize', 'event', "this.setValue('pageSize', Number(event.target.value)); this.setValue('page', 1);"], ['select', 'id', "this.setValue('selectedId', id); this.emitEvent('select', id);"]],
      template: `<section class="data-pagination-table"><header><h2>评估样本</h2><select :value="pageSize" @change="updatePageSize"><option :value="4">4 行</option><option :value="6">6 行</option></select></header><table><thead><tr><th><button @click="setSort('id')">编号</button></th><th>名称</th><th><button @click="setSort('score')">得分</button></th></tr></thead><tbody><tr v-for="row in pageRows" :key="row.id" :class="row.id === selectedId ? 'selected' : ''" @click="select(row.id)"><td>{{ row.id }}</td><td>{{ row.name }}</td><td>{{ row.score }}</td></tr></tbody></table><footer><button @click="go(-1)" :disabled="page === 1">上一页</button><span>{{ page }}/{{ pageCount }}</span><button @click="go(1)" :disabled="page === pageCount">下一页</button><strong v-if="selectedRow">已选 {{ selectedRow.name }}</strong></footer></section>`,
      css: 'header,footer{display:flex;justify-content:space-between;align-items:center}table{width:100%;border-collapse:collapse;margin:12px 0}th,td{padding:9px;border:1px solid #e2e8f0}th button{border:0}tr.selected{background:#f1f5f9}footer{justify-content:flex-start;gap:10px}footer strong{margin-left:auto}'
    },
    ColorPaletteBuilder: {
      props: { initialColors: ['array', ['#2563eb', '#7c3aed', '#059669']], maxColors: ['number', 6] }, state: { colors: [], draft: '#dc2626', locked: [], selectedIndex: 0 }, inited: "this.setValue('colors', this.initialColors.slice());", computed: [['previewStyle', "return 'background:linear-gradient(90deg,' + this.colors.join(',') + ')';"], ['canAdd', "return this.colors.length < this.maxColors;"]],
      methods: [['updateDraft', 'event', "this.setValue('draft', event.target.value);"], ['add', '', "if (!this.canAdd) return; this.setValue('colors', this.colors.concat(this.draft)); this.notify();"], ['remove', 'index', "if (this.locked.indexOf(index) >= 0) return; this.setValue('colors', this.colors.filter((item, i) => i !== index)); this.notify();"], ['toggleLock', 'index', "const list = this.locked; this.setValue('locked', list.indexOf(index) >= 0 ? list.filter(item => item !== index) : list.concat(index));"], ['isLocked', 'index, locked', "return locked.indexOf(index) >= 0;"], ['notify', '', "this.emitEvent('change', this.colors.slice());"], ['exportPalette', '', "this.emitEvent('export', this.colors.join(','));"]],
      template: `<section class="color-palette-builder"><header><h2>品牌色板</h2><button @click="exportPalette">导出</button></header><div class="preview" :style="previewStyle"></div><div class="swatches"><article v-for="color, index in colors" :key="index" :style="'border-color:' + color"><i :style="'background:' + color"></i><code>{{ color }}</code><button @click="toggleLock(index)">{{ isLocked(index, locked) ? '解锁' : '锁定' }}</button><button @click="remove(index)" :disabled="isLocked(index, locked)">删除</button></article></div><div class="add-color"><input type="color" :value="draft" @input="updateDraft"><button class="primary" @click="add" :disabled="!canAdd">添加颜色</button></div></section>`,
      css: 'header{display:flex;justify-content:space-between}.preview{height:60px;margin:12px 0}.swatches{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.swatches article{display:grid;grid-template-columns:32px 1fr auto auto;gap:6px;align-items:center;padding:8px;border-left:5px solid}.swatches i{height:28px}.add-color{display:flex;gap:8px;margin-top:12px}'
    },
    AudioSegmentMarker: {
      props: { duration: ['number', 300], initialMarkers: ['array', [{ id: 1, start: 20, end: 55, label: '引言' }, { id: 2, start: 120, end: 165, label: '核心观点' }]] }, state: { position: 0, markers: [], start: 0, end: 30, label: '', selectedId: null, nextId: 10 }, inited: "this.setValue('markers', this.initialMarkers.map(item => Object.assign({}, item)));", computed: [['headStyle', "return 'left:' + this.position / this.duration * 100 + '%';"]],
      methods: [['updatePosition', 'event', "this.setValue('position', Number(event.target.value));"], ['updateField', 'field, event', "this.setValue(field, field === 'label' ? event.target.value : Number(event.target.value) || 0);"], ['add', 'event', "event.preventDefault(); if (!this.label.trim() || this.start >= this.end || this.end > this.duration) return; this.setValue('markers', this.markers.concat({ id: this.nextId, start: this.start, end: this.end, label: this.label.trim() })); this.setValue('nextId', this.nextId + 1); this.setValue('label', ''); this.notify();"], ['remove', 'id', "this.setValue('markers', this.markers.filter(item => item.id !== id)); this.notify();"], ['select', 'id', "this.setValue('selectedId', id);"], ['markerStyle', 'marker, duration', "return 'left:' + marker.start / duration * 100 + '%;width:' + (marker.end - marker.start) / duration * 100 + '%';"], ['notify', '', "this.emitEvent('markers-change', this.markers.slice());"]],
      template: `<section class="audio-segment-marker"><h2>访谈片段标注</h2><input class="scrubber" type="range" min="0" :max="duration" :value="position" @input="updatePosition"><div class="timeline"><span class="head" :style="headStyle"></span><button v-for="marker in markers" :key="marker.id" :class="marker.id === selectedId ? 'selected' : ''" :style="markerStyle(marker, duration)" @click="select(marker.id)">{{ marker.label }}</button></div><form @submit="add"><input type="number" :value="start" @input="updateField('start', $event)" placeholder="开始秒"><input type="number" :value="end" @input="updateField('end', $event)" placeholder="结束秒"><input :value="label" @input="updateField('label', $event)" placeholder="标签"><button class="primary" type="submit">添加</button></form><ul><li v-for="marker in markers" :key="marker.id">{{ marker.start }}–{{ marker.end }}s {{ marker.label }}<button @click="remove(marker.id)">删除</button></li></ul></section>`,
      css: '.scrubber{width:100%}.timeline{position:relative;height:70px;margin:10px 0;background:#f1f5f9}.timeline .head{position:absolute;top:0;bottom:0;width:2px;background:#be185d}.timeline button{position:absolute;top:20px;overflow:hidden;white-space:nowrap}.timeline button.selected{background:#fce7f3}form{display:grid;grid-template-columns:90px 90px 1fr auto;gap:8px}ul{padding:0;list-style:none}li{display:flex;justify-content:space-between;padding:6px}'
    }
  };
  if (implementations[item.name]) return implementations[item.name];
  return genericMedium(item);
}

function genericMedium(item) {
  const variants = {
    FormRulePlayground: null,
    DataPaginationTable: null,
    CourseModuleAccordion: null,
    DeliveryRouteTimeline: null,
    ImageCropControls: null
  };
  if (Object.prototype.hasOwnProperty.call(variants, item.name)) throw new Error(`Missing explicit medium implementation: ${item.name}`);
  throw new Error(`Unknown medium component: ${item.name}`);
}

function complexImplementation(item) {
  return buildComplexImplementation(item);
  /* Legacy prototype retained below only as historical context. It is unreachable;
     the production batch uses the structurally distinct implementations above. */
  const seed = {
    WorkflowDiagramEditor: ['工作流编排', ['读取数据', '转换字段', '质量校验'], ['draft', 'validated', 'running', 'saved']],
    PolicyRuleComposer: ['策略规则', ['用户角色', '资源标签', '访问时段'], ['draft', 'tested', 'published', 'archived']],
    FleetDispatchConsole: ['车队调度', ['订单池', '车辆容量', '配送区域'], ['unassigned', 'planned', 'dispatched', 'returned']],
    ClinicalTriageBoard: ['急诊分诊', ['患者队列', '生命体征', '床位资源'], ['waiting', 'triaged', 'assigned', 'discharged']],
    DependencyReleasePlanner: ['发布依赖', ['服务版本', '依赖关系', '环境门禁'], ['editing', 'blocked', 'approved', 'released']],
    EnergyLoadScheduler: ['负载排程', ['设备负载', '小时费率', '功率上限'], ['draft', 'balanced', 'scheduled', 'completed']],
    AuctionControlRoom: ['竞拍控制', ['拍品清单', '出价队列', '风险标记'], ['preview', 'running', 'paused', 'closed']],
    ResearchAnnotationStudio: ['语料标注', ['文档跨度', '标签集合', '冲突仲裁'], ['annotating', 'conflicted', 'reviewed', 'submitted']],
    ProcurementBidMatrix: ['投标评审', ['供应商报价', '评价权重', '评委评分'], ['scoring', 'locked', 'ranked', 'awarded']],
    WarehousePickingWave: ['拣选波次', ['订单任务', '库位路径', '人员分配'], ['building', 'picking', 'checking', 'completed']],
    SubscriptionRevenueModeler: ['收入建模', ['套餐分群', '增长流失', '月度序列'], ['baseline', 'modeled', 'compared', 'exported']],
    ApiContractWorkbench: ['接口契约', ['端点参数', '响应结构', '校验问题'], ['editing', 'validated', 'generated', 'saved']],
    CrisisCommunicationHub: ['危机沟通', ['受众渠道', '消息版本', '审批记录'], ['draft', 'reviewing', 'approved', 'sent']]
  }[item.name];
  const [title, dimensions, stages] = seed;
  const initialRecords = dimensions.map((name, index) => ({ id: index + 1, name, value: 30 + index * 20, status: index === 0 ? 'active' : 'pending', owner: ['林晓', '周宁', '陈雨'][index] }));
  return {
    props: { title: ['string', title], dimensions: ['array', dimensions], initialRecords: ['array', initialRecords], stages: ['array', stages] },
    state: { records: [], stageIndex: 0, selectedId: 1, query: '', threshold: 100, history: [], issues: [], draft: '', saved: false, revision: 1 },
    inited: "this.setValue('records', this.initialRecords.map(item => Object.assign({}, item))); this.setValue('selectedId', this.initialRecords[0] ? this.initialRecords[0].id : null); this.validate();",
    computed: [
      ['visibleRecords', "const q = this.query.toLowerCase(); return this.records.filter(item => item.name.toLowerCase().indexOf(q) >= 0);"],
      ['selectedRecord', "return this.records.find(item => item.id === this.selectedId) || null;"],
      ['totalValue', "return this.records.reduce((sum, item) => sum + item.value, 0);"],
      ['progress', "return Math.round(this.records.filter(item => item.status === 'done').length / (this.records.length || 1) * 100);"],
      ['currentStage', "return this.stages[this.stageIndex] || '';"],
      ['canAdvance', "return this.issues.length === 0 && this.stageIndex < this.stages.length - 1;"]
    ],
    watch: [['threshold', "this.validate();"]],
    methods: [
      ['updateQuery', 'event', "this.setValue('query', event.target.value);"],
      ['select', 'id', "this.setValue('selectedId', id);"],
      ['updateValue', 'id, event', "const value = Math.max(0, Number(event.target.value) || 0); this.snapshot('调整数值'); this.setValue('records', this.records.map(item => item.id === id ? Object.assign({}, item, { value, status: value ? 'active' : 'pending' }) : item)); this.setValue('saved', false); this.validate(); this.emitEvent('change', this.records);"],
      ['updateThreshold', 'event', "this.setValue('threshold', Number(event.target.value) || 0);"],
      ['updateDraft', 'event', "this.setValue('draft', event.target.value);"],
      ['addRecord', 'event', "event.preventDefault(); const name = this.draft.trim(); if (!name) return; const nextId = this.records.reduce((max, row) => Math.max(max, row.id), 0) + 1; this.snapshot('新增记录'); this.setValue('records', this.records.concat({ id: nextId, name, value: 0, status: 'pending', owner: '未分配' })); this.setValue('draft', ''); this.setValue('saved', false); this.validate();"],
      ['removeRecord', 'id', "this.snapshot('删除记录'); this.setValue('records', this.records.filter(item => item.id !== id)); if (this.selectedId === id) this.setValue('selectedId', null); this.setValue('saved', false); this.validate();"],
      ['markDone', 'id', "this.snapshot('完成记录'); this.setValue('records', this.records.map(item => item.id === id ? Object.assign({}, item, { status: 'done' }) : item)); this.validate();"],
      ['validate', '', "const issues = []; if (!this.records.length) issues.push('至少保留一条记录'); if (this.totalValue > this.threshold) issues.push('总值超过当前阈值'); if (this.records.some(item => !item.owner || item.owner === '未分配')) issues.push('存在未分配负责人'); this.setValue('issues', issues); this.emitEvent('validate', issues);"],
      ['advance', '', "if (!this.canAdvance) return; this.snapshot('推进阶段'); this.setValue('stageIndex', this.stageIndex + 1); this.emitEvent('advance', this.currentStage);"],
      ['save', '', "this.setValue('saved', true); this.setValue('revision', this.revision + 1); this.snapshot('保存版本'); this.emitEvent('save', { stage: this.currentStage, records: this.records });"],
      ['snapshot', 'label', "this.setValue('history', [{ id: Date.now() + Math.random(), label, stageIndex: this.stageIndex, records: this.records.map(item => Object.assign({}, item)) }].concat(this.history).slice(0, 6));"],
      ['undo', '', "if (!this.history.length) return; const entry = this.history[0]; this.setValue('records', entry.records.map(item => Object.assign({}, item))); this.setValue('stageIndex', entry.stageIndex); this.setValue('history', this.history.slice(1)); this.validate();"],
      ['rowClass', 'record, selectedId', "return (record.id === selectedId ? 'selected ' : '') + record.status;"],
      ['barStyle', 'record, threshold', "return 'width:' + Math.min(100, record.value / (threshold || 1) * 100) + '%';"]
    ],
    template: `<section class="${kebab(item.name)}"><header class="page-head"><div><p class="muted">v{{ revision }} · {{ saved ? '已保存' : '有未保存变更' }}</p><h2>{{ title }}</h2></div><div class="actions"><button @click="undo" :disabled="!history.length">撤销</button><button class="primary" @click="save">保存</button></div></header><div class="stage-track"><button v-for="stage, index in stages" :key="stage" :class="index === stageIndex ? 'active' : index < stageIndex ? 'done' : ''">{{ index + 1 }}. {{ stage }}</button></div><div class="metrics"><article><span>总值</span><strong>{{ totalValue }}</strong></article><article><span>进度</span><strong>{{ progress }}%</strong></article><article><span>问题</span><strong>{{ issues.length }}</strong></article></div><div class="workbench"><aside><input :value="query" @input="updateQuery" placeholder="筛选记录"><button v-for="record in visibleRecords" :key="record.id" :class="rowClass(record, selectedId)" @click="select(record.id)"><strong>{{ record.name }}</strong><small>{{ record.owner }} · {{ record.status }}</small></button><form @submit="addRecord"><input :value="draft" @input="updateDraft" placeholder="新增记录"><button type="submit">＋</button></form></aside><main><article v-for="record in records" :key="record.id" :class="rowClass(record, selectedId)"><div><strong>{{ record.name }}</strong><small>{{ record.owner }}</small></div><input type="number" :value="record.value" @input="updateValue(record.id, $event)"><div class="bar"><span :style="barStyle(record, threshold)"></span></div><button @click="markDone(record.id)">完成</button><button @click="removeRecord(record.id)">删除</button></article><p v-if="!records.length" class="empty">暂无记录</p></main><aside class="inspector"><h3>控制面板</h3><label>阈值<input type="number" :value="threshold" @input="updateThreshold"></label><div v-if="selectedRecord"><strong>{{ selectedRecord.name }}</strong><p>当前值 {{ selectedRecord.value }}</p><p>负责人 {{ selectedRecord.owner }}</p></div><ul><li v-for="issue in issues" :key="issue">{{ issue }}</li></ul><button class="primary" @click="advance" :disabled="!canAdvance">推进到下一阶段</button></aside></div><footer><span>当前阶段：{{ currentStage }}</span><span v-for="entry in history" :key="entry.id">{{ entry.label }}</span></footer></section>`,
    css: '.page-head{display:flex;justify-content:space-between}.stage-track{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:12px 0}.stage-track button.active{background:#dbeafe}.stage-track button.done{background:#dcfce7}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.metrics article{padding:12px;background:#f8fafc}.metrics strong{display:block;font-size:22px}.workbench{display:grid;grid-template-columns:180px 1fr 190px;gap:12px;margin-top:12px}.workbench>aside{padding:10px;background:#f8fafc}.workbench>aside>button{display:block;width:100%;margin:6px 0;text-align:left}.workbench>aside>button.selected{border-color:#2563eb;background:#eff6ff}.workbench small{display:block}.workbench main article{display:grid;grid-template-columns:1fr 75px 90px auto auto;gap:7px;align-items:center;padding:9px;border-bottom:1px solid #e2e8f0}.workbench main article.done{background:#f0fdf4}.bar{height:7px;background:#e5e7eb}.bar span{display:block;height:100%;background:currentColor}.inspector label{display:grid}.inspector ul{padding-left:18px;color:#b91c1c}footer{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;font-size:11px}footer span{padding:5px;background:#f1f5f9}'
  };
}

function implementation(item) {
  if (item.level === 'simple') return simpleImplementation(item);
  if (item.level === 'medium') return mediumImplementation(item);
  return complexImplementation(item);
}

function literal(value, indent = 0) {
  const raw = JSON.stringify(value, null, 2);
  if (!raw.includes('\n')) return raw;
  const pad = ' '.repeat(indent);
  return raw.split('\n').map((line, index) => index ? pad + line : line).join('\n');
}

function vueProp(type, value) {
  const constructors = { string: 'String', number: 'Number', bool: 'Boolean', array: 'Array', object: 'Object' };
  const valueCode = type === 'array' || type === 'object' ? `() => (${literal(value, 8)})` : literal(value, 8);
  return `{ type: ${constructors[type]}, default: ${valueCode} }`;
}

function renderVue(item, impl) {
  const props = Object.entries(impl.props).map(([name, [type, value]]) => `    ${name}: ${vueProp(type, value)}`).join(',\n');
  const state = Object.assign({}, impl.state, impl.vueState || {});
  const stateCode = Object.entries(state).map(([name, value]) => `        ${name}: ${literal(value, 8)}`).join(',\n');
  const computed = (impl.computed || []).map(([name, body]) => `    ${name}() {\n      ${body}\n    }`).join(',\n');
  const watch = (impl.watch || []).map(([name, body]) => `    ${name}() {\n      ${body}\n    }`).join(',\n');
  const hooks = [];
  if (impl.inited) hooks.push(`  created() {\n    ${impl.inited}\n  }`);
  if (impl.attached) hooks.push(`  mounted() {\n    ${impl.attached}\n  }`);
  if (impl.disposed) hooks.push(`  beforeDestroy() {\n    ${impl.disposed}\n  }`);
  const methods = [`    setValue(key, value) { this[key] = value; }`, `    emitEvent(name, payload) { this.$emit(name, payload); }`]
    .concat((impl.methods || []).map(([name, args, body]) => `    ${name}(${args}) {\n      ${body}\n    }`)).join(',\n');
  return `<template>\n  ${impl.template}\n</template>\n\n<script>\nmodule.exports = {\n  name: '${item.name}',${props ? `\n  props: {\n${props}\n  },` : ''}\n  data() {\n    return {\n${stateCode}\n    };\n  },${computed ? `\n  computed: {\n${computed}\n  },` : ''}${watch ? `\n  watch: {\n${watch}\n  },` : ''}${hooks.length ? `\n${hooks.join(',\n')},` : ''}\n  methods: {\n${methods}\n  }\n};\n</script>\n\n<style scoped>\n${commonCss(item, impl.css)}\n</style>\n`;
}

function sanBody(body, names) {
  let output = body;
  [...names].sort((a, b) => b.length - a.length).forEach(name => {
    output = output.replace(new RegExp(`\\bthis\\.${name}\\b`, 'g'), `this.data.get('${name}')`);
  });
  output = output.replace(/this\.setValue\(/g, 'this.setValue(').replace(/this\.emitEvent\(/g, 'this.emitEvent(');
  return output;
}

function toSanTemplate(template) {
  let output = template;
  output = output.replace(/v-for="([^"]+)"\s+:key="([^"]+)"/g, 's-for="$1 trackby $2"');
  output = output.replace(/\s:key="[^"]*"/g, '');
  output = output.replace(/v-for=/g, 's-for=').replace(/v-if=/g, 's-if=').replace(/v-else/g, 's-else');
  output = output.replace(/@([a-z]+)(?:\.[a-z]+)?=/g, 'on-$1=');
  output = output.replace(/:([a-zA-Z-]+)="([^"]*)"/g, (_, attribute, expression) => `${attribute}="{{ ${expression} }}"`);
  return output;
}

function complexityFeatures(item, impl) {
  const template = impl.template;
  const methodText = (impl.methods || []).map(row => row[2]).join('\n');
  const features = ['data', item.pattern];
  if (Object.keys(impl.props).length) features.push('props');
  if (template.includes('v-for')) features.push('v-for');
  if (template.includes('v-if')) features.push('v-if');
  if (template.includes(':')) features.push('v-bind');
  if (template.includes('@')) features.push('v-on');
  if (template.includes(':class')) features.push('dynamic-class');
  if (template.includes(':style')) features.push('dynamic-style');
  if (impl.computed && impl.computed.length) features.push('computed');
  if (impl.watch && impl.watch.length) features.push('watch');
  if (impl.inited || impl.attached || impl.disposed) features.push('lifecycle');
  if (methodText.includes('emitEvent(')) features.push('emit');
  return [...new Set(features)];
}

function renderSan(item, impl) {
  const props = impl.props;
  const state = Object.assign({}, impl.state, impl.sanState || {});
  const names = new Set([...Object.keys(props), ...Object.keys(state), ...(impl.computed || []).map(row => row[0])]);
  const typeMap = { string: 'string', number: 'number', bool: 'bool', array: 'array', object: 'object' };
  const dataTypes = Object.entries(props).map(([name, [type]]) => `    ${name}: DataTypes.${typeMap[type]}`).join(',\n');
  const initValues = [...Object.entries(props).map(([name, [, value]]) => [name, value]), ...Object.entries(state)];
  const initData = initValues.map(([name, value]) => `      ${name}: ${literal(value, 6)}`).join(',\n');
  const computed = (impl.computed || []).map(([name, body]) => `    ${name}() {\n      ${sanBody(body, names)}\n    }`).join(',\n');
  const hooks = [];
  const inited = [];
  if (impl.inited) inited.push(sanBody(impl.inited, names));
  (impl.watch || []).forEach(([name, body]) => inited.push(`this.watch('${name}', () => { ${sanBody(body, names)} });`));
  if (inited.length) hooks.push(`  inited() {\n    ${inited.join('\n    ')}\n  }`);
  if (impl.attached) hooks.push(`  attached() {\n    ${sanBody(impl.attached, names)}\n  }`);
  if (impl.disposed) hooks.push(`  disposed() {\n    ${sanBody(impl.disposed, names)}\n  }`);
  const methods = [`  setValue(key, value) { this.data.set(key, value); }`, `  emitEvent(name, payload) { this.fire(name, payload); }`]
    .concat((impl.methods || []).map(([name, args, body]) => `  ${name}(${args}) {\n    ${sanBody(body, names)}\n  }`)).join(',\n');
  return `<template>\n  ${impl.sanTemplate || toSanTemplate(impl.template)}\n</template>\n\n<script>\nconst san = require('san');\nconst DataTypes = san.DataTypes;\n\nmodule.exports = san.defineComponent({\n  name: '${item.name}',${dataTypes ? `\n  dataTypes: {\n${dataTypes}\n  },` : ''}\n  initData() {\n    return {\n${initData}\n    };\n  },${computed ? `\n  computed: {\n${computed}\n  },` : ''}${hooks.length ? `\n${hooks.join(',\n')},` : ''}\n${methods}\n});\n</script>\n\n<style>\n${commonCss(item, impl.css)}\n</style>\n`;
}

function patternEntry(item, impl) {
  const template = impl.template;
  return {
    templates: { has_v_for: template.includes('v-for'), has_v_if: template.includes('v-if'), has_v_bind: template.includes(':'), has_v_on: template.includes('@'), has_slot: false },
    scripts: { has_props: Object.keys(impl.props).length > 0, has_data: true, has_computed: !!(impl.computed && impl.computed.length), has_methods: !!(impl.methods && impl.methods.length), has_watch: !!(impl.watch && impl.watch.length), has_lifecycle: !!(impl.inited || impl.attached || impl.disposed) },
    styles: { has_scoped: true, has_dynamic_class: template.includes(':class'), has_dynamic_style: template.includes(':style') },
    migration_patterns: ['event_name_conversion', 'attribute_binding_conversion', 'props_to_data_types', 'data_access_conversion'].concat(impl.watch ? ['watch_registration'] : []).concat(impl.attached || impl.disposed ? ['lifecycle_mapping'] : [])
  };
}

function generate() {
  const designErrors = validateDesign();
  if (designErrors.length) throw new Error(designErrors.join('\n'));
  const manifestFile = path.join(dataRoot, 'dataset_manifest.json');
  const complexityFile = path.join(dataRoot, 'features', 'complexity_tags.json');
  const patternFile = path.join(dataRoot, 'features', 'pattern_tags.json');
  const notesFile = path.join(dataRoot, 'features', 'migration_notes.json');
  const manifest = JSON.parse(fs.readFileSync(manifestFile, 'utf8'));
  const complexity = JSON.parse(fs.readFileSync(complexityFile, 'utf8'));
  const patterns = JSON.parse(fs.readFileSync(patternFile, 'utf8'));
  const notes = JSON.parse(fs.readFileSync(notesFile, 'utf8'));
  const ids = new Set(specs.map(item => snake(item.name)));
  const names = new Set(specs.map(item => item.name));
  manifest.components = manifest.components.filter(item => !ids.has(item.id));
  const nextComplexity = complexity.filter(item => !names.has(item.component_name));

  for (const item of specs) {
    const impl = implementation(item);
    const componentRoot = path.join(dataRoot, 'components', levelDirs[item.level], item.name);
    fs.mkdirSync(path.join(componentRoot, 'vue'), { recursive: true });
    fs.mkdirSync(path.join(componentRoot, 'san'), { recursive: true });
    fs.writeFileSync(path.join(componentRoot, 'vue', `${item.name}.vue`), renderVue(item, impl), 'utf8');
    fs.writeFileSync(path.join(componentRoot, 'san', `${item.name}.san`), renderSan(item, impl), 'utf8');
    const id = snake(item.name);
    manifest.components.push({ id, name: item.label, path: `components/${levelDirs[item.level]}/${item.name}/`, complexity: item.level, vue_file: `${item.name}.vue`, san_file: `${item.name}.san`, created_date: createdDate, status: 'vue_ready,san_ready', notes: item.workflow });
    nextComplexity.push({ component_name: item.name, complexity_score: item.score, total_score: Object.values(item.score).reduce((sum, value) => sum + value, 0), level: item.level, features: complexityFeatures(item, impl), sub_components: [] });
    const key = kebab(item.name);
    patterns[key] = patternEntry(item, impl);
    notes[key] = { notebook: '', challenges: [`${item.model}需要在 Vue 与 San 中保持语义一致。`, `${item.structure}涉及${item.migrationFocus}。`], solutions: [`围绕“${item.workflow}”使用不可变数据更新、显式响应式依赖和稳定列表身份。`, '将 Vue 指令、props、生命周期与事件映射为 San 的对应语义。'], validation: { structure_score: 1, functional_test: 'static_validate_passed', visual_test: 'not_run' } };
  }
  manifest.total_components = manifest.components.length;
  writeJson(manifestFile, manifest);
  writeJson(complexityFile, nextComplexity);
  writeJson(patternFile, patterns);
  writeJson(notesFile, notes);
  writeJson(designFile, designMatrix());
  console.log(JSON.stringify({ generated: specs.length, byLevel: specs.reduce((out, item) => { out[item.level] = (out[item.level] || 0) + 1; return out; }, {}), totalComponents: manifest.total_components }, null, 2));
}

const errors = validateDesign();
if (process.argv.includes('--design-only')) {
  if (errors.length) throw new Error(errors.join('\n'));
  writeJson(designFile, designMatrix());
  console.log(JSON.stringify({ designed: specs.length, byLevel: specs.reduce((out, item) => { out[item.level] = (out[item.level] || 0) + 1; return out; }, {}) }, null, 2));
}
else {
  generate();
}
