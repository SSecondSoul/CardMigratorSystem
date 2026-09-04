const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const createdDate = '2026-09-02';
const specs = [];

function kebab(name) {
  return name.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
}

function snake(name) {
  return kebab(name).replace(/-/g, '_');
}

function add(spec) {
  spec.id = snake(spec.name);
  spec.rootClass = kebab(spec.name);
  specs.push(spec);
}

const commonCss = (rootClass, accent, extra = '') => `
.${rootClass} { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.${rootClass} * { box-sizing: border-box; }
.${rootClass} h2, .${rootClass} h3, .${rootClass} p { margin-top: 0; }
.${rootClass} h2 { margin-bottom: 14px; font-size: 21px; }
.${rootClass} button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.${rootClass} button.primary { border-color: ${accent}; background: ${accent}; color: #fff; }
.${rootClass} button:disabled { opacity: .45; cursor: not-allowed; }
.${rootClass} input, .${rootClass} select, .${rootClass} textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.${rootClass} .toolbar, .${rootClass} .summary, .${rootClass} .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.${rootClass} .muted { color: #71808e; font-size: 12px; }
.${rootClass} .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
${extra.trim()}
`;

const simpleScore = (overrides = {}) => Object.assign({ template: 1, data_logic: 1, interaction: 1, styling: 2, communication: 1 }, overrides);
const mediumScore = (overrides = {}) => Object.assign({ template: 2, data_logic: 2, interaction: 2, styling: 2, communication: 2 }, overrides);
const complexScore = (overrides = {}) => Object.assign({ template: 3, data_logic: 3, interaction: 3, styling: 3, communication: 2 }, overrides);

// Simple: ten distinct state models and one-step workflows.
add({
  name: 'PasswordStrengthMeter', label: '密码强度计', level: 'simple', accent: '#2563eb',
  model: '单个密码字符串与派生强度等级', workflow: '输入密码并清空', structure: '输入框、强度条与规则提示', stateChange: '字符输入驱动分数和视觉等级', communication: '2 个 props，无事件输出', migrationFocus: '输入事件、computed、动态 class/style',
  props: { label: ['string', '设置访问密码'], minLength: ['number', 8] },
  state: { password: '' },
  computed: [
    ['strength', '', "let score = 0; const value = GET_password; if (value.length >= GET_minLength) score += 1; if (/[A-Z]/.test(value)) score += 1; if (/[0-9]/.test(value)) score += 1; return score;"],
    ['strengthLabel', '', "return ['未输入', '较弱', '一般', '较强'][GET_strength];"],
    ['barStyle', '', "return 'width:' + (GET_strength * 33.33) + '%';"]
  ],
  methods: [
    ['updatePassword', 'event', "SET_password(event.target.value);"],
    ['clear', '', "SET_password('');"]
  ],
  template: `<section class="password-strength-meter"><h2>{{ label }}</h2><div class="field-row"><input type="password" :value="password" @input="updatePassword" placeholder="输入密码"><button @click="clear" :disabled="!password">清空</button></div><div class="meter"><span :class="'level-' + strength" :style="barStyle"></span></div><p>{{ strengthLabel }} · 至少 {{ minLength }} 位</p></section>`,
  css: `.field-row{display:grid;grid-template-columns:1fr auto;gap:8px}.meter{height:8px;background:#e6ebf0;overflow:hidden}.meter span{display:block;height:100%;background:#2563eb;transition:.2s}.level-1{opacity:.45}.level-2{opacity:.7}.level-3{opacity:1}`,
  score: simpleScore({ data_logic: 2 }), features: ['v-on', 'v-bind', 'computed', 'props', 'dynamic-class', 'dynamic-style', 'scoped']
});

add({
  name: 'VolumeControl', label: '音量控制器', level: 'simple', accent: '#0f766e',
  model: '当前音量与静音前音量', workflow: '拖动音量并在静音/恢复间切换', structure: '数值读数、滑杆和静音按钮', stateChange: '静音时保存并恢复上次非零值', communication: '1 个 prop，发出 change', migrationFocus: 'range 输入、派生标签、emit/fire',
  props: { initialVolume: ['number', 45] }, state: { volume: 45, lastVolume: 45 },
  inited: "SET_volume(GET_initialVolume); SET_lastVolume(GET_initialVolume || 45);",
  computed: [['volumeLabel', '', "return GET_volume === 0 ? '已静音' : GET_volume + '%';"]],
  methods: [
    ['updateVolume', 'event', "const value = Number(event.target.value); SET_volume(value); if (value > 0) SET_lastVolume(value); EMIT('change', value);"],
    ['toggleMute', '', "const next = GET_volume === 0 ? GET_lastVolume : 0; SET_volume(next); EMIT('change', next);"]
  ],
  template: `<section class="volume-control"><header><h2>播放音量</h2><strong>{{ volumeLabel }}</strong></header><input class="volume-slider" type="range" min="0" max="100" :value="volume" @input="updateVolume"><button class="primary" @click="toggleMute">{{ volume === 0 ? '恢复音量' : '静音' }}</button></section>`,
  css: `header{display:flex;justify-content:space-between}.volume-slider{width:100%;margin:12px 0;accent-color:#0f766e}`,
  score: simpleScore({ interaction: 2, communication: 2 }), features: ['v-on', 'v-bind', 'computed', 'props', 'emit', 'scoped']
});

add({
  name: 'InlineRename', label: '行内重命名', level: 'simple', accent: '#7c3aed',
  model: '已保存名称、编辑草稿与编辑模式', workflow: '进入编辑后保存或取消', structure: '查看态与编辑态互斥区域', stateChange: '两态切换并校验空名称', communication: '1 个 prop，无事件输出', migrationFocus: 'v-if/v-else、输入同步和草稿回滚',
  props: { initialName: ['string', '季度报告'] }, state: { name: '季度报告', draft: '', editing: false, error: '' },
  inited: "SET_name(GET_initialName);",
  computed: [],
  methods: [
    ['begin', '', "SET_draft(GET_name); SET_error(''); SET_editing(true);"],
    ['updateDraft', 'event', "SET_draft(event.target.value);"],
    ['save', '', "const value = GET_draft.trim(); if (!value) { SET_error('名称不能为空'); return; } SET_name(value); SET_editing(false);"],
    ['cancel', '', "SET_editing(false); SET_error('');"]
  ],
  template: `<section class="inline-rename"><h2>文件名称</h2><div v-if="!editing" class="read-row"><strong>{{ name }}</strong><button @click="begin">重命名</button></div><div v-else class="edit-row"><input :value="draft" @input="updateDraft"><button class="primary" @click="save">保存</button><button @click="cancel">取消</button><small v-if="error">{{ error }}</small></div></section>`,
  css: `.read-row,.edit-row{display:flex;align-items:center;gap:8px}.read-row strong{margin-right:auto}.edit-row input{flex:1}.edit-row small{width:100%;color:#b42318}`,
  score: simpleScore({ data_logic: 2, interaction: 2 }), features: ['v-if', 'v-on', 'v-bind', 'props', 'scoped']
});

add({
  name: 'QueueTicket', label: '排队取号器', level: 'simple', accent: '#b45309',
  model: 'idle/waiting 三态票号数据', workflow: '取号后可取消排队', structure: '状态说明、票号和条件按钮', stateChange: '空闲与等待状态机转换', communication: '1 个 prop，无输出', migrationFocus: '条件渲染和状态机文案',
  props: { counterName: ['string', '业务 A 窗口'] }, state: { status: 'idle', ticket: 18 },
  computed: [['statusText', '', "return GET_status === 'idle' ? '当前可取号' : '前方还有 ' + (GET_ticket - 12) + ' 人';"]],
  methods: [['takeTicket', '', "SET_ticket(GET_ticket + 1); SET_status('waiting');"], ['cancelTicket', '', "SET_status('idle');"]],
  template: `<section class="queue-ticket"><p class="muted">{{ counterName }}</p><h2>{{ statusText }}</h2><strong v-if="status === 'waiting'" class="ticket-number">A{{ ticket }}</strong><button v-if="status === 'idle'" class="primary" @click="takeTicket">立即取号</button><button v-else @click="cancelTicket">取消排队</button></section>`,
  css: `.ticket-number{display:block;margin:18px 0;font-size:42px;color:#b45309}`,
  score: simpleScore(), features: ['v-if', 'v-on', 'computed', 'props', 'scoped']
});

add({
  name: 'SearchClearField', label: '搜索清空框', level: 'simple', accent: '#0369a1',
  model: '单一搜索字符串', workflow: '输入关键字并一键清空', structure: '搜索输入、清空按钮与字符提示', stateChange: '输入直接更新查询内容', communication: '1 个 prop，无输出', migrationFocus: '输入事件与条件按钮',
  props: { placeholder: ['string', '搜索文档'] }, state: { query: '' }, computed: [],
  methods: [['updateQuery', 'event', "SET_query(event.target.value);"], ['clear', '', "SET_query('');"]],
  template: `<section class="search-clear-field"><h2>快速搜索</h2><div class="search-box"><input :value="query" @input="updateQuery" :placeholder="placeholder"><button v-if="query" @click="clear">×</button></div><p>{{ query ? '正在搜索：' + query : '输入内容开始搜索' }}</p></section>`,
  css: `.search-box{display:grid;grid-template-columns:1fr 40px;gap:6px}.search-box button{font-size:18px}`,
  score: simpleScore(), features: ['v-if', 'v-on', 'v-bind', 'props', 'scoped']
});

add({
  name: 'ReactionBar', label: '内容反馈条', level: 'simple', accent: '#be185d',
  model: '赞同/疑问计数与当前选择', workflow: '选择反馈并可切换另一种反馈', structure: '两个并列反馈按钮与总数', stateChange: '互斥选择时回退旧计数并增加新计数', communication: '无 props，无输出', migrationFocus: '对象不可变更新与动态 class',
  props: {}, state: { counts: { like: 12, question: 3 }, selected: '' },
  computed: [['total', '', "return GET_counts.like + GET_counts.question;"]],
  methods: [['react', 'kind', "const counts = Object.assign({}, GET_counts); const old = GET_selected; if (old) counts[old] -= 1; const next = old === kind ? '' : kind; if (next) counts[next] += 1; SET_counts(counts); SET_selected(next);"]],
  template: `<section class="reaction-bar"><h2>这段内容有帮助吗？</h2><div class="reaction-actions"><button :class="selected === 'like' ? 'active' : ''" @click="react('like')">有帮助 {{ counts.like }}</button><button :class="selected === 'question' ? 'active' : ''" @click="react('question')">仍有疑问 {{ counts.question }}</button></div><p class="muted">共 {{ total }} 次反馈</p></section>`,
  css: `.reaction-actions{display:flex;gap:8px}.reaction-actions .active{border-color:#be185d;background:#fce7f3;color:#9d174d}`,
  score: simpleScore(), features: ['v-on', 'v-bind', 'computed', 'dynamic-class', 'scoped']
});

add({
  name: 'UnitConverter', label: '长度换算器', level: 'simple', accent: '#047857',
  model: '数值与公制/英制方向', workflow: '输入数值并翻转换算方向', structure: '输入区、方向按钮和结果输出', stateChange: '数值或方向变化时重新派生结果', communication: '无 props，无输出', migrationFocus: '数值输入和格式化 computed',
  props: {}, state: { value: 1, mode: 'metric' },
  computed: [['result', '', "const converted = GET_mode === 'metric' ? GET_value * 3.28084 : GET_value / 3.28084; return converted.toFixed(2);"], ['unitLabel', '', "return GET_mode === 'metric' ? '米 → 英尺' : '英尺 → 米';"]],
  methods: [['updateValue', 'event', "SET_value(Number(event.target.value) || 0);"], ['flip', '', "SET_mode(GET_mode === 'metric' ? 'imperial' : 'metric');"]],
  template: `<section class="unit-converter"><h2>{{ unitLabel }}</h2><div class="converter-grid"><input type="number" min="0" :value="value" @input="updateValue"><button @click="flip">⇄</button><output>{{ result }}</output></div></section>`,
  css: `.converter-grid{display:grid;grid-template-columns:1fr 46px 1fr;gap:8px;align-items:center}.converter-grid output{padding:10px;background:#ecfdf5;font-weight:700}`,
  score: simpleScore(), features: ['v-on', 'v-bind', 'computed', 'scoped']
});

