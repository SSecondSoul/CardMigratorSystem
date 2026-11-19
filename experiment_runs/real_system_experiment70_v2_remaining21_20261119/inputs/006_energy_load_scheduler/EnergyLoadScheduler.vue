<template>
  <section class="energy-load-scheduler"><header><div><small>{{ optimized ? '已自动优化' : '手工排程' }}</small><h2>{{ siteName }}</h2></div><button class="primary" @click="optimize">平衡峰值</button></header><div class="energy-layout"><main><div class="matrix-head"><span>设备 / 小时</span><button v-for="hour in hours" :key="hour" :class="selectedHour === hour ? 'active' : ''" @click="selectHour(hour)">{{ hour }}时</button></div><div v-for="device in devices" :key="device.id" class="device-row"><strong>{{ device.name }}<small>{{ device.kw }} kW</small></strong><button v-for="hour in hours" :key="hour" :class="slotClass(device.id, hour)" @click="toggleSlot(device.id, hour)">{{ schedule[device.id][hour] ? '开' : '—' }}</button></div><div class="load-chart"><i v-for="load, index in hourlyLoads" :key="index" :class="load > capacity ? 'over' : ''" :style="loadStyle(load)"><span>{{ load }}</span></i></div></main><aside><h3>{{ selectedHour }}:00 详情</h3><strong>{{ selectedLoad }} / {{ capacity }} kW</strong><p>峰值 {{ peakLoad }} kW</p><p>预计成本 ¥{{ totalCost }}</p><p class="warn" v-if="violations.length">超限时段：{{ violationsLabel }}</p><input :value="scenarioName" @input="updateScenarioName"><button @click="saveScenario">保存情景</button><ul><li v-for="scenario in savedScenarios" :key="scenario.id">{{ scenario.name }} · ¥{{ scenario.cost }} · {{ scenario.peak }}kW</li></ul></aside></div></section>
</template>

<script>
module.exports = {
  name: 'EnergyLoadScheduler',
  props: {
    siteName: { type: String, default: "微电网负载计划" },
    devices: { type: Array, default: () => ([
          {
            "id": "pump",
            "name": "循环泵",
            "kw": 20
          },
          {
            "id": "chiller",
            "name": "冷水机",
            "kw": 35
          },
          {
            "id": "charge",
            "name": "充电桩",
            "kw": 15
          }
        ]) },
    hours: { type: Array, default: () => ([
          0,
          1,
          2,
          3,
          4,
          5,
          6,
          7
        ]) },
    rates: { type: Array, default: () => ([
          0.42,
          0.38,
          0.36,
          0.4,
          0.55,
          0.72,
          0.9,
          0.8
        ]) },
    capacity: { type: Number, default: 55 }
  },
  data() {
    return {
        schedule: {},
        selectedHour: 0,
        scenarioName: "基准方案",
        savedScenarios: [],
        optimized: false
    };
  },
  computed: {
    hourlyLoads() {
      return this.hours.map(hour => this.devices.reduce((sum, device) => sum + (this.schedule[device.id] && this.schedule[device.id][hour] ? device.kw : 0), 0));
    },
    totalCost() {
      return this.hourlyLoads.reduce((sum, load, index) => sum + load * (this.rates[index] || 0), 0).toFixed(2);
    },
    peakLoad() {
      return Math.max.apply(Math, this.hourlyLoads.concat(0));
    },
    violations() {
      return this.hours.filter((hour, index) => this.hourlyLoads[index] > this.capacity);
    },
    violationsLabel() {
      return this.violations.join('、');
    },
    selectedLoad() {
      const index = this.hours.indexOf(this.selectedHour); return index < 0 ? 0 : this.hourlyLoads[index];
    }
  },
  created() {
    const schedule = {}; this.devices.forEach((device, d) => { schedule[device.id] = {}; this.hours.forEach(hour => { schedule[device.id][hour] = (hour + d) % 3 === 0; }); }); this.setValue('schedule', schedule);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    toggleSlot(deviceId, hour) {
      const deviceSchedule = Object.assign({}, this.schedule[deviceId], { [hour]: !this.schedule[deviceId][hour] }); this.setValue('schedule', Object.assign({}, this.schedule, { [deviceId]: deviceSchedule })); this.setValue('selectedHour', hour); this.setValue('optimized', false); this.emitEvent('schedule', this.schedule);
    },
    selectHour(hour) {
      this.setValue('selectedHour', hour);
    },
    optimize() {
      const schedule = {}; this.devices.forEach((device, deviceIndex) => { schedule[device.id] = {}; this.hours.forEach((hour, hourIndex) => { schedule[device.id][hour] = (hourIndex + deviceIndex * 2) % 5 === 0 && this.rates[hourIndex] < 0.7; }); }); this.setValue('schedule', schedule); this.setValue('optimized', true); this.emitEvent('optimize', { schedule, cost: this.totalCost });
    },
    updateScenarioName(event) {
      this.setValue('scenarioName', event.target.value);
    },
    saveScenario() {
      const scenario = { id: Date.now(), name: this.scenarioName, cost: this.totalCost, peak: this.peakLoad, schedule: JSON.parse(JSON.stringify(this.schedule)) }; this.setValue('savedScenarios', [scenario].concat(this.savedScenarios).slice(0, 4)); this.emitEvent('save', scenario);
    },
    slotClass(deviceId, hour) {
      return this.schedule[deviceId] && this.schedule[deviceId][hour] ? 'on' : 'off';
    },
    loadStyle(load) {
      return 'height:' + Math.min(100, load / this.capacity * 100) + '%';
    }
  }
};
</script>

<style scoped>

.energy-load-scheduler{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.energy-load-scheduler *{box-sizing:border-box}
.energy-load-scheduler h2,.energy-load-scheduler h3,.energy-load-scheduler p{margin-top:0}
.energy-load-scheduler button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.energy-load-scheduler button.primary{border-color:#059669;background:#059669;color:#fff}
.energy-load-scheduler button:disabled{opacity:.45;cursor:not-allowed}
.energy-load-scheduler input,.energy-load-scheduler select,.energy-load-scheduler textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.energy-load-scheduler .muted{color:#71808e;font-size:12px}
.energy-load-scheduler .toolbar,.energy-load-scheduler .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.energy-layout{display:grid;grid-template-columns:1fr 220px;gap:14px}.matrix-head,.device-row{display:grid;grid-template-columns:130px repeat(8,1fr);gap:4px;margin-bottom:4px}.matrix-head button.active{background:#d1fae5}.device-row strong{display:grid}.device-row button.on{background:#059669;color:white}.device-row button.off{background:#f1f5f9;color:#94a3b8}.load-chart{height:130px;display:flex;align-items:flex-end;gap:8px;padding:16px 8px 0;border-bottom:1px solid}.load-chart i{flex:1;min-height:3px;background:#34d399;position:relative}.load-chart i.over{background:#ef4444}.load-chart span{position:absolute;top:-16px;font-size:10px}.energy-layout aside{padding:12px;background:#f8fafc}.energy-layout aside input,.energy-layout aside button{width:100%;margin:5px 0}.warn{color:#b91c1c}
</style>
