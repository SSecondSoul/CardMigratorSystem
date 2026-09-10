function workflowDiagram() {
  return {
    props: {
      title: ['string', '订单履约工作流'],
      initialNodes: ['array', [
        { id: 1, label: '接收订单', type: 'trigger', x: 8, y: 18, enabled: true },
        { id: 2, label: '库存校验', type: 'condition', x: 38, y: 48, enabled: true },
        { id: 3, label: '创建运单', type: 'action', x: 70, y: 20, enabled: true }
      ]],
      initialEdges: ['array', [{ from: 1, to: 2 }, { from: 2, to: 3 }]],
      nodeTypes: ['array', ['trigger', 'condition', 'action']],
      readonly: ['bool', false]
    },
    state: { nodes: [], edges: [], selectedId: null, connectFrom: null, undoStack: [], validationErrors: [], runLog: [], nextId: 10 },
    inited: "this.setValue('nodes', this.initialNodes.map(item => Object.assign({}, item))); this.setValue('edges', this.initialEdges.map(item => Object.assign({}, item))); this.validateGraph();",
    computed: [
      ['selectedNode', "return this.nodes.find(item => item.id === this.selectedId) || null;"],
      ['enabledNodes', "return this.nodes.filter(item => item.enabled);"],
      ['canRun', "return this.validationErrors.length === 0 && this.nodes.length > 1;"],
      ['edgeSummary', "return this.edges.map(edge => edge.from + '→' + edge.to).join('，');"]
    ],
    methods: [
      ['snapshot', '', "this.setValue('undoStack', [{ nodes: this.nodes.map(item => Object.assign({}, item)), edges: this.edges.map(item => Object.assign({}, item)) }].concat(this.undoStack).slice(0, 8));"],
      ['selectNode', 'id', "this.setValue('selectedId', id);"],
      ['addNode', 'type', "if (this.readonly) return; this.snapshot(); const id = this.nextId; this.setValue('nodes', this.nodes.concat({ id, label: '新' + type, type, x: 12 + id * 5 % 70, y: 15 + id * 9 % 60, enabled: true })); this.setValue('nextId', id + 1); this.validateGraph();"],
      ['nudgeNode', 'id, dx, dy', "if (this.readonly) return; this.snapshot(); this.setValue('nodes', this.nodes.map(node => node.id === id ? Object.assign({}, node, { x: Math.max(0, Math.min(86, node.x + dx)), y: Math.max(0, Math.min(75, node.y + dy)) }) : node)); this.emitEvent('graph-change', { nodes: this.nodes, edges: this.edges });"],
      ['beginConnect', 'id', "if (this.connectFrom === null) { this.setValue('connectFrom', id); return; } if (this.connectFrom !== id && !this.edges.some(edge => edge.from === this.connectFrom && edge.to === id)) { this.snapshot(); this.setValue('edges', this.edges.concat({ from: this.connectFrom, to: id })); } this.setValue('connectFrom', null); this.validateGraph();"],
      ['toggleNode', 'id', "this.snapshot(); this.setValue('nodes', this.nodes.map(node => node.id === id ? Object.assign({}, node, { enabled: !node.enabled }) : node)); this.validateGraph();"],
      ['validateGraph', '', "const ids = this.nodes.map(item => item.id); const incoming = {}; this.edges.forEach(edge => { incoming[edge.to] = true; }); const errors = []; if (!this.nodes.some(item => item.type === 'trigger')) errors.push('缺少触发节点'); this.nodes.forEach((node, index) => { if (index && !incoming[node.id]) errors.push(node.label + ' 没有入边'); }); if (this.edges.some(edge => ids.indexOf(edge.from) < 0 || ids.indexOf(edge.to) < 0)) errors.push('存在悬空连线'); this.setValue('validationErrors', errors); this.emitEvent('validate', errors);"],
      ['run', '', "if (!this.canRun) return; this.setValue('runLog', this.enabledNodes.map((node, index) => ({ id: index + 1, text: '执行：' + node.label }))); this.emitEvent('run', this.enabledNodes);"],
      ['undo', '', "if (!this.undoStack.length) return; const previous = this.undoStack[0]; this.setValue('nodes', previous.nodes); this.setValue('edges', previous.edges); this.setValue('undoStack', this.undoStack.slice(1)); this.validateGraph();"],
      ['nodeStyle', 'node', "return 'left:' + node.x + '%;top:' + node.y + '%';"]
    ],
    template: `<section class="workflow-diagram-editor"><header><div><small>图校验 · {{ validationErrors.length }} 个问题</small><h2>{{ title }}</h2></div><div><button @click="undo" :disabled="!undoStack.length">撤销</button><button class="primary" @click="run" :disabled="!canRun">模拟运行</button></div></header><nav><button v-for="type in nodeTypes" :key="type" @click="addNode(type)">新增 {{ type }}</button><span>连线：{{ edgeSummary || '暂无' }}</span></nav><div class="diagram-layout"><main class="canvas"><article v-for="node in nodes" :key="node.id" :class="(selectedId === node.id ? 'selected ' : '') + (node.enabled ? '' : 'disabled')" :style="nodeStyle(node)" @click="selectNode(node.id)"><strong>{{ node.label }}</strong><small>{{ node.type }} #{{ node.id }}</small><button @click="beginConnect(node.id)">{{ connectFrom === node.id ? '选择目标' : '连线' }}</button></article></main><aside><h3>节点属性</h3><div v-if="selectedNode"><strong>{{ selectedNode.label }}</strong><p>位置 {{ selectedNode.x }}, {{ selectedNode.y }}</p><div class="nudge"><button @click="nudgeNode(selectedNode.id, -5, 0)">←</button><button @click="nudgeNode(selectedNode.id, 0, -5)">↑</button><button @click="nudgeNode(selectedNode.id, 0, 5)">↓</button><button @click="nudgeNode(selectedNode.id, 5, 0)">→</button></div><button @click="toggleNode(selectedNode.id)">{{ selectedNode.enabled ? '停用' : '启用' }}</button></div><ul><li v-for="error in validationErrors" :key="error">{{ error }}</li></ul></aside></div><footer><span v-for="entry in runLog" :key="entry.id">{{ entry.text }}</span></footer></section>`,
    css: 'header,nav{display:flex;justify-content:space-between;gap:8px;align-items:center}.diagram-layout{display:grid;grid-template-columns:1fr 210px;gap:12px;margin-top:12px}.canvas{position:relative;min-height:360px;background:linear-gradient(#eef2ff 1px,transparent 1px),linear-gradient(90deg,#eef2ff 1px,transparent 1px);background-size:24px 24px}.canvas article{position:absolute;width:130px;padding:10px;background:white;border:2px solid #a5b4fc;border-radius:10px}.canvas article.selected{border-color:#4f46e5;box-shadow:0 0 0 3px #e0e7ff}.canvas article.disabled{opacity:.45}.canvas small,.canvas button{display:block;margin-top:5px}.diagram-layout aside{padding:12px;background:#f8fafc}.nudge{display:grid;grid-template-columns:repeat(4,1fr);gap:4px}.diagram-layout ul{padding-left:18px;color:#b91c1c}footer{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}footer span{padding:5px 8px;background:#ecfdf5}'
  };
}

function policyRule() {
  return {
    props: {
      policyName: ['string', '研发仓库访问策略'],
      initialGroups: ['array', [
        { id: 1, operator: 'AND', conditions: [{ id: 11, field: 'role', comparator: 'equals', value: 'developer' }, { id: 12, field: 'hour', comparator: 'less', value: '20' }] },
        { id: 2, operator: 'OR', conditions: [{ id: 21, field: 'network', comparator: 'equals', value: 'office' }] }
      ]],
      fields: ['array', ['role', 'hour', 'network']],
      effect: ['string', 'allow'],
      publishable: ['bool', true]
    },
    state: { groups: [], context: { role: 'developer', hour: '16', network: 'office' }, groupJoin: 'AND', testResult: null, testTrace: [], publishedVersion: 0, nextConditionId: 100 },
    inited: "this.setValue('groups', this.initialGroups.map(group => Object.assign({}, group, { conditions: group.conditions.map(item => Object.assign({}, item)) })));",
    computed: [
      ['conditionCount', "return this.groups.reduce((sum, group) => sum + group.conditions.length, 0);"],
      ['invalidConditions', "return this.groups.reduce((out, group) => out.concat(group.conditions.filter(item => !item.field || !item.value)), []);"],
      ['decisionLabel', "return this.testResult === null ? '尚未测试' : this.testResult ? '允许访问' : '拒绝访问';"],
      ['canPublish', "return this.publishable && this.invalidConditions.length === 0 && this.testResult !== null;"]
    ],
    methods: [
      ['setContext', 'field, event', "this.setValue('context', Object.assign({}, this.context, { [field]: event.target.value })); this.setValue('testResult', null);"],
      ['toggleJoin', '', "this.setValue('groupJoin', this.groupJoin === 'AND' ? 'OR' : 'AND'); this.setValue('testResult', null);"],
      ['toggleGroup', 'id', "this.setValue('groups', this.groups.map(group => group.id === id ? Object.assign({}, group, { operator: group.operator === 'AND' ? 'OR' : 'AND' }) : group)); this.setValue('testResult', null);"],
      ['updateCondition', 'groupId, conditionId, field, event', "this.setValue('groups', this.groups.map(group => group.id !== groupId ? group : Object.assign({}, group, { conditions: group.conditions.map(condition => condition.id === conditionId ? Object.assign({}, condition, { [field]: event.target.value }) : condition) }))); this.setValue('testResult', null); this.emitEvent('change', this.groups);"],
      ['addCondition', 'groupId', "const id = this.nextConditionId; this.setValue('groups', this.groups.map(group => group.id === groupId ? Object.assign({}, group, { conditions: group.conditions.concat({ id, field: 'role', comparator: 'equals', value: '' }) }) : group)); this.setValue('nextConditionId', id + 1);"],
      ['removeCondition', 'groupId, conditionId', "this.setValue('groups', this.groups.map(group => group.id === groupId ? Object.assign({}, group, { conditions: group.conditions.filter(item => item.id !== conditionId) }) : group));"],
      ['evaluateCondition', 'condition', "const actual = this.context[condition.field]; if (condition.comparator === 'less') return Number(actual) < Number(condition.value); return String(actual) === String(condition.value);"],
      ['testPolicy', '', "const traces = this.groups.map(group => { const values = group.conditions.map(condition => this.evaluateCondition(condition)); return { id: group.id, passed: group.operator === 'AND' ? values.every(Boolean) : values.some(Boolean) }; }); const passed = this.groupJoin === 'AND' ? traces.every(item => item.passed) : traces.some(item => item.passed); this.setValue('testTrace', traces); this.setValue('testResult', passed); this.emitEvent('test', { passed, traces });"],
      ['publish', '', "if (!this.canPublish) return; this.setValue('publishedVersion', this.publishedVersion + 1); this.emitEvent('publish', { version: this.publishedVersion, groups: this.groups, effect: this.effect });"]
    ],
    template: `<section class="policy-rule-composer"><header><div><small>v{{ publishedVersion || '草稿' }}</small><h2>{{ policyName }}</h2></div><button class="primary" @click="publish" :disabled="!canPublish">发布策略</button></header><div class="policy-layout"><main><div class="join-row">规则组之间 <button @click="toggleJoin">{{ groupJoin }}</button></div><article v-for="group in groups" :key="group.id" class="rule-group"><h3>规则组 {{ group.id }} <button @click="toggleGroup(group.id)">{{ group.operator }}</button></h3><div v-for="condition in group.conditions" :key="condition.id" class="condition"><select :value="condition.field" @change="updateCondition(group.id, condition.id, 'field', $event)"><option v-for="field in fields" :key="field" :value="field">{{ field }}</option></select><select :value="condition.comparator" @change="updateCondition(group.id, condition.id, 'comparator', $event)"><option value="equals">等于</option><option value="less">小于</option></select><input :value="condition.value" @input="updateCondition(group.id, condition.id, 'value', $event)"><button @click="removeCondition(group.id, condition.id)">删除</button></div><button @click="addCondition(group.id)">添加条件</button></article></main><aside><h3>测试上下文</h3><label v-for="field in fields" :key="field">{{ field }}<input :value="context[field]" @input="setContext(field, $event)"></label><button @click="testPolicy">运行判定</button><output :class="testResult ? 'pass' : 'deny'">{{ decisionLabel }}</output><ul><li v-for="trace in testTrace" :key="trace.id">组 {{ trace.id }}：{{ trace.passed ? '通过' : '未通过' }}</li></ul></aside></div><footer>条件 {{ conditionCount }} 条 · 无效 {{ invalidConditions.length }} 条 · 效果 {{ effect }}</footer></section>`,
    css: 'header{display:flex;justify-content:space-between}.policy-layout{display:grid;grid-template-columns:1fr 240px;gap:14px}.join-row{padding:10px;background:#fffbeb}.rule-group{margin:10px 0;padding:12px;border:1px solid #fcd34d}.condition{display:grid;grid-template-columns:110px 90px 1fr auto;gap:6px;margin:7px 0}.policy-layout aside{padding:12px;background:#f8fafc}.policy-layout label{display:grid;margin:8px 0}.policy-layout output{display:block;padding:12px;margin-top:10px;text-align:center}.policy-layout output.pass{background:#dcfce7;color:#166534}.policy-layout output.deny{background:#fee2e2;color:#991b1b}footer{margin-top:10px;color:#64748b}'
  };
}

