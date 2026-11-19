<template>
  <section class="topology-editor">
    <header class="editor-toolbar">
      <div>
        <p class="eyebrow">网络拓扑</p>
        <h2>{{ title }}</h2>
      </div>
      <div class="toolbar-actions">
        <button type="button" @click="addNode">添加节点</button>
        <button type="button" :class="{ active: connectFromId !== null }" :disabled="selectedId === null" @click="beginConnection">
          {{ connectFromId === null ? '开始连线' : '取消连线' }}
        </button>
        <button type="button" :class="{ active: isSimulating }" @click="toggleSimulation">
          {{ isSimulating ? '停止模拟' : '运行模拟' }}
        </button>
      </div>
      <div class="zoom-control">
        <button type="button" @click="changeZoom(-0.1)">−</button>
        <output>{{ zoomPercent(zoom) }}%</output>
        <button type="button" @click="changeZoom(0.1)">＋</button>
      </div>
    </header>

    <div class="editor-layout">
      <main class="canvas-shell">
        <div class="canvas-grid" :style="canvasStyle">
          <svg class="edge-layer" viewBox="0 0 760 470" preserveAspectRatio="none">
            <line
              v-for="edge in drawableEdges"
              :key="edge.id"
              :x1="edge.from.x"
              :y1="edge.from.y"
              :x2="edge.to.x"
              :y2="edge.to.y"
              :class="{ active: edge.active }"
            ></line>
          </svg>
          <button
            v-for="node in nodes"
            :key="node.id"
            type="button"
            class="topology-node"
            :class="[node.status, { selected: node.id === selectedId, source: node.id === connectFromId }]"
            :style="nodeStyle(node)"
            @click="selectNode(node.id)"
          >
            <span class="node-icon">{{ node.type === 'gateway' ? 'GW' : node.type === 'database' ? 'DB' : 'SV' }}</span>
            <strong>{{ node.name }}</strong>
            <small>{{ statusLabel(node.status) }}</small>
          </button>
        </div>
        <div v-if="connectFromId !== null" class="connection-hint">
          请选择目标节点完成连接
        </div>
      </main>

      <aside class="inspector">
        <div v-if="selectedNode" class="selected-inspector">
          <div class="inspector-heading">
            <div>
              <span>节点检查器</span>
              <h3>{{ selectedNode.name }}</h3>
            </div>
            <i :class="selectedNode.status"></i>
          </div>

          <label class="field-label">
            节点名称
            <input :value="selectedNode.name" @input="renameSelected">
          </label>

          <div class="detail-grid">
            <div><span>类型</span><strong>{{ selectedNode.type }}</strong></div>
            <div><span>连接数</span><strong>{{ selectedConnectionCount }}</strong></div>
            <div><span>X 坐标</span><strong>{{ selectedNode.x }}</strong></div>
            <div><span>Y 坐标</span><strong>{{ selectedNode.y }}</strong></div>
          </div>

          <div class="move-pad">
            <span>调整位置</span>
            <button type="button" class="move-up" @click="nudge(0, -20)">↑</button>
            <button type="button" class="move-left" @click="nudge(-20, 0)">←</button>
            <button type="button" class="move-down" @click="nudge(0, 20)">↓</button>
            <button type="button" class="move-right" @click="nudge(20, 0)">→</button>
          </div>

          <button type="button" class="danger-button" @click="removeSelected">删除节点</button>
        </div>
        <div v-else class="empty-inspector">
          <strong>未选择节点</strong>
          <p>从画布中选择一个节点以查看属性。</p>
        </div>

        <div class="event-log">
          <h3>运行事件</h3>
          <ol>
            <li v-for="entry in eventLog" :key="entry.id">
              <time>{{ entry.time }}</time>
              <span>{{ entry.message }}</span>
            </li>
          </ol>
          <p v-if="eventLog.length === 0">等待拓扑操作</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<script>
