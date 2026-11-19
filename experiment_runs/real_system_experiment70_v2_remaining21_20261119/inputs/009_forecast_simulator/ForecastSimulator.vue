<template>
  <main class="forecast-simulator">
    <header class="simulator-header">
      <div><span class="eyebrow">情景推演</span><h1>{{ title }}</h1><p>调整经营假设并比较预测结果</p></div>
      <div class="header-actions">
        <button type="button" class="secondary" @click="reset">恢复基线</button>
        <button type="button" :disabled="running" @click="runSimulation">{{ running ? '计算中' : '运行模拟' }}</button>
      </div>
    </header>
    <section class="simulator-layout">
      <aside class="assumption-panel">
        <div class="panel-title"><strong>模型参数</strong><small>{{ scenarioName }}</small></div>
        <label>初始月收入<input type="number" min="1000" :value="assumptions.baseRevenue" @input="updateAssumption('baseRevenue', $event)" /></label>
        <label>月增长率 %<input type="number" min="-20" max="50" :value="assumptions.monthlyGrowth" @input="updateAssumption('monthlyGrowth', $event)" /></label>
        <label>客户流失率 %<input type="number" min="0" max="30" :value="assumptions.churn" @input="updateAssumption('churn', $event)" /></label>
        <label>营销投入<input type="number" min="0" :value="assumptions.marketing" @input="updateAssumption('marketing', $event)" /></label>
        <label>单位服务成本<input type="number" min="0" :value="assumptions.unitCost" @input="updateAssumption('unitCost', $event)" /></label>
        <button type="button" class="save-scenario" @click="saveScenario">保存当前情景</button>
        <p v-if="error" class="error-message">{{ error }}</p>
      </aside>
      <section class="forecast-panel">
        <div class="metric-tabs">
          <button v-for="metric in metrics" :key="metric.key" type="button" :class="{ active: selectedMetric === metric.key }" @click="selectMetric(metric.key)">{{ metric.label }}</button>
        </div>
        <div class="forecast-chart">
          <div v-for="point in chartBars" :key="point.month" class="bar-column">
            <span class="bar-value">{{ point.label }}</span>
            <span class="bar" :style="{ height: point.height + '%' }"></span>
            <small>M{{ point.month }}</small>
          </div>
        </div>
        <div class="forecast-summary">
          <article><span>累计收入</span><strong>¥{{ formatNumber(totalRevenue) }}</strong></article>
          <article><span>峰值月份</span><strong>M{{ peakMonth }}</strong></article>
          <article><span>期末客户</span><strong>{{ endingCustomers }}</strong></article>
          <article><span>预计利润</span><strong>¥{{ formatNumber(totalProfit) }}</strong></article>
        </div>
        <details class="data-table">
          <summary>查看月度明细</summary>
          <table><thead><tr><th>月份</th><th>收入</th><th>客户</th><th>成本</th><th>利润</th></tr></thead><tbody><tr v-for="row in series" :key="row.month"><td>M{{ row.month }}</td><td>{{ row.revenue }}</td><td>{{ row.customers }}</td><td>{{ row.cost }}</td><td>{{ row.profit }}</td></tr></tbody></table>
        </details>
      </section>
    </section>
    <section class="scenario-panel">
      <div class="panel-title"><strong>已保存情景</strong><span>选择最多两个用于对比</span></div>
      <div class="scenario-list">
        <article v-for="scenario in savedScenarios" :key="scenario.id" :class="{ compared: isCompared(scenario.id, compareIds) }">
          <div><strong>{{ scenario.name }}</strong><small>累计 ¥{{ formatNumber(scenario.totalRevenue) }}</small></div>
          <button type="button" @click="toggleCompare(scenario.id)">{{ isCompared(scenario.id, compareIds) ? '取消对比' : '加入对比' }}</button>
          <button type="button" class="remove" @click="removeScenario(scenario.id)">删除</button>
        </article>
      </div>
      <p v-if="!savedScenarios.length" class="empty-state">尚未保存情景</p>
    </section>
    <footer class="simulator-footer"><span>当前指标：{{ selectedMetricLabel }}</span><span>最后运行：{{ lastRun || '尚未运行' }}</span></footer>
  </main>