function fleetDispatch() {
  return {
    props: {
      depotName: ['string', '城北配送中心'],
      initialVehicles: ['array', [{ id: 'V1', driver: '李航', capacity: 12, status: 'idle' }, { id: 'V2', driver: '周敏', capacity: 8, status: 'idle' }, { id: 'V3', driver: '何青', capacity: 16, status: 'route' }]],
      initialOrders: ['array', [{ id: 'O101', zone: '东区', units: 4, priority: 2 }, { id: 'O102', zone: '西区', units: 7, priority: 1 }, { id: 'O103', zone: '东区', units: 5, priority: 3 }, { id: 'O104', zone: '南区', units: 3, priority: 2 }]],
      zones: ['array', ['全部', '东区', '西区', '南区']],
      maxBatch: ['number', 3]
    },
    state: { vehicles: [], orders: [], selectedVehicleId: null, selectedOrderIds: [], zone: '全部', dispatches: [], alert: '' },
    inited: "this.setValue('vehicles', this.initialVehicles.map(item => Object.assign({}, item))); this.setValue('orders', this.initialOrders.map(item => Object.assign({}, item, { status: 'pending' })));",
    computed: [
      ['visibleOrders', "return this.orders.filter(order => order.status === 'pending' && (this.zone === '全部' || order.zone === this.zone)).sort((a, b) => a.priority - b.priority);"],
      ['selectedVehicle', "return this.vehicles.find(item => item.id === this.selectedVehicleId) || null;"],
      ['selectedUnits', "return this.orders.filter(item => this.selectedOrderIds.indexOf(item.id) >= 0).reduce((sum, item) => sum + item.units, 0);"],
      ['canDispatch', "return !!this.selectedVehicle && this.selectedVehicle.status === 'idle' && this.selectedOrderIds.length > 0 && this.selectedOrderIds.length <= this.maxBatch && this.selectedUnits <= this.selectedVehicle.capacity;"],
      ['pendingUnits', "return this.orders.filter(item => item.status === 'pending').reduce((sum, item) => sum + item.units, 0);"]
    ],
    methods: [
      ['setZone', 'event', "this.setValue('zone', event.target.value); this.setValue('selectedOrderIds', []);"],
      ['chooseVehicle', 'id', "this.setValue('selectedVehicleId', id); this.setValue('alert', '');"],
      ['toggleOrder', 'id', "const list = this.selectedOrderIds; this.setValue('selectedOrderIds', list.indexOf(id) >= 0 ? list.filter(item => item !== id) : list.concat(id));"],
      ['confirmDispatch', '', "if (!this.canDispatch) { this.setValue('alert', '请选择空闲车辆，并检查容量与批量上限'); return; } const ids = this.selectedOrderIds.slice(); const vehicleId = this.selectedVehicleId; this.setValue('orders', this.orders.map(order => ids.indexOf(order.id) >= 0 ? Object.assign({}, order, { status: 'assigned', vehicleId }) : order)); this.setValue('vehicles', this.vehicles.map(vehicle => vehicle.id === vehicleId ? Object.assign({}, vehicle, { status: 'route' }) : vehicle)); this.setValue('dispatches', [{ id: Date.now(), vehicleId, orderIds: ids, units: this.selectedUnits }].concat(this.dispatches)); this.setValue('selectedOrderIds', []); this.setValue('selectedVehicleId', null); this.emitEvent('dispatch', { vehicleId, orderIds: ids });"],
      ['returnVehicle', 'id', "this.setValue('vehicles', this.vehicles.map(vehicle => vehicle.id === id ? Object.assign({}, vehicle, { status: 'idle' }) : vehicle)); this.setValue('orders', this.orders.map(order => order.vehicleId === id ? Object.assign({}, order, { status: 'delivered' }) : order)); this.emitEvent('return', id);"],
      ['isSelected', 'id, selectedOrderIds', "return selectedOrderIds.indexOf(id) >= 0;"],
      ['routeOrders', 'route', "return route.orderIds.join('、');"]
    ],
    template: `<section class="fleet-dispatch-console"><header><div><small>待配送 {{ pendingUnits }} 件</small><h2>{{ depotName }}</h2></div><select :value="zone" @change="setZone"><option v-for="item in zones" :key="item" :value="item">{{ item }}</option></select></header><div class="dispatch-grid"><aside><h3>车辆</h3><button v-for="vehicle in vehicles" :key="vehicle.id" :class="(selectedVehicleId === vehicle.id ? 'selected ' : '') + vehicle.status" @click="chooseVehicle(vehicle.id)"><strong>{{ vehicle.id }} · {{ vehicle.driver }}</strong><span>容量 {{ vehicle.capacity }} · {{ vehicle.status }}</span><i>{{ vehicle.status === 'idle' ? '可派单' : '运输中' }}</i></button></aside><main><h3>订单池</h3><article v-for="order in visibleOrders" :key="order.id" :class="isSelected(order.id, selectedOrderIds) ? 'selected' : ''" @click="toggleOrder(order.id)"><b>P{{ order.priority }}</b><strong>{{ order.id }}</strong><span>{{ order.zone }}</span><em>{{ order.units }} 件</em></article><p v-if="!visibleOrders.length">当前区域无待分配订单</p></main><aside class="summary"><h3>派单摘要</h3><p>车辆：{{ selectedVehicle ? selectedVehicle.id : '未选择' }}</p><p>订单：{{ selectedOrderIds.length }}/{{ maxBatch }}</p><p>载荷：{{ selectedUnits }} / {{ selectedVehicle ? selectedVehicle.capacity : 0 }}</p><button class="primary" @click="confirmDispatch" :disabled="!canDispatch">确认派单</button><small>{{ alert }}</small></aside></div><section class="routes"><article v-for="route in dispatches" :key="route.id"><span>{{ route.vehicleId }} → {{ routeOrders(route) }}</span><strong>{{ route.units }} 件</strong><button @click="returnVehicle(route.vehicleId)">完成返仓</button></article></section></section>`,
    css: 'header{display:flex;justify-content:space-between}.dispatch-grid{display:grid;grid-template-columns:200px 1fr 210px;gap:12px}.dispatch-grid>aside{padding:10px;background:#f8fafc}.dispatch-grid>aside>button{display:grid;width:100%;text-align:left;margin:7px 0}.dispatch-grid>aside>button.selected{border-color:#0284c7;background:#e0f2fe}.dispatch-grid>aside>button.route{opacity:.6}.dispatch-grid main article{display:grid;grid-template-columns:40px 1fr 70px 60px;gap:8px;padding:10px;border-bottom:1px solid #e2e8f0}.dispatch-grid main article.selected{background:#dbeafe}.dispatch-grid .summary p{display:flex;justify-content:space-between}.routes article{display:flex;gap:12px;align-items:center;padding:8px;margin-top:6px;background:#ecfeff}.routes article button{margin-left:auto}'
  };
}