add({
  name: 'SortCycleButton', label: '排序循环按钮', level: 'simple', accent: '#475569',
  model: 'none/asc/desc 三态方向', workflow: '连续点击循环切换排序方向', structure: '字段说明和单个状态按钮', stateChange: '有限状态循环', communication: '1 个 prop，发出 change', migrationFocus: '三态 computed、动态类和 emit/fire',
  props: { fieldLabel: ['string', '更新时间'] }, state: { direction: 'none' },
  computed: [['buttonLabel', '', "return GET_direction === 'none' ? '不排序' : GET_direction === 'asc' ? '升序 ↑' : '降序 ↓';"]],
  methods: [['cycle', '', "const order = ['none', 'asc', 'desc']; const index = order.indexOf(GET_direction); const next = order[(index + 1) % order.length]; SET_direction(next); EMIT('change', next);"]],
  template: `<section class="sort-cycle-button"><span>{{ fieldLabel }}</span><button :class="direction" @click="cycle">{{ buttonLabel }}</button></section>`,
  css: `.sort-cycle-button{display:flex;align-items:center;justify-content:space-between}.sort-cycle-button button.asc{border-color:#15803d;color:#15803d}.sort-cycle-button button.desc{border-color:#b91c1c;color:#b91c1c}`,
  score: simpleScore({ communication: 2 }), features: ['v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'scoped']
});

add({
  name: 'PasswordVisibilityField', label: '密码可见输入框', level: 'simple', accent: '#9333ea',
  model: '输入内容与可见性布尔值', workflow: '输入密码并显示/隐藏', structure: '标签、动态类型输入框和图标按钮', stateChange: '切换 input type 而不丢失内容', communication: '1 个 prop，无输出', migrationFocus: '动态属性与输入同步',
  props: { label: ['string', '接口密钥'] }, state: { value: '', visible: false },
  computed: [['inputType', '', "return GET_visible ? 'text' : 'password';"]],
  methods: [['updateValue', 'event', "SET_value(event.target.value);"], ['toggleVisibility', '', "SET_visible(!GET_visible);"]],
  template: `<label class="password-visibility-field"><span>{{ label }}</span><div class="secret-row"><input :type="inputType" :value="value" @input="updateValue"><button type="button" @click="toggleVisibility">{{ visible ? '隐藏' : '显示' }}</button></div><small>{{ value ? '已输入 ' + value.length + ' 个字符' : '尚未输入' }}</small></label>`,
  css: `.secret-row{display:grid;grid-template-columns:1fr auto;gap:7px}.password-visibility-field>span{display:block;margin-bottom:7px;font-weight:700}.password-visibility-field small{display:block;margin-top:7px;color:#71808e}`,
  score: simpleScore(), features: ['v-on', 'v-bind', 'computed', 'props', 'scoped']
});

add({
  name: 'BudgetThreshold', label: '预算阈值提示', level: 'simple', accent: '#c2410c',
  model: '预算上限与当前支出数值', workflow: '录入支出并重置', structure: '金额输入、余额输出和状态提示', stateChange: '支出驱动剩余额度及超支状态', communication: '1 个 prop，无输出', migrationFocus: '数值输入、条件 class 和派生金额',
  props: { limit: ['number', 5000] }, state: { amount: 1200 },
  computed: [['remaining', '', "return GET_limit - GET_amount;"], ['statusText', '', "return GET_remaining < 0 ? '已超支 ' + Math.abs(GET_remaining) + ' 元' : '剩余 ' + GET_remaining + ' 元';"]],
  methods: [['updateAmount', 'event', "SET_amount(Number(event.target.value) || 0);"], ['reset', '', "SET_amount(0);"]],
  template: `<section :class="'budget-threshold ' + (remaining < 0 ? 'over' : 'safe')"><h2>项目预算</h2><input type="number" min="0" :value="amount" @input="updateAmount"><strong>{{ statusText }}</strong><button @click="reset">归零</button></section>`,
  css: `.budget-threshold{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center}.budget-threshold h2{grid-column:1/-1}.budget-threshold strong{color:#15803d}.budget-threshold.over strong{color:#b91c1c}`,
  score: simpleScore(), features: ['v-on', 'v-bind', 'computed', 'props', 'dynamic-class', 'scoped']
});

// Medium: lists, forms, derived calculations, and multi-step workflows.
add({
  name: 'TransferList', label: '双列表选择器', level: 'medium', accent: '#2563eb',
  model: '可用项、已选项和两侧当前选择', workflow: '在左右列表间移动条目并搜索', structure: '搜索栏加左右双面板', stateChange: '条目从一个集合迁移到另一个集合', communication: '2 个数组 props，发出 change', migrationFocus: '多列表、条件禁用、不可变数组和 emit/fire',
  props: { initialAvailable: ['array', [{ id: 1, name: '设计' }, { id: 2, name: '开发' }, { id: 3, name: '测试' }]], initialChosen: ['array', [{ id: 4, name: '部署' }]] },
  state: { available: [], chosen: [], leftId: null, rightId: null, query: '' },
  inited: "SET_available(GET_initialAvailable.map(item => Object.assign({}, item))); SET_chosen(GET_initialChosen.map(item => Object.assign({}, item)));",
  computed: [['filteredAvailable', '', "const q = GET_query.toLowerCase(); return GET_available.filter(item => item.name.toLowerCase().indexOf(q) >= 0);"]],
  methods: [
    ['updateQuery', 'event', "SET_query(event.target.value);"], ['selectLeft', 'id', "SET_leftId(id);"], ['selectRight', 'id', "SET_rightId(id);"],
    ['moveRight', '', "const id = GET_leftId; const item = GET_available.find(row => row.id === id); if (!item) return; SET_available(GET_available.filter(row => row.id !== id)); SET_chosen(GET_chosen.concat(item)); SET_leftId(null); this.notify();"],
    ['moveLeft', '', "const id = GET_rightId; const item = GET_chosen.find(row => row.id === id); if (!item) return; SET_chosen(GET_chosen.filter(row => row.id !== id)); SET_available(GET_available.concat(item)); SET_rightId(null); this.notify();"],
    ['notify', '', "EMIT('change', GET_chosen.slice());"]
  ],
  template: `<section class="transfer-list"><h2>项目角色分配</h2><input class="transfer-search" :value="query" @input="updateQuery" placeholder="筛选可用角色"><div class="transfer-grid"><div class="list-panel"><h3>可用</h3><button v-for="item in filteredAvailable" :key="item.id" :class="item.id === leftId ? 'selected' : ''" @click="selectLeft(item.id)">{{ item.name }}</button></div><div class="transfer-actions"><button @click="moveRight" :disabled="leftId === null">→</button><button @click="moveLeft" :disabled="rightId === null">←</button></div><div class="list-panel"><h3>已选</h3><button v-for="item in chosen" :key="item.id" :class="item.id === rightId ? 'selected' : ''" @click="selectRight(item.id)">{{ item.name }}</button></div></div></section>`,
  css: `.transfer-search{width:100%;margin-bottom:12px}.transfer-grid{display:grid;grid-template-columns:1fr 44px 1fr;gap:10px}.list-panel{min-height:190px;padding:10px;border:1px solid #d6dde4}.list-panel button{display:block;width:100%;margin:5px 0;text-align:left}.list-panel button.selected{background:#dbeafe;border-color:#2563eb}.transfer-actions{display:grid;align-content:center;gap:8px}`,
  score: mediumScore(), features: ['v-for', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'scoped']
});

function literal(value, indent = 0) {
  const raw = JSON.stringify(value, null, 2);
  if (!raw.includes('\n')) return raw;
  const padding = ' '.repeat(indent);
  return raw.split('\n').map((line, index) => index ? padding + line : line).join('\n');
}

function compileCode(code, spec, framework) {
  let output = code || '';
  const names = [...Object.keys(spec.props), ...Object.keys(spec.state), ...(spec.computed || []).map(item => item[0])]
    .sort((a, b) => b.length - a.length);
  names.forEach(name => {
    const getter = framework === 'vue' ? `this.${name}` : `this.data.get('${name}')`;
    output = output.replace(new RegExp(`\\bGET_${name}\\b`, 'g'), getter);
    output = output.replace(new RegExp(`\\bSET_${name}\\(`, 'g'), `this.setValue('${name}', `);
  });
  output = output.replace(/\bEMIT\(/g, 'this.emitEvent(');
  output = output.replace(/\bthis\.timer\b/g, 'this._timer');
  return output;
}

function indentCode(code, spaces) {
  const padding = ' '.repeat(spaces);
  return code.split('\n').map(line => padding + line).join('\n');
}

function vueProp(type, defaultValue) {
  const constructors = { string: 'String', number: 'Number', bool: 'Boolean', array: 'Array', object: 'Object' };
  const defaultCode = (type === 'array' || type === 'object')
    ? `() => (${literal(defaultValue, 8)})`
    : literal(defaultValue, 8);
  return `{ type: ${constructors[type]}, default: ${defaultCode} }`;
}

function renderVue(spec) {
  const props = Object.entries(spec.props).map(([name, [type, value]]) => `    ${name}: ${vueProp(type, value)}`).join(',\n');
  const state = Object.entries(spec.state).map(([name, value]) => `        ${name}: ${literal(value, 8)}`).join(',\n');
  const computed = (spec.computed || []).map(([name, args, body]) => `    ${name}(${args}) {\n${indentCode(compileCode(body, spec, 'vue'), 6)}\n    }`).join(',\n');
  const methods = [
    `    setValue(key, value) { this[key] = value; }`,
    `    emitEvent(name, payload) { this.$emit(name, payload); }`,
    ...(spec.methods || []).concat(sanExtraMethods(spec)).map(([name, args, body]) => `    ${name}(${args}) {\n${indentCode(compileCode(body, spec, 'vue'), 6)}\n    }`)
  ].join(',\n');
  const watch = (spec.watch || []).map(([name, body]) => `    ${name}() {\n${indentCode(compileCode(body, spec, 'vue'), 6)}\n    }`).join(',\n');
  const hooks = [];
  if (spec.inited) hooks.push(`  created() {\n${indentCode(compileCode(spec.inited, spec, 'vue'), 4)}\n  }`);
  if (spec.attached) hooks.push(`  mounted() {\n${indentCode(compileCode(spec.attached, spec, 'vue'), 4)}\n  }`);
  if (spec.disposed) hooks.push(`  beforeDestroy() {\n${indentCode(compileCode(spec.disposed, spec, 'vue'), 4)}\n  }`);
  return `<template>\n  ${spec.template}\n</template>\n\n<script>\nmodule.exports = {\n  name: '${spec.name}',${props ? `\n  props: {\n${props}\n  },` : ''}\n  data() {\n    return {\n${state}\n    };\n  },${computed ? `\n  computed: {\n${computed}\n  },` : ''}${watch ? `\n  watch: {\n${watch}\n  },` : ''}${hooks.length ? `\n${hooks.join(',\n')},` : ''}\n  methods: {\n${methods}\n  }\n};\n</script>\n\n<style scoped>\n${commonCss(spec.rootClass, spec.accent, spec.css)}\n</style>\n`;
}

function sanTemplate(template) {
  let output = template;
  output = output.replace(`:class="{ selected: record.key === selectedKey, reviewed: record.reviewed[language] }"`, `:class="(record.key === selectedKey ? 'selected ' : '') + (record.reviewed[language] ? 'reviewed' : '')"`);
  output = output.replace(`:class="{ selected: ticket.id === selectedId, urgent: ticket.priority === 'urgent' }"`, `:class="(ticket.id === selectedId ? 'selected ' : '') + (ticket.priority === 'urgent' ? 'urgent' : '')"`);
  output = output.replace(`:class="{ active: index === stageIndex, done: index < stageIndex }"`, `:class="(index === stageIndex ? 'active ' : '') + (index < stageIndex ? 'done' : '')"`);
  output = output.replace(/selectedTools\.indexOf\(tool\) >= 0/g, 'isIncluded(selectedTools, tool)');
  output = output.replace(/lane\.member\.skills\.join\(' \/ '\)/g, `joinValues(lane.member.skills, ' / ')`);
  output = output.replace(/\s:key="[^"]*"/g, '');
  output = output.replace(/v-for=/g, 's-for=').replace(/v-if=/g, 's-if=').replace(/v-else/g, 's-else');
  output = output.replace(/@([a-z]+)(?:\.[a-z]+)?=/g, 'on-$1=');
  output = output.replace(/:([a-zA-Z-]+)="([^"]*)"/g, (_, attribute, expression) => `${attribute}="{{ ${expression} }}"`);
  return output;
}

function sanExtraMethods(spec) {
  const methods = [];
  if (spec.template.includes('batchRowClass(')) {
    methods.push(['batchRowClass', 'batch', "return (this.isSelected(batch.id) ? 'selected ' : '') + (batch.expiryDays <= 3 ? 'risk' : '');"]);
  }
  if (spec.template.includes('selectedTools.indexOf(tool)')) {
    methods.push(['isIncluded', 'list, value', 'return list.indexOf(value) >= 0;']);
  }
  if (spec.template.includes("lane.member.skills.join(' / ')")) {
    methods.push(['joinValues', 'values, separator', 'return values.join(separator);']);
  }
  return methods;
}

function renderSan(spec) {
  const typeMap = { string: 'string', number: 'number', bool: 'bool', array: 'array', object: 'object' };
  const dataTypes = Object.entries(spec.props).map(([name, [type]]) => `    ${name}: DataTypes.${typeMap[type]}`).join(',\n');
  const defaults = [...Object.entries(spec.props).map(([name, [, value]]) => [name, value]), ...Object.entries(spec.state)];
  const initData = defaults.map(([name, value]) => `      ${name}: ${literal(value, 6)}`).join(',\n');
  const computed = (spec.computed || []).map(([name, args, body]) => `    ${name}(${args}) {\n${indentCode(compileCode(body, spec, 'san'), 6)}\n    }`).join(',\n');
  const allMethods = [...(spec.methods || []), ...sanExtraMethods(spec)];
  const methods = [
    `  setValue(key, value) { this.data.set(key, value); }`,
    `  emitEvent(name, payload) { this.fire(name, payload); }`,
    ...allMethods.map(([name, args, body]) => `  ${name}(${args}) {\n${indentCode(compileCode(body, spec, 'san'), 4)}\n  }`)
  ].join(',\n');
  const initedParts = [];
  if (spec.inited) initedParts.push(compileCode(spec.inited, spec, 'san'));
  (spec.watch || []).forEach(([name, body]) => initedParts.push(`this.watch('${name}', () => { ${compileCode(body, spec, 'san')} });`));
  const hooks = [];
  if (initedParts.length) hooks.push(`  inited() {\n${indentCode(initedParts.join('\n'), 4)}\n  }`);
  if (spec.attached) hooks.push(`  attached() {\n${indentCode(compileCode(spec.attached, spec, 'san'), 4)}\n  }`);
  if (spec.disposed) hooks.push(`  disposed() {\n${indentCode(compileCode(spec.disposed, spec, 'san'), 4)}\n  }`);
  return `<template>\n  ${sanTemplate(spec.template)}\n</template>\n\n<script>\nconst san = require('san');\nconst DataTypes = san.DataTypes;\n\nmodule.exports = san.defineComponent({\n  name: '${spec.name}',${dataTypes ? `\n  dataTypes: {\n${dataTypes}\n  },` : ''}\n  initData() {\n    return {\n${initData}\n    };\n  },${computed ? `\n  computed: {\n${computed}\n  },` : ''}${hooks.length ? `\n${hooks.join(',\n')},` : ''}\n${methods}\n});\n</script>\n\n<style>\n${commonCss(spec.rootClass, spec.accent, spec.css)}\n</style>\n`;
}

function levelDir(level) {
  return { simple: '01_simple', medium: '02_medium', complex: '03_complex' }[level];
}

function patternEntry(spec) {
  const template = spec.template;
  return {
    templates: {
      has_v_for: template.includes('v-for'), has_v_if: template.includes('v-if'), has_v_bind: template.includes(':'),
      has_v_on: template.includes('@'), has_slot: template.includes('<slot')
    },
    scripts: {
      has_props: Object.keys(spec.props).length > 0, has_data: Object.keys(spec.state).length > 0,
      has_computed: spec.computed.length > 0, has_methods: spec.methods.length > 0,
      has_watch: !!(spec.watch && spec.watch.length), has_lifecycle: !!(spec.inited || spec.attached || spec.disposed)
    },
    styles: {
      has_scoped: true, has_dynamic_class: template.includes(':class'), has_dynamic_style: template.includes(':style')
    },
    migration_patterns: spec.features.filter(item => ['v-for', 'v-if', 'v-on', 'v-bind', 'v-model', 'props', 'emit', 'watch', 'lifecycle-hooks', 'dynamic-class', 'dynamic-style'].includes(item)).map(item => ({
      'v-for': 'v_for_conversion', 'v-if': 'v_if_conversion', 'v-on': 'event_name_conversion', 'v-bind': 'attribute_binding_conversion',
      'v-model': 'model_binding_conversion', props: 'props_to_data_types', emit: 'emit_to_fire', watch: 'watch_registration',
      'lifecycle-hooks': 'lifecycle_mapping', 'dynamic-class': 'class_binding_conversion', 'dynamic-style': 'style_binding_conversion'
    })[item])
  };
}

function writeJson(file, value) {
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n', 'utf8');
}

function generate() {
  const names = new Set();
  specs.forEach(spec => {
    if (names.has(spec.name)) throw new Error(`Duplicate batch name: ${spec.name}`);
    names.add(spec.name);
    const total = Object.values(spec.score).reduce((sum, value) => sum + value, 0);
    if ((spec.level === 'simple' && (total < 5 || total > 8)) || (spec.level === 'medium' && (total < 9 || total > 12)) || (spec.level === 'complex' && (total < 13 || total > 15))) {
      throw new Error(`Invalid score for ${spec.name}: ${total}`);
    }
    const componentRoot = path.join(root, 'data', 'datasets', 'components', levelDir(spec.level), spec.name);
    const vueDir = path.join(componentRoot, 'vue');
    const sanDir = path.join(componentRoot, 'san');
    fs.mkdirSync(vueDir, { recursive: true });
    fs.mkdirSync(sanDir, { recursive: true });
    fs.writeFileSync(path.join(vueDir, `${spec.name}.vue`), renderVue(spec), 'utf8');
    fs.writeFileSync(path.join(sanDir, `${spec.name}.san`), renderSan(spec), 'utf8');
  });

  const dataRoot = path.join(root, 'data', 'datasets');
  const manifestFile = path.join(dataRoot, 'dataset_manifest.json');
  const complexityFile = path.join(dataRoot, 'features', 'complexity_tags.json');
  const patternFile = path.join(dataRoot, 'features', 'pattern_tags.json');
  const notesFile = path.join(dataRoot, 'features', 'migration_notes.json');
  const manifest = JSON.parse(fs.readFileSync(manifestFile, 'utf8'));
  const complexity = JSON.parse(fs.readFileSync(complexityFile, 'utf8'));
  const patterns = JSON.parse(fs.readFileSync(patternFile, 'utf8'));
  const notes = JSON.parse(fs.readFileSync(notesFile, 'utf8'));
  const ids = new Set(specs.map(spec => spec.id));
  manifest.components = manifest.components.filter(item => !ids.has(item.id));
  const componentNames = new Set(specs.map(spec => spec.name));
  const nextComplexity = complexity.filter(item => !componentNames.has(item.component_name));

  specs.forEach(spec => {
    const relativeRoot = `components/${levelDir(spec.level)}/${spec.name}/`;
    manifest.components.push({ id: spec.id, name: spec.label, path: relativeRoot, complexity: spec.level, vue_file: `${spec.name}.vue`, san_file: `${spec.name}.san`, created_date: createdDate, status: 'vue_ready,san_ready', notes: spec.workflow });
    const total = Object.values(spec.score).reduce((sum, value) => sum + value, 0);
    nextComplexity.push({ component_name: spec.name, complexity_score: spec.score, total_score: total, level: spec.level, features: spec.features, sub_components: [] });
    patterns[spec.id.replace(/_/g, '-')] = patternEntry(spec);
    notes[spec.id.replace(/_/g, '-')] = {
      notebook: '',
      challenges: [`${spec.model}需要在 Vue 与 San 中保持语义一致。`, `${spec.structure}涉及${spec.migrationFocus}。`],
      solutions: [`围绕“${spec.workflow}”使用不可变数据更新和显式状态转换。`, `将 Vue 指令与状态访问映射为 San 指令、dataTypes、initData、this.data.get/set 和 this.fire。`],
      validation: { structure_score: 1, functional_test: 'static_validate_passed', visual_test: 'not_run' }
    };
  });
  manifest.total_components = manifest.components.length;
  writeJson(manifestFile, manifest);
  writeJson(complexityFile, nextComplexity);
  writeJson(patternFile, patterns);
  writeJson(notesFile, notes);
  writeJson(path.join(dataRoot, 'features', 'design_matrix_2026-09-02_batch_30.json'), {
    created_date: createdDate,
    batch_size: specs.length,
    diversity_rule: '任意候选在数据模型、核心工作流、模板结构等维度中至少存在两个实质差异，且至少一项来自前三者。',
    components: specs.map(spec => ({ component_name: spec.name, level: spec.level, data_model: spec.model, core_workflow: spec.workflow, template_structure: spec.structure, state_change: spec.stateChange, communication: spec.communication, migration_focus: spec.migrationFocus }))
  });
  console.log(JSON.stringify({ generated: specs.length, byLevel: specs.reduce((acc, spec) => { acc[spec.level] = (acc[spec.level] || 0) + 1; return acc; }, {}), totalComponents: manifest.total_components }, null, 2));
}

add({
  name: 'DocumentApprovalFlow', label: '文档审批流程', level: 'complex', accent: '#b45309',
  model: '文档版本、审批步骤、评论线程和修订请求', workflow: '逐级审批、驳回、评论、提交新版本和查看历史', structure: '文档摘要、审批轨、正文、评论和版本历史', stateChange: '审批决定推进步骤或进入修订态，新版本重置流程', communication: '4 个 props，发出 approve/reject/version', migrationFocus: '多阶段审批、嵌套评论、版本重置和多事件输出',
  props: { documentTitle: ['string', '数据治理方案'], author: ['string', '研究小组'], reviewers: ['array', ['导师审核', '合规审核', '最终签发']], initialContent: ['string', '本方案描述数据采集、清洗、标注与质量控制流程。'] },
  state: { version: 1, content: '', steps: [], activeStep: 0, status: 'reviewing', commentDraft: '', comments: [], versions: [], rejectionReason: '', showHistory: false, updatedAt: '' }, inited: "SET_content(GET_initialContent); SET_steps(GET_reviewers.map((name, index) => ({ id: index + 1, name, status: index === 0 ? 'active' : 'pending' }))); this.refreshTime();",
  computed: [['currentReviewer', '', "return GET_steps[GET_activeStep] || null;"], ['approvedCount', '', "return GET_steps.filter(item => item.status === 'approved').length;"], ['canDecide', '', "return GET_status === 'reviewing' && !!GET_currentReviewer;"], ['progressStyle', '', "return 'width:' + Math.round(GET_approvedCount / GET_steps.length * 100) + '%';"]],
  methods: [['approve', '', "if (!GET_canDecide) return; const index = GET_activeStep; const steps = GET_steps.map((item, itemIndex) => Object.assign({}, item, { status: itemIndex === index ? 'approved' : itemIndex === index + 1 ? 'active' : item.status })); SET_steps(steps); if (index === steps.length - 1) SET_status('approved'); else SET_activeStep(index + 1); this.addComment('system', '步骤已批准'); this.refreshTime(); EMIT('approve', { version: GET_version, step: index });"], ['updateReason', 'event', "SET_rejectionReason(event.target.value);"], ['reject', '', "const reason = GET_rejectionReason.trim(); if (!GET_canDecide || !reason) return; SET_steps(GET_steps.map((item, index) => index === GET_activeStep ? Object.assign({}, item, { status: 'rejected' }) : item)); SET_status('revision'); this.addComment('system', '需要修订：' + reason); SET_rejectionReason(''); EMIT('reject', reason);"], ['updateComment', 'event', "SET_commentDraft(event.target.value);"], ['submitComment', 'event', "event.preventDefault(); const text = GET_commentDraft.trim(); if (!text) return; this.addComment('reviewer', text); SET_commentDraft('');"], ['addComment', 'role, text', "SET_comments([{ id: Date.now(), role, text, version: GET_version }].concat(GET_comments));"], ['updateContent', 'event', "SET_content(event.target.value);"], ['submitRevision', '', "if (GET_status !== 'revision') return; SET_versions([{ version: GET_version, content: GET_content, status: GET_status }].concat(GET_versions)); const version = GET_version + 1; SET_version(version); SET_steps(GET_reviewers.map((name, index) => ({ id: index + 1, name, status: index === 0 ? 'active' : 'pending' }))); SET_activeStep(0); SET_status('reviewing'); this.addComment('system', '已提交版本 v' + version); EMIT('version', version);"], ['toggleHistory', '', "SET_showHistory(!GET_showHistory);"], ['refreshTime', '', "SET_updatedAt(new Date().toLocaleString('zh-CN', { hour12: false }));"], ['statusText', 'status', "return { pending: '等待', active: '审批中', approved: '已通过', rejected: '需修订' }[status] || status;"]],
  template: `<section class="document-approval-flow"><header><div><p class="muted">v{{ version }} · {{ updatedAt }}</p><h2>{{ documentTitle }}</h2><span>作者：{{ author }}</span></div><button @click="toggleHistory">版本历史</button></header><div class="approval-progress"><span :style="progressStyle"></span></div><div class="approval-steps"><article v-for="step, index in steps" :key="step.id" :class="step.status"><i>{{ index + 1 }}</i><div><strong>{{ step.name }}</strong><small>{{ statusText(step.status) }}</small></div></article></div><div class="approval-layout"><main><textarea class="document-content" :value="content" @input="updateContent" :disabled="status !== 'revision'"></textarea><div v-if="status === 'reviewing'" class="decision-panel"><h3>当前：{{ currentReviewer.name }}</h3><input :value="rejectionReason" @input="updateReason" placeholder="驳回原因"><button @click="reject" :disabled="!rejectionReason">要求修订</button><button class="primary" @click="approve">批准</button></div><div v-if="status === 'revision'" class="revision-panel"><strong>文档正在修订</strong><button class="primary" @click="submitRevision">提交新版本</button></div><div v-if="status === 'approved'" class="approved-panel">全部审批完成</div></main><aside><h3>评论</h3><form @submit="submitComment"><textarea :value="commentDraft" @input="updateComment"></textarea><button type="submit">发送</button></form><ol><li v-for="comment in comments" :key="comment.id"><small>v{{ comment.version }} · {{ comment.role }}</small><p>{{ comment.text }}</p></li></ol></aside></div><section v-if="showHistory" class="version-history"><article v-for="item in versions" :key="item.version"><strong>v{{ item.version }}</strong><span>{{ item.status }}</span></article><p v-if="!versions.length">暂无历史版本</p></section></section>`,
  css: `header{display:flex;justify-content:space-between}.approval-progress{height:7px;margin:14px 0;background:#e5e7eb}.approval-progress span{display:block;height:100%;background:#b45309}.approval-steps{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.approval-steps article{display:flex;gap:8px;padding:10px;background:#f8fafc}.approval-steps i{display:grid;width:26px;height:26px;place-items:center;border-radius:50%;background:#d9dee4}.approval-steps article.active i{background:#f59e0b}.approval-steps article.approved i{background:#15803d;color:#fff}.approval-layout{display:grid;grid-template-columns:1fr 250px;gap:14px;margin-top:14px}.document-content{width:100%;min-height:180px}.decision-panel,.revision-panel,.approved-panel{padding:12px;background:#fffbeb}.decision-panel{display:flex;gap:7px}.decision-panel input{flex:1}.approved-panel{background:#ecfdf5}aside{padding:12px;background:#f8fafc}aside textarea{width:100%}aside ol{padding:0;list-style:none}.version-history{display:flex;gap:8px;margin-top:12px}`,
  score: complexScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'dynamic-style', 'scoped', 'approval-workflow', 'version-history']
});