module.exports = {
  name: 'TopologyEditor',
  props: {
    title: { type: String, default: '边缘服务部署图' },
    initialNodes: {
      type: Array,
      default: function () {
        return [
          { id: 1, name: '入口网关', type: 'gateway', x: 110, y: 220, status: 'healthy' },
          { id: 2, name: '订单服务', type: 'service', x: 360, y: 110, status: 'healthy' },
          { id: 3, name: '库存服务', type: 'service', x: 360, y: 330, status: 'warning' },
          { id: 4, name: '业务数据库', type: 'database', x: 640, y: 220, status: 'healthy' }
        ];
      }
    },
    initialEdges: {
      type: Array,
      default: function () {
        return [
          { id: 1, from: 1, to: 2, active: true },
          { id: 2, from: 1, to: 3, active: true },
          { id: 3, from: 2, to: 4, active: true },
          { id: 4, from: 3, to: 4, active: false }
        ];
      }
    }
  },
  data() {
    return {
      nodes: this.initialNodes.map((node) => Object.assign({}, node)),
      edges: this.initialEdges.map((edge) => Object.assign({}, edge)),
      selectedId: null,
      connectFromId: null,
      zoom: 1,
      isSimulating: false,
      eventLog: [],
      nextNodeNumber: this.initialNodes.length + 1,
      timer: null,
      statuses: ['healthy', 'warning', 'offline']
    };
  },
  computed: {
    selectedNode() {
      return this.nodes.find((node) => node.id === this.selectedId) || null;
    },
    selectedConnectionCount() {
      return this.edges.filter((edge) => edge.from === this.selectedId || edge.to === this.selectedId).length;
    },
    drawableEdges() {
      return this.edges.map((edge) => ({
        id: edge.id,
        active: edge.active,
        from: this.nodes.find((node) => node.id === edge.from),
        to: this.nodes.find((node) => node.id === edge.to)
      })).filter((edge) => edge.from && edge.to);
    },
    canvasStyle() {
      return { transform: 'scale(' + this.zoom + ')' };
    }
  },
  mounted() {
    this.timer = setInterval(this.simulateTick, 1800);
  },
  beforeDestroy() {
    clearInterval(this.timer);
  },
  methods: {
    selectNode(id) {
      if (this.connectFromId !== null && this.connectFromId !== id) {
        this.completeConnection(id);
        return;
      }
      this.selectedId = id;
    },
    beginConnection() {
      if (this.selectedId === null) return;
      this.connectFromId = this.connectFromId === null ? this.selectedId : null;
    },
    completeConnection(targetId) {
      const exists = this.edges.some((edge) => edge.from === this.connectFromId && edge.to === targetId);
      if (!exists) {
        this.edges.push({ id: Date.now(), from: this.connectFromId, to: targetId, active: true });
        this.addLog('已创建一条节点连接');
        this.$emit('topology-change', { nodes: this.nodes, edges: this.edges });
      }
      this.selectedId = targetId;
      this.connectFromId = null;
    },
    addNode() {
      const id = Date.now();
      this.nodes.push({
        id,
        name: '新服务 ' + this.nextNodeNumber,
        type: 'service',
        x: 180 + (this.nextNodeNumber * 47) % 420,
        y: 90 + (this.nextNodeNumber * 61) % 300,
        status: 'healthy'
      });
      this.nextNodeNumber += 1;
      this.selectedId = id;
      this.addLog('已添加新服务节点');
    },
    removeSelected() {
      if (this.selectedId === null) return;
      const id = this.selectedId;
      this.nodes = this.nodes.filter((node) => node.id !== id);
      this.edges = this.edges.filter((edge) => edge.from !== id && edge.to !== id);
      this.selectedId = null;
      this.connectFromId = null;
      this.addLog('节点及关联连线已删除');
      this.$emit('topology-change', { nodes: this.nodes, edges: this.edges });
    },
    renameSelected(event) {
      if (this.selectedNode) this.selectedNode.name = event.target.value;
    },
    nudge(deltaX, deltaY) {
      if (!this.selectedNode) return;
      this.selectedNode.x = Math.max(50, Math.min(710, this.selectedNode.x + deltaX));
      this.selectedNode.y = Math.max(50, Math.min(420, this.selectedNode.y + deltaY));
    },
    changeZoom(delta) {
      this.zoom = Math.max(0.7, Math.min(1.3, Number((this.zoom + delta).toFixed(1))));
    },
    zoomPercent(value) {
      return Math.round(Number(value) * 100);
    },
    toggleSimulation() {
      this.isSimulating = !this.isSimulating;
      this.addLog(this.isSimulating ? '状态模拟已启动' : '状态模拟已停止');
    },
    simulateTick() {
      if (!this.isSimulating || this.nodes.length === 0) return;
      const index = Math.floor(Date.now() / 1800) % this.nodes.length;
      const node = this.nodes[index];
      const statusIndex = this.statuses.indexOf(node.status);
      node.status = this.statuses[(statusIndex + 1) % this.statuses.length];
      this.edges = this.edges.map((edge) => Object.assign({}, edge, {
        active: this.nodes.some((item) => (item.id === edge.from || item.id === edge.to) && item.status !== 'offline')
      }));
      this.addLog(node.name + ' 切换为' + this.statusLabel(node.status));
    },
    addLog(message) {
      this.eventLog.unshift({
        id: Date.now() + Math.random(),
        time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
        message
      });
      this.eventLog = this.eventLog.slice(0, 6);
    },
    nodeStyle(node) {
      return { left: node.x + 'px', top: node.y + 'px' };
    },
    statusLabel(status) {
      return { healthy: '正常', warning: '告警', offline: '离线' }[status] || '未知';
    }
  }
};
</script>