function clinicalTriage() {
  return {
    props: {
      unitName: ['string', '急诊分诊台'],
      initialPatients: ['array', [{ id: 1, name: '王婷', age: 32, pulse: 118, oxygen: 91, pain: 7 }, { id: 2, name: '赵晨', age: 67, pulse: 88, oxygen: 96, pain: 3 }, { id: 3, name: '陈宇', age: 19, pulse: 105, oxygen: 98, pain: 5 }]],
      initialBeds: ['array', [{ id: 'A01', area: '复苏区', status: 'free' }, { id: 'B03', area: '观察区', status: 'free' }, { id: 'B04', area: '观察区', status: 'occupied' }]],
      clinicians: ['array', ['林医生', '高护士', '周医生']],
      oxygenCritical: ['number', 92]
    },
    state: { patients: [], beds: [], selectedPatientId: null, selectedBedId: null, clinician: '林医生', audit: [], filter: 'all' },
    inited: "this.setValue('patients', this.initialPatients.map(item => Object.assign({}, item, { level: this.triageLevel(item), status: 'waiting' }))); this.setValue('beds', this.initialBeds.map(item => Object.assign({}, item)));",
    computed: [
      ['queue', "const ranks = { red: 1, orange: 2, yellow: 3, green: 4 }; return this.patients.filter(item => item.status !== 'discharged' && (this.filter === 'all' || item.level === this.filter)).slice().sort((a, b) => ranks[a.level] - ranks[b.level]);"],
      ['selectedPatient', "return this.patients.find(item => item.id === this.selectedPatientId) || null;"],
      ['freeBeds', "return this.beds.filter(item => item.status === 'free');"],
      ['waitingCount', "return this.patients.filter(item => item.status === 'waiting').length;"]
    ],
    methods: [
      ['triageLevel', 'patient', "if (patient.oxygen <= this.oxygenCritical || patient.pulse >= 130) return 'red'; if (patient.pain >= 7 || patient.pulse >= 115) return 'orange'; if (patient.pain >= 4) return 'yellow'; return 'green';"],
      ['selectPatient', 'id', "this.setValue('selectedPatientId', id); this.setValue('selectedBedId', null);"],
      ['setFilter', 'value', "this.setValue('filter', value);"],
      ['updateVital', 'field, event', "if (!this.selectedPatient) return; const value = Number(event.target.value) || 0; this.setValue('patients', this.patients.map(patient => patient.id === this.selectedPatientId ? Object.assign({}, patient, { [field]: value, level: this.triageLevel(Object.assign({}, patient, { [field]: value })) }) : patient)); this.record('更新体征 ' + field); this.emitEvent('triage', this.selectedPatient);"],
      ['chooseBed', 'id', "this.setValue('selectedBedId', id);"],
      ['assignBed', '', "if (!this.selectedPatient || !this.selectedBedId) return; const patientId = this.selectedPatientId; const bedId = this.selectedBedId; this.setValue('patients', this.patients.map(item => item.id === patientId ? Object.assign({}, item, { status: 'assigned', bedId, clinician: this.clinician }) : item)); this.setValue('beds', this.beds.map(item => item.id === bedId ? Object.assign({}, item, { status: 'occupied', patientId }) : item)); this.record('分配床位 ' + bedId); this.emitEvent('assign', { patientId, bedId });"],
      ['discharge', '', "if (!this.selectedPatient) return; const bedId = this.selectedPatient.bedId; const patientId = this.selectedPatientId; this.setValue('patients', this.patients.map(item => item.id === patientId ? Object.assign({}, item, { status: 'discharged' }) : item)); if (bedId) this.setValue('beds', this.beds.map(item => item.id === bedId ? Object.assign({}, item, { status: 'free', patientId: null }) : item)); this.record('患者离院'); this.emitEvent('discharge', patientId);"],
      ['setClinician', 'event', "this.setValue('clinician', event.target.value);"],
      ['record', 'action', "this.setValue('audit', [{ id: Date.now(), action, patientId: this.selectedPatientId, clinician: this.clinician }].concat(this.audit).slice(0, 6));"]
    ],
    template: `<section class="clinical-triage-board"><header><div><small>等待 {{ waitingCount }} 人 · 空床 {{ freeBeds.length }} 张</small><h2>{{ unitName }}</h2></div><div class="filters"><button v-for="level in ['all','red','orange','yellow','green']" :key="level" :class="filter === level ? 'active' : ''" @click="setFilter(level)">{{ level }}</button></div></header><div class="triage-layout"><aside class="queue"><button v-for="patient in queue" :key="patient.id" :class="(selectedPatientId === patient.id ? 'selected ' : '') + patient.level" @click="selectPatient(patient.id)"><b>{{ patient.level }}</b><strong>{{ patient.name }} · {{ patient.age }}岁</strong><span>血氧 {{ patient.oxygen }}% · 脉搏 {{ patient.pulse }}</span></button></aside><main v-if="selectedPatient"><h3>{{ selectedPatient.name }} 的体征</h3><div class="vitals"><label>血氧<input type="number" :value="selectedPatient.oxygen" @input="updateVital('oxygen', $event)"></label><label>脉搏<input type="number" :value="selectedPatient.pulse" @input="updateVital('pulse', $event)"></label><label>疼痛<input type="number" :value="selectedPatient.pain" @input="updateVital('pain', $event)"></label></div><select :value="clinician" @change="setClinician"><option v-for="person in clinicians" :key="person" :value="person">{{ person }}</option></select><h3>床位</h3><div class="beds"><button v-for="bed in beds" :key="bed.id" :class="(selectedBedId === bed.id ? 'selected ' : '') + bed.status" @click="chooseBed(bed.id)" :disabled="bed.status !== 'free'"><strong>{{ bed.id }}</strong><span>{{ bed.area }} · {{ bed.status }}</span></button></div><button class="primary" @click="assignBed" :disabled="!selectedBedId">确认收治</button><button @click="discharge">办理离院</button></main><main v-else class="empty">请选择患者查看详情</main><aside class="audit"><h3>审计记录</h3><ol><li v-for="entry in audit" :key="entry.id">{{ entry.clinician }} · {{ entry.action }}</li></ol></aside></div></section>`,
    css: 'header{display:flex;justify-content:space-between}.filters{display:flex;gap:4px}.filters button.active{background:#0f172a;color:white}.triage-layout{display:grid;grid-template-columns:220px 1fr 190px;gap:12px}.queue>button{display:grid;width:100%;text-align:left;margin-bottom:7px;border-left:7px solid}.queue>button.red{border-left-color:#dc2626}.queue>button.orange{border-left-color:#f97316}.queue>button.yellow{border-left-color:#eab308}.queue>button.green{border-left-color:#16a34a}.queue>button.selected{background:#f1f5f9}.vitals{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.vitals label{display:grid}.beds{display:flex;gap:8px;margin:10px 0}.beds button{display:grid}.beds button.selected{border-color:#dc2626}.beds button.occupied{opacity:.45}.audit{padding:10px;background:#f8fafc}.audit ol{padding-left:20px}'
  };
}

function dependencyRelease() {
  return {
    props: {
      releaseName: ['string', '秋季平台发布'],
      initialServices: ['array', [{ id: 'web', version: '2.4.0' }, { id: 'api', version: '3.1.0' }, { id: 'billing', version: '1.8.2' }, { id: 'notify', version: '1.3.5' }]],
      dependencies: ['array', [{ from: 'web', to: 'api' }, { from: 'api', to: 'billing' }, { from: 'api', to: 'notify' }]],
      environments: ['array', ['测试', '预发', '生产']],
      requiredApprovals: ['number', 2]
    },
    state: { services: [], waves: [[], [], []], selectedServiceId: null, environment: '测试', approvals: [], releaseStatus: 'planning', history: [] },
    inited: "this.setValue('services', this.initialServices.map(item => Object.assign({}, item, { health: 'ready' })));",
    computed: [
      ['plannedIds', "return this.waves.reduce((out, wave) => out.concat(wave), []);"],
      ['unplanned', "return this.services.filter(service => this.plannedIds.indexOf(service.id) < 0);"],
      ['dependencyViolations', "const position = {}; this.waves.forEach((wave, index) => wave.forEach(id => { position[id] = index; })); return this.dependencies.filter(edge => position[edge.from] !== undefined && (position[edge.to] === undefined || position[edge.to] > position[edge.from]));"],
      ['canRelease', "return this.unplanned.length === 0 && this.dependencyViolations.length === 0 && this.approvals.length >= this.requiredApprovals && this.releaseStatus !== 'released';"]
    ],
    methods: [
      ['chooseService', 'id', "this.setValue('selectedServiceId', id);"],
      ['assignWave', 'index', "if (!this.selectedServiceId) return; const id = this.selectedServiceId; this.setValue('waves', this.waves.map((wave, waveIndex) => waveIndex === index ? wave.filter(item => item !== id).concat(id) : wave.filter(item => item !== id))); this.setValue('selectedServiceId', null); this.setValue('approvals', []); this.emitEvent('plan', this.waves);"],
      ['removeFromWave', 'id', "this.setValue('waves', this.waves.map(wave => wave.filter(item => item !== id))); this.setValue('approvals', []);"],
      ['approve', 'role', "if (this.approvals.indexOf(role) >= 0) return; this.setValue('approvals', this.approvals.concat(role)); this.emitEvent('approve', this.approvals);"],
      ['setEnvironment', 'event', "this.setValue('environment', event.target.value); this.setValue('approvals', []);"],
      ['release', '', "if (!this.canRelease) return; this.setValue('history', [{ id: Date.now(), environment: this.environment, waves: this.waves.map(wave => wave.slice()) }].concat(this.history)); this.setValue('releaseStatus', 'released'); this.emitEvent('release', this.history[0]);"],
      ['rollback', '', "if (!this.history.length) return; this.setValue('releaseStatus', 'rolled-back'); this.emitEvent('rollback', this.history[0]);"],
      ['serviceLabel', 'id', "const service = this.services.find(item => item.id === id); return service ? service.id + '@' + service.version : id;"]
    ],
    template: `<section class="dependency-release-planner"><header><div><small>{{ environment }} · {{ releaseStatus }}</small><h2>{{ releaseName }}</h2></div><select :value="environment" @change="setEnvironment"><option v-for="env in environments" :key="env" :value="env">{{ env }}</option></select></header><div class="release-layout"><aside><h3>未编排服务</h3><button v-for="service in unplanned" :key="service.id" :class="selectedServiceId === service.id ? 'selected' : ''" @click="chooseService(service.id)"><strong>{{ service.id }}</strong><span>{{ service.version }} · {{ service.health }}</span></button><h3>依赖边</h3><p v-for="edge in dependencies" :key="edge.from + edge.to">{{ edge.from }} → {{ edge.to }}</p></aside><main><section v-for="wave, index in waves" :key="index" class="wave"><header><h3>波次 {{ index + 1 }}</h3><button @click="assignWave(index)" :disabled="!selectedServiceId">放入此波次</button></header><article v-for="id in wave" :key="id"><strong>{{ serviceLabel(id) }}</strong><button @click="removeFromWave(id)">移出</button></article></section></main><aside class="gate"><h3>发布门禁</h3><p :class="unplanned.length ? 'bad' : 'good'">未编排 {{ unplanned.length }}</p><p :class="dependencyViolations.length ? 'bad' : 'good'">依赖冲突 {{ dependencyViolations.length }}</p><p>审批 {{ approvals.length }}/{{ requiredApprovals }}</p><button @click="approve('技术负责人')">技术审批</button><button @click="approve('运维负责人')">运维审批</button><button class="primary" @click="release" :disabled="!canRelease">执行发布</button><button @click="rollback" :disabled="releaseStatus !== 'released'">回滚</button></aside></div></section>`,
    css: 'header{display:flex;justify-content:space-between}.release-layout{display:grid;grid-template-columns:180px 1fr 190px;gap:12px}.release-layout>aside{padding:10px;background:#f8fafc}.release-layout>aside>button{display:grid;width:100%;margin:6px 0;text-align:left}.release-layout>aside>button.selected{background:#e0e7ff}.release-layout main{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.wave{min-height:260px;padding:9px;border:1px dashed #818cf8}.wave header{display:block}.wave article{display:flex;justify-content:space-between;padding:8px;margin-top:7px;background:#eef2ff}.gate button{width:100%;margin:4px 0}.good{color:#15803d}.bad{color:#b91c1c}'
  };
}