add({
  name: 'CapacityPlanningBoard', label: '团队容量规划板', level: 'complex', accent: '#047857',
  model: '团队成员、周期容量、工作项分配和技能标签', workflow: '筛选周期、选择工作项、分配/取消、调容量并检测过载', structure: '周期头、待分配池、成员泳道和工作项详情', stateChange: '任务归属和个人容量共同影响利用率', communication: '4 个 props，发出 assignment/capacity/save', migrationFocus: '泳道分组、容量聚合、选中分配和过载样式',
  props: { boardTitle: ['string', '迭代容量规划'], cycles: ['array', ['Sprint 21', 'Sprint 22']], initialMembers: ['array', [{ id: 1, name: '林晓', capacity: 8, skills: ['前端'] }, { id: 2, name: '周宁', capacity: 10, skills: ['后端'] }, { id: 3, name: '陈雨', capacity: 6, skills: ['测试'] }]], initialWork: ['array', [{ id: 1, title: '登录页改造', points: 5, assigneeId: 1, cycle: 'Sprint 21' }, { id: 2, title: '接口缓存', points: 8, assigneeId: null, cycle: 'Sprint 21' }, { id: 3, title: '回归测试', points: 3, assigneeId: 3, cycle: 'Sprint 21' }, { id: 4, title: '埋点方案', points: 5, assigneeId: null, cycle: 'Sprint 22' }]] },
  state: { members: [], workItems: [], cycle: 'Sprint 21', selectedWorkId: null, skillFilter: 'all', saved: true, changeLog: [] }, inited: "SET_members(GET_initialMembers.map(item => Object.assign({}, item, { skills: item.skills.slice() }))); SET_workItems(GET_initialWork.map(item => Object.assign({}, item))); SET_cycle(GET_cycles[0] || '');",
  computed: [['cycleWork', '', "return GET_workItems.filter(item => item.cycle === GET_cycle);"], ['unassigned', '', "return GET_cycleWork.filter(item => item.assigneeId === null);"], ['visibleMembers', '', "return GET_skillFilter === 'all' ? GET_members : GET_members.filter(member => member.skills.indexOf(GET_skillFilter) >= 0);"], ['lanes', '', "return GET_visibleMembers.map(member => { const items = GET_cycleWork.filter(item => item.assigneeId === member.id); const load = items.reduce((sum, item) => sum + item.points, 0); return { member, items, load, percent: Math.round(load / member.capacity * 100), bar: 'width:' + Math.min(100, load / member.capacity * 100) + '%' }; });"], ['selectedWork', '', "return GET_workItems.find(item => item.id === GET_selectedWorkId) || null;"], ['totalPoints', '', "return GET_cycleWork.reduce((sum, item) => sum + item.points, 0);"]],
  methods: [['updateCycle', 'event', "SET_cycle(event.target.value); SET_selectedWorkId(null);"], ['updateSkill', 'event', "SET_skillFilter(event.target.value);"], ['selectWork', 'id', "SET_selectedWorkId(id);"], ['assign', 'memberId', "const id = GET_selectedWorkId; if (id === null) return; SET_workItems(GET_workItems.map(item => item.id === id ? Object.assign({}, item, { assigneeId: memberId }) : item)); SET_saved(false); this.log('已分配工作项'); EMIT('assignment', { workId: id, memberId });"], ['unassign', 'id', "SET_workItems(GET_workItems.map(item => item.id === id ? Object.assign({}, item, { assigneeId: null }) : item)); SET_saved(false); this.log('工作项退回待分配池');"], ['changeCapacity', 'memberId, delta', "SET_members(GET_members.map(member => member.id === memberId ? Object.assign({}, member, { capacity: Math.max(1, member.capacity + delta) }) : member)); SET_saved(false); EMIT('capacity', { memberId, delta });"], ['save', '', "SET_saved(true); this.log('规划已保存'); EMIT('save', { members: GET_members, workItems: GET_workItems });"], ['log', 'message', "SET_changeLog([{ id: Date.now(), message }].concat(GET_changeLog).slice(0, 4));"], ['laneClass', 'lane', "return lane.percent > 100 ? 'overloaded' : lane.percent > 80 ? 'near-limit' : '';"], ['isSelected', 'id', "return GET_selectedWorkId === id;"]],
  template: `<section class="capacity-planning-board"><header><div><p class="muted">{{ saved ? '规划已保存' : '有未保存变更' }}</p><h2>{{ boardTitle }}</h2></div><div class="actions"><select :value="cycle" @change="updateCycle"><option v-for="item in cycles" :key="item" :value="item">{{ item }}</option></select><button class="primary" @click="save">保存</button></div></header><div class="capacity-summary"><span>总工作量 {{ totalPoints }} 点</span><select :value="skillFilter" @change="updateSkill"><option value="all">全部技能</option><option>前端</option><option>后端</option><option>测试</option></select></div><div class="planning-layout"><aside><h3>待分配 {{ unassigned.length }}</h3><button v-for="item in unassigned" :key="item.id" :class="isSelected(item.id) ? 'selected' : ''" @click="selectWork(item.id)"><strong>{{ item.title }}</strong><small>{{ item.points }} 点</small></button><p v-if="!unassigned.length" class="empty">全部已分配</p><section v-if="selectedWork"><h3>当前工作项</h3><p>{{ selectedWork.title }}</p><strong>{{ selectedWork.points }} 点</strong></section></aside><main><article v-for="lane in lanes" :key="lane.member.id" :class="'member-lane ' + laneClass(lane)"><header><div><strong>{{ lane.member.name }}</strong><small>{{ lane.member.skills.join(' / ') }}</small></div><div><button @click="changeCapacity(lane.member.id, -1)">−</button><span>{{ lane.load }}/{{ lane.member.capacity }}</span><button @click="changeCapacity(lane.member.id, 1)">＋</button><button @click="assign(lane.member.id)" :disabled="selectedWorkId === null">分配到此</button></div></header><div class="capacity-bar"><span :style="lane.bar"></span></div><div class="lane-items"><button v-for="item in lane.items" :key="item.id" :class="isSelected(item.id) ? 'selected' : ''" @click="selectWork(item.id)">{{ item.title }} · {{ item.points }}<i @click.stop="unassign(item.id)">×</i></button></div></article></main></div><footer><span v-for="entry in changeLog" :key="entry.id">{{ entry.message }}</span></footer></section>`,
  css: `header,.capacity-summary{display:flex;justify-content:space-between}.capacity-summary{padding:10px;background:#ecfdf5}.planning-layout{display:grid;grid-template-columns:175px 1fr;gap:14px;margin-top:12px}.planning-layout>aside{padding:10px;background:#f6f8f8}.planning-layout>aside>button{display:block;width:100%;margin:6px 0}.planning-layout button.selected{background:#d1fae5}.member-lane{margin-bottom:10px;padding:12px;border:1px solid #dce3df}.member-lane.near-limit{border-color:#d97706}.member-lane.overloaded{border-color:#dc2626;background:#fef2f2}.capacity-bar{height:6px;margin:8px 0;background:#e5e7eb}.capacity-bar span{display:block;height:100%;background:#047857}.lane-items{display:flex;gap:7px;flex-wrap:wrap}.lane-items i{margin-left:6px;color:#b91c1c}footer{display:flex;gap:8px;font-size:11px}`,
  score: complexScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'dynamic-style', 'scoped', 'swimlane', 'capacity-planning']
});