<style scoped>
.topology-editor { max-width: 1120px; min-height: 650px; margin: 0 auto; overflow: hidden; border: 1px solid #d4d9df; background: #f3f5f7; color: #202b37; font-family: Arial, sans-serif; }
.editor-toolbar { display: grid; grid-template-columns: 1fr auto auto; align-items: center; padding: 16px 20px; gap: 22px; border-bottom: 1px solid #d4d9df; background: #ffffff; }
.editor-toolbar h2 { margin: 2px 0 0; font-size: 20px; }
.eyebrow { margin: 0; color: #6e7885; font-size: 11px; text-transform: uppercase; }
.toolbar-actions { display: flex; gap: 7px; }
.toolbar-actions button, .zoom-control button { padding: 8px 10px; border: 1px solid #bfc7d1; border-radius: 4px; background: #ffffff; color: #344251; cursor: pointer; }
.toolbar-actions button.active { border-color: #396a93; background: #e8f1f8; color: #214e72; }
.toolbar-actions button:disabled { opacity: .42; cursor: not-allowed; }
.zoom-control { display: grid; grid-template-columns: 30px 48px 30px; align-items: center; text-align: center; }
.zoom-control button { padding: 7px 0; }
.zoom-control output { color: #566474; font-size: 12px; }
.editor-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; min-height: 580px; }
.canvas-shell { display: flex; min-width: 0; align-items: center; justify-content: center; position: relative; overflow: auto; background: #e9edf1; }
.canvas-grid { width: 760px; height: 470px; position: relative; flex: 0 0 auto; transform-origin: center; border: 1px solid #cad1d9; background-color: #f9fafb; background-image: linear-gradient(#dde3e9 1px, transparent 1px), linear-gradient(90deg, #dde3e9 1px, transparent 1px); background-size: 24px 24px; transition: transform .18s ease; }
.edge-layer { width: 100%; height: 100%; position: absolute; inset: 0; overflow: visible; pointer-events: none; }
.edge-layer line { stroke: #9ba8b5; stroke-width: 3; stroke-dasharray: 7 5; }
.edge-layer line.active { stroke: #3b789f; stroke-dasharray: none; }
.topology-node { display: grid; width: 116px; min-height: 76px; padding: 9px; place-items: center; position: absolute; transform: translate(-50%, -50%); border: 2px solid #87a1b4; border-radius: 6px; background: #ffffff; color: #22313e; box-shadow: 0 5px 14px rgba(47, 61, 73, .12); cursor: pointer; z-index: 2; }
.topology-node.selected { outline: 3px solid rgba(42, 116, 161, .22); border-color: #2a74a1; }
.topology-node.source { outline: 3px dashed #d09025; }
.topology-node.warning { border-color: #d29a35; background: #fff9eb; }
.topology-node.offline { border-color: #a6adb5; background: #eceff2; color: #6d7680; filter: grayscale(1); }
.node-icon { display: grid; width: 30px; height: 25px; place-items: center; border-radius: 3px; background: #334e5c; color: #ffffff; font-size: 10px; font-weight: 700; }
.topology-node strong { font-size: 12px; }
.topology-node small { color: #687685; font-size: 10px; }
.connection-hint { bottom: 16px; left: 50%; position: absolute; transform: translateX(-50%); padding: 8px 12px; border-radius: 4px; background: #243746; color: #ffffff; font-size: 12px; }
.inspector { padding: 18px; background: #ffffff; border-left: 1px solid #d4d9df; }
.inspector-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 17px; }
.inspector-heading span { color: #77818d; font-size: 11px; }
.inspector-heading h3 { margin: 3px 0 0; font-size: 17px; }
.inspector-heading i { width: 11px; height: 11px; border-radius: 50%; background: #4c9b68; }
.inspector-heading i.warning { background: #d59a2d; }
.inspector-heading i.offline { background: #8b929a; }
.field-label { display: grid; gap: 6px; color: #5c6875; font-size: 12px; }
.field-label input { padding: 8px; border: 1px solid #c7ced6; border-radius: 3px; font: inherit; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; margin: 16px 0; gap: 8px; }
.detail-grid div { display: grid; padding: 9px; gap: 3px; background: #f2f5f7; }
.detail-grid span { color: #7b8591; font-size: 10px; }
.detail-grid strong { font-size: 12px; }
.move-pad { display: grid; grid-template-columns: repeat(3, 34px); grid-template-rows: auto repeat(2, 34px); justify-content: center; margin: 15px 0; gap: 3px; }
.move-pad span { grid-column: 1 / -1; margin-bottom: 5px; color: #65717d; text-align: center; font-size: 11px; }
.move-pad button { border: 1px solid #c6ced6; background: #f8f9fa; cursor: pointer; }
.move-up { grid-column: 2; }
.move-left { grid-column: 1; grid-row: 3; }
.move-down { grid-column: 2; grid-row: 3; }
.move-right { grid-column: 3; grid-row: 3; }
.danger-button { width: 100%; padding: 8px; border: 1px solid #cf8d85; border-radius: 3px; background: #fff5f3; color: #a23d32; cursor: pointer; }
.empty-inspector { padding: 28px 4px; color: #6e7885; text-align: center; }
.empty-inspector p { line-height: 1.5; font-size: 12px; }
.event-log { margin-top: 22px; padding-top: 16px; border-top: 1px solid #e0e4e8; }
.event-log h3 { margin: 0 0 10px; font-size: 13px; }
.event-log ol { margin: 0; padding: 0; list-style: none; }
.event-log li { display: grid; grid-template-columns: 58px 1fr; padding: 7px 0; gap: 7px; border-bottom: 1px solid #edf0f2; font-size: 11px; }
.event-log time { color: #81909d; font-variant-numeric: tabular-nums; }
.event-log p { color: #8b949e; font-size: 11px; }
@media (max-width: 820px) { .editor-toolbar { grid-template-columns: 1fr; } .editor-layout { grid-template-columns: 1fr; } .canvas-shell { min-height: 520px; } .inspector { border-top: 1px solid #d4d9df; border-left: 0; } }
</style>
