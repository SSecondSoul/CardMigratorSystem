<template>
  <section class="workflow-diagram-editor"><header><div><small>图校验 · {{ validationErrors.length }} 个问题</small><h2>{{ title }}</h2></div><div><button @click="undo" :disabled="!undoStack.length">撤销</button><button class="primary" @click="run" :disabled="!canRun">模拟运行</button></div></header><nav><button v-for="type in nodeTypes" :key="type" @click="addNode(type)">新增 {{ type }}</button><span>连线：{{ edgeSummary || '暂无' }}</span></nav><div class="diagram-layout"><main class="canvas"><article v-for="node in nodes" :key="node.id" :class="(selectedId === node.id ? 'selected ' : '') + (node.enabled ? '' : 'disabled')" :style="nodeStyle(node)" @click="selectNode(node.id)"><strong>{{ node.label }}</strong><small>{{ node.type }} #{{ node.id }}</small><button @click="beginConnect(node.id)">{{ connectFrom === node.id ? '选择目标' : '连线' }}</button></article></main><aside><h3>节点属性</h3><div v-if="selectedNode"><strong>{{ selectedNode.label }}</strong><p>位置 {{ selectedNode.x }}, {{ selectedNode.y }}</p><div class="nudge"><button @click="nudgeNode(selectedNode.id, -5, 0)">←</button><button @click="nudgeNode(selectedNode.id, 0, -5)">↑</button><button @click="nudgeNode(selectedNode.id, 0, 5)">↓</button><button @click="nudgeNode(selectedNode.id, 5, 0)">→</button></div><button @click="toggleNode(selectedNode.id)">{{ selectedNode.enabled ? '停用' : '启用' }}</button></div><ul><li v-for="error in validationErrors" :key="error">{{ error }}</li></ul></aside></div><footer><span v-for="entry in runLog" :key="entry.id">{{ entry.text }}</span></footer></section>
</template>