function energyLoad() {
  const hours = [0, 1, 2, 3, 4, 5, 6, 7];
  return {
    props: {
      siteName: ['string', '微电网负载计划'],
      devices: ['array', [{ id: 'pump', name: '循环泵', kw: 20 }, { id: 'chiller', name: '冷水机', kw: 35 }, { id: 'charge', name: '充电桩', kw: 15 }]],
      hours: ['array', hours],
      rates: ['array', [0.42, 0.38, 0.36, 0.4, 0.55, 0.72, 0.9, 0.8]],
      capacity: ['number', 55]
    },
    state: { schedule: {}, selectedHour: 0, scenarioName: '基准方案', savedScenarios: [], optimized: false },
    inited: "const schedule = {}; this.devices.forEach((device, d) => { schedule[device.id] = {}; this.hours.forEach(hour => { schedule[device.id][hour] = (hour + d) % 3 === 0; }); }); this.setValue('schedule', schedule);",
    computed: [
      ['hourlyLoads', "return this.hours.map(hour => this.devices.reduce((sum, device) => sum + (this.schedule[device.id] && this.schedule[device.id][hour] ? device.kw : 0), 0));"],
      ['totalCost', "return this.hourlyLoads.reduce((sum, load, index) => sum + load * (this.rates[index] || 0), 0).toFixed(2);"],
      ['peakLoad', "return Math.max.apply(Math, this.hourlyLoads.concat(0));"],
      ['violations', "return this.hours.filter((hour, index) => this.hourlyLoads[index] > this.capacity);"],
      ['violationsLabel', "return this.violations.join('、');"],
      ['selectedLoad', "const index = this.hours.indexOf(this.selectedHour); return index < 0 ? 0 : this.hourlyLoads[index];"]
    ],
    methods: [
      ['toggleSlot', 'deviceId, hour', "const deviceSchedule = Object.assign({}, this.schedule[deviceId], { [hour]: !this.schedule[deviceId][hour] }); this.setValue('schedule', Object.assign({}, this.schedule, { [deviceId]: deviceSchedule })); this.setValue('selectedHour', hour); this.setValue('optimized', false); this.emitEvent('schedule', this.schedule);"],
      ['selectHour', 'hour', "this.setValue('selectedHour', hour);"],
      ['optimize', '', "const schedule = {}; this.devices.forEach((device, deviceIndex) => { schedule[device.id] = {}; this.hours.forEach((hour, hourIndex) => { schedule[device.id][hour] = (hourIndex + deviceIndex * 2) % 5 === 0 && this.rates[hourIndex] < 0.7; }); }); this.setValue('schedule', schedule); this.setValue('optimized', true); this.emitEvent('optimize', { schedule, cost: this.totalCost });"],
      ['updateScenarioName', 'event', "this.setValue('scenarioName', event.target.value);"],
      ['saveScenario', '', "const scenario = { id: Date.now(), name: this.scenarioName, cost: this.totalCost, peak: this.peakLoad, schedule: JSON.parse(JSON.stringify(this.schedule)) }; this.setValue('savedScenarios', [scenario].concat(this.savedScenarios).slice(0, 4)); this.emitEvent('save', scenario);"],
      ['slotClass', 'deviceId, hour', "return this.schedule[deviceId] && this.schedule[deviceId][hour] ? 'on' : 'off';"],
      ['loadStyle', 'load', "return 'height:' + Math.min(100, load / this.capacity * 100) + '%';"]
    ],
    template: `<section class="energy-load-scheduler"><header><div><small>{{ optimized ? '已自动优化' : '手工排程' }}</small><h2>{{ siteName }}</h2></div><button class="primary" @click="optimize">平衡峰值</button></header><div class="energy-layout"><main><div class="matrix-head"><span>设备 / 小时</span><button v-for="hour in hours" :key="hour" :class="selectedHour === hour ? 'active' : ''" @click="selectHour(hour)">{{ hour }}时</button></div><div v-for="device in devices" :key="device.id" class="device-row"><strong>{{ device.name }}<small>{{ device.kw }} kW</small></strong><button v-for="hour in hours" :key="hour" :class="schedule[device.id][hour] ? 'on' : 'off'" @click="toggleSlot(device.id, hour)">{{ schedule[device.id][hour] ? '开' : '—' }}</button></div><div class="load-chart"><i v-for="load, index in hourlyLoads" :key="index" :class="load > capacity ? 'over' : ''" :style="loadStyle(load)"><span>{{ load }}</span></i></div></main><aside><h3>{{ selectedHour }}:00 详情</h3><strong>{{ selectedLoad }} / {{ capacity }} kW</strong><p>峰值 {{ peakLoad }} kW</p><p>预计成本 ¥{{ totalCost }}</p><p class="warn" v-if="violations.length">超限时段：{{ violationsLabel }}</p><input :value="scenarioName" @input="updateScenarioName"><button @click="saveScenario">保存情景</button><ul><li v-for="scenario in savedScenarios" :key="scenario.id">{{ scenario.name }} · ¥{{ scenario.cost }} · {{ scenario.peak }}kW</li></ul></aside></div></section>`,
    css: 'header{display:flex;justify-content:space-between}.energy-layout{display:grid;grid-template-columns:1fr 220px;gap:14px}.matrix-head,.device-row{display:grid;grid-template-columns:130px repeat(8,1fr);gap:4px;margin-bottom:4px}.matrix-head button.active{background:#d1fae5}.device-row strong{display:grid}.device-row button.on{background:#059669;color:white}.device-row button.off{background:#f1f5f9;color:#94a3b8}.load-chart{height:130px;display:flex;align-items:flex-end;gap:8px;padding:16px 8px 0;border-bottom:1px solid}.load-chart i{flex:1;min-height:3px;background:#34d399;position:relative}.load-chart i.over{background:#ef4444}.load-chart span{position:absolute;top:-16px;font-size:10px}.energy-layout aside{padding:12px;background:#f8fafc}.energy-layout aside input,.energy-layout aside button{width:100%;margin:5px 0}.warn{color:#b91c1c}'
  };
}

function auctionRoom() {
  return {
    props: {
      roomName: ['string', '当代艺术专场'],
      lots: ['array', [{ id: 'L01', title: '山海之间', reserve: 1200 }, { id: 'L02', title: '蓝色构成', reserve: 900 }, { id: 'L03', title: '城市切片', reserve: 1600 }]],
      bidders: ['array', ['B-108', 'B-205', 'B-311']],
      initialSeconds: ['number', 45],
      minIncrement: ['number', 100]
    },
    state: { activeLotId: 'L01', bidsByLot: {}, bidder: 'B-108', amount: 1300, seconds: 45, status: 'preview', riskFlags: [], audit: [], timer: null },
    inited: "const bids = {}; this.lots.forEach(lot => { bids[lot.id] = []; }); this.setValue('bidsByLot', bids); this.setValue('seconds', this.initialSeconds); this.setValue('amount', this.lots[0] ? this.lots[0].reserve + this.minIncrement : 0);",
    attached: "this.startTimer();",
    disposed: "if (this.timer) clearInterval(this.timer);",
    computed: [
      ['activeLot', "return this.lots.find(item => item.id === this.activeLotId) || null;"],
      ['activeBids', "return (this.bidsByLot[this.activeLotId] || []).slice().sort((a, b) => b.amount - a.amount);"],
      ['topBid', "return this.activeBids[0] || null;"],
      ['minimumBid', "return this.topBid ? this.topBid.amount + this.minIncrement : (this.activeLot ? this.activeLot.reserve : 0);"],
      ['canBid', "return this.status === 'running' && this.seconds > 0 && this.amount >= this.minimumBid;"],
      ['clockLabel', "return '00:' + String(this.seconds).padStart(2, '0');"]
    ],
    methods: [
      ['startTimer', '', "if (this.timer) return; const timer = setInterval(() => { if (this.status !== 'running') return; const next = Math.max(0, this.seconds - 1); this.setValue('seconds', next); if (next === 0) this.closeLot(); }, 1000); this.setValue('timer', timer);"],
      ['switchLot', 'id', "this.setValue('activeLotId', id); this.setValue('seconds', this.initialSeconds); this.setValue('status', 'preview'); const lot = this.lots.find(item => item.id === id); this.setValue('amount', lot ? lot.reserve + this.minIncrement : 0);"],
      ['openLot', '', "if (!this.activeLot) return; this.setValue('status', 'running'); this.setValue('seconds', this.initialSeconds); this.startTimer();"],
      ['setBidder', 'event', "this.setValue('bidder', event.target.value);"],
      ['setAmount', 'event', "this.setValue('amount', Number(event.target.value) || 0);"],
      ['placeBid', '', "if (!this.canBid) return; const bid = { id: Date.now(), bidder: this.bidder, amount: this.amount, second: this.seconds }; const list = (this.bidsByLot[this.activeLotId] || []).concat(bid); this.setValue('bidsByLot', Object.assign({}, this.bidsByLot, { [this.activeLotId]: list })); this.setValue('seconds', Math.max(this.seconds, 12)); this.setValue('amount', this.amount + this.minIncrement); this.setValue('audit', [{ id: bid.id, text: this.bidder + ' 出价 ¥' + bid.amount }].concat(this.audit).slice(0, 8)); this.emitEvent('bid', bid);"],
      ['togglePause', '', "this.setValue('status', this.status === 'paused' ? 'running' : 'paused');"],
      ['flagBid', 'id', "const flags = this.riskFlags; this.setValue('riskFlags', flags.indexOf(id) >= 0 ? flags.filter(item => item !== id) : flags.concat(id)); this.emitEvent('flag', id);"],
      ['closeLot', '', "if (this.status === 'closed') return; this.setValue('status', 'closed'); this.emitEvent('close', { lot: this.activeLotId, winner: this.topBid });"],
      ['isFlagged', 'id, riskFlags', "return riskFlags.indexOf(id) >= 0;"]
    ],
    template: `<section class="auction-control-room"><header><div><small>{{ roomName }} · {{ status }}</small><h2>{{ activeLot ? activeLot.title : '无拍品' }}</h2></div><output :class="seconds < 10 ? 'urgent' : ''">{{ clockLabel }}</output></header><nav><button v-for="lot in lots" :key="lot.id" :class="activeLotId === lot.id ? 'active' : ''" @click="switchLot(lot.id)">{{ lot.id }} {{ lot.title }}</button></nav><div class="auction-layout"><main><section class="price"><small>当前最高价</small><strong>¥{{ topBid ? topBid.amount : activeLot.reserve }}</strong><span>{{ topBid ? topBid.bidder : '尚无出价' }}</span></section><div class="bid-form"><select :value="bidder" @change="setBidder"><option v-for="person in bidders" :key="person" :value="person">{{ person }}</option></select><input type="number" :value="amount" @input="setAmount"><button class="primary" @click="placeBid" :disabled="!canBid">提交出价</button></div><div class="controls"><button @click="openLot">开始竞拍</button><button @click="togglePause" :disabled="status !== 'running' && status !== 'paused'">{{ status === 'paused' ? '继续' : '暂停' }}</button><button @click="closeLot">成交/流拍</button></div></main><aside><h3>实时出价队列</h3><article v-for="bid in activeBids" :key="bid.id" :class="isFlagged(bid.id, riskFlags) ? 'flagged' : ''"><strong>¥{{ bid.amount }}</strong><span>{{ bid.bidder }} · 剩余{{ bid.second }}秒</span><button @click="flagBid(bid.id)">{{ isFlagged(bid.id, riskFlags) ? '取消标记' : '风险标记' }}</button></article></aside></div><footer><span v-for="entry in audit" :key="entry.id">{{ entry.text }}</span></footer></section>`,
    css: 'header{display:flex;justify-content:space-between}header output{font:700 34px monospace;padding:8px 16px;background:#0f172a;color:white}header output.urgent{background:#be123c}nav{display:flex;gap:7px;margin:10px 0}nav button.active{background:#ffe4e6;border-color:#be123c}.auction-layout{display:grid;grid-template-columns:1fr 300px;gap:14px}.auction-layout main{padding:18px;text-align:center;background:#fff1f2}.price strong,.price span{display:block}.price strong{font-size:42px}.bid-form{display:grid;grid-template-columns:1fr 1fr auto;gap:8px;margin:16px 0}.controls{display:flex;justify-content:center;gap:8px}.auction-layout aside article{display:grid;grid-template-columns:90px 1fr auto;padding:9px;border-bottom:1px solid #e2e8f0}.auction-layout aside article.flagged{background:#fef2f2;color:#b91c1c}footer{display:flex;gap:6px;overflow:auto;margin-top:10px}footer span{white-space:nowrap;padding:5px;background:#f8fafc}'
  };
}

