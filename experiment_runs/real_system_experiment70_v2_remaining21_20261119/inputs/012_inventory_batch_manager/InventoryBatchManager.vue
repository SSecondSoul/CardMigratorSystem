<template>
  <section class="inventory-batch-manager"><header class="page-head"><div><p class="muted">最后同步 {{ lastSynced }}</p><h2>{{ title }}</h2></div><button @click="exportData">导出视图</button></header><div class="metric-strip"><article><span>库存件数</span><strong>{{ summary.units }}</strong></article><article><span>临期批次</span><strong>{{ summary.expiring }}</strong></article><article><span>低库存</span><strong>{{ summary.low }}</strong></article></div><div class="toolbar"><select :value="warehouse" @change="updateWarehouse"><option value="all">全部仓库</option><option v-for="item in warehouses" :key="item" :value="item">{{ item }}</option></select><label><input type="checkbox" :checked="riskOnly" @change="toggleRisk"> 仅看风险</label><button @click="selectVisible">全选结果</button><button @click="undo" :disabled="!history.length">撤销</button></div><div class="inventory-layout"><div><table><thead><tr><th></th><th>批次</th><th>仓库</th><th>库存</th><th>保质期</th></tr></thead><tbody><tr v-for="batch in visibleBatches" :key="batch.id" :class="batchRowClass(batch)"><td><input type="checkbox" :checked="isSelected(batch.id)" @change="toggleBatch(batch.id)"></td><td><strong>{{ batch.product }}</strong><small>{{ batch.sku }}</small></td><td>{{ batch.warehouse }}</td><td><div class="stock-bar"><span :style="stockStyle(batch)"></span></div>{{ batch.quantity }}/{{ batch.capacity }}</td><td>{{ batch.expiryDays }} 天</td></tr></tbody></table><p v-if="!visibleBatches.length" class="empty">没有匹配批次</p></div><aside><h3>批量调整</h3><p>已选 {{ selectedCount }} 批</p><label>数量变化<input type="number" :value="adjustment" @input="updateAdjustment"></label><label>原因<select :value="reason" @change="updateReason"><option>盘点修正</option><option>损耗登记</option><option>入库补录</option></select></label><button class="primary" @click="applyAdjustment" :disabled="!canApply">应用</button><h3>操作历史</h3><ol><li v-for="entry in history" :key="entry.id">{{ entry.reason }}：{{ entry.count }} 批</li></ol></aside></div></section>
</template>