add({
  name: 'LocalizationWorkspace', label: '本地化翻译工作台', level: 'complex', accent: '#6d28d9',
  model: '源文案键、多语言译文、审核状态、术语和过滤器', workflow: '选语言、搜索、编辑、审核、术语插入和批量提交', structure: '语言头、键列表、翻译编辑器和术语侧栏', stateChange: '嵌套语言译文和审核状态独立更新', communication: '4 个 props，发出 translation-change/review/submit', migrationFocus: '嵌套对象更新、主从视图和批量提交',
  props: { projectName: ['string', '管理后台'], languages: ['array', [{ code: 'en', name: 'English' }, { code: 'ja', name: '日本語' }]], entries: ['array', [{ key: 'nav.home', source: '首页', translations: { en: 'Home', ja: 'ホーム' }, reviewed: { en: true, ja: false } }, { key: 'action.save', source: '保存', translations: { en: 'Save', ja: '' }, reviewed: { en: false, ja: false } }, { key: 'message.empty', source: '暂无数据', translations: { en: 'No data', ja: 'データなし' }, reviewed: { en: true, ja: true } }]], glossary: ['array', [{ source: '保存', target: 'Save' }, { source: '数据', target: 'data' }]] },
  state: { records: [], language: 'en', query: '', filter: 'all', selectedKey: '', draft: '', showGlossary: true, dirtyKeys: [], submittedAt: '' }, inited: "SET_records(GET_entries.map(item => ({ key: item.key, source: item.source, translations: Object.assign({}, item.translations), reviewed: Object.assign({}, item.reviewed) }))); SET_language(GET_languages[0] ? GET_languages[0].code : ''); SET_selectedKey(GET_entries[0] ? GET_entries[0].key : ''); this.loadDraft();",
  computed: [['visibleRecords', '', "const q = GET_query.toLowerCase(); return GET_records.filter(item => (item.key.toLowerCase().indexOf(q) >= 0 || item.source.indexOf(GET_query) >= 0) && (GET_filter === 'all' || (GET_filter === 'missing' ? !item.translations[GET_language] : !item.reviewed[GET_language])));"], ['selectedRecord', '', "return GET_records.find(item => item.key === GET_selectedKey) || null;"], ['progress', '', "const records = GET_records; return records.length ? Math.round(records.filter(item => item.reviewed[GET_language]).length / records.length * 100) : 0;"], ['missingCount', '', "return GET_records.filter(item => !item.translations[GET_language]).length;"], ['currentLanguageName', '', "const item = GET_languages.find(row => row.code === GET_language); return item ? item.name : '';"]],
  methods: [['updateLanguage', 'event', "this.commitDraft(); SET_language(event.target.value); this.loadDraft();"], ['updateQuery', 'event', "SET_query(event.target.value);"], ['updateFilter', 'event', "SET_filter(event.target.value);"], ['selectRecord', 'key', "this.commitDraft(); SET_selectedKey(key); this.loadDraft();"], ['updateDraft', 'event', "SET_draft(event.target.value);"], ['loadDraft', '', "const record = GET_records.find(item => item.key === GET_selectedKey); SET_draft(record ? record.translations[GET_language] || '' : '');"], ['commitDraft', '', "const key = GET_selectedKey; if (!key) return; const language = GET_language; const value = GET_draft; SET_records(GET_records.map(item => item.key === key ? Object.assign({}, item, { translations: Object.assign({}, item.translations, { [language]: value }), reviewed: Object.assign({}, item.reviewed, { [language]: false }) }) : item)); if (GET_dirtyKeys.indexOf(key) < 0) SET_dirtyKeys(GET_dirtyKeys.concat(key)); EMIT('translation-change', { key, language, value });"], ['markReviewed', '', "this.commitDraft(); const key = GET_selectedKey; const language = GET_language; SET_records(GET_records.map(item => item.key === key ? Object.assign({}, item, { reviewed: Object.assign({}, item.reviewed, { [language]: true }) }) : item)); EMIT('review', { key, language });"], ['applyTerm', 'term', "SET_draft(GET_draft + (GET_draft ? ' ' : '') + term.target);"], ['toggleGlossary', '', "SET_showGlossary(!GET_showGlossary);"], ['submitBatch', '', "this.commitDraft(); SET_submittedAt(new Date().toLocaleString('zh-CN', { hour12: false })); EMIT('submit', { language: GET_language, keys: GET_dirtyKeys }); SET_dirtyKeys([]);"], ['translationFor', 'record', "return record.translations[GET_language] || '未翻译';"]],
  template: `<section class="localization-workspace"><header><div><p class="muted">{{ projectName }} · {{ currentLanguageName }}</p><h2>本地化翻译</h2></div><div class="actions"><select :value="language" @change="updateLanguage"><option v-for="item in languages" :key="item.code" :value="item.code">{{ item.name }}</option></select><button @click="toggleGlossary">术语表</button><button class="primary" @click="submitBatch">提交 {{ dirtyKeys.length }} 项</button></div></header><div class="locale-metrics"><span>审核 {{ progress }}%</span><span>缺失 {{ missingCount }} 项</span><span v-if="submittedAt">{{ submittedAt }}</span></div><div :class="'locale-layout ' + (showGlossary ? 'with-glossary' : '')"><aside class="entry-list"><input :value="query" @input="updateQuery" placeholder="搜索"><select :value="filter" @change="updateFilter"><option value="all">全部</option><option value="missing">缺失</option><option value="unreviewed">待审核</option></select><button v-for="record in visibleRecords" :key="record.key" :class="{ selected: record.key === selectedKey, reviewed: record.reviewed[language] }" @click="selectRecord(record.key)"><strong>{{ record.key }}</strong><span>{{ record.source }}</span><small>{{ translationFor(record) }}</small></button><p v-if="!visibleRecords.length" class="empty">无匹配文案</p></aside><main v-if="selectedRecord"><div class="source-panel"><span>源文案</span><strong>{{ selectedRecord.source }}</strong><small>{{ selectedRecord.key }}</small></div><label>目标译文<textarea :value="draft" @input="updateDraft"></textarea></label><div class="editor-actions"><span>{{ draft.length }} 字符</span><button class="primary" @click="markReviewed" :disabled="!draft">保存并审核</button></div></main><aside v-if="showGlossary" class="glossary"><h3>推荐术语</h3><button v-for="term in glossary" :key="term.source" @click="applyTerm(term)"><span>{{ term.source }}</span><strong>{{ term.target }}</strong></button></aside></div></section>`,
  css: `header,.locale-metrics{display:flex;justify-content:space-between}.locale-metrics{padding:10px;background:#f5f3ff}.locale-layout{display:grid;grid-template-columns:220px 1fr;gap:12px;margin-top:12px}.locale-layout.with-glossary{grid-template-columns:220px 1fr 150px}.entry-list{max-height:450px;overflow:auto}.entry-list>button{display:grid;width:100%;margin:6px 0;text-align:left}.entry-list>button.selected{background:#ede9fe}.entry-list>button.reviewed{border-left:4px solid #15803d}.entry-list small{color:#77818e}.locale-layout main{padding:16px;background:#fafafa}.source-panel{display:grid;padding:12px;background:#f1f2f4}.locale-layout main label{display:grid;gap:6px;margin-top:14px}.locale-layout main textarea{min-height:160px}.editor-actions{display:flex;justify-content:space-between}.glossary{padding:10px;background:#f7f5fb}.glossary button{display:grid;width:100%;margin:6px 0}`,
  score: complexScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'scoped', 'nested-locales', 'master-detail', 'batch-submit']
});

add({
  name: 'SupportTicketConsole', label: '客服工单控制台', level: 'complex', accent: '#2563eb',
  model: '工单队列、消息线程、标签、优先级、负责人和草稿', workflow: '筛选、回复、内部备注、改状态、转派和合并', structure: '筛选队列、对话主区、属性侧栏和 SLA 提示', stateChange: '消息、状态和队列排序随处理动作联动', communication: '4 个 props，发出 reply/status/assign/merge', migrationFocus: '主从视图、消息线程、SLA 定时器和嵌套更新',
  props: { inboxTitle: ['string', '客户支持收件箱'], agents: ['array', ['林晓', '周宁', '陈雨']], initialTickets: ['array', [{ id: 101, subject: '无法完成付款', customer: '安然', priority: 'urgent', status: 'open', assignee: '林晓', tags: ['支付'], age: 18, messages: [{ id: 1, author: '客户', text: '付款页面一直提示失败。', internal: false }] }, { id: 102, subject: '申请导出数据', customer: '北辰', priority: 'normal', status: 'pending', assignee: '周宁', tags: ['数据'], age: 55, messages: [{ id: 2, author: '客户', text: '请问如何导出历史数据？', internal: false }] }, { id: 103, subject: '账号权限异常', customer: '知夏', priority: 'high', status: 'open', assignee: '', tags: ['权限'], age: 32, messages: [{ id: 3, author: '客户', text: '管理员菜单突然消失。', internal: false }] }]], cannedReplies: ['array', ['已收到，我们正在处理。', '问题已修复，请刷新后重试。']] },
  state: { tickets: [], selectedId: null, query: '', statusFilter: 'all', replyDraft: '', internalNote: false, selectedTag: '', mergeTargetId: null, nowTick: 0, timer: null }, inited: "SET_tickets(GET_initialTickets.map(ticket => Object.assign({}, ticket, { tags: ticket.tags.slice(), messages: ticket.messages.map(message => Object.assign({}, message)) }))); SET_selectedId(GET_initialTickets[0] ? GET_initialTickets[0].id : null);", attached: "this.timer = setInterval(() => SET_nowTick(GET_nowTick + 1), 60000);", disposed: "clearInterval(this.timer);",
  computed: [['visibleTickets', '', "const q = GET_query.toLowerCase(); const rank = { urgent: 0, high: 1, normal: 2 }; return GET_tickets.filter(ticket => (GET_statusFilter === 'all' || ticket.status === GET_statusFilter) && (!GET_selectedTag || ticket.tags.indexOf(GET_selectedTag) >= 0) && (ticket.subject.toLowerCase().indexOf(q) >= 0 || ticket.customer.toLowerCase().indexOf(q) >= 0)).slice().sort((a, b) => (rank[a.priority] || 3) - (rank[b.priority] || 3));"], ['selectedTicket', '', "return GET_tickets.find(ticket => ticket.id === GET_selectedId) || null;"], ['openCount', '', "return GET_tickets.filter(ticket => ticket.status === 'open').length;"], ['slaState', '', "const ticket = GET_selectedTicket; if (!ticket) return 'none'; const age = ticket.age + GET_nowTick; return age >= 60 ? 'breached' : age >= 45 ? 'warning' : 'safe';"], ['allTags', '', "return Array.from(new Set(GET_tickets.reduce((all, ticket) => all.concat(ticket.tags), [])));"], ['mergeCandidates', '', "return GET_tickets.filter(ticket => ticket.id !== GET_selectedId && ticket.status !== 'closed');"]],
  methods: [['updateQuery', 'event', "SET_query(event.target.value);"], ['updateStatusFilter', 'event', "SET_statusFilter(event.target.value);"], ['filterTag', 'tag', "SET_selectedTag(GET_selectedTag === tag ? '' : tag);"], ['selectTicket', 'id', "SET_selectedId(id); SET_replyDraft(''); SET_mergeTargetId(null);"], ['updateReply', 'event', "SET_replyDraft(event.target.value);"], ['toggleInternal', 'event', "SET_internalNote(event.target.checked);"], ['useCanned', 'text', "SET_replyDraft(text);"], ['sendReply', 'event', "event.preventDefault(); const text = GET_replyDraft.trim(); const id = GET_selectedId; if (!text || id === null) return; const message = { id: Date.now(), author: GET_internalNote ? '内部备注' : '客服', text, internal: GET_internalNote }; SET_tickets(GET_tickets.map(ticket => ticket.id === id ? Object.assign({}, ticket, { messages: ticket.messages.concat(message), status: GET_internalNote ? ticket.status : 'pending' }) : ticket)); SET_replyDraft(''); EMIT('reply', { ticketId: id, message });"], ['changeStatus', 'status', "const id = GET_selectedId; SET_tickets(GET_tickets.map(ticket => ticket.id === id ? Object.assign({}, ticket, { status }) : ticket)); EMIT('status', { ticketId: id, status });"], ['assignAgent', 'event', "const assignee = event.target.value; const id = GET_selectedId; SET_tickets(GET_tickets.map(ticket => ticket.id === id ? Object.assign({}, ticket, { assignee }) : ticket)); EMIT('assign', { ticketId: id, assignee });"], ['setMergeTarget', 'event', "SET_mergeTargetId(Number(event.target.value) || null);"], ['mergeTicket', '', "const sourceId = GET_selectedId; const targetId = GET_mergeTargetId; if (!targetId) return; const source = GET_tickets.find(ticket => ticket.id === sourceId); SET_tickets(GET_tickets.map(ticket => ticket.id === targetId ? Object.assign({}, ticket, { messages: ticket.messages.concat(source.messages) }) : ticket).filter(ticket => ticket.id !== sourceId)); SET_selectedId(targetId); EMIT('merge', { sourceId, targetId });"], ['priorityRank', 'priority', "return { urgent: 0, high: 1, normal: 2 }[priority] || 3;"], ['priorityText', 'priority', "return { urgent: '紧急', high: '高', normal: '普通' }[priority];"], ['statusText', 'status', "return { open: '处理中', pending: '等待客户', closed: '已关闭' }[status];"]],
  template: `<section class="support-ticket-console"><header><div><p class="muted">{{ openCount }} 个处理中</p><h2>{{ inboxTitle }}</h2></div><div class="actions"><input :value="query" @input="updateQuery" placeholder="搜索"><select :value="statusFilter" @change="updateStatusFilter"><option value="all">全部状态</option><option value="open">处理中</option><option value="pending">等待客户</option><option value="closed">已关闭</option></select></div></header><div class="tag-strip"><button v-for="tag in allTags" :key="tag" :class="tag === selectedTag ? 'active' : ''" @click="filterTag(tag)">{{ tag }}</button></div><div class="ticket-layout"><aside class="ticket-list"><button v-for="ticket in visibleTickets" :key="ticket.id" :class="{ selected: ticket.id === selectedId, urgent: ticket.priority === 'urgent' }" @click="selectTicket(ticket.id)"><span><strong>#{{ ticket.id }} {{ ticket.subject }}</strong><small>{{ ticket.customer }} · {{ statusText(ticket.status) }}</small></span><i>{{ priorityText(ticket.priority) }}</i></button><p v-if="!visibleTickets.length" class="empty">无匹配工单</p></aside><main v-if="selectedTicket"><div class="conversation-head"><div><h3>{{ selectedTicket.subject }}</h3><span>{{ selectedTicket.customer }}</span></div><span :class="'sla ' + slaState">SLA {{ selectedTicket.age + nowTick }} 分钟</span></div><div class="messages"><article v-for="message in selectedTicket.messages" :key="message.id" :class="message.internal ? 'internal' : ''"><strong>{{ message.author }}</strong><p>{{ message.text }}</p></article></div><form class="reply-box" @submit="sendReply"><div><button v-for="text in cannedReplies" :key="text" type="button" @click="useCanned(text)">{{ text }}</button></div><textarea :value="replyDraft" @input="updateReply"></textarea><footer><label><input type="checkbox" :checked="internalNote" @change="toggleInternal"> 内部备注</label><button class="primary" type="submit" :disabled="!replyDraft">发送</button></footer></form></main><aside v-if="selectedTicket" class="ticket-properties"><h3>工单属性</h3><label>负责人<select :value="selectedTicket.assignee" @change="assignAgent"><option value="">未分配</option><option v-for="agent in agents" :key="agent" :value="agent">{{ agent }}</option></select></label><div><b v-for="tag in selectedTicket.tags" :key="tag">{{ tag }}</b></div><div><button @click="changeStatus('open')">处理中</button><button @click="changeStatus('pending')">等待</button><button @click="changeStatus('closed')">关闭</button></div><label>合并到<select :value="mergeTargetId || ''" @change="setMergeTarget"><option value="">选择工单</option><option v-for="ticket in mergeCandidates" :key="ticket.id" :value="ticket.id">#{{ ticket.id }}</option></select></label><button @click="mergeTicket" :disabled="!mergeTargetId">执行合并</button></aside></div></section>`,
  css: `header{display:flex;justify-content:space-between}.tag-strip{display:flex;gap:6px;margin:10px 0}.tag-strip button.active{background:#dbeafe}.ticket-layout{display:grid;grid-template-columns:210px 1fr 175px;min-height:480px;border:1px solid #dce2e8}.ticket-list{border-right:1px solid #dce2e8}.ticket-list>button{display:flex;width:100%;justify-content:space-between;border:0;border-bottom:1px solid #e6e9ec;text-align:left}.ticket-list>button.selected{background:#eff6ff}.ticket-list>button.urgent{border-left:4px solid #dc2626}.ticket-list small{display:block}.ticket-layout main{display:flex;flex-direction:column;padding:12px}.conversation-head{display:flex;justify-content:space-between}.sla.warning{background:#fef3c7}.sla.breached{background:#fee2e2}.messages{flex:1}.messages article{max-width:80%;padding:10px;background:#eff6ff}.messages article.internal{background:#fff7ed}.reply-box textarea{width:100%}.reply-box footer{display:flex;justify-content:space-between}.ticket-properties{padding:12px;border-left:1px solid #dce2e8;background:#f8fafc}.ticket-properties label{display:grid;margin:10px 0}.ticket-properties b{display:inline-block;margin:4px;padding:4px;background:#e2e8f0}`,
  score: complexScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'lifecycle-hooks', 'dynamic-class', 'scoped', 'master-detail', 'message-thread', 'sla-timer']
});