function annotationStudio() {
  return {
    props: {
      documentTitle: ['string', '访谈记录 07'],
      documentText: ['string', '受访者认为公共交通改善了通勤效率，但高峰时段的换乘体验仍然需要优化。'],
      labels: ['array', [{ id: 'benefit', name: '积极影响', color: '#16a34a' }, { id: 'problem', name: '问题', color: '#dc2626' }, { id: 'suggestion', name: '建议', color: '#2563eb' }]],
      reviewers: ['array', ['标注员A', '标注员B']],
      minAnnotations: ['number', 2]
    },
    state: { annotations: [{ id: 1, start: 5, end: 15, labelId: 'benefit', author: '标注员A', status: 'accepted' }, { id: 2, start: 21, end: 35, labelId: 'problem', author: '标注员B', status: 'pending' }], start: 0, end: 4, activeLabelId: 'benefit', reviewer: '标注员A', selectedId: null, resolutions: [], submitted: false, nextId: 10 },
    computed: [
      ['selectedText', "return this.documentText.slice(this.start, this.end);"],
      ['conflicts', "return this.annotations.filter((item, index, list) => list.some((other, otherIndex) => otherIndex !== index && Math.max(item.start, other.start) < Math.min(item.end, other.end) && item.labelId !== other.labelId));"],
      ['selectedAnnotation', "return this.annotations.find(item => item.id === this.selectedId) || null;"],
      ['coverage', "const covered = {}; this.annotations.forEach(item => { for (let index = item.start; index < item.end; index += 1) covered[index] = true; }); return Math.round(Object.keys(covered).length / (this.documentText.length || 1) * 100);"],
      ['canSubmit', "return this.annotations.length >= this.minAnnotations && this.conflicts.length === 0 && !this.submitted;"]
    ],
    methods: [
      ['setBoundary', 'field, event', "const value = Math.max(0, Math.min(this.documentText.length, Number(event.target.value) || 0)); this.setValue(field, value);"],
      ['chooseLabel', 'id', "this.setValue('activeLabelId', id);"],
      ['setReviewer', 'event', "this.setValue('reviewer', event.target.value);"],
      ['addAnnotation', '', "if (this.start >= this.end || !this.selectedText.trim()) return; const item = { id: this.nextId, start: this.start, end: this.end, labelId: this.activeLabelId, author: this.reviewer, status: 'pending' }; this.setValue('annotations', this.annotations.concat(item)); this.setValue('nextId', this.nextId + 1); this.setValue('selectedId', item.id); this.setValue('submitted', false); this.emitEvent('annotate', item);"],
      ['selectAnnotation', 'id', "const item = this.annotations.find(annotation => annotation.id === id); this.setValue('selectedId', id); if (item) { this.setValue('start', item.start); this.setValue('end', item.end); this.setValue('activeLabelId', item.labelId); }"],
      ['resolve', 'id, action', "this.setValue('annotations', this.annotations.map(item => item.id === id ? Object.assign({}, item, { status: action }) : item)); this.setValue('resolutions', [{ id: Date.now(), annotationId: id, action, reviewer: this.reviewer }].concat(this.resolutions)); this.emitEvent('resolve', { id, action });"],
      ['removeAnnotation', 'id', "this.setValue('annotations', this.annotations.filter(item => item.id !== id)); if (this.selectedId === id) this.setValue('selectedId', null);"],
      ['submit', '', "if (!this.canSubmit) return; this.setValue('submitted', true); this.emitEvent('submit', this.annotations);"],
      ['labelName', 'id', "const label = this.labels.find(item => item.id === id); return label ? label.name : id;"],
      ['annotationStyle', 'item', "const label = this.labels.find(entry => entry.id === item.labelId); return 'border-left-color:' + (label ? label.color : '#64748b');"],
      ['annotationText', 'item', "return this.documentText.slice(item.start, item.end);"]
    ],
    template: `<section class="research-annotation-studio"><header><div><small>覆盖率 {{ coverage }}% · 冲突 {{ conflicts.length }}</small><h2>{{ documentTitle }}</h2></div><button class="primary" @click="submit" :disabled="!canSubmit">提交语料</button></header><div class="annotation-layout"><main><article class="document">{{ documentText }}</article><div class="span-form"><label>起点<input type="number" :value="start" @input="setBoundary('start', $event)"></label><label>终点<input type="number" :value="end" @input="setBoundary('end', $event)"></label><output>“{{ selectedText }}”</output></div><div class="labels"><button v-for="label in labels" :key="label.id" :class="activeLabelId === label.id ? 'active' : ''" :style="'border-color:' + label.color" @click="chooseLabel(label.id)">{{ label.name }}</button></div><select :value="reviewer" @change="setReviewer"><option v-for="person in reviewers" :key="person" :value="person">{{ person }}</option></select><button @click="addAnnotation">创建标注</button></main><aside><h3>标注列表</h3><article v-for="item in annotations" :key="item.id" :class="(selectedId === item.id ? 'selected ' : '') + item.status" :style="annotationStyle(item)" @click="selectAnnotation(item.id)"><strong>{{ labelName(item.labelId) }} · {{ item.start }}–{{ item.end }}</strong><span>{{ annotationText(item) }}</span><small>{{ item.author }} · {{ item.status }}</small><div><button @click="resolve(item.id, 'accepted')">接受</button><button @click="resolve(item.id, 'rejected')">拒绝</button><button @click="removeAnnotation(item.id)">删除</button></div></article></aside><aside class="conflicts"><h3>冲突仲裁</h3><p v-if="!conflicts.length">暂无重叠冲突</p><button v-for="item in conflicts" :key="item.id" @click="selectAnnotation(item.id)">#{{ item.id }} {{ labelName(item.labelId) }}</button><h3>仲裁记录</h3><p v-for="entry in resolutions" :key="entry.id">#{{ entry.annotationId }} {{ entry.action }}</p></aside></div></section>`,
    css: 'header{display:flex;justify-content:space-between}.annotation-layout{display:grid;grid-template-columns:1fr 300px 180px;gap:12px}.document{padding:24px;font-size:18px;line-height:2;background:#fffbeb}.span-form{display:grid;grid-template-columns:90px 90px 1fr;gap:8px;margin:12px 0}.span-form label{display:grid}.span-form output{padding:8px;background:#f8fafc}.labels{display:flex;gap:7px;margin-bottom:8px}.labels button{border-left-width:6px}.labels button.active{background:#e0f2fe}.annotation-layout>aside{max-height:430px;overflow:auto}.annotation-layout>aside article{display:grid;padding:9px;margin-bottom:7px;border-left:6px solid #64748b;background:#f8fafc}.annotation-layout>aside article.selected{box-shadow:0 0 0 2px #93c5fd}.annotation-layout>aside article.rejected{opacity:.5}.conflicts{padding:10px;background:#fef2f2}.conflicts button{display:block;width:100%;margin:5px 0}'
  };
}