<script>
module.exports = {
  name: 'WorkflowDiagramEditor',
  props: {
    title: { type: String, default: "订单履约工作流" },
    initialNodes: { type: Array, default: () => ([
          {
            "id": 1,
            "label": "接收订单",
            "type": "trigger",
            "x": 8,
            "y": 18,
            "enabled": true
          },
          {
            "id": 2,
            "label": "库存校验",
            "type": "condition",
            "x": 38,
            "y": 48,
            "enabled": true
          },
          {
            "id": 3,
            "label": "创建运单",
            "type": "action",
            "x": 70,
            "y": 20,
            "enabled": true
          }
        ]) },
    initialEdges: { type: Array, default: () => ([
          {
            "from": 1,
            "to": 2
          },
          {
            "from": 2,
            "to": 3
          }
        ]) },
    nodeTypes: { type: Array, default: () => ([
          "trigger",
          "condition",
          "action"
        ]) },
    readonly: { type: Boolean, default: false }
  },
  data() {
    return {
        nodes: [],
        edges: [],
        selectedId: null,
        connectFrom: null,
        undoStack: [],
        validationErrors: [],
        runLog: [],
        nextId: 10
    };
  },
  computed: {
    selectedNode() {
      return this.nodes.find(item => item.id === this.selectedId) || null;
    },
    enabledNodes() {
      return this.nodes.filter(item => item.enabled);
    },
    canRun() {
      return this.validationErrors.length === 0 && this.nodes.length > 1;
    },
    edgeSummary() {
      return this.edges.map(edge => edge.from + '→' + edge.to).join('，');
    }
  },
  created() {
    this.setValue('nodes', this.initialNodes.map(item => Object.assign({}, item))); this.setValue('edges', this.initialEdges.map(item => Object.assign({}, item))); this.validateGraph();
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    snapshot() {
      this.setValue('undoStack', [{ nodes: this.nodes.map(item => Object.assign({}, item)), edges: this.edges.map(item => Object.assign({}, item)) }].concat(this.undoStack).slice(0, 8));
    },
    selectNode(id) {
      this.setValue('selectedId', id);
    },
    addNode(type) {
      if (this.readonly) return; this.snapshot(); const id = this.nextId; this.setValue('nodes', this.nodes.concat({ id, label: '新' + type, type, x: 12 + id * 5 % 70, y: 15 + id * 9 % 60, enabled: true })); this.setValue('nextId', id + 1); this.validateGraph();
    },
    nudgeNode(id, dx, dy) {
      if (this.readonly) return; this.snapshot(); this.setValue('nodes', this.nodes.map(node => node.id === id ? Object.assign({}, node, { x: Math.max(0, Math.min(86, node.x + dx)), y: Math.max(0, Math.min(75, node.y + dy)) }) : node)); this.emitEvent('graph-change', { nodes: this.nodes, edges: this.edges });
    },
    beginConnect(id) {
      if (this.connectFrom === null) { this.setValue('connectFrom', id); return; } if (this.connectFrom !== id && !this.edges.some(edge => edge.from === this.connectFrom && edge.to === id)) { this.snapshot(); this.setValue('edges', this.edges.concat({ from: this.connectFrom, to: id })); } this.setValue('connectFrom', null); this.validateGraph();
    },
    toggleNode(id) {
      this.snapshot(); this.setValue('nodes', this.nodes.map(node => node.id === id ? Object.assign({}, node, { enabled: !node.enabled }) : node)); this.validateGraph();
    },
    validateGraph() {
      const ids = this.nodes.map(item => item.id); const incoming = {}; this.edges.forEach(edge => { incoming[edge.to] = true; }); const errors = []; if (!this.nodes.some(item => item.type === 'trigger')) errors.push('缺少触发节点'); this.nodes.forEach((node, index) => { if (index && !incoming[node.id]) errors.push(node.label + ' 没有入边'); }); if (this.edges.some(edge => ids.indexOf(edge.from) < 0 || ids.indexOf(edge.to) < 0)) errors.push('存在悬空连线'); this.setValue('validationErrors', errors); this.emitEvent('validate', errors);
    },
    run() {
      if (!this.canRun) return; this.setValue('runLog', this.enabledNodes.map((node, index) => ({ id: index + 1, text: '执行：' + node.label }))); this.emitEvent('run', this.enabledNodes);
    },
    undo() {
      if (!this.undoStack.length) return; const previous = this.undoStack[0]; this.setValue('nodes', previous.nodes); this.setValue('edges', previous.edges); this.setValue('undoStack', this.undoStack.slice(1)); this.validateGraph();
    },
    nodeStyle(node) {
      return 'left:' + node.x + '%;top:' + node.y + '%';
    }
  }
};
</script>

<style scoped>

.workflow-diagram-editor{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.workflow-diagram-editor *{box-sizing:border-box}
.workflow-diagram-editor h2,.workflow-diagram-editor h3,.workflow-diagram-editor p{margin-top:0}
.workflow-diagram-editor button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.workflow-diagram-editor button.primary{border-color:#7c3aed;background:#7c3aed;color:#fff}
.workflow-diagram-editor button:disabled{opacity:.45;cursor:not-allowed}
.workflow-diagram-editor input,.workflow-diagram-editor select,.workflow-diagram-editor textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.workflow-diagram-editor .muted{color:#71808e;font-size:12px}
.workflow-diagram-editor .toolbar,.workflow-diagram-editor .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header,nav{display:flex;justify-content:space-between;gap:8px;align-items:center}.diagram-layout{display:grid;grid-template-columns:1fr 210px;gap:12px;margin-top:12px}.canvas{position:relative;min-height:360px;background:linear-gradient(#eef2ff 1px,transparent 1px),linear-gradient(90deg,#eef2ff 1px,transparent 1px);background-size:24px 24px}.canvas article{position:absolute;width:130px;padding:10px;background:white;border:2px solid #a5b4fc;border-radius:10px}.canvas article.selected{border-color:#4f46e5;box-shadow:0 0 0 3px #e0e7ff}.canvas article.disabled{opacity:.45}.canvas small,.canvas button{display:block;margin-top:5px}.diagram-layout aside{padding:12px;background:#f8fafc}.nudge{display:grid;grid-template-columns:repeat(4,1fr);gap:4px}.diagram-layout ul{padding-left:18px;color:#b91c1c}footer{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}footer span{padding:5px 8px;background:#ecfdf5}
</style>