add({
  name: 'TripItineraryPlanner', label: '行程规划工作台', level: 'complex', accent: '#0369a1',
  model: '按天分组的行程段、时间、地点、预算和冲突', workflow: '选天、增删行程、调整顺序、预算汇总和冲突检测', structure: '日期侧栏、时间线编辑区和新增表单', stateChange: '有序时间段变更触发冲突与预算派生', communication: '3 个 props，发出 itinerary-change/save', migrationFocus: '分组数据、有序重排、时间冲突和深层更新',
  props: { tripName: ['string', '杭州周末行'], days: ['array', [{ id: 'd1', label: '周六' }, { id: 'd2', label: '周日' }]], initialItems: ['array', [{ id: 1, dayId: 'd1', start: '09:00', end: '11:00', place: '西湖', cost: 0 }, { id: 2, dayId: 'd1', start: '10:30', end: '12:00', place: '博物馆', cost: 30 }, { id: 3, dayId: 'd2', start: '14:00', end: '17:00', place: '湿地公园', cost: 80 }]] },
  state: { items: [], activeDayId: 'd1', draft: { start: '09:00', end: '10:00', place: '', cost: 0 }, budgetLimit: 500, saved: false, nextId: 10 }, inited: "SET_items(GET_initialItems.map(item => Object.assign({}, item))); SET_activeDayId(GET_days[0] ? GET_days[0].id : '');",
  computed: [['dayItems', '', "return GET_items.filter(item => item.dayId === GET_activeDayId).slice().sort((a, b) => a.start.localeCompare(b.start));"], ['totalCost', '', "return GET_items.reduce((sum, item) => sum + item.cost, 0);"], ['remainingBudget', '', "return GET_budgetLimit - GET_totalCost;"], ['conflictIds', '', "const rows = GET_dayItems; const ids = []; rows.forEach((item, index) => rows.slice(index + 1).forEach(other => { if (item.start < other.end && other.start < item.end) ids.push(item.id, other.id); })); return Array.from(new Set(ids));"], ['activeDayLabel', '', "const day = GET_days.find(item => item.id === GET_activeDayId); return day ? day.label : '';"]],
  methods: [['selectDay', 'id', "SET_activeDayId(id);"], ['updateDraft', 'field, event', "SET_draft(Object.assign({}, GET_draft, { [field]: field === 'cost' ? Number(event.target.value) || 0 : event.target.value }));"], ['addItem', 'event', "event.preventDefault(); const draft = GET_draft; if (!draft.place.trim() || draft.start >= draft.end) return; const next = GET_items.concat({ id: GET_nextId, dayId: GET_activeDayId, start: draft.start, end: draft.end, place: draft.place.trim(), cost: draft.cost }); SET_items(next); SET_nextId(GET_nextId + 1); SET_draft({ start: draft.end, end: '18:00', place: '', cost: 0 }); SET_saved(false); this.notify(next);"], ['removeItem', 'id', "const next = GET_items.filter(item => item.id !== id); SET_items(next); SET_saved(false); this.notify(next);"], ['moveItem', 'index, delta', "const rows = GET_dayItems.slice(); const target = index + delta; if (target < 0 || target >= rows.length) return; const temp = rows[index].start; rows[index].start = rows[target].start; rows[target].start = temp; const mapped = {}; rows.forEach(item => mapped[item.id] = item); const next = GET_items.map(item => mapped[item.id] ? Object.assign({}, mapped[item.id]) : item); SET_items(next); SET_saved(false); this.notify(next);"], ['updateBudget', 'event', "SET_budgetLimit(Number(event.target.value) || 0);"], ['save', '', "SET_saved(true); EMIT('save', { items: GET_items, budget: GET_budgetLimit });"], ['notify', 'items', "EMIT('itinerary-change', items);"], ['isConflict', 'id', "return GET_conflictIds.indexOf(id) >= 0;"], ['dayCount', 'id', "return GET_items.filter(item => item.dayId === id).length;"]],
  template: `<section class="trip-itinerary-planner"><header><div><p class="muted">{{ saved ? '已保存' : '有未保存更改' }}</p><h2>{{ tripName }}</h2></div><button class="primary" @click="save">保存行程</button></header><div class="trip-layout"><nav><button v-for="day in days" :key="day.id" :class="day.id === activeDayId ? 'active' : ''" @click="selectDay(day.id)">{{ day.label }}<small>{{ dayCount(day.id) }} 项</small></button><label>预算<input type="number" :value="budgetLimit" @input="updateBudget"></label><p :class="remainingBudget < 0 ? 'over' : ''">余额 {{ remainingBudget }} 元</p></nav><main><h3>{{ activeDayLabel }}安排</h3><ol><li v-for="item, index in dayItems" :key="item.id" :class="isConflict(item.id) ? 'conflict' : ''"><time>{{ item.start }}<br>{{ item.end }}</time><div><strong>{{ item.place }}</strong><span>¥{{ item.cost }}</span><small v-if="isConflict(item.id)">时间冲突</small></div><div><button @click="moveItem(index, -1)" :disabled="index === 0">↑</button><button @click="moveItem(index, 1)" :disabled="index === dayItems.length - 1">↓</button><button @click="removeItem(item.id)">删除</button></div></li></ol><form @submit="addItem"><input type="time" :value="draft.start" @input="updateDraft('start', $event)"><input type="time" :value="draft.end" @input="updateDraft('end', $event)"><input :value="draft.place" @input="updateDraft('place', $event)" placeholder="地点"><input type="number" :value="draft.cost" @input="updateDraft('cost', $event)" placeholder="费用"><button class="primary" type="submit">添加</button></form></main></div></section>`,
  css: `header{display:flex;justify-content:space-between}.trip-layout{display:grid;grid-template-columns:150px 1fr;gap:16px}nav{display:grid;align-content:start;gap:7px;padding:10px;background:#f4f7f9}nav button.active{background:#e0f2fe;border-color:#0369a1}nav button small{display:block}.over{color:#b91c1c}ol{padding:0;list-style:none}li{display:grid;grid-template-columns:60px 1fr auto;gap:10px;padding:11px;border-left:3px solid #7aa8c4;border-bottom:1px solid #e2e7eb}li.conflict{border-left-color:#dc2626;background:#fef2f2}li span,li small{display:block}li small{color:#b91c1c}form{display:grid;grid-template-columns:90px 90px 1fr 80px auto;gap:7px}`,
  score: complexScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'scoped', 'grouped-timeline', 'conflict-detection']
});

add({
  name: 'SchemaMappingWorkbench', label: '字段映射工作台', level: 'complex', accent: '#7c3aed',
  model: '源字段、目标字段、映射规则、转换器和校验结果', workflow: '选择字段建立映射、配置转换、校验并提交', structure: '源字段栏、映射画布、目标字段栏和问题面板', stateChange: '映射图随选择和规则变更重新验证', communication: '4 个 props，发出 validate/submit', migrationFocus: '映射关系、多选状态、规则编辑和校验聚合',
  props: { title: ['string', '客户数据映射'], sourceFields: ['array', [{ key: 'full_name', type: 'string' }, { key: 'birth_year', type: 'number' }, { key: 'email_addr', type: 'string' }]], targetFields: ['array', [{ key: 'name', type: 'string', required: true }, { key: 'age', type: 'number', required: false }, { key: 'email', type: 'string', required: true }]], initialMappings: ['array', [{ id: 1, source: 'full_name', target: 'name', transform: 'trim' }]] },
  state: { mappings: [], sourceKey: '', targetKey: '', issues: [], validated: false, previewMode: false, nextId: 10, transforms: ['none', 'trim', 'uppercase', 'to-number'] }, inited: "SET_mappings(GET_initialMappings.map(item => Object.assign({}, item)));",
  computed: [['unmappedSources', '', "const used = GET_mappings.map(item => item.source); return GET_sourceFields.filter(field => used.indexOf(field.key) < 0);"], ['unmappedTargets', '', "const used = GET_mappings.map(item => item.target); return GET_targetFields.filter(field => used.indexOf(field.key) < 0);"], ['mappedCount', '', "return GET_mappings.length;"], ['canConnect', '', "return !!GET_sourceKey && !!GET_targetKey;"]],
  methods: [['selectSource', 'key', "SET_sourceKey(key); SET_validated(false);"], ['selectTarget', 'key', "SET_targetKey(key); SET_validated(false);"], ['connect', '', "if (!GET_canConnect) return; SET_mappings(GET_mappings.concat({ id: GET_nextId, source: GET_sourceKey, target: GET_targetKey, transform: 'none' })); SET_nextId(GET_nextId + 1); SET_sourceKey(''); SET_targetKey(''); SET_validated(false);"], ['removeMapping', 'id', "SET_mappings(GET_mappings.filter(item => item.id !== id)); SET_validated(false);"], ['updateTransform', 'id, event', "SET_mappings(GET_mappings.map(item => item.id === id ? Object.assign({}, item, { transform: event.target.value }) : item)); SET_validated(false);"], ['validateMappings', '', "const mappings = GET_mappings; const issues = []; GET_targetFields.filter(field => field.required).forEach(field => { if (!mappings.some(item => item.target === field.key)) issues.push('必填字段 ' + field.key + ' 未映射'); }); mappings.forEach(item => { const source = GET_sourceFields.find(field => field.key === item.source); const target = GET_targetFields.find(field => field.key === item.target); if (source && target && source.type !== target.type && item.transform !== 'to-number') issues.push(item.source + ' 与 ' + item.target + ' 类型不一致'); }); SET_issues(issues); SET_validated(true); EMIT('validate', issues);"], ['togglePreview', '', "SET_previewMode(!GET_previewMode);"], ['submit', '', "this.validateMappings(); if (!GET_issues.length) EMIT('submit', GET_mappings);"], ['fieldType', 'key, list', "const field = list.find(item => item.key === key); return field ? field.type : '';"]],
  template: `<section class="schema-mapping-workbench"><header><div><p class="muted">{{ mappedCount }} 条规则</p><h2>{{ title }}</h2></div><div class="actions"><button @click="togglePreview">{{ previewMode ? '编辑' : '预览' }}</button><button @click="validateMappings">校验</button><button class="primary" @click="submit">提交</button></div></header><div class="mapping-layout"><aside><h3>源字段</h3><button v-for="field in unmappedSources" :key="field.key" :class="field.key === sourceKey ? 'selected' : ''" @click="selectSource(field.key)"><strong>{{ field.key }}</strong><small>{{ field.type }}</small></button></aside><main><article v-for="mapping in mappings" :key="mapping.id"><div><strong>{{ mapping.source }}</strong><small>{{ fieldType(mapping.source, sourceFields) }}</small></div><span>→</span><select :value="mapping.transform" @change="updateTransform(mapping.id, $event)" :disabled="previewMode"><option v-for="transform in transforms" :key="transform" :value="transform">{{ transform }}</option></select><span>→</span><div><strong>{{ mapping.target }}</strong><small>{{ fieldType(mapping.target, targetFields) }}</small></div><button v-if="!previewMode" @click="removeMapping(mapping.id)">删除</button></article><p v-if="!mappings.length" class="empty">选择字段建立映射</p><button class="connect" @click="connect" :disabled="!canConnect || previewMode">连接所选字段</button><section v-if="validated" :class="issues.length ? 'validation bad' : 'validation good'"><h3>{{ issues.length ? '发现问题' : '校验通过' }}</h3><ul><li v-for="issue in issues" :key="issue">{{ issue }}</li></ul></section></main><aside><h3>目标字段</h3><button v-for="field in unmappedTargets" :key="field.key" :class="field.key === targetKey ? 'selected' : ''" @click="selectTarget(field.key)"><strong>{{ field.key }}</strong><small>{{ field.type }}{{ field.required ? ' · 必填' : '' }}</small></button></aside></div></section>`,
  css: `header{display:flex;justify-content:space-between}.mapping-layout{display:grid;grid-template-columns:145px 1fr 145px;gap:12px;margin-top:14px}.mapping-layout>aside{padding:10px;background:#f6f5fb}.mapping-layout>aside button{display:block;width:100%;margin:6px 0;text-align:left}.mapping-layout>aside button.selected{background:#ede9fe;border-color:#7c3aed}.mapping-layout small{display:block}.mapping-layout main>article{display:grid;grid-template-columns:1fr 18px 100px 18px 1fr auto;align-items:center;gap:5px;padding:10px;border-bottom:1px solid #e3e2e9}.connect{display:block;margin:12px auto}.validation{padding:12px}.validation.bad{background:#fef2f2}.validation.good{background:#f0fdf4}`,
  score: complexScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'scoped', 'graph-mapping', 'validation']
});

