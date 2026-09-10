<template>
  <section class="warehouse-picking-wave"><header><div><small>开放订单 {{ openOrders.length }} · 异常 {{ unresolvedExceptions.length }}</small><h2>{{ warehouseName }} 拣选波次</h2></div><div><select :value="picker" @change="setPicker"><option v-for="person in pickers" :key="person" :value="person">{{ person }}</option></select><button class="primary" @click="createWave" :disabled="!selectedOrderIds.length || selectedLineCount > maxLinesPerWave">组建波次（{{ selectedLineCount }}/{{ maxLinesPerWave }}行）</button></div></header><div class="wave-layout"><aside><h3>订单池</h3><button v-for="order in openOrders" :key="order.id" :class="isOrderSelected(order.id, selectedOrderIds) ? 'selected' : ''" @click="toggleOrder(order.id)"><strong>{{ order.id }}</strong><span>{{ order.lines.length }} 行</span></button><h3>波次</h3><button v-for="wave in waves" :key="wave.id" :class="activeWaveId === wave.id ? 'selected' : ''" @click="selectWave(wave.id)">波次 {{ wave.id }} · {{ wave.picker }} · {{ wave.status }}</button></aside><main><h3>拣选路径 · {{ waveProgress }}%</h3><article v-for="task in activeTasks" :key="task.id" :class="task.picked ? 'picked' : ''"><button @click="togglePicked(task.orderId, task.id)">{{ task.picked ? '✓' : '○' }}</button><b>{{ task.bin }}</b><strong>{{ task.sku }}</strong><span>{{ task.qty }} 件 · {{ task.orderId }}</span><button @click="reportException(task)">报异常</button></article><p v-if="!activeWave">请选择或创建波次</p><button class="primary complete" @click="completeWave" :disabled="waveProgress < 100 || unresolvedExceptions.length > 0">完成波次</button></main><aside class="exceptions"><h3>异常流</h3><article v-for="item in exceptions" :key="item.id" :class="item.resolved ? 'resolved' : ''"><strong>{{ item.orderId }} · {{ item.reason }}</strong><button @click="resolveException(item.id)" :disabled="item.resolved">{{ item.resolved ? '已处理' : '补货完成' }}</button></article></aside></div></section>
</template>