function procurementMatrix() {
  return {
    props: {
      projectName: ['string', '园区安防采购评审'],
      suppliers: ['array', [{ id: 'S1', name: '远见科技', price: 86 }, { id: 'S2', name: '安域系统', price: 92 }, { id: 'S3', name: '云盾智能', price: 79 }]],
      criteria: ['array', [{ id: 'tech', name: '技术', weight: 40 }, { id: 'service', name: '服务', weight: 25 }, { id: 'delivery', name: '交付', weight: 15 }, { id: 'price', name: '价格', weight: 20 }]],
      reviewers: ['array', ['评委甲', '评委乙', '评委丙']],
      passingScore: ['number', 70]
    },
    state: { weights: {}, scores: {}, reviewer: '评委甲', lockedReviewers: [], selectedSupplierId: null, comments: {}, awardedSupplierId: null },
    inited: "const weights = {}; this.criteria.forEach(item => { weights[item.id] = item.weight; }); const scores = {}; this.suppliers.forEach((supplier, sIndex) => { scores[supplier.id] = {}; this.criteria.forEach((criterion, cIndex) => { scores[supplier.id][criterion.id] = 72 + (sIndex * 7 + cIndex * 5) % 24; }); }); this.setValue('weights', weights); this.setValue('scores', scores);",
    computed: [
      ['weightTotal', "const weights = this.weights || {}; return this.criteria.reduce((sum, item) => sum + Number(weights[item.id] || 0), 0);"],
      ['rankings', "const scores = this.scores || {}; const weights = this.weights || {}; return this.suppliers.map(supplier => { const row = scores[supplier.id] || {}; const weighted = this.criteria.reduce((sum, criterion) => sum + Number(row[criterion.id] || 0) * Number(weights[criterion.id] || 0), 0) / (this.weightTotal || 1); return Object.assign({}, supplier, { total: weighted.toFixed(1) }); }).sort((a, b) => Number(b.total) - Number(a.total));"],
      ['winner', "return this.rankings.find(item => item.id === this.awardedSupplierId) || null;"],
      ['isLocked', "return this.lockedReviewers.indexOf(this.reviewer) >= 0;"]
    ],
    methods: [
      ['setReviewer', 'event', "this.setValue('reviewer', event.target.value);"],
      ['updateWeight', 'id, event', "if (this.isLocked) return; this.setValue('weights', Object.assign({}, this.weights, { [id]: Number(event.target.value) || 0 })); this.emitEvent('score', { weights: this.weights, scores: this.scores });"],
      ['updateScore', 'supplierId, criterionId, event', "if (this.isLocked) return; const row = Object.assign({}, this.scores[supplierId], { [criterionId]: Math.max(0, Math.min(100, Number(event.target.value) || 0)) }); this.setValue('scores', Object.assign({}, this.scores, { [supplierId]: row })); this.setValue('selectedSupplierId', supplierId);"],
      ['toggleLock', '', "const list = this.lockedReviewers; this.setValue('lockedReviewers', list.indexOf(this.reviewer) >= 0 ? list.filter(item => item !== this.reviewer) : list.concat(this.reviewer)); this.emitEvent('lock', { reviewer: this.reviewer, locked: !this.isLocked });"],
      ['updateComment', 'supplierId, event', "this.setValue('comments', Object.assign({}, this.comments, { [supplierId]: event.target.value }));"],
      ['award', 'supplierId', "const supplier = this.rankings.find(item => item.id === supplierId); if (!supplier || Number(supplier.total) < this.passingScore || this.weightTotal !== 100) return; this.setValue('awardedSupplierId', supplierId); this.emitEvent('award', supplier);"],
      ['rankOf', 'id', "return this.rankings.findIndex(item => item.id === id) + 1;"],
      ['supplierTotal', 'id', "const supplier = this.rankings.find(item => item.id === id); return supplier ? supplier.total : '0.0';"],
      ['canAward', 'supplier', "return Number(this.supplierTotal(supplier.id)) >= this.passingScore && this.weightTotal === 100;"]
    ],
    template: `<section class="procurement-bid-matrix"><header><div><small>权重合计 {{ weightTotal }}% · {{ reviewer }}</small><h2>{{ projectName }}</h2></div><div><select :value="reviewer" @change="setReviewer"><option v-for="person in reviewers" :key="person" :value="person">{{ person }}</option></select><button @click="toggleLock">{{ isLocked ? '解锁本评委' : '锁定本评委' }}</button></div></header><div class="matrix-wrap"><table><thead><tr><th>供应商</th><th>报价/万元</th><th v-for="criterion in criteria" :key="criterion.id"><span>{{ criterion.name }}</span><input type="number" :value="weights[criterion.id]" @input="updateWeight(criterion.id, $event)" :disabled="isLocked"></th><th>总分</th><th>排名</th></tr></thead><tbody><tr v-for="supplier in suppliers" :key="supplier.id" :class="selectedSupplierId === supplier.id ? 'selected' : ''"><th>{{ supplier.name }}</th><td>{{ supplier.price }}</td><td v-for="criterion in criteria" :key="criterion.id"><input type="number" :value="scores[supplier.id][criterion.id]" @input="updateScore(supplier.id, criterion.id, $event)" :disabled="isLocked"></td><td><strong>{{ supplierTotal(supplier.id) }}</strong></td><td>#{{ rankOf(supplier.id) }}</td></tr></tbody></table></div><div class="ranking"><article v-for="supplier, index in rankings" :key="supplier.id" :class="awardedSupplierId === supplier.id ? 'winner' : ''"><b>#{{ index + 1 }}</b><strong>{{ supplier.name }}</strong><span>{{ supplier.total }} 分</span><textarea :value="comments[supplier.id] || ''" @input="updateComment(supplier.id, $event)" placeholder="评审意见"></textarea><button @click="award(supplier.id)" :disabled="!canAward(supplier)">选定供应商</button></article></div><footer v-if="winner">已选定：{{ winner.name }}，综合得分 {{ winner.total }}</footer></section>`,
    css: 'header{display:flex;justify-content:space-between}.matrix-wrap{overflow:auto;margin:12px 0}table{width:100%;border-collapse:collapse}th,td{padding:8px;border:1px solid #cbd5e1;text-align:center}thead th input,tbody td input{width:60px}tbody tr.selected{background:#f0fdfa}.ranking{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.ranking article{display:grid;grid-template-columns:35px 1fr auto;gap:7px;align-items:center;padding:10px;background:#f8fafc}.ranking textarea{grid-column:1/-1}.ranking button{grid-column:1/-1}.ranking article.winner{background:#dcfce7;box-shadow:0 0 0 2px #16a34a}footer{margin-top:10px;padding:12px;background:#dcfce7;color:#166534}'
  };
}

function warehouseWave() {
  return {
    props: {
      warehouseName: ['string', 'A3 智能仓'],
      initialOrders: ['array', [{ id: 'W201', lines: [{ sku: 'K11', bin: 'A-01', qty: 2 }, { sku: 'M20', bin: 'C-04', qty: 1 }] }, { id: 'W202', lines: [{ sku: 'P08', bin: 'B-03', qty: 3 }] }, { id: 'W203', lines: [{ sku: 'K11', bin: 'A-01', qty: 1 }, { sku: 'R77', bin: 'D-02', qty: 2 }] }]],
      pickers: ['array', ['刘佳', '彭越', '宋宁']],
      maxLinesPerWave: ['number', 5],
      zones: ['array', ['A', 'B', 'C', 'D']]
    },
    state: { orders: [], waves: [], selectedOrderIds: [], activeWaveId: null, picker: '刘佳', exceptions: [], nextWaveId: 1 },
    inited: "this.setValue('orders', this.initialOrders.map(order => Object.assign({}, order, { status: 'open', lines: order.lines.map((line, index) => Object.assign({}, line, { id: order.id + '-' + index, picked: false })) })));",
    computed: [
      ['openOrders', "return this.orders.filter(item => item.status === 'open');"],
      ['selectedLineCount', "return this.orders.filter(order => this.selectedOrderIds.indexOf(order.id) >= 0).reduce((sum, order) => sum + order.lines.length, 0);"],
      ['activeWave', "return this.waves.find(item => item.id === this.activeWaveId) || null;"],
      ['activeTasks', "if (!this.activeWave) return []; const ids = this.activeWave.orderIds; return this.orders.filter(order => ids.indexOf(order.id) >= 0).reduce((out, order) => out.concat(order.lines.map(line => Object.assign({}, line, { orderId: order.id }))), []);"],
      ['waveProgress', "return Math.round(this.activeTasks.filter(item => item.picked).length / (this.activeTasks.length || 1) * 100);"],
      ['unresolvedExceptions', "return this.exceptions.filter(item => !item.resolved);"]
    ],
    methods: [
      ['toggleOrder', 'id', "const ids = this.selectedOrderIds; this.setValue('selectedOrderIds', ids.indexOf(id) >= 0 ? ids.filter(item => item !== id) : ids.concat(id));"],
      ['setPicker', 'event', "this.setValue('picker', event.target.value);"],
      ['createWave', '', "if (!this.selectedOrderIds.length || this.selectedLineCount > this.maxLinesPerWave) return; const wave = { id: this.nextWaveId, orderIds: this.selectedOrderIds.slice(), picker: this.picker, status: 'picking' }; const ids = this.selectedOrderIds; this.setValue('waves', this.waves.concat(wave)); this.setValue('orders', this.orders.map(order => ids.indexOf(order.id) >= 0 ? Object.assign({}, order, { status: 'assigned', waveId: wave.id }) : order)); this.setValue('activeWaveId', wave.id); this.setValue('nextWaveId', wave.id + 1); this.setValue('selectedOrderIds', []); this.emitEvent('wave', wave);"],
      ['selectWave', 'id', "this.setValue('activeWaveId', id);"],
      ['togglePicked', 'orderId, lineId', "this.setValue('orders', this.orders.map(order => order.id !== orderId ? order : Object.assign({}, order, { lines: order.lines.map(line => line.id === lineId ? Object.assign({}, line, { picked: !line.picked }) : line) }))); this.emitEvent('pick', { orderId, lineId });"],
      ['reportException', 'task', "this.setValue('exceptions', [{ id: Date.now(), orderId: task.orderId, lineId: task.id, reason: '库位缺货', resolved: false }].concat(this.exceptions));"],
      ['resolveException', 'id', "this.setValue('exceptions', this.exceptions.map(item => item.id === id ? Object.assign({}, item, { resolved: true }) : item)); this.emitEvent('exception', id);"],
      ['completeWave', '', "if (!this.activeWave || this.waveProgress < 100 || this.unresolvedExceptions.length > 0) return; const waveId = this.activeWaveId; this.setValue('waves', this.waves.map(wave => wave.id === waveId ? Object.assign({}, wave, { status: 'completed' }) : wave)); this.setValue('orders', this.orders.map(order => order.waveId === waveId ? Object.assign({}, order, { status: 'completed' }) : order)); this.emitEvent('complete', waveId);"],
      ['isOrderSelected', 'id, selectedOrderIds', "return selectedOrderIds.indexOf(id) >= 0;"]
    ],
    template: `<section class="warehouse-picking-wave"><header><div><small>开放订单 {{ openOrders.length }} · 异常 {{ unresolvedExceptions.length }}</small><h2>{{ warehouseName }} 拣选波次</h2></div><div><select :value="picker" @change="setPicker"><option v-for="person in pickers" :key="person" :value="person">{{ person }}</option></select><button class="primary" @click="createWave" :disabled="!selectedOrderIds.length || selectedLineCount > maxLinesPerWave">组建波次（{{ selectedLineCount }}/{{ maxLinesPerWave }}行）</button></div></header><div class="wave-layout"><aside><h3>订单池</h3><button v-for="order in openOrders" :key="order.id" :class="isOrderSelected(order.id, selectedOrderIds) ? 'selected' : ''" @click="toggleOrder(order.id)"><strong>{{ order.id }}</strong><span>{{ order.lines.length }} 行</span></button><h3>波次</h3><button v-for="wave in waves" :key="wave.id" :class="activeWaveId === wave.id ? 'selected' : ''" @click="selectWave(wave.id)">波次 {{ wave.id }} · {{ wave.picker }} · {{ wave.status }}</button></aside><main><h3>拣选路径 · {{ waveProgress }}%</h3><article v-for="task in activeTasks" :key="task.id" :class="task.picked ? 'picked' : ''"><button @click="togglePicked(task.orderId, task.id)">{{ task.picked ? '✓' : '○' }}</button><b>{{ task.bin }}</b><strong>{{ task.sku }}</strong><span>{{ task.qty }} 件 · {{ task.orderId }}</span><button @click="reportException(task)">报异常</button></article><p v-if="!activeWave">请选择或创建波次</p><button class="primary complete" @click="completeWave" :disabled="waveProgress < 100 || unresolvedExceptions.length > 0">完成波次</button></main><aside class="exceptions"><h3>异常流</h3><article v-for="item in exceptions" :key="item.id" :class="item.resolved ? 'resolved' : ''"><strong>{{ item.orderId }} · {{ item.reason }}</strong><button @click="resolveException(item.id)" :disabled="item.resolved">{{ item.resolved ? '已处理' : '补货完成' }}</button></article></aside></div></section>`,
    css: 'header{display:flex;justify-content:space-between}.wave-layout{display:grid;grid-template-columns:200px 1fr 210px;gap:12px}.wave-layout>aside{padding:10px;background:#f8fafc}.wave-layout>aside>button{display:flex;justify-content:space-between;width:100%;margin:6px 0;text-align:left}.wave-layout>aside>button.selected{background:#fef3c7;border-color:#d97706}.wave-layout main article{display:grid;grid-template-columns:40px 70px 1fr 150px auto;gap:8px;align-items:center;padding:10px;border-bottom:1px solid #e2e8f0}.wave-layout main article.picked{background:#ecfdf5;text-decoration:line-through}.complete{width:100%;margin-top:12px}.exceptions article{padding:8px;margin:7px 0;background:#fee2e2}.exceptions article.resolved{background:#dcfce7;opacity:.7}.exceptions button{display:block;margin-top:5px}'
  };
}

