<template>
  <section class="experiment-rollout-console"><header><div><p class="muted">{{ targetMetric }} · {{ statusText() }}</p><h2>{{ experimentName }}</h2></div><div class="actions"><button class="primary" @click="start" :disabled="!canStart">开始</button><button @click="pause" :disabled="status !== 'running'">暂停</button></div></header><div class="rollout-grid"><main><section class="allocation-panel"><h3>流量分配 <span :class="validAllocation ? 'valid' : 'invalid'">{{ allocationTotal }}%</span></h3><label v-for="variant in variants" :key="variant.id"><span>{{ variant.name }}</span><input type="range" :value="variant.allocation" @input="updateAllocation(variant.id, $event)"><output>{{ variant.allocation }}%</output></label></section><table><thead><tr><th>版本</th><th>访客</th><th>转化率</th><th>错误率</th><th>决策</th></tr></thead><tbody><tr v-for="row in metricRows" :key="row.id" :class="rowClass(row)"><td>{{ row.name }}</td><td>{{ row.visitors }}</td><td>{{ row.conversionRate }}%</td><td>{{ row.errorRate }}%</td><td><button @click="declareWinner(row.id)" :disabled="status === 'running' || status === 'completed'">设为胜出</button></td></tr></tbody></table></main><aside><h3>实验历史</h3><ol><li v-for="entry in history" :key="entry.id"><div><strong>{{ entry.label }}</strong><small>{{ entry.status }}</small></div><button @click="rollback(entry)">回滚</button></li></ol><p v-if="!history.length" class="empty">尚无快照</p></aside></div></section>
</template>

<script>
module.exports = {
  name: 'ExperimentRolloutConsole',
  props: {
    experimentName: { type: String, default: "结算页按钮实验" },
    initialVariants: { type: Array, default: () => ([
          {
            "id": "control",
            "name": "原版",
            "allocation": 50
          },
          {
            "id": "new",
            "name": "新版",
            "allocation": 50
          }
        ]) },
    targetMetric: { type: String, default: "转化率" }
  },
  data() {
    return {
        variants: [],
        status: "draft",
        metrics: {},
        history: [],
        winnerId: "",
        tick: 0,
        timer: null
    };
  },
  computed: {
    allocationTotal() {
      return this.variants.reduce((sum, item) => sum + item.allocation, 0);
    },
    validAllocation() {
      return this.allocationTotal === 100;
    },
    metricRows() {
      return this.variants.map(variant => { const metric = this.metrics[variant.id] || { visitors: 0, conversions: 0, errors: 0 }; const visitors = metric.visitors || 1; return { id: variant.id, name: variant.name, visitors: metric.visitors, conversionRate: (metric.conversions / visitors * 100).toFixed(2), errorRate: (metric.errors / visitors * 100).toFixed(2) }; });
    },
    leaderId() {
      const rows = this.metricRows.slice().sort((a, b) => Number(b.conversionRate) - Number(a.conversionRate)); return rows[0] ? rows[0].id : '';
    },
    canStart() {
      return this.validAllocation && this.status !== 'running';
    }
  },
  created() {
    this.setValue('variants', this.initialVariants.map(item => Object.assign({}, item))); const metrics = {}; this.initialVariants.forEach(item => metrics[item.id] = { visitors: 1000, conversions: item.id === 'control' ? 82 : 91, errors: 8 }); this.setValue('metrics', metrics);
  },
  mounted() {
    this._timer = setInterval(() => this.simulateTick(), 2200);
  },
  beforeDestroy() {
    clearInterval(this._timer);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateAllocation(id, event) {
      const value = Math.max(0, Math.min(100, Number(event.target.value) || 0)); this.setValue('variants', this.variants.map(item => item.id === id ? Object.assign({}, item, { allocation: value }) : item)); this.emitEvent('allocation', this.variants);
    },
    start() {
      if (!this.canStart) return; this.snapshot('开始实验'); this.setValue('status', 'running'); this.emitEvent('status', 'running');
    },
    pause() {
      if (this.status !== 'running') return; this.snapshot('暂停实验'); this.setValue('status', 'paused'); this.emitEvent('status', 'paused');
    },
    simulateTick() {
      if (this.status !== 'running') return; const tick = this.tick + 1; const metrics = {}; this.variants.forEach((variant, index) => { const current = this.metrics[variant.id]; metrics[variant.id] = { visitors: current.visitors + variant.allocation * 2, conversions: current.conversions + Math.round(variant.allocation * (index ? .19 : .16)), errors: current.errors + (tick % (index + 3) === 0 ? 1 : 0) }; }); this.setValue('metrics', metrics); this.setValue('tick', tick);
    },
    declareWinner(id) {
      if (this.status === 'running') return; this.setValue('winnerId', id); this.setValue('status', 'completed'); this.snapshot('选定胜出版本'); this.emitEvent('winner', id);
    },
    snapshot(label) {
      this.setValue('history', [{ id: Date.now(), label, status: this.status, variants: this.variants.map(item => Object.assign({}, item)) }].concat(this.history).slice(0, 6));
    },
    rollback(entry) {
      this.setValue('variants', entry.variants.map(item => Object.assign({}, item))); this.setValue('status', entry.status); this.setValue('winnerId', '');
    },
    rowClass(row) {
      return row.id === this.winnerId ? 'winner' : row.id === this.leaderId ? 'leader' : '';
    },
    statusText() {
      return { draft: '草稿', running: '运行中', paused: '已暂停', completed: '已完成' }[this.status];
    }
  }
};
</script>

<style scoped>

.experiment-rollout-console { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.experiment-rollout-console * { box-sizing: border-box; }
.experiment-rollout-console h2, .experiment-rollout-console h3, .experiment-rollout-console p { margin-top: 0; }
.experiment-rollout-console h2 { margin-bottom: 14px; font-size: 21px; }
.experiment-rollout-console button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.experiment-rollout-console button.primary { border-color: #be185d; background: #be185d; color: #fff; }
.experiment-rollout-console button:disabled { opacity: .45; cursor: not-allowed; }
.experiment-rollout-console input, .experiment-rollout-console select, .experiment-rollout-console textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.experiment-rollout-console .toolbar, .experiment-rollout-console .summary, .experiment-rollout-console .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.experiment-rollout-console .muted { color: #71808e; font-size: 12px; }
.experiment-rollout-console .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
header{display:flex;justify-content:space-between}.rollout-grid{display:grid;grid-template-columns:1fr 200px;gap:14px}.allocation-panel{padding:14px;background:#fdf2f8}.allocation-panel h3{display:flex;justify-content:space-between}.valid{color:#15803d}.invalid{color:#b91c1c}.allocation-panel label{display:grid;grid-template-columns:80px 1fr 45px;gap:8px}table{width:100%;margin-top:12px;border-collapse:collapse}th,td{padding:9px;border:1px solid #e3e5e8}tr.leader{background:#fdf2f8}tr.winner{background:#ecfdf5}aside{padding:12px;background:#f8fafc}aside ol{padding:0;list-style:none}aside li{display:flex;justify-content:space-between;padding:8px 0}

</style>