<script>
module.exports = {
  name: 'WarehousePickingWave',
  props: {
    warehouseName: { type: String, default: "A3 智能仓" },
    initialOrders: { type: Array, default: () => ([
          {
            "id": "W201",
            "lines": [
              {
                "sku": "K11",
                "bin": "A-01",
                "qty": 2
              },
              {
                "sku": "M20",
                "bin": "C-04",
                "qty": 1
              }
            ]
          },
          {
            "id": "W202",
            "lines": [
              {
                "sku": "P08",
                "bin": "B-03",
                "qty": 3
              }
            ]
          },
          {
            "id": "W203",
            "lines": [
              {
                "sku": "K11",
                "bin": "A-01",
                "qty": 1
              },
              {
                "sku": "R77",
                "bin": "D-02",
                "qty": 2
              }
            ]
          }
        ]) },
    pickers: { type: Array, default: () => ([
          "刘佳",
          "彭越",
          "宋宁"
        ]) },
    maxLinesPerWave: { type: Number, default: 5 },
    zones: { type: Array, default: () => ([
          "A",
          "B",
          "C",
          "D"
        ]) }
  },
  data() {
    return {
        orders: [],
        waves: [],
        selectedOrderIds: [],
        activeWaveId: null,
        picker: "刘佳",
        exceptions: [],
        nextWaveId: 1
    };
  },
  computed: {
    openOrders() {
      return this.orders.filter(item => item.status === 'open');
    },
    selectedLineCount() {
      return this.orders.filter(order => this.selectedOrderIds.indexOf(order.id) >= 0).reduce((sum, order) => sum + order.lines.length, 0);
    },
    activeWave() {
      return this.waves.find(item => item.id === this.activeWaveId) || null;
    },
    activeTasks() {
      if (!this.activeWave) return []; const ids = this.activeWave.orderIds; return this.orders.filter(order => ids.indexOf(order.id) >= 0).reduce((out, order) => out.concat(order.lines.map(line => Object.assign({}, line, { orderId: order.id }))), []);
    },
    waveProgress() {
      return Math.round(this.activeTasks.filter(item => item.picked).length / (this.activeTasks.length || 1) * 100);
    },
    unresolvedExceptions() {
      return this.exceptions.filter(item => !item.resolved);
    }
  },
  created() {
    this.setValue('orders', this.initialOrders.map(order => Object.assign({}, order, { status: 'open', lines: order.lines.map((line, index) => Object.assign({}, line, { id: order.id + '-' + index, picked: false })) })));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    toggleOrder(id) {
      const ids = this.selectedOrderIds; this.setValue('selectedOrderIds', ids.indexOf(id) >= 0 ? ids.filter(item => item !== id) : ids.concat(id));
    },
    setPicker(event) {
      this.setValue('picker', event.target.value);
    },
    createWave() {
      if (!this.selectedOrderIds.length || this.selectedLineCount > this.maxLinesPerWave) return; const wave = { id: this.nextWaveId, orderIds: this.selectedOrderIds.slice(), picker: this.picker, status: 'picking' }; const ids = this.selectedOrderIds; this.setValue('waves', this.waves.concat(wave)); this.setValue('orders', this.orders.map(order => ids.indexOf(order.id) >= 0 ? Object.assign({}, order, { status: 'assigned', waveId: wave.id }) : order)); this.setValue('activeWaveId', wave.id); this.setValue('nextWaveId', wave.id + 1); this.setValue('selectedOrderIds', []); this.emitEvent('wave', wave);
    },
    selectWave(id) {
      this.setValue('activeWaveId', id);
    },
    togglePicked(orderId, lineId) {
      this.setValue('orders', this.orders.map(order => order.id !== orderId ? order : Object.assign({}, order, { lines: order.lines.map(line => line.id === lineId ? Object.assign({}, line, { picked: !line.picked }) : line) }))); this.emitEvent('pick', { orderId, lineId });
    },
    reportException(task) {
      this.setValue('exceptions', [{ id: Date.now(), orderId: task.orderId, lineId: task.id, reason: '库位缺货', resolved: false }].concat(this.exceptions));
    },
    resolveException(id) {
      this.setValue('exceptions', this.exceptions.map(item => item.id === id ? Object.assign({}, item, { resolved: true }) : item)); this.emitEvent('exception', id);
    },
    completeWave() {
      if (!this.activeWave || this.waveProgress < 100 || this.unresolvedExceptions.length > 0) return; const waveId = this.activeWaveId; this.setValue('waves', this.waves.map(wave => wave.id === waveId ? Object.assign({}, wave, { status: 'completed' }) : wave)); this.setValue('orders', this.orders.map(order => order.waveId === waveId ? Object.assign({}, order, { status: 'completed' }) : order)); this.emitEvent('complete', waveId);
    },
    isOrderSelected(id, selectedOrderIds) {
      return selectedOrderIds.indexOf(id) >= 0;
    }
  }
};
</script>

<style scoped>

.warehouse-picking-wave{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.warehouse-picking-wave *{box-sizing:border-box}
.warehouse-picking-wave h2,.warehouse-picking-wave h3,.warehouse-picking-wave p{margin-top:0}
.warehouse-picking-wave button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.warehouse-picking-wave button.primary{border-color:#ea580c;background:#ea580c;color:#fff}
.warehouse-picking-wave button:disabled{opacity:.45;cursor:not-allowed}
.warehouse-picking-wave input,.warehouse-picking-wave select,.warehouse-picking-wave textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.warehouse-picking-wave .muted{color:#71808e;font-size:12px}
.warehouse-picking-wave .toolbar,.warehouse-picking-wave .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.wave-layout{display:grid;grid-template-columns:200px 1fr 210px;gap:12px}.wave-layout>aside{padding:10px;background:#f8fafc}.wave-layout>aside>button{display:flex;justify-content:space-between;width:100%;margin:6px 0;text-align:left}.wave-layout>aside>button.selected{background:#fef3c7;border-color:#d97706}.wave-layout main article{display:grid;grid-template-columns:40px 70px 1fr 150px auto;gap:8px;align-items:center;padding:10px;border-bottom:1px solid #e2e8f0}.wave-layout main article.picked{background:#ecfdf5;text-decoration:line-through}.complete{width:100%;margin-top:12px}.exceptions article{padding:8px;margin:7px 0;background:#fee2e2}.exceptions article.resolved{background:#dcfce7;opacity:.7}.exceptions button{display:block;margin-top:5px}
</style>