add({
  name: 'ExperimentRolloutConsole', label: '实验流量控制台', level: 'complex', accent: '#be185d',
  model: '实验变体、流量权重、指标、阶段和历史快照', workflow: '调整流量、开始/暂停、模拟指标、判定胜出与回滚', structure: '状态头、流量编辑、指标表和历史快照', stateChange: '定时指标更新与流量约束驱动实验阶段', communication: '3 个 props，发出 allocation/status/winner', migrationFocus: '权重约束、定时模拟、历史快照和多状态控制',
  props: { experimentName: ['string', '结算页按钮实验'], initialVariants: ['array', [{ id: 'control', name: '原版', allocation: 50 }, { id: 'new', name: '新版', allocation: 50 }]], targetMetric: ['string', '转化率'] },
  state: { variants: [], status: 'draft', metrics: {}, history: [], winnerId: '', tick: 0, timer: null }, inited: "SET_variants(GET_initialVariants.map(item => Object.assign({}, item))); const metrics = {}; GET_initialVariants.forEach(item => metrics[item.id] = { visitors: 1000, conversions: item.id === 'control' ? 82 : 91, errors: 8 }); SET_metrics(metrics);", attached: "this.timer = setInterval(() => this.simulateTick(), 2200);", disposed: "clearInterval(this.timer);",
  computed: [['allocationTotal', '', "return GET_variants.reduce((sum, item) => sum + item.allocation, 0);"], ['validAllocation', '', "return GET_allocationTotal === 100;"], ['metricRows', '', "return GET_variants.map(variant => { const metric = GET_metrics[variant.id] || { visitors: 0, conversions: 0, errors: 0 }; const visitors = metric.visitors || 1; return { id: variant.id, name: variant.name, visitors: metric.visitors, conversionRate: (metric.conversions / visitors * 100).toFixed(2), errorRate: (metric.errors / visitors * 100).toFixed(2) }; });"], ['leaderId', '', "const rows = GET_metricRows.slice().sort((a, b) => Number(b.conversionRate) - Number(a.conversionRate)); return rows[0] ? rows[0].id : '';"], ['canStart', '', "return GET_validAllocation && GET_status !== 'running';"]],
  methods: [['updateAllocation', 'id, event', "const value = Math.max(0, Math.min(100, Number(event.target.value) || 0)); SET_variants(GET_variants.map(item => item.id === id ? Object.assign({}, item, { allocation: value }) : item)); EMIT('allocation', GET_variants);"], ['start', '', "if (!GET_canStart) return; this.snapshot('开始实验'); SET_status('running'); EMIT('status', 'running');"], ['pause', '', "if (GET_status !== 'running') return; this.snapshot('暂停实验'); SET_status('paused'); EMIT('status', 'paused');"], ['simulateTick', '', "if (GET_status !== 'running') return; const tick = GET_tick + 1; const metrics = {}; GET_variants.forEach((variant, index) => { const current = GET_metrics[variant.id]; metrics[variant.id] = { visitors: current.visitors + variant.allocation * 2, conversions: current.conversions + Math.round(variant.allocation * (index ? .19 : .16)), errors: current.errors + (tick % (index + 3) === 0 ? 1 : 0) }; }); SET_metrics(metrics); SET_tick(tick);"], ['declareWinner', 'id', "if (GET_status === 'running') return; SET_winnerId(id); SET_status('completed'); this.snapshot('选定胜出版本'); EMIT('winner', id);"], ['snapshot', 'label', "SET_history([{ id: Date.now(), label, status: GET_status, variants: GET_variants.map(item => Object.assign({}, item)) }].concat(GET_history).slice(0, 6));"], ['rollback', 'entry', "SET_variants(entry.variants.map(item => Object.assign({}, item))); SET_status(entry.status); SET_winnerId('');"], ['rowClass', 'row', "return row.id === GET_winnerId ? 'winner' : row.id === GET_leaderId ? 'leader' : '';"], ['statusText', '', "return { draft: '草稿', running: '运行中', paused: '已暂停', completed: '已完成' }[GET_status];"]],
  template: `<section class="experiment-rollout-console"><header><div><p class="muted">{{ targetMetric }} · {{ statusText() }}</p><h2>{{ experimentName }}</h2></div><div class="actions"><button class="primary" @click="start" :disabled="!canStart">开始</button><button @click="pause" :disabled="status !== 'running'">暂停</button></div></header><div class="rollout-grid"><main><section class="allocation-panel"><h3>流量分配 <span :class="validAllocation ? 'valid' : 'invalid'">{{ allocationTotal }}%</span></h3><label v-for="variant in variants" :key="variant.id"><span>{{ variant.name }}</span><input type="range" :value="variant.allocation" @input="updateAllocation(variant.id, $event)"><output>{{ variant.allocation }}%</output></label></section><table><thead><tr><th>版本</th><th>访客</th><th>转化率</th><th>错误率</th><th>决策</th></tr></thead><tbody><tr v-for="row in metricRows" :key="row.id" :class="rowClass(row)"><td>{{ row.name }}</td><td>{{ row.visitors }}</td><td>{{ row.conversionRate }}%</td><td>{{ row.errorRate }}%</td><td><button @click="declareWinner(row.id)" :disabled="status === 'running' || status === 'completed'">设为胜出</button></td></tr></tbody></table></main><aside><h3>实验历史</h3><ol><li v-for="entry in history" :key="entry.id"><div><strong>{{ entry.label }}</strong><small>{{ entry.status }}</small></div><button @click="rollback(entry)">回滚</button></li></ol><p v-if="!history.length" class="empty">尚无快照</p></aside></div></section>`,
  css: `header{display:flex;justify-content:space-between}.rollout-grid{display:grid;grid-template-columns:1fr 200px;gap:14px}.allocation-panel{padding:14px;background:#fdf2f8}.allocation-panel h3{display:flex;justify-content:space-between}.valid{color:#15803d}.invalid{color:#b91c1c}.allocation-panel label{display:grid;grid-template-columns:80px 1fr 45px;gap:8px}table{width:100%;margin-top:12px;border-collapse:collapse}th,td{padding:9px;border:1px solid #e3e5e8}tr.leader{background:#fdf2f8}tr.winner{background:#ecfdf5}aside{padding:12px;background:#f8fafc}aside ol{padding:0;list-style:none}aside li{display:flex;justify-content:space-between;padding:8px 0}`,
  score: complexScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'lifecycle-hooks', 'dynamic-class', 'scoped', 'timer', 'rollback', 'experiment-allocation']
});

// Complex components use deeper, domain-specific workflows.
add({
  name: 'InventoryBatchManager', label: '库存批次管理器', level: 'complex', accent: '#0f766e',
  model: '仓库、SKU 批次、保质期、选中集合与调整记录', workflow: '筛选风险批次、批量调整库存并撤销', structure: '指标栏、批次表、调整侧栏和审计记录', stateChange: '批量数量变更生成可撤销事务', communication: '3 个 props，发出 inventory-change/export', migrationFocus: '表格多状态、批量事务、watch、生命周期和动态库存条',
  props: { title: ['string', '冷链库存控制台'], warehouses: ['array', ['华东仓', '华南仓']], initialBatches: ['array', [{ id: 1, sku: 'FD-101', product: '鲜奶', warehouse: '华东仓', quantity: 38, capacity: 80, expiryDays: 2 }, { id: 2, sku: 'FD-205', product: '酸奶', warehouse: '华东仓', quantity: 64, capacity: 80, expiryDays: 8 }, { id: 3, sku: 'FR-311', product: '果汁', warehouse: '华南仓', quantity: 21, capacity: 60, expiryDays: 14 }, { id: 4, sku: 'FD-402', product: '奶酪', warehouse: '华南仓', quantity: 9, capacity: 40, expiryDays: 1 }]] },
  state: { batches: [], warehouse: 'all', riskOnly: false, selectedIds: [], adjustment: 0, reason: '盘点修正', history: [], lastSynced: '', timer: null },
  inited: "SET_batches(GET_initialBatches.map(item => Object.assign({}, item)));", attached: "this.refreshClock(); this.timer = setInterval(() => this.refreshClock(), 30000);", disposed: "clearInterval(this.timer);", watch: [['warehouse', "SET_selectedIds([]);"]],
  computed: [['visibleBatches', '', "return GET_batches.filter(item => (GET_warehouse === 'all' || item.warehouse === GET_warehouse) && (!GET_riskOnly || item.expiryDays <= 3 || item.quantity <= 10));"], ['summary', '', "return GET_batches.reduce((result, item) => { result.units += item.quantity; if (item.expiryDays <= 3) result.expiring += 1; if (item.quantity <= 10) result.low += 1; return result; }, { units: 0, expiring: 0, low: 0 });"], ['selectedCount', '', "return GET_selectedIds.length;"], ['canApply', '', "return GET_selectedCount > 0 && GET_adjustment !== 0;"]],
  methods: [['refreshClock', '', "SET_lastSynced(new Date().toLocaleTimeString('zh-CN', { hour12: false }));"], ['updateWarehouse', 'event', "SET_warehouse(event.target.value);"], ['toggleRisk', 'event', "SET_riskOnly(event.target.checked);"], ['isSelected', 'id', "return GET_selectedIds.indexOf(id) >= 0;"], ['toggleBatch', 'id', "const list = GET_selectedIds; SET_selectedIds(list.indexOf(id) >= 0 ? list.filter(item => item !== id) : list.concat(id));"], ['selectVisible', '', "SET_selectedIds(GET_visibleBatches.map(item => item.id));"], ['updateAdjustment', 'event', "SET_adjustment(Number(event.target.value) || 0);"], ['updateReason', 'event', "SET_reason(event.target.value);"], ['applyAdjustment', '', "if (!GET_canApply) return; const ids = GET_selectedIds; const before = GET_batches.map(item => Object.assign({}, item)); const next = GET_batches.map(item => ids.indexOf(item.id) >= 0 ? Object.assign({}, item, { quantity: Math.max(0, Math.min(item.capacity, item.quantity + GET_adjustment)) }) : item); SET_batches(next); SET_history([{ id: Date.now(), reason: GET_reason, count: ids.length, delta: GET_adjustment, before }].concat(GET_history).slice(0, 5)); SET_selectedIds([]); SET_adjustment(0); EMIT('inventory-change', next);"], ['undo', '', "const history = GET_history; if (!history.length) return; SET_batches(history[0].before.map(item => Object.assign({}, item))); SET_history(history.slice(1)); EMIT('inventory-change', GET_batches);"], ['exportData', '', "EMIT('export', GET_visibleBatches);"], ['stockStyle', 'batch', "return 'width:' + Math.round(batch.quantity / batch.capacity * 100) + '%';"]],
  template: `<section class="inventory-batch-manager"><header class="page-head"><div><p class="muted">最后同步 {{ lastSynced }}</p><h2>{{ title }}</h2></div><button @click="exportData">导出视图</button></header><div class="metric-strip"><article><span>库存件数</span><strong>{{ summary.units }}</strong></article><article><span>临期批次</span><strong>{{ summary.expiring }}</strong></article><article><span>低库存</span><strong>{{ summary.low }}</strong></article></div><div class="toolbar"><select :value="warehouse" @change="updateWarehouse"><option value="all">全部仓库</option><option v-for="item in warehouses" :key="item" :value="item">{{ item }}</option></select><label><input type="checkbox" :checked="riskOnly" @change="toggleRisk"> 仅看风险</label><button @click="selectVisible">全选结果</button><button @click="undo" :disabled="!history.length">撤销</button></div><div class="inventory-layout"><div><table><thead><tr><th></th><th>批次</th><th>仓库</th><th>库存</th><th>保质期</th></tr></thead><tbody><tr v-for="batch in visibleBatches" :key="batch.id" :class="batchRowClass(batch)"><td><input type="checkbox" :checked="isSelected(batch.id)" @change="toggleBatch(batch.id)"></td><td><strong>{{ batch.product }}</strong><small>{{ batch.sku }}</small></td><td>{{ batch.warehouse }}</td><td><div class="stock-bar"><span :style="stockStyle(batch)"></span></div>{{ batch.quantity }}/{{ batch.capacity }}</td><td>{{ batch.expiryDays }} 天</td></tr></tbody></table><p v-if="!visibleBatches.length" class="empty">没有匹配批次</p></div><aside><h3>批量调整</h3><p>已选 {{ selectedCount }} 批</p><label>数量变化<input type="number" :value="adjustment" @input="updateAdjustment"></label><label>原因<select :value="reason" @change="updateReason"><option>盘点修正</option><option>损耗登记</option><option>入库补录</option></select></label><button class="primary" @click="applyAdjustment" :disabled="!canApply">应用</button><h3>操作历史</h3><ol><li v-for="entry in history" :key="entry.id">{{ entry.reason }}：{{ entry.count }} 批</li></ol></aside></div></section>`,
  css: `.page-head,.metric-strip{display:flex;justify-content:space-between}.metric-strip{margin:12px 0;gap:8px}.metric-strip article{flex:1;padding:12px;background:#edf7f5}.metric-strip strong{display:block;font-size:23px}.inventory-layout{display:grid;grid-template-columns:1fr 200px;gap:14px}table{width:100%;border-collapse:collapse}th,td{padding:9px;border-bottom:1px solid #e0e5e9;text-align:left}td small{display:block}tr.selected{background:#ecfdf5}tr.risk{box-shadow:inset 3px 0 #dc2626}.stock-bar{width:75px;height:6px;background:#e5e7eb}.stock-bar span{display:block;height:100%;background:#0f766e}aside{padding:12px;background:#f7f9fa}aside label{display:grid;gap:5px;margin:8px 0}`,
  score: complexScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'watch', 'props', 'emit', 'lifecycle-hooks', 'dynamic-class', 'dynamic-style', 'scoped', 'batch-operation', 'undo']
});

add({
  name: 'IncidentResponseBoard', label: '故障响应看板', level: 'complex', accent: '#b91c1c',
  model: '事件阶段、响应人、检查项、时间线和严重度', workflow: '认领、推进阶段、执行检查项、记录、升级与关闭', structure: '事件头、阶段轨、处置区和时间线', stateChange: '事件生命周期状态机联动计时与审计', communication: '3 个 props，发出 status-change/resolve/escalate', migrationFocus: '状态机、定时器、检查清单和多事件通信',
  props: { incidentId: ['string', 'INC-2048'], serviceName: ['string', '支付网关'], initialSeverity: ['string', 'P1'] },
  state: { status: 'detected', severity: 'P1', owner: '', elapsed: 0, checklist: [{ id: 1, text: '确认监控告警', done: true }, { id: 2, text: '隔离异常节点', done: false }, { id: 3, text: '通知业务负责人', done: false }], timeline: [{ id: 1, time: '09:20', text: '监控触发错误率告警' }], note: '', timer: null, stages: ['detected', 'triage', 'mitigation', 'resolved'] },
  inited: "SET_severity(GET_initialSeverity);", attached: "this.timer = setInterval(() => SET_elapsed(GET_elapsed + 1), 60000);", disposed: "clearInterval(this.timer);",
  computed: [['stageIndex', '', "return GET_stages.indexOf(GET_status);"], ['completedChecks', '', "return GET_checklist.filter(item => item.done).length;"], ['canResolve', '', "return !!GET_owner && GET_completedChecks === GET_checklist.length;"], ['elapsedLabel', '', "return Math.floor(GET_elapsed / 60) + 'h ' + (GET_elapsed % 60) + 'm';"]],
  methods: [['claim', '', "SET_owner(GET_owner ? '' : '当前值班员'); this.addTimeline(GET_owner ? '事件已认领' : '已取消认领');"], ['advance', '', "const index = GET_stageIndex; if (index >= GET_stages.length - 1) return; const next = GET_stages[index + 1]; SET_status(next); this.addTimeline('推进至' + this.statusText(next)); EMIT('status-change', next);"], ['toggleCheck', 'id', "SET_checklist(GET_checklist.map(item => item.id === id ? Object.assign({}, item, { done: !item.done }) : item));"], ['updateNote', 'event', "SET_note(event.target.value);"], ['addNote', 'event', "event.preventDefault(); const text = GET_note.trim(); if (!text) return; this.addTimeline(text); SET_note('');"], ['escalate', '', "const next = GET_severity === 'P2' ? 'P1' : 'P0'; SET_severity(next); this.addTimeline('严重度升级为 ' + next); EMIT('escalate', next);"], ['resolve', '', "if (!GET_canResolve) return; SET_status('resolved'); this.addTimeline('事件已关闭'); EMIT('resolve', { id: GET_incidentId, elapsed: GET_elapsed });"], ['addTimeline', 'text', "const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }); SET_timeline([{ id: Date.now(), time: now, text }].concat(GET_timeline));"], ['statusText', 'status', "return { detected: '已发现', triage: '排查中', mitigation: '处置中', resolved: '已恢复' }[status];"]],
  template: `<section class="incident-response-board"><header class="incident-head"><div><span :class="'severity ' + severity">{{ severity }}</span><small>{{ incidentId }}</small><h2>{{ serviceName }}异常</h2></div><div><strong>{{ elapsedLabel }}</strong><button @click="escalate" :disabled="status === 'resolved'">升级</button></div></header><div class="stage-track"><div v-for="stage, index in stages" :key="stage" :class="{ active: index === stageIndex, done: index < stageIndex }"><i></i><span>{{ statusText(stage) }}</span></div></div><div class="response-grid"><main><div class="owner-card"><div><span>事件负责人</span><strong>{{ owner || '尚未认领' }}</strong></div><button @click="claim">{{ owner ? '释放' : '认领' }}</button></div><section class="check-panel"><h3>处置检查项 {{ completedChecks }}/{{ checklist.length }}</h3><label v-for="item in checklist" :key="item.id" :class="item.done ? 'done' : ''"><input type="checkbox" :checked="item.done" @change="toggleCheck(item.id)"> {{ item.text }}</label></section><div class="actions"><button @click="advance">推进阶段</button><button class="primary" @click="resolve" :disabled="!canResolve">关闭事件</button></div></main><aside><h3>响应时间线</h3><form @submit="addNote"><textarea :value="note" @input="updateNote" placeholder="记录处置进展"></textarea><button type="submit">添加</button></form><ol><li v-for="entry in timeline" :key="entry.id"><time>{{ entry.time }}</time><span>{{ entry.text }}</span></li></ol></aside></div></section>`,
  css: `.incident-head{display:flex;justify-content:space-between}.severity{padding:4px 7px;background:#fee2e2;color:#991b1b}.severity.P0{background:#991b1b;color:#fff}.stage-track{display:grid;grid-template-columns:repeat(4,1fr);margin:18px 0}.stage-track div{display:grid;gap:5px;text-align:center}.stage-track i{height:6px;background:#d9dee3}.stage-track .active i,.stage-track .done i{background:#b91c1c}.response-grid{display:grid;grid-template-columns:1fr 280px;gap:14px}.owner-card{display:flex;justify-content:space-between;padding:14px;background:#f8fafc}.check-panel{margin:12px 0;padding:14px;border:1px solid #e2e5e9}.check-panel label{display:block;padding:7px}.check-panel label.done{text-decoration:line-through;color:#77818b}aside{padding:12px;background:#f8fafc}aside textarea{width:100%}aside ol{padding:0;list-style:none}aside li{display:grid;grid-template-columns:48px 1fr;gap:7px;padding:8px 0}`,
  score: complexScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'lifecycle-hooks', 'dynamic-class', 'scoped', 'state-machine', 'timer', 'audit-log']
});