</template>

<script>
module.exports = {
  name: 'ForecastSimulator',
  props: {
    title: { type: String, default: '订阅业务预测' },
    scenarioName: { type: String, default: '基础情景' },
    horizon: { type: Number, default: 12 },
    initialAssumptions: { type: Object, default: function () { return { baseRevenue: 80000, monthlyGrowth: 6, churn: 2, marketing: 12000, unitCost: 35 }; } }
  },
  data() {
    return {
      assumptions: Object.assign({}, this.initialAssumptions),
      series: [],
      savedScenarios: [],
      selectedMetric: 'revenue',
      compareIds: [],
      running: false,
      error: '',
      lastRun: '',
      simulationTimer: null,
      nextScenarioId: 1,
      metrics: [{ key: 'revenue', label: '收入' }, { key: 'customers', label: '客户' }, { key: 'profit', label: '利润' }]
    };
  },
  computed: {
    totalRevenue() { return this.series.reduce((sum, row) => sum + row.revenue, 0); },
    totalProfit() { return this.series.reduce((sum, row) => sum + row.profit, 0); },
    peakMonth() {
      if (!this.series.length) return '--';
      return this.series.reduce((best, row) => row.revenue > best.revenue ? row : best, this.series[0]).month;
    },
    endingCustomers() { return this.series.length ? this.series[this.series.length - 1].customers : 0; },
    chartBars() {
      const values = this.series.map((row) => row[this.selectedMetric]);
      const max = Math.max.apply(null, values.concat(1));
      return this.series.map((row) => ({ month: row.month, height: Math.max(4, Math.round((row[this.selectedMetric] / max) * 100)), label: row[this.selectedMetric] }));
    },
    selectedMetricLabel() { const metric = this.metrics.find((item) => item.key === this.selectedMetric); return metric ? metric.label : ''; }
  },
  mounted() { this.runSimulation(); },
  beforeDestroy() { clearTimeout(this.simulationTimer); },
  methods: {
    updateAssumption(key, event) { this.$set(this.assumptions, key, Number(event.target.value)); },
    buildSeries() {
      const rows = [];
      let revenue = this.assumptions.baseRevenue;
      let customers = Math.max(1, Math.round(revenue / 400));
      for (let month = 1; month <= this.horizon; month += 1) {
        const acquired = Math.round(this.assumptions.marketing / 120);
        customers = Math.max(1, Math.round(customers * (1 - this.assumptions.churn / 100) + acquired));
        revenue = Math.round(revenue * (1 + this.assumptions.monthlyGrowth / 100) + acquired * 90);
        const cost = Math.round(customers * this.assumptions.unitCost + this.assumptions.marketing);
        rows.push({ month: month, revenue: revenue, customers: customers, cost: cost, profit: revenue - cost });
      }
      return rows;
    },
    async runSimulation() {
      if (this.assumptions.baseRevenue <= 0 || this.horizon < 1) { this.error = '请输入有效的收入与预测周期'; return; }
      this.running = true; this.error = '';
      await new Promise((resolve) => { this.simulationTimer = setTimeout(resolve, 120); });
      this.series = this.buildSeries();
      this.lastRun = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
      this.running = false;
      this.$emit('run', this.series.slice());
    },
    selectMetric(key) { this.selectedMetric = key; },
    saveScenario() {
      const scenario = { id: this.nextScenarioId++, name: `${this.scenarioName} ${this.savedScenarios.length + 1}`, totalRevenue: this.totalRevenue, assumptions: Object.assign({}, this.assumptions) };
      this.savedScenarios.push(scenario);
    },
    removeScenario(id) { this.savedScenarios = this.savedScenarios.filter((scenario) => scenario.id !== id); this.compareIds = this.compareIds.filter((item) => item !== id); },
    toggleCompare(id) {
      if (this.compareIds.indexOf(id) >= 0) this.compareIds = this.compareIds.filter((item) => item !== id);
      else this.compareIds = this.compareIds.concat(id).slice(-2);
    },
    formatNumber(value) { return Number(value).toLocaleString('zh-CN'); },
    isCompared(id, compareIds) { return compareIds.indexOf(id) >= 0; },
    reset() { this.assumptions = Object.assign({}, this.initialAssumptions); this.compareIds = []; this.runSimulation(); }
  }
};
</script>