<script>
module.exports = {
  name: 'InventoryBatchManager',
  props: {
    title: { type: String, default: "冷链库存控制台" },
    warehouses: { type: Array, default: () => ([
          "华东仓",
          "华南仓"
        ]) },
    initialBatches: { type: Array, default: () => ([
          {
            "id": 1,
            "sku": "FD-101",
            "product": "鲜奶",
            "warehouse": "华东仓",
            "quantity": 38,
            "capacity": 80,
            "expiryDays": 2
          },
          {
            "id": 2,
            "sku": "FD-205",
            "product": "酸奶",
            "warehouse": "华东仓",
            "quantity": 64,
            "capacity": 80,
            "expiryDays": 8
          },
          {
            "id": 3,
            "sku": "FR-311",
            "product": "果汁",
            "warehouse": "华南仓",
            "quantity": 21,
            "capacity": 60,
            "expiryDays": 14
          },
          {
            "id": 4,
            "sku": "FD-402",
            "product": "奶酪",
            "warehouse": "华南仓",
            "quantity": 9,
            "capacity": 40,
            "expiryDays": 1
          }
        ]) }
  },
  data() {
    return {
        batches: [],
        warehouse: "all",
        riskOnly: false,
        selectedIds: [],
        adjustment: 0,
        reason: "盘点修正",
        history: [],
        lastSynced: "",
        timer: null
    };
  },
  computed: {
    visibleBatches() {
      return this.batches.filter(item => (this.warehouse === 'all' || item.warehouse === this.warehouse) && (!this.riskOnly || item.expiryDays <= 3 || item.quantity <= 10));
    },
    summary() {
      return this.batches.reduce((result, item) => { result.units += item.quantity; if (item.expiryDays <= 3) result.expiring += 1; if (item.quantity <= 10) result.low += 1; return result; }, { units: 0, expiring: 0, low: 0 });
    },
    selectedCount() {
      return this.selectedIds.length;
    },
    canApply() {
      return this.selectedCount > 0 && this.adjustment !== 0;
    }
  },
  watch: {
    warehouse() {
      this.setValue('selectedIds', []);
    }
  },
  created() {
    this.setValue('batches', this.initialBatches.map(item => Object.assign({}, item)));
  },
  mounted() {
    this.refreshClock(); this._timer = setInterval(() => this.refreshClock(), 30000);
  },
  beforeDestroy() {
    clearInterval(this._timer);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    refreshClock() {
      this.setValue('lastSynced', new Date().toLocaleTimeString('zh-CN', { hour12: false }));
    },
    updateWarehouse(event) {
      this.setValue('warehouse', event.target.value);
    },
    toggleRisk(event) {
      this.setValue('riskOnly', event.target.checked);
    },
    isSelected(id) {
      return this.selectedIds.indexOf(id) >= 0;
    },
    toggleBatch(id) {
      const list = this.selectedIds; this.setValue('selectedIds', list.indexOf(id) >= 0 ? list.filter(item => item !== id) : list.concat(id));
    },
    selectVisible() {
      this.setValue('selectedIds', this.visibleBatches.map(item => item.id));
    },
    updateAdjustment(event) {
      this.setValue('adjustment', Number(event.target.value) || 0);
    },
    updateReason(event) {
      this.setValue('reason', event.target.value);
    },
    applyAdjustment() {
      if (!this.canApply) return; const ids = this.selectedIds; const before = this.batches.map(item => Object.assign({}, item)); const next = this.batches.map(item => ids.indexOf(item.id) >= 0 ? Object.assign({}, item, { quantity: Math.max(0, Math.min(item.capacity, item.quantity + this.adjustment)) }) : item); this.setValue('batches', next); this.setValue('history', [{ id: Date.now(), reason: this.reason, count: ids.length, delta: this.adjustment, before }].concat(this.history).slice(0, 5)); this.setValue('selectedIds', []); this.setValue('adjustment', 0); this.emitEvent('inventory-change', next);
    },
    undo() {
      const history = this.history; if (!history.length) return; this.setValue('batches', history[0].before.map(item => Object.assign({}, item))); this.setValue('history', history.slice(1)); this.emitEvent('inventory-change', this.batches);
    },
    exportData() {
      this.emitEvent('export', this.visibleBatches);
    },
    stockStyle(batch) {
      return 'width:' + Math.round(batch.quantity / batch.capacity * 100) + '%';
    },
    batchRowClass(batch) {
      return (this.isSelected(batch.id) ? 'selected ' : '') + (batch.expiryDays <= 3 ? 'risk' : '');
    }
  }
};
</script>

<style scoped>

.inventory-batch-manager { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.inventory-batch-manager * { box-sizing: border-box; }
.inventory-batch-manager h2, .inventory-batch-manager h3, .inventory-batch-manager p { margin-top: 0; }
.inventory-batch-manager h2 { margin-bottom: 14px; font-size: 21px; }
.inventory-batch-manager button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.inventory-batch-manager button.primary { border-color: #0f766e; background: #0f766e; color: #fff; }
.inventory-batch-manager button:disabled { opacity: .45; cursor: not-allowed; }
.inventory-batch-manager input, .inventory-batch-manager select, .inventory-batch-manager textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.inventory-batch-manager .toolbar, .inventory-batch-manager .summary, .inventory-batch-manager .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.inventory-batch-manager .muted { color: #71808e; font-size: 12px; }
.inventory-batch-manager .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.page-head,.metric-strip{display:flex;justify-content:space-between}.metric-strip{margin:12px 0;gap:8px}.metric-strip article{flex:1;padding:12px;background:#edf7f5}.metric-strip strong{display:block;font-size:23px}.inventory-layout{display:grid;grid-template-columns:1fr 200px;gap:14px}table{width:100%;border-collapse:collapse}th,td{padding:9px;border-bottom:1px solid #e0e5e9;text-align:left}td small{display:block}tr.selected{background:#ecfdf5}tr.risk{box-shadow:inset 3px 0 #dc2626}.stock-bar{width:75px;height:6px;background:#e5e7eb}.stock-bar span{display:block;height:100%;background:#0f766e}aside{padding:12px;background:#f7f9fa}aside label{display:grid;gap:5px;margin:8px 0}

</style>