add({
  name: 'GradebookMatrix', label: '课程成绩矩阵', level: 'complex', accent: '#1d4ed8',
  model: '学生、作业列、单元格成绩、权重和排序', workflow: '编辑成绩、调权重、排序、筛选并发布', structure: '指标栏、可编辑矩阵和学生详情', stateChange: '单元格修改实时重算加权总分及排名', communication: '3 个 props，发出 grade-change/publish', migrationFocus: '二维矩阵、动态字段、watch 和派生排名',
  props: { courseTitle: ['string', '前端工程实践'], assignments: ['array', [{ id: 'lab', label: '实验', weight: 40 }, { id: 'exam', label: '考试', weight: 60 }]], initialStudents: ['array', [{ id: 1, name: '林晓', grades: { lab: 88, exam: 92 } }, { id: 2, name: '周宁', grades: { lab: 74, exam: 81 } }, { id: 3, name: '陈雨', grades: { lab: 95, exam: 86 } }, { id: 4, name: '孟然', grades: { lab: 62, exam: 55 } }]] },
  state: { students: [], weights: {}, sortMode: 'name', failingOnly: false, selectedId: null, published: false, changeCount: 0, lastEdited: '' },
  inited: "SET_students(GET_initialStudents.map(item => ({ id: item.id, name: item.name, grades: Object.assign({}, item.grades) }))); const weights = {}; GET_assignments.forEach(item => { weights[item.id] = item.weight; }); SET_weights(weights);", watch: [['changeCount', "SET_published(false);"]],
  computed: [['rows', '', "const weights = GET_weights; const totalWeight = Object.keys(weights).reduce((sum, key) => sum + weights[key], 0) || 1; const rows = GET_students.map(student => { const total = GET_assignments.reduce((sum, item) => sum + (student.grades[item.id] || 0) * (weights[item.id] || 0), 0) / totalWeight; return Object.assign({}, student, { total: Math.round(total), failing: total < 60 }); }); const filtered = GET_failingOnly ? rows.filter(row => row.failing) : rows; return filtered.slice().sort((a, b) => GET_sortMode === 'score' ? b.total - a.total : a.name.localeCompare(b.name, 'zh-CN'));"], ['classAverage', '', "const rows = GET_rows; return rows.length ? Math.round(rows.reduce((sum, row) => sum + row.total, 0) / rows.length) : 0;"], ['passRate', '', "const rows = GET_rows; return rows.length ? Math.round(rows.filter(row => !row.failing).length / rows.length * 100) : 0;"], ['selectedStudent', '', "return GET_students.find(item => item.id === GET_selectedId) || null;"]],
  methods: [['updateSort', 'event', "SET_sortMode(event.target.value);"], ['toggleFailing', 'event', "SET_failingOnly(event.target.checked);"], ['selectStudent', 'id', "SET_selectedId(id);"], ['closeDetail', '', "SET_selectedId(null);"], ['updateGrade', 'studentId, assignmentId, event', "const value = Math.max(0, Math.min(100, Number(event.target.value) || 0)); SET_students(GET_students.map(student => student.id === studentId ? Object.assign({}, student, { grades: Object.assign({}, student.grades, { [assignmentId]: value }) }) : student)); SET_changeCount(GET_changeCount + 1); SET_lastEdited(studentId + ':' + assignmentId); EMIT('grade-change', { studentId, assignmentId, value });"], ['updateWeight', 'id, event', "SET_weights(Object.assign({}, GET_weights, { [id]: Number(event.target.value) || 0 })); SET_changeCount(GET_changeCount + 1);"], ['resetWeights', '', "const next = {}; GET_assignments.forEach(item => { next[item.id] = item.weight; }); SET_weights(next); SET_changeCount(GET_changeCount + 1);"], ['publish', '', "SET_published(true); EMIT('publish', GET_rows.map(row => ({ id: row.id, total: row.total })));"], ['gradeClass', 'value', "return value < 60 ? 'low' : value >= 90 ? 'high' : '';"], ['letterGrade', 'value', "return value >= 90 ? 'A' : value >= 80 ? 'B' : value >= 70 ? 'C' : value >= 60 ? 'D' : 'F';"]],
  template: `<section class="gradebook-matrix"><header><div><p class="muted">{{ published ? '成绩已发布' : changeCount + ' 项未发布变更' }}</p><h2>{{ courseTitle }}</h2></div><button class="primary" @click="publish">发布成绩</button></header><div class="metric-strip"><article><span>班级均分</span><strong>{{ classAverage }}</strong></article><article><span>通过率</span><strong>{{ passRate }}%</strong></article><article><span>学生数</span><strong>{{ students.length }}</strong></article></div><div class="toolbar"><select :value="sortMode" @change="updateSort"><option value="name">按姓名</option><option value="score">按总分</option></select><label><input type="checkbox" :checked="failingOnly" @change="toggleFailing"> 仅看不及格</label><button @click="resetWeights">恢复权重</button></div><div class="gradebook-layout"><table><thead><tr><th>学生</th><th v-for="assignment in assignments" :key="assignment.id">{{ assignment.label }}<input type="number" :value="weights[assignment.id]" @input="updateWeight(assignment.id, $event)">%</th><th>总分</th></tr></thead><tbody><tr v-for="student in rows" :key="student.id" :class="student.failing ? 'failing' : ''"><th><button @click="selectStudent(student.id)">{{ student.name }}</button></th><td v-for="assignment in assignments" :key="assignment.id"><input type="number" :class="gradeClass(student.grades[assignment.id])" :value="student.grades[assignment.id]" @input="updateGrade(student.id, assignment.id, $event)"></td><td><strong>{{ student.total }}</strong><small>{{ letterGrade(student.total) }}</small></td></tr></tbody></table><aside v-if="selectedStudent"><button @click="closeDetail">×</button><h3>{{ selectedStudent.name }}</h3><dl><div v-for="assignment in assignments" :key="assignment.id"><dt>{{ assignment.label }}</dt><dd>{{ selectedStudent.grades[assignment.id] }}</dd></div></dl><p>最近编辑：{{ lastEdited || '无' }}</p></aside></div></section>`,
  css: `header,.metric-strip{display:flex;justify-content:space-between}.metric-strip{gap:8px;margin:12px 0}.metric-strip article{flex:1;padding:12px;background:#eff6ff}.metric-strip strong{display:block;font-size:24px}.gradebook-layout{display:grid;grid-template-columns:1fr auto;gap:12px;overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:8px;border:1px solid #dce2e8;text-align:center}thead input{width:54px}tbody input{width:60px}.low{border-color:#dc2626!important}.high{border-color:#15803d!important}tr.failing{background:#fff7ed}td small{display:block}aside{width:180px;padding:12px;background:#f8fafc}dl div{display:flex;justify-content:space-between}`,
  score: complexScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'watch', 'props', 'emit', 'dynamic-class', 'scoped', 'matrix-editing', 'ranking']
});

add({
  name: 'PollResults', label: '投票结果面板', level: 'medium', accent: '#7c3aed',
  model: '选项票数、当前投票与结果可见性', workflow: '单选投票、查看结果并重置', structure: '问题、选项列表和比例条', stateChange: '投票转移时同步增减票数', communication: '2 个 props，发出 vote', migrationFocus: '派生百分比列表、动态宽度和事件输出',
  props: { question: ['string', '下次分享主题？'], initialOptions: ['array', [{ id: 1, label: '性能优化', votes: 8 }, { id: 2, label: '测试策略', votes: 5 }, { id: 3, label: '组件设计', votes: 7 }]] },
  state: { options: [], selectedId: null, showResults: false },
  inited: "SET_options(GET_initialOptions.map(item => Object.assign({}, item)));",
  computed: [['totalVotes', '', "return GET_options.reduce((sum, item) => sum + item.votes, 0);"], ['results', '', "const total = GET_totalVotes || 1; return GET_options.map(item => Object.assign({}, item, { percent: Math.round(item.votes / total * 100), bar: 'width:' + (item.votes / total * 100) + '%' }));"]],
  methods: [
    ['vote', 'id', "const old = GET_selectedId; const next = GET_options.map(item => Object.assign({}, item, { votes: item.votes + (item.id === id ? 1 : 0) - (item.id === old ? 1 : 0) })); SET_options(next); SET_selectedId(old === id ? null : id); EMIT('vote', id);"],
    ['toggleResults', '', "SET_showResults(!GET_showResults);"], ['reset', '', "SET_options(GET_initialOptions.map(item => Object.assign({}, item))); SET_selectedId(null);"]
  ],
  template: `<section class="poll-results"><header><h2>{{ question }}</h2><button @click="toggleResults">{{ showResults ? '隐藏结果' : '查看结果' }}</button></header><div class="poll-list"><article v-for="item in results" :key="item.id" :class="item.id === selectedId ? 'chosen' : ''"><button @click="vote(item.id)">{{ item.label }}</button><div v-if="showResults" class="result-line"><span :style="item.bar"></span><strong>{{ item.percent }}%</strong></div></article></div><footer>{{ totalVotes }} 票 <button @click="reset">重置</button></footer></section>`,
  css: `header,footer{display:flex;justify-content:space-between;align-items:center}.poll-list article{padding:9px;border-bottom:1px solid #e4e8ec}.poll-list article.chosen{background:#f5f3ff}.result-line{display:grid;grid-template-columns:1fr 44px;gap:8px;align-items:center;margin-top:6px;background:#eee}.result-line span{height:7px;background:#7c3aed}`,
  score: mediumScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'dynamic-style', 'scoped']
});

add({
  name: 'RecipeScaler', label: '配方缩放器', level: 'medium', accent: '#15803d',
  model: '基准份数、目标份数和原料数组', workflow: '调整份数并切换克/千克显示', structure: '份数控制、原料表和总重量', stateChange: '缩放因子驱动所有原料数量', communication: '2 个 props，无事件输出', migrationFocus: '数组映射 computed 与格式化方法',
  props: { baseServings: ['number', 4], ingredients: ['array', [{ name: '面粉', grams: 320 }, { name: '牛奶', grams: 240 }, { name: '黄油', grams: 60 }]] },
  state: { servings: 4, unit: 'g' }, inited: "SET_servings(GET_baseServings);",
  computed: [['scaledIngredients', '', "const factor = GET_servings / GET_baseServings; return GET_ingredients.map(item => ({ name: item.name, amount: item.grams * factor }));"], ['totalWeight', '', "return GET_scaledIngredients.reduce((sum, item) => sum + item.amount, 0);"]],
  methods: [['changeServings', 'delta', "SET_servings(Math.max(1, GET_servings + delta));"], ['toggleUnit', '', "SET_unit(GET_unit === 'g' ? 'kg' : 'g');"], ['formatAmount', 'value', "return GET_unit === 'g' ? Math.round(value) + ' g' : (value / 1000).toFixed(2) + ' kg';"]],
  template: `<section class="recipe-scaler"><header><h2>烘焙配方</h2><div><button @click="changeServings(-1)">−</button><strong>{{ servings }} 份</strong><button @click="changeServings(1)">＋</button></div></header><table><tbody><tr v-for="item in scaledIngredients" :key="item.name"><td>{{ item.name }}</td><td>{{ formatAmount(item.amount) }}</td></tr></tbody></table><footer><strong>总重量 {{ formatAmount(totalWeight) }}</strong><button @click="toggleUnit">切换单位</button></footer></section>`,
  css: `header,footer{display:flex;justify-content:space-between;align-items:center}header div{display:flex;gap:8px;align-items:center}table{width:100%;margin:12px 0;border-collapse:collapse}td{padding:9px;border-bottom:1px solid #dce3df}td:last-child{text-align:right}`,
  score: mediumScore({ communication: 1 }), features: ['v-for', 'v-on', 'computed', 'props', 'scoped']
});

add({
  name: 'BatchRenamer', label: '批量重命名器', level: 'medium', accent: '#c2410c',
  model: '文件名列表与重命名规则', workflow: '配置前缀/起始序号、预览并应用', structure: '规则表单、双列预览与冲突提示', stateChange: '规则字段驱动预览，应用后替换文件集', communication: '1 个 prop，发出 apply', migrationFocus: '表单输入、预览 computed、条件告警',
  props: { files: ['array', ['cover.png', 'hero.png', 'thumb.png']] }, state: { currentFiles: [], prefix: 'asset', startAt: 1, previewVisible: true },
  inited: "SET_currentFiles(GET_files.slice());",
  computed: [['previews', '', "return GET_currentFiles.map((oldName, index) => { const dot = oldName.lastIndexOf('.'); const ext = dot >= 0 ? oldName.slice(dot) : ''; return { oldName, newName: GET_prefix + '-' + (GET_startAt + index) + ext }; });"], ['hasDuplicates', '', "const names = GET_previews.map(item => item.newName); return new Set(names).size !== names.length;"]],
  methods: [['updatePrefix', 'event', "SET_prefix(event.target.value);"], ['updateStart', 'event', "SET_startAt(Number(event.target.value) || 1);"], ['togglePreview', '', "SET_previewVisible(!GET_previewVisible);"], ['apply', '', "if (GET_hasDuplicates || !GET_prefix.trim()) return; const next = GET_previews.map(item => item.newName); SET_currentFiles(next); EMIT('apply', next.slice());"]],
  template: `<section class="batch-renamer"><h2>批量重命名</h2><div class="rename-rules"><label>前缀<input :value="prefix" @input="updatePrefix"></label><label>起始序号<input type="number" min="1" :value="startAt" @input="updateStart"></label><button @click="togglePreview">{{ previewVisible ? '隐藏预览' : '显示预览' }}</button></div><p v-if="hasDuplicates" class="warning">新文件名存在冲突</p><table v-if="previewVisible"><thead><tr><th>原文件名</th><th>新文件名</th></tr></thead><tbody><tr v-for="item in previews" :key="item.oldName"><td>{{ item.oldName }}</td><td>{{ item.newName }}</td></tr></tbody></table><button class="primary" @click="apply" :disabled="hasDuplicates || !prefix">应用规则</button></section>`,
  css: `.rename-rules{display:grid;grid-template-columns:1fr 150px auto;gap:10px;align-items:end}.rename-rules label{display:grid;gap:5px}table{width:100%;margin:14px 0;border-collapse:collapse}th,td{padding:8px;border:1px solid #e0e4e8;text-align:left}.warning{color:#b42318}`,
  score: mediumScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'scoped']
});