function revenueModeler() {
  return {
    props: {
      modelName: ['string', '订阅收入预测 FY27'],
      plans: ['array', [{ id: 'basic', name: '基础版', price: 39, subscribers: 1200 }, { id: 'pro', name: '专业版', price: 99, subscribers: 420 }, { id: 'enterprise', name: '企业版', price: 399, subscribers: 65 }]],
      months: ['array', ['1月', '2月', '3月', '4月', '5月', '6月']],
      currency: ['string', 'CNY'],
      maxGrowth: ['number', 30]
    },
    state: { growth: 8, churn: 3, expansion: 2, selectedPlanId: 'basic', scenarioName: '稳健增长', scenarios: [], compareId: null },
    computed: [
      ['selectedPlan', "return this.plans.find(item => item.id === this.selectedPlanId) || this.plans[0];"],
      ['forecast', "let subscribers = this.plans.reduce((sum, plan) => sum + plan.subscribers, 0); const averagePrice = this.plans.reduce((sum, plan) => sum + plan.price * plan.subscribers, 0) / (subscribers || 1); return this.months.map((month, index) => { if (index) subscribers = subscribers * (1 + this.growth / 100 - this.churn / 100); const revenue = subscribers * averagePrice * (1 + this.expansion / 100); return { month, subscribers: Math.round(subscribers), revenue: Math.round(revenue) }; });"],
      ['totalRevenue', "return this.forecast.reduce((sum, item) => sum + item.revenue, 0);"],
      ['compareScenario', "return this.scenarios.find(item => item.id === this.compareId) || null;"],
      ['delta', "return this.compareScenario ? this.totalRevenue - this.compareScenario.totalRevenue : 0;"]
    ],
    methods: [
      ['updateRate', 'field, event', "this.setValue(field, Math.max(0, Math.min(this.maxGrowth, Number(event.target.value) || 0)));"],
      ['selectPlan', 'id', "this.setValue('selectedPlanId', id);"],
      ['updateScenarioName', 'event', "this.setValue('scenarioName', event.target.value);"],
      ['saveScenario', '', "const scenario = { id: Date.now(), name: this.scenarioName || '未命名情景', growth: this.growth, churn: this.churn, expansion: this.expansion, totalRevenue: this.totalRevenue, forecast: this.forecast.map(item => Object.assign({}, item)) }; this.setValue('scenarios', [scenario].concat(this.scenarios)); this.setValue('compareId', scenario.id); this.emitEvent('save', scenario);"],
      ['loadScenario', 'id', "const scenario = this.scenarios.find(item => item.id === id); if (!scenario) return; this.setValue('growth', scenario.growth); this.setValue('churn', scenario.churn); this.setValue('expansion', scenario.expansion); this.setValue('compareId', id);"],
      ['exportModel', '', "this.emitEvent('export', { currency: this.currency, forecast: this.forecast, total: this.totalRevenue });"],
      ['barStyle', 'revenue', "const max = Math.max.apply(Math, this.forecast.map(item => item.revenue)); return 'height:' + Math.round(revenue / (max || 1) * 100) + '%';"],
      ['money', 'value', "return this.currency + ' ' + Number(value).toLocaleString();"]
    ],
    template: `<section class="subscription-revenue-modeler"><header><div><small>{{ currency }} · 6个月模型</small><h2>{{ modelName }}</h2></div><button @click="exportModel">导出预测</button></header><div class="model-layout"><aside><h3>情景参数</h3><label>新增率 {{ growth }}%<input type="range" min="0" :max="maxGrowth" :value="growth" @input="updateRate('growth', $event)"></label><label>流失率 {{ churn }}%<input type="range" min="0" :max="maxGrowth" :value="churn" @input="updateRate('churn', $event)"></label><label>扩张收入 {{ expansion }}%<input type="range" min="0" :max="maxGrowth" :value="expansion" @input="updateRate('expansion', $event)"></label><input :value="scenarioName" @input="updateScenarioName"><button class="primary" @click="saveScenario">保存情景</button></aside><main><div class="plans"><button v-for="plan in plans" :key="plan.id" :class="selectedPlanId === plan.id ? 'active' : ''" @click="selectPlan(plan.id)"><strong>{{ plan.name }}</strong><span>{{ money(plan.price) }}/月 · {{ plan.subscribers }}户</span></button></div><div class="chart"><article v-for="point in forecast" :key="point.month"><i :style="barStyle(point.revenue)"></i><strong>{{ point.month }}</strong><small>{{ money(point.revenue) }}</small></article></div><div class="total"><span>累计收入</span><strong>{{ money(totalRevenue) }}</strong><em v-if="compareScenario" :class="delta >= 0 ? 'up' : 'down'">较 {{ compareScenario.name }} {{ delta >= 0 ? '+' : '' }}{{ money(delta) }}</em></div></main><aside class="saved"><h3>已保存情景</h3><button v-for="scenario in scenarios" :key="scenario.id" :class="compareId === scenario.id ? 'active' : ''" @click="loadScenario(scenario.id)"><strong>{{ scenario.name }}</strong><span>新增 {{ scenario.growth }}% / 流失 {{ scenario.churn }}%</span><small>{{ money(scenario.totalRevenue) }}</small></button><p v-if="!scenarios.length">保存后可对比预测</p></aside></div></section>`,
    css: 'header{display:flex;justify-content:space-between}.model-layout{display:grid;grid-template-columns:210px 1fr 220px;gap:14px}.model-layout>aside{padding:12px;background:#f8fafc}.model-layout>aside label{display:grid;margin-bottom:10px}.plans{display:flex;gap:7px}.plans button{display:grid;flex:1}.plans button.active,.saved button.active{background:#ede9fe;border-color:#7c3aed}.chart{height:240px;display:flex;align-items:flex-end;gap:10px;padding-top:25px}.chart article{height:100%;flex:1;display:flex;flex-direction:column;justify-content:flex-end;text-align:center}.chart i{display:block;background:#8b5cf6;min-height:4px}.total{display:flex;gap:14px;align-items:baseline;padding:12px;background:#f5f3ff}.total strong{font-size:24px}.up{color:#15803d}.down{color:#b91c1c}.saved button{display:grid;width:100%;text-align:left;margin-bottom:7px}'
  };
}

function apiWorkbench() {
  return {
    props: {
      serviceName: ['string', '支付服务 API'],
      initialEndpoints: ['array', [{ id: 1, method: 'POST', path: '/payments', summary: '创建支付' }, { id: 2, method: 'GET', path: '/payments/:id', summary: '查询支付' }]],
      authSchemes: ['array', ['Bearer Token', 'API Key', 'None']],
      responseCodes: ['array', [200, 201, 400, 404, 500]],
      readonly: ['bool', false]
    },
    state: { endpoints: [], selectedId: 1, parameters: {}, schemas: {}, auth: 'Bearer Token', issues: [], generated: '', savedRevision: 0, nextParameterId: 10 },
    inited: "this.setValue('endpoints', this.initialEndpoints.map(item => Object.assign({}, item))); const parameters = {}; let nextParameterId = 1; this.initialEndpoints.forEach(item => { const parameterId = item.id * 10; parameters[item.id] = [{ id: parameterId, name: item.method === 'GET' ? 'id' : 'amount', location: item.method === 'GET' ? 'path' : 'body', required: true, type: item.method === 'GET' ? 'string' : 'number' }]; nextParameterId = Math.max(nextParameterId, parameterId + 1); }); this.setValue('parameters', parameters); this.setValue('nextParameterId', nextParameterId); this.validateContract();",
    computed: [
      ['selectedEndpoint', "return this.endpoints.find(item => item.id === this.selectedId) || null;"],
      ['selectedParameters', "return this.parameters[this.selectedId] || [];"],
      ['operationId', "return this.selectedEndpoint ? (this.selectedEndpoint.method.toLowerCase() + this.selectedEndpoint.path.replace(/[^a-zA-Z0-9]+/g, '_')) : '';"],
      ['canGenerate', "return !!this.selectedEndpoint && this.issues.length === 0;"]
    ],
    methods: [
      ['selectEndpoint', 'id', "this.setValue('selectedId', id); this.validateContract();"],
      ['updateEndpoint', 'field, event', "if (this.readonly || !this.selectedEndpoint) return; this.setValue('endpoints', this.endpoints.map(item => item.id === this.selectedId ? Object.assign({}, item, { [field]: event.target.value }) : item)); this.validateContract(); this.emitEvent('change', this.selectedEndpoint);"],
      ['setAuth', 'event', "this.setValue('auth', event.target.value);"],
      ['addParameter', '', "if (this.readonly || !this.selectedEndpoint) return; const id = this.nextParameterId; const list = this.selectedParameters.concat({ id, name: '', location: 'query', required: false, type: 'string' }); this.setValue('parameters', Object.assign({}, this.parameters, { [this.selectedId]: list })); this.setValue('nextParameterId', id + 1); this.validateContract();"],
      ['updateParameter', 'id, field, event', "const value = field === 'required' ? event.target.checked : event.target.value; const list = this.selectedParameters.map(item => item.id === id ? Object.assign({}, item, { [field]: value }) : item); this.setValue('parameters', Object.assign({}, this.parameters, { [this.selectedId]: list })); this.validateContract();"],
      ['removeParameter', 'id', "const list = this.selectedParameters.filter(item => item.id !== id); this.setValue('parameters', Object.assign({}, this.parameters, { [this.selectedId]: list })); this.validateContract();"],
      ['validateContract', '', "const issues = []; if (!this.selectedEndpoint) issues.push('请选择端点'); else { if (this.selectedEndpoint.path.charAt(0) !== '/') issues.push('路径必须以 / 开头'); if (!this.selectedEndpoint.summary.trim()) issues.push('缺少摘要'); const names = {}; this.selectedParameters.forEach(item => { if (!item.name) issues.push('参数名不能为空'); else if (names[item.name]) issues.push('参数名重复：' + item.name); names[item.name] = true; }); } this.setValue('issues', issues); this.emitEvent('validate', issues);"],
      ['generateClient', '', "if (!this.canGenerate) return; const endpoint = this.selectedEndpoint; const code = 'client.' + endpoint.method.toLowerCase() + '(' + endpoint.path + ', payload)'; this.setValue('generated', code); this.emitEvent('generate', code);"],
      ['saveContract', '', "if (!this.canGenerate) return; this.setValue('savedRevision', this.savedRevision + 1); this.emitEvent('save', { revision: this.savedRevision, endpoints: this.endpoints, parameters: this.parameters });"]
    ],
    template: `<section class="api-contract-workbench"><header><div><small>修订版 {{ savedRevision }} · {{ auth }}</small><h2>{{ serviceName }}</h2></div><button class="primary" @click="saveContract" :disabled="!canGenerate">保存契约</button></header><div class="api-layout"><aside><h3>端点</h3><button v-for="endpoint in endpoints" :key="endpoint.id" :class="selectedId === endpoint.id ? 'active' : ''" @click="selectEndpoint(endpoint.id)"><b>{{ endpoint.method }}</b><code>{{ endpoint.path }}</code><span>{{ endpoint.summary }}</span></button></aside><main v-if="selectedEndpoint"><div class="endpoint-form"><select :value="selectedEndpoint.method" @change="updateEndpoint('method', $event)"><option>GET</option><option>POST</option><option>PUT</option><option>DELETE</option></select><input :value="selectedEndpoint.path" @input="updateEndpoint('path', $event)"><input :value="selectedEndpoint.summary" @input="updateEndpoint('summary', $event)"></div><p>operationId: <code>{{ operationId }}</code></p><table><thead><tr><th>参数名</th><th>位置</th><th>类型</th><th>必填</th><th></th></tr></thead><tbody><tr v-for="parameter in selectedParameters" :key="parameter.id"><td><input :value="parameter.name" @input="updateParameter(parameter.id, 'name', $event)"></td><td><select :value="parameter.location" @change="updateParameter(parameter.id, 'location', $event)"><option>query</option><option>path</option><option>body</option><option>header</option></select></td><td><select :value="parameter.type" @change="updateParameter(parameter.id, 'type', $event)"><option>string</option><option>number</option><option>boolean</option><option>object</option></select></td><td><input type="checkbox" :checked="parameter.required" @change="updateParameter(parameter.id, 'required', $event)"></td><td><button @click="removeParameter(parameter.id)">删除</button></td></tr></tbody></table><button @click="addParameter">添加参数</button></main><aside class="preview"><h3>校验与生成</h3><select :value="auth" @change="setAuth"><option v-for="scheme in authSchemes" :key="scheme" :value="scheme">{{ scheme }}</option></select><ul><li v-for="issue in issues" :key="issue">{{ issue }}</li></ul><button @click="generateClient" :disabled="!canGenerate">生成调用代码</button><pre>{{ generated || '校验通过后生成客户端片段' }}</pre></aside></div></section>`,
    css: 'header{display:flex;justify-content:space-between}.api-layout{display:grid;grid-template-columns:220px 1fr 230px;gap:12px}.api-layout>aside{padding:10px;background:#f8fafc}.api-layout>aside>button{display:grid;width:100%;text-align:left;margin-bottom:7px}.api-layout>aside>button.active{background:#e0f2fe;border-color:#0284c7}.endpoint-form{display:grid;grid-template-columns:90px 1fr 1fr;gap:7px}table{width:100%;border-collapse:collapse;margin:10px 0}th,td{padding:6px;border:1px solid #cbd5e1}td input,td select{width:100%;box-sizing:border-box}.preview select,.preview button{width:100%;margin-bottom:8px}.preview ul{padding-left:18px;color:#b91c1c}.preview pre{padding:10px;white-space:pre-wrap;background:#0f172a;color:#e2e8f0}'
  };
}