<style scoped>
.forecast-simulator { width: 900px; padding: 24px; border: 1px solid #cbd5e1; border-radius: 7px; background: #f8fafc; color: #172026; font-family: Arial, sans-serif; }
.simulator-header { display: flex; justify-content: space-between; gap: 24px; }
.simulator-header h1 { margin: 3px 0; font-size: 24px; }
.simulator-header p, .eyebrow { color: #64748b; font-size: 12px; }
.header-actions { display: flex; gap: 8px; }
.forecast-simulator button { padding: 8px 11px; border: 1px solid #7c2d12; border-radius: 4px; background: #7c2d12; color: #ffffff; cursor: pointer; }
.forecast-simulator button.secondary { border-color: #94a3b8; background: #ffffff; color: #334155; }
.simulator-layout { display: grid; grid-template-columns: 230px 1fr; gap: 16px; margin-top: 20px; }
.assumption-panel { display: grid; gap: 11px; padding: 16px; border: 1px solid #d6d3d1; background: #fff7ed; }
.panel-title { display: flex; justify-content: space-between; gap: 14px; }
.panel-title small, .panel-title span { color: #78716c; font-size: 12px; }
.assumption-panel label { display: grid; gap: 5px; color: #57534e; font-size: 12px; }
.assumption-panel input { padding: 8px; border: 1px solid #a8a29e; background: #ffffff; }
.save-scenario { margin-top: 4px; }
.error-message { color: #b91c1c; font-size: 12px; }
.forecast-panel { padding: 16px; border: 1px solid #d1d5db; background: #ffffff; }
.metric-tabs { display: flex; gap: 5px; }
.metric-tabs button { background: #ffffff; color: #57534e; border-color: #d6d3d1; }
.metric-tabs button.active { background: #ffedd5; border-color: #c2410c; color: #9a3412; }
.forecast-chart { height: 230px; display: grid; grid-template-columns: repeat(12, 1fr); align-items: end; gap: 5px; margin: 18px 0; padding-top: 22px; border-bottom: 1px solid #a8a29e; }
.bar-column { height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; gap: 4px; min-width: 0; }
.bar { width: 70%; min-height: 4px; background: #c2410c; transition: height 0.25s ease; }
.bar-value { overflow: hidden; width: 100%; color: #78716c; font-size: 9px; text-align: center; }
.bar-column small { font-size: 10px; }
.forecast-summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.forecast-summary article { padding: 10px; border-left: 3px solid #c2410c; background: #fff7ed; }
.forecast-summary span { display: block; color: #78716c; font-size: 11px; }
.forecast-summary strong { font-size: 16px; }
.data-table { margin-top: 14px; }
.data-table table { width: 100%; margin-top: 10px; border-collapse: collapse; font-size: 12px; }
.data-table th, .data-table td { padding: 7px; border: 1px solid #e7e5e4; }
.scenario-panel { margin-top: 16px; padding: 16px; border: 1px solid #d1d5db; background: #ffffff; }
.scenario-list { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px; }
.scenario-list article { padding: 10px; border: 1px solid #d6d3d1; }
.scenario-list article.compared { border-color: #c2410c; background: #fff7ed; }
.scenario-list small { display: block; margin: 4px 0 9px; color: #78716c; }
.scenario-list button { padding: 5px 7px; font-size: 11px; }
.scenario-list button.remove { border-color: #a8a29e; background: #ffffff; color: #991b1b; }
.empty-state { text-align: center; color: #a8a29e; }
.simulator-footer { display: flex; justify-content: space-between; margin-top: 14px; color: #64748b; font-size: 12px; }
</style>
