<template>
  <section class="subscription-revenue-modeler"><header><div><small>{{ currency }} · 6个月模型</small><h2>{{ modelName }}</h2></div><button @click="exportModel">导出预测</button></header><div class="model-layout"><aside><h3>情景参数</h3><label>新增率 {{ growth }}%<input type="range" min="0" :max="maxGrowth" :value="growth" @input="updateRate('growth', $event)"></label><label>流失率 {{ churn }}%<input type="range" min="0" :max="maxGrowth" :value="churn" @input="updateRate('churn', $event)"></label><label>扩张收入 {{ expansion }}%<input type="range" min="0" :max="maxGrowth" :value="expansion" @input="updateRate('expansion', $event)"></label><input :value="scenarioName" @input="updateScenarioName"><button class="primary" @click="saveScenario">保存情景</button></aside><main><div class="plans"><button v-for="plan in plans" :key="plan.id" :class="selectedPlanId === plan.id ? 'active' : ''" @click="selectPlan(plan.id)"><strong>{{ plan.name }}</strong><span>{{ money(plan.price) }}/月 · {{ plan.subscribers }}户</span></button></div><div class="chart"><article v-for="point in forecast" :key="point.month"><i :style="barStyle(point.revenue)"></i><strong>{{ point.month }}</strong><small>{{ money(point.revenue) }}</small></article></div><div class="total"><span>累计收入</span><strong>{{ money(totalRevenue) }}</strong><em v-if="compareScenario" :class="delta >= 0 ? 'up' : 'down'">较 {{ compareScenario.name }} {{ delta >= 0 ? '+' : '' }}{{ money(delta) }}</em></div></main><aside class="saved"><h3>已保存情景</h3><button v-for="scenario in scenarios" :key="scenario.id" :class="compareId === scenario.id ? 'active' : ''" @click="loadScenario(scenario.id)"><strong>{{ scenario.name }}</strong><span>新增 {{ scenario.growth }}% / 流失 {{ scenario.churn }}%</span><small>{{ money(scenario.totalRevenue) }}</small></button><p v-if="!scenarios.length">保存后可对比预测</p></aside></div></section>
</template>

<script>
module.exports = {
  name: 'SubscriptionRevenueModeler',
  props: {
    modelName: { type: String, default: "订阅收入预测 FY27" },
    plans: { type: Array, default: () => ([
          {
            "id": "basic",
            "name": "基础版",
            "price": 39,
            "subscribers": 1200
          },
          {
            "id": "pro",
            "name": "专业版",
            "price": 99,
            "subscribers": 420
          },
          {
            "id": "enterprise",
            "name": "企业版",
            "price": 399,
            "subscribers": 65
          }
        ]) },
    months: { type: Array, default: () => ([
          "1月",
          "2月",
          "3月",
          "4月",
          "5月",
          "6月"
        ]) },
    currency: { type: String, default: "CNY" },
    maxGrowth: { type: Number, default: 30 }
  },
  data() {
    return {
        growth: 8,
        churn: 3,
        expansion: 2,
        selectedPlanId: "basic",
        scenarioName: "稳健增长",
        scenarios: [],
        compareId: null
    };
  },
  computed: {
    selectedPlan() {
      return this.plans.find(item => item.id === this.selectedPlanId) || this.plans[0];
    },
    forecast() {
      let subscribers = this.plans.reduce((sum, plan) => sum + plan.subscribers, 0); const averagePrice = this.plans.reduce((sum, plan) => sum + plan.price * plan.subscribers, 0) / (subscribers || 1); return this.months.map((month, index) => { if (index) subscribers = subscribers * (1 + this.growth / 100 - this.churn / 100); const revenue = subscribers * averagePrice * (1 + this.expansion / 100); return { month, subscribers: Math.round(subscribers), revenue: Math.round(revenue) }; });
    },
    totalRevenue() {
      return this.forecast.reduce((sum, item) => sum + item.revenue, 0);
    },
    compareScenario() {
      return this.scenarios.find(item => item.id === this.compareId) || null;
    },
    delta() {
      return this.compareScenario ? this.totalRevenue - this.compareScenario.totalRevenue : 0;
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateRate(field, event) {
      this.setValue(field, Math.max(0, Math.min(this.maxGrowth, Number(event.target.value) || 0)));
    },
    selectPlan(id) {
      this.setValue('selectedPlanId', id);
    },
    updateScenarioName(event) {
      this.setValue('scenarioName', event.target.value);
    },
    saveScenario() {
      const scenario = { id: Date.now(), name: this.scenarioName || '未命名情景', growth: this.growth, churn: this.churn, expansion: this.expansion, totalRevenue: this.totalRevenue, forecast: this.forecast.map(item => Object.assign({}, item)) }; this.setValue('scenarios', [scenario].concat(this.scenarios)); this.setValue('compareId', scenario.id); this.emitEvent('save', scenario);
    },
    loadScenario(id) {
      const scenario = this.scenarios.find(item => item.id === id); if (!scenario) return; this.setValue('growth', scenario.growth); this.setValue('churn', scenario.churn); this.setValue('expansion', scenario.expansion); this.setValue('compareId', id);
    },
    exportModel() {
      this.emitEvent('export', { currency: this.currency, forecast: this.forecast, total: this.totalRevenue });
    },
    barStyle(revenue) {
      const max = Math.max.apply(Math, this.forecast.map(item => item.revenue)); return 'height:' + Math.round(revenue / (max || 1) * 100) + '%';
    },
    money(value) {
      return this.currency + ' ' + Number(value).toLocaleString();
    }
  }
};
</script>

<style scoped>

.subscription-revenue-modeler{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.subscription-revenue-modeler *{box-sizing:border-box}
.subscription-revenue-modeler h2,.subscription-revenue-modeler h3,.subscription-revenue-modeler p{margin-top:0}
.subscription-revenue-modeler button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.subscription-revenue-modeler button.primary{border-color:#0891b2;background:#0891b2;color:#fff}
.subscription-revenue-modeler button:disabled{opacity:.45;cursor:not-allowed}
.subscription-revenue-modeler input,.subscription-revenue-modeler select,.subscription-revenue-modeler textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.subscription-revenue-modeler .muted{color:#71808e;font-size:12px}
.subscription-revenue-modeler .toolbar,.subscription-revenue-modeler .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.model-layout{display:grid;grid-template-columns:210px 1fr 220px;gap:14px}.model-layout>aside{padding:12px;background:#f8fafc}.model-layout>aside label{display:grid;margin-bottom:10px}.plans{display:flex;gap:7px}.plans button{display:grid;flex:1}.plans button.active,.saved button.active{background:#ede9fe;border-color:#7c3aed}.chart{height:240px;display:flex;align-items:flex-end;gap:10px;padding-top:25px}.chart article{height:100%;flex:1;display:flex;flex-direction:column;justify-content:flex-end;text-align:center}.chart i{display:block;background:#8b5cf6;min-height:4px}.total{display:flex;gap:14px;align-items:baseline;padding:12px;background:#f5f3ff}.total strong{font-size:24px}.up{color:#15803d}.down{color:#b91c1c}.saved button{display:grid;width:100%;text-align:left;margin-bottom:7px}
</style>