function crisisHub() {
  return {
    props: {
      incidentTitle: ['string', '区域服务中断通报'],
      audiences: ['array', [{ id: 'customers', name: '受影响客户', count: 1280 }, { id: 'staff', name: '内部员工', count: 230 }, { id: 'media', name: '媒体联系人', count: 18 }]],
      channels: ['array', [{ id: 'sms', name: '短信' }, { id: 'email', name: '邮件' }, { id: 'status', name: '状态页' }]],
      approvers: ['array', ['值班经理', '法务负责人']],
      requiredApprovals: ['number', 2]
    },
    state: { versions: [{ id: 1, subject: '服务异常通知', body: '我们正在处理区域服务中断，下一次更新将在30分钟内发布。', author: '响应组', status: 'draft' }], activeVersionId: 1, selectedAudienceIds: ['customers'], selectedChannelIds: ['email', 'status'], approvals: [], deliveryLog: [], editSubject: '', editBody: '', nextVersionId: 2 },
    inited: "const active = this.versions[0]; this.setValue('editSubject', active.subject); this.setValue('editBody', active.body);",
    computed: [
      ['activeVersion', "return this.versions.find(item => item.id === this.activeVersionId) || null;"],
      ['recipientCount', "return this.audiences.filter(item => this.selectedAudienceIds.indexOf(item.id) >= 0).reduce((sum, item) => sum + item.count, 0);"],
      ['canRequestApproval', "return this.editSubject.trim().length > 0 && this.editBody.trim().length >= 20 && this.selectedAudienceIds.length > 0 && this.selectedChannelIds.length > 0;"],
      ['canSend', "return this.canRequestApproval && this.approvals.length >= this.requiredApprovals && this.activeVersion && this.activeVersion.status === 'approved';"]
    ],
    methods: [
      ['updateDraft', 'field, event', "this.setValue(field, event.target.value); this.setValue('approvals', []); this.setValue('versions', this.versions.map(item => item.id === this.activeVersionId ? Object.assign({}, item, { status: 'draft' }) : item));"],
      ['toggleAudience', 'id', "const ids = this.selectedAudienceIds; this.setValue('selectedAudienceIds', ids.indexOf(id) >= 0 ? ids.filter(item => item !== id) : ids.concat(id)); this.setValue('approvals', []);"],
      ['toggleChannel', 'id', "const ids = this.selectedChannelIds; this.setValue('selectedChannelIds', ids.indexOf(id) >= 0 ? ids.filter(item => item !== id) : ids.concat(id)); this.setValue('approvals', []);"],
      ['saveVersion', '', "if (!this.canRequestApproval) return; const version = { id: this.nextVersionId, subject: this.editSubject, body: this.editBody, author: '响应组', status: 'draft' }; this.setValue('versions', this.versions.concat(version)); this.setValue('activeVersionId', version.id); this.setValue('nextVersionId', version.id + 1); this.setValue('approvals', []); this.emitEvent('version', version);"],
      ['selectVersion', 'id', "const version = this.versions.find(item => item.id === id); if (!version) return; this.setValue('activeVersionId', id); this.setValue('editSubject', version.subject); this.setValue('editBody', version.body); this.setValue('approvals', []);"],
      ['requestApproval', '', "if (!this.canRequestApproval) return; this.setValue('versions', this.versions.map(item => item.id === this.activeVersionId ? Object.assign({}, item, { subject: this.editSubject, body: this.editBody, status: 'reviewing' }) : item)); this.emitEvent('review', this.activeVersionId);"],
      ['approve', 'person', "if (!this.activeVersion || this.activeVersion.status !== 'reviewing' || this.approvals.indexOf(person) >= 0) return; const approvals = this.approvals.concat(person); this.setValue('approvals', approvals); if (approvals.length >= this.requiredApprovals) this.setValue('versions', this.versions.map(item => item.id === this.activeVersionId ? Object.assign({}, item, { status: 'approved' }) : item)); this.emitEvent('approve', { person, versionId: this.activeVersionId });"],
      ['send', '', "if (!this.canSend) return; const deliveries = this.selectedChannelIds.map((channelId, index) => ({ id: Date.now() + index, channelId, recipients: this.recipientCount, status: 'sent' })); this.setValue('deliveryLog', deliveries.concat(this.deliveryLog)); this.setValue('versions', this.versions.map(item => item.id === this.activeVersionId ? Object.assign({}, item, { status: 'sent' }) : item)); this.emitEvent('send', { versionId: this.activeVersionId, audiences: this.selectedAudienceIds, channels: this.selectedChannelIds });"],
      ['isSelected', 'id, list', "return list.indexOf(id) >= 0;"],
      ['hasApproval', 'person, approvals', "return approvals.indexOf(person) >= 0;"]
    ],
    template: `<section class="crisis-communication-hub"><header><div><small>受众 {{ recipientCount }} 人 · 审批 {{ approvals.length }}/{{ requiredApprovals }}</small><h2>{{ incidentTitle }}</h2></div><button class="primary" @click="send" :disabled="!canSend">立即发送</button></header><div class="crisis-layout"><aside><h3>消息版本</h3><button v-for="version in versions" :key="version.id" :class="activeVersionId === version.id ? 'active' : ''" @click="selectVersion(version.id)"><strong>v{{ version.id }} · {{ version.status }}</strong><span>{{ version.subject }}</span></button><button @click="saveVersion">另存为新版本</button></aside><main><label>标题<input :value="editSubject" @input="updateDraft('editSubject', $event)"></label><label>正文<textarea :value="editBody" @input="updateDraft('editBody', $event)"></textarea></label><div class="selectors"><section><h3>受众</h3><button v-for="audience in audiences" :key="audience.id" :class="isSelected(audience.id, selectedAudienceIds) ? 'selected' : ''" @click="toggleAudience(audience.id)">{{ audience.name }} · {{ audience.count }}</button></section><section><h3>渠道</h3><button v-for="channel in channels" :key="channel.id" :class="isSelected(channel.id, selectedChannelIds) ? 'selected' : ''" @click="toggleChannel(channel.id)">{{ channel.name }}</button></section></div><button @click="requestApproval" :disabled="!canRequestApproval">提交审批</button></main><aside class="approval"><h3>审批链</h3><button v-for="person in approvers" :key="person" :class="hasApproval(person, approvals) ? 'approved' : ''" @click="approve(person)">{{ person }} · {{ hasApproval(person, approvals) ? '已批准' : '待批准' }}</button><h3>发送记录</h3><p v-for="entry in deliveryLog" :key="entry.id">{{ entry.channelId }} · {{ entry.recipients }}人 · {{ entry.status }}</p></aside></div></section>`,
    css: 'header{display:flex;justify-content:space-between}.crisis-layout{display:grid;grid-template-columns:200px 1fr 220px;gap:12px}.crisis-layout>aside{padding:10px;background:#f8fafc}.crisis-layout>aside>button{display:grid;width:100%;text-align:left;margin-bottom:7px}.crisis-layout>aside>button.active{background:#fef3c7;border-color:#d97706}.crisis-layout main label{display:grid;margin-bottom:10px}.crisis-layout textarea{min-height:150px}.selectors{display:grid;grid-template-columns:1fr 1fr;gap:10px}.selectors section{padding:10px;border:1px solid #e2e8f0}.selectors button{display:block;width:100%;margin:5px 0}.selectors button.selected{background:#fef3c7}.approval button.approved{background:#dcfce7;color:#166534}.approval p{padding:6px;background:white}'
  };
}

const builders = {
  WorkflowDiagramEditor: workflowDiagram,
  PolicyRuleComposer: policyRule,
  FleetDispatchConsole: fleetDispatch,
  ClinicalTriageBoard: clinicalTriage,
  DependencyReleasePlanner: dependencyRelease,
  EnergyLoadScheduler: energyLoad,
  AuctionControlRoom: auctionRoom,
  ResearchAnnotationStudio: annotationStudio,
  ProcurementBidMatrix: procurementMatrix,
  WarehousePickingWave: warehouseWave,
  SubscriptionRevenueModeler: revenueModeler,
  ApiContractWorkbench: apiWorkbench,
  CrisisCommunicationHub: crisisHub
};

module.exports = function buildComplexImplementation(item) {
  const builder = builders[item.name];
  if (!builder) throw new Error(`Unknown complex component: ${item.name}`);
  return builder(item);
};