add({
  name: 'ShippingEstimator', label: '运费估算表', level: 'medium', accent: '#0369a1',
  model: '目的地区、重量、加急选项和估算结果', workflow: '填写表单、校验后计算并重置', structure: '网格表单、错误区和报价结果', stateChange: '提交触发校验与分段计价', communication: '1 个 prop，发出 estimate', migrationFocus: '表单提交、select/checkbox 与结构化事件',
  props: { regions: ['array', [{ code: 'near', name: '同城', base: 8 }, { code: 'domestic', name: '国内', base: 16 }, { code: 'remote', name: '偏远', base: 28 }]] },
  state: { regionCode: 'near', weight: 1, express: false, result: null, error: '' },
  computed: [['selectedRegion', '', "return GET_regions.find(item => item.code === GET_regionCode) || GET_regions[0];"], ['weightBand', '', "return GET_weight <= 1 ? '首重' : '续重 ' + Math.ceil(GET_weight - 1) + ' kg';"]],
  methods: [
    ['updateRegion', 'event', "SET_regionCode(event.target.value);"], ['updateWeight', 'event', "SET_weight(Number(event.target.value) || 0);"], ['toggleExpress', 'event', "SET_express(event.target.checked);"],
    ['estimate', 'event', "event.preventDefault(); if (GET_weight <= 0) { SET_error('重量必须大于 0'); SET_result(null); return; } const region = GET_selectedRegion; const fee = (region.base + Math.max(0, Math.ceil(GET_weight - 1)) * 5) * (GET_express ? 1.5 : 1); const result = { fee: fee.toFixed(2), days: GET_express ? 1 : region.code === 'remote' ? 5 : 3 }; SET_error(''); SET_result(result); EMIT('estimate', result);"],
    ['reset', '', "SET_weight(1); SET_express(false); SET_result(null); SET_error('');"]
  ],
  template: `<form class="shipping-estimator" @submit="estimate"><h2>配送费用估算</h2><div class="shipping-grid"><label>目的地区<select :value="regionCode" @change="updateRegion"><option v-for="region in regions" :key="region.code" :value="region.code">{{ region.name }}</option></select></label><label>重量（kg）<input type="number" min="0" :value="weight" @input="updateWeight"></label><label class="check-line"><input type="checkbox" :checked="express" @change="toggleExpress"> 加急配送</label></div><p class="muted">{{ weightBand }}</p><p v-if="error" class="error">{{ error }}</p><div v-if="result" class="quote"><strong>¥{{ result.fee }}</strong><span>预计 {{ result.days }} 天送达</span></div><div class="actions"><button type="button" @click="reset">重置</button><button class="primary" type="submit">计算运费</button></div></form>`,
  css: `.shipping-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.shipping-grid label{display:grid;gap:5px}.check-line{display:flex!important;align-items:center}.quote{display:flex;justify-content:space-between;padding:16px;background:#e0f2fe}.quote strong{font-size:24px}.error{color:#b42318}`,
  score: mediumScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'scoped']
});

add({
  name: 'AttendanceRoster', label: '出勤点名册', level: 'medium', accent: '#0f766e',
  model: '学生列表及 present/late/absent 状态', workflow: '筛选、逐人标记和全员签到', structure: '汇总标签、筛选器和人员行列表', stateChange: '状态循环并实时聚合计数', communication: '1 个 prop，发出 change', migrationFocus: '状态聚合、列表更新与动态 class',
  props: { students: ['array', [{ id: 1, name: '林晓', status: 'present' }, { id: 2, name: '周宁', status: 'late' }, { id: 3, name: '陈雨', status: 'absent' }, { id: 4, name: '孟然', status: 'present' }]] },
  state: { records: [], filter: 'all' }, inited: "SET_records(GET_students.map(item => Object.assign({}, item)));",
  computed: [['counts', '', "return GET_records.reduce((result, item) => { result[item.status] += 1; return result; }, { present: 0, late: 0, absent: 0 });"], ['visibleRecords', '', "return GET_filter === 'all' ? GET_records : GET_records.filter(item => item.status === GET_filter);"]],
  methods: [['updateFilter', 'event', "SET_filter(event.target.value);"], ['cycleStatus', 'id', "const order = ['present', 'late', 'absent']; const next = GET_records.map(item => item.id === id ? Object.assign({}, item, { status: order[(order.indexOf(item.status) + 1) % order.length] }) : item); SET_records(next); this.notify();"], ['markAllPresent', '', "SET_records(GET_records.map(item => Object.assign({}, item, { status: 'present' }))); this.notify();"], ['notify', '', "EMIT('change', GET_records.map(item => Object.assign({}, item)));"], ['statusText', 'status', "return { present: '出勤', late: '迟到', absent: '缺席' }[status];"]],
  template: `<section class="attendance-roster"><header><h2>课程点名</h2><div class="summary"><span>出勤 {{ counts.present }}</span><span>迟到 {{ counts.late }}</span><span>缺席 {{ counts.absent }}</span></div></header><div class="toolbar"><select :value="filter" @change="updateFilter"><option value="all">全部</option><option value="present">出勤</option><option value="late">迟到</option><option value="absent">缺席</option></select><button @click="markAllPresent">全员签到</button></div><ul><li v-for="student in visibleRecords" :key="student.id" :class="student.status"><strong>{{ student.name }}</strong><button @click="cycleStatus(student.id)">{{ statusText(student.status) }}</button></li></ul><p v-if="!visibleRecords.length" class="empty">当前筛选无学生</p></section>`,
  css: `header{display:flex;justify-content:space-between}.summary span{padding:5px 8px;background:#f0fdfa}.toolbar{margin:12px 0}ul{padding:0;list-style:none}li{display:flex;justify-content:space-between;padding:10px;border-bottom:1px solid #e2e8e7}li.late{border-left:4px solid #d97706}li.absent{border-left:4px solid #dc2626}`,
  score: mediumScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'scoped']
});

add({
  name: 'PlaybackQueue', label: '播放队列', level: 'medium', accent: '#be185d',
  model: '有序曲目、当前曲目和循环模式', workflow: '播放、上移、删除并切换循环', structure: '当前播放区、队列列表和工具栏', stateChange: '当前项与队列顺序联动', communication: '1 个 prop，发出 play/change', migrationFocus: '有序列表重排、条件按钮与多事件输出',
  props: { tracks: ['array', [{ id: 1, title: '晨间序曲', duration: 185 }, { id: 2, title: '城市漫步', duration: 214 }, { id: 3, title: '夜航', duration: 197 }]] },
  state: { queue: [], currentId: null, loop: false }, inited: "SET_queue(GET_tracks.map(item => Object.assign({}, item)));",
  computed: [['currentTrack', '', "return GET_queue.find(item => item.id === GET_currentId) || null;"], ['totalDuration', '', "return GET_queue.reduce((sum, item) => sum + item.duration, 0);"]],
  methods: [['play', 'id', "SET_currentId(id); EMIT('play', id);"], ['moveUp', 'index', "if (index < 1) return; const list = GET_queue.slice(); const item = list.splice(index, 1)[0]; list.splice(index - 1, 0, item); SET_queue(list); EMIT('change', list.slice());"], ['remove', 'id', "const list = GET_queue.filter(item => item.id !== id); SET_queue(list); if (GET_currentId === id) SET_currentId(null); EMIT('change', list.slice());"], ['toggleLoop', '', "SET_loop(!GET_loop);"], ['formatTime', 'seconds', "const minutes = Math.floor(seconds / 60); return minutes + ':' + String(seconds % 60).padStart(2, '0');"]],
  template: `<section class="playback-queue"><header><div><p class="muted">正在播放</p><h2>{{ currentTrack ? currentTrack.title : '尚未选择' }}</h2></div><button :class="loop ? 'active' : ''" @click="toggleLoop">循环 {{ loop ? '开' : '关' }}</button></header><ol><li v-for="track, index in queue" :key="track.id" :class="track.id === currentId ? 'playing' : ''"><button class="track-title" @click="play(track.id)">{{ track.title }}</button><span>{{ formatTime(track.duration) }}</span><button @click="moveUp(index)" :disabled="index === 0">↑</button><button @click="remove(track.id)">移除</button></li></ol><footer>总时长 {{ formatTime(totalDuration) }}</footer></section>`,
  css: `header{display:flex;justify-content:space-between}header button.active{background:#fce7f3;border-color:#be185d}ol{padding-left:24px}li{display:grid;grid-template-columns:1fr 55px 38px auto;gap:7px;padding:8px}li.playing{background:#fdf2f8}.track-title{text-align:left;border:0}`,
  score: mediumScore(), features: ['v-for', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'scoped']
});

add({
  name: 'SurveyBranchForm', label: '分支问卷', level: 'medium', accent: '#6d28d9',
  model: '角色选择、工具多选、补充说明与提交态', workflow: '角色驱动后续问题，填写后提交/重来', structure: '分步骤条件表单与结果摘要', stateChange: '首题选择决定第二段问题内容', communication: '2 个 props，发出 submit', migrationFocus: '分支条件、复选集合和表单提交',
  props: { title: ['string', '开发体验调研'], tools: ['array', ['编辑器', '调试器', '终端']] }, state: { role: '', selectedTools: [], comment: '', submitted: false, error: '' },
  computed: [['branchPrompt', '', "return GET_role === 'developer' ? '日常使用哪些工具？' : GET_role === 'manager' ? '最关注哪类协作信息？' : '';"], ['summary', '', "return GET_role + ' / ' + (GET_selectedTools.length ? GET_selectedTools.join('、') : '未选择工具');"]],
  methods: [['selectRole', 'role', "SET_role(role); SET_selectedTools([]);"], ['toggleTool', 'tool', "const list = GET_selectedTools; SET_selectedTools(list.indexOf(tool) >= 0 ? list.filter(item => item !== tool) : list.concat(tool));"], ['updateComment', 'event', "SET_comment(event.target.value);"], ['submit', 'event', "event.preventDefault(); if (!GET_role) { SET_error('请选择角色'); return; } SET_error(''); SET_submitted(true); EMIT('submit', { role: GET_role, tools: GET_selectedTools.slice(), comment: GET_comment });"], ['restart', '', "SET_role(''); SET_selectedTools([]); SET_comment(''); SET_submitted(false);"]],
  template: `<form class="survey-branch-form" @submit="submit"><h2>{{ title }}</h2><div v-if="!submitted"><fieldset><legend>你的角色</legend><button type="button" :class="role === 'developer' ? 'selected' : ''" @click="selectRole('developer')">开发者</button><button type="button" :class="role === 'manager' ? 'selected' : ''" @click="selectRole('manager')">管理者</button></fieldset><fieldset v-if="role"><legend>{{ branchPrompt }}</legend><label v-for="tool in tools" :key="tool"><input type="checkbox" :checked="selectedTools.indexOf(tool) >= 0" @change="toggleTool(tool)"> {{ tool }}</label></fieldset><textarea :value="comment" @input="updateComment" placeholder="其他建议"></textarea><p v-if="error" class="error">{{ error }}</p><button class="primary" type="submit">提交问卷</button></div><div v-else class="survey-result"><strong>提交成功</strong><p>{{ summary }}</p><button type="button" @click="restart">重新填写</button></div></form>`,
  css: `fieldset{margin:12px 0;padding:12px;border:1px solid #ddd6fe}fieldset label{margin-right:12px}fieldset button.selected{background:#ede9fe;border-color:#6d28d9}textarea{width:100%;min-height:80px}.error{color:#b42318}.survey-result{text-align:center;padding:28px;background:#f5f3ff}`,
  score: mediumScore(), features: ['v-for', 'v-if', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'scoped']
});

add({
  name: 'SeatBookingMap', label: '座位预订图', level: 'medium', accent: '#047857',
  model: '二维座位状态与当前选择集合', workflow: '按座位切换选择、清空并确认', structure: '图例、嵌套座位网格和结算栏', stateChange: '仅可用座位在 available/selected 间切换', communication: '2 个 props，发出 confirm', migrationFocus: '嵌套循环、动态 class、数组选中判断',
  props: { rowLabels: ['array', ['A', 'B', 'C']], seatsPerRow: ['number', 5] }, state: { rows: [], selectedIds: [] },
  inited: "const rows = GET_rowLabels.map((label, rowIndex) => ({ label, seats: Array.from({ length: GET_seatsPerRow }, (_, index) => ({ id: label + (index + 1), reserved: (rowIndex + index) % 4 === 0 })) })); SET_rows(rows);",
  computed: [['selectedCount', '', "return GET_selectedIds.length;"], ['availableCount', '', "return GET_rows.reduce((sum, row) => sum + row.seats.filter(seat => !seat.reserved).length, 0);"]],
  methods: [['seatClass', 'seat', "if (seat.reserved) return 'reserved'; return GET_selectedIds.indexOf(seat.id) >= 0 ? 'selected' : 'available';"], ['toggleSeat', 'seat', "if (seat.reserved) return; const list = GET_selectedIds; SET_selectedIds(list.indexOf(seat.id) >= 0 ? list.filter(id => id !== seat.id) : list.concat(seat.id));"], ['clearSelection', '', "SET_selectedIds([]);"], ['confirm', '', "if (!GET_selectedIds.length) return; EMIT('confirm', GET_selectedIds.slice());"]],
  template: `<section class="seat-booking-map"><header><h2>小剧场选座</h2><div class="legend"><span>可选 {{ availableCount }}</span><span>已选 {{ selectedCount }}</span></div></header><div class="screen">银幕</div><div class="seat-rows"><div v-for="row in rows" :key="row.label" class="seat-row"><strong>{{ row.label }}</strong><button v-for="seat in row.seats" :key="seat.id" :class="seatClass(seat)" @click="toggleSeat(seat)" :disabled="seat.reserved">{{ seat.id }}</button></div></div><footer><button @click="clearSelection">清空</button><button class="primary" @click="confirm" :disabled="!selectedCount">确认 {{ selectedCount }} 个座位</button></footer></section>`,
  css: `header,footer{display:flex;justify-content:space-between}.legend{display:flex;gap:12px}.screen{margin:14px 50px 22px;padding:7px;background:#dfe7e3;text-align:center}.seat-row{display:grid;grid-template-columns:28px repeat(5,1fr);gap:8px;margin:8px 0}.seat-row button.reserved{background:#e5e7eb}.seat-row button.selected{background:#047857;color:#fff}`,
  score: mediumScore({ template: 3 }), features: ['v-for', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'scoped']
});

add({
  name: 'BreadcrumbNavigator', label: '路径导航编辑器', level: 'medium', accent: '#1d4ed8',
  model: '有序路径段与新增草稿', workflow: '跳转上级、追加子级、删除末级和重置', structure: '面包屑导航、编辑表单与当前位置', stateChange: '数组截断或追加改变当前位置', communication: '1 个 prop，发出 navigate/change', migrationFocus: '索引截断、条件操作和多事件输出',
  props: { initialPath: ['array', ['项目', '文档', '设计稿']] }, state: { pathItems: [], draft: '' }, inited: "SET_pathItems(GET_initialPath.slice());",
  computed: [['current', '', "return GET_pathItems.length ? GET_pathItems[GET_pathItems.length - 1] : '根目录';"], ['depth', '', "return GET_pathItems.length;"]],
  methods: [['updateDraft', 'event', "SET_draft(event.target.value);"], ['navigate', 'index', "const next = GET_pathItems.slice(0, index + 1); SET_pathItems(next); EMIT('navigate', next.slice());"], ['addLevel', 'event', "event.preventDefault(); const value = GET_draft.trim(); if (!value) return; const next = GET_pathItems.concat(value); SET_pathItems(next); SET_draft(''); EMIT('change', next.slice());"], ['removeLast', '', "if (!GET_pathItems.length) return; const next = GET_pathItems.slice(0, -1); SET_pathItems(next); EMIT('change', next.slice());"], ['reset', '', "SET_pathItems(GET_initialPath.slice()); SET_draft('');"]],
  template: `<section class="breadcrumb-navigator"><h2>目录定位</h2><nav><button @click="navigate(-1)">根目录</button><span v-for="item, index in pathItems" :key="index"><b>/</b><button :class="index === pathItems.length - 1 ? 'current' : ''" @click="navigate(index)">{{ item }}</button></span></nav><div class="location-card"><span class="muted">当前位置 · 深度 {{ depth }}</span><strong>{{ current }}</strong></div><form @submit="addLevel"><input :value="draft" @input="updateDraft" placeholder="新建子目录"><button class="primary" type="submit">进入新层级</button></form><div class="actions"><button @click="removeLast" :disabled="!pathItems.length">返回上级</button><button @click="reset">恢复路径</button></div></section>`,
  css: `nav{display:flex;align-items:center;gap:4px;flex-wrap:wrap}nav span{display:flex;align-items:center;gap:4px}nav button{border:0;padding:4px}nav button.current{color:#1d4ed8;font-weight:700}.location-card{display:grid;padding:18px;margin:14px 0;background:#eff6ff}.location-card strong{font-size:24px}form{display:grid;grid-template-columns:1fr auto;gap:8px}`,
  score: mediumScore(), features: ['v-for', 'v-on', 'v-bind', 'computed', 'props', 'emit', 'dynamic-class', 'scoped']
});

['DocumentApprovalFlow', 'TripItineraryPlanner', 'SchemaMappingWorkbench', 'ExperimentRolloutConsole', 'IncidentResponseBoard', 'GradebookMatrix']
  .forEach(name => { specs.find(spec => spec.name === name).score.styling = 2; });
const levelOrder = { simple: 0, medium: 1, complex: 2 };
specs.sort((left, right) => levelOrder[left.level] - levelOrder[right.level]);

generate();
