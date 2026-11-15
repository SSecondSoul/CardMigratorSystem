<template>
  <section :class="'budget-threshold ' + (remaining < 0 ? 'over' : 'safe')"><h2>项目预算</h2><input type="number" min="0" :value="amount" @input="updateAmount"><strong>{{ statusText }}</strong><button @click="reset">归零</button></section>
</template>

<script>
module.exports = {
  name: 'BudgetThreshold',
  props: {
    limit: { type: Number, default: 5000 }
  },
  data() {
    return {
        amount: 1200
    };
  },
  computed: {
    remaining() {
      return this.limit - this.amount;
    },
    statusText() {
      return this.remaining < 0 ? '已超支 ' + Math.abs(this.remaining) + ' 元' : '剩余 ' + this.remaining + ' 元';
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateAmount(event) {
      this.setValue('amount', Number(event.target.value) || 0);
    },
    reset() {
      this.setValue('amount', 0);
    }
  }
};
</script>

<style scoped>

.budget-threshold { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.budget-threshold * { box-sizing: border-box; }
.budget-threshold h2, .budget-threshold h3, .budget-threshold p { margin-top: 0; }
.budget-threshold h2 { margin-bottom: 14px; font-size: 21px; }
.budget-threshold button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.budget-threshold button.primary { border-color: #c2410c; background: #c2410c; color: #fff; }
.budget-threshold button:disabled { opacity: .45; cursor: not-allowed; }
.budget-threshold input, .budget-threshold select, .budget-threshold textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.budget-threshold .toolbar, .budget-threshold .summary, .budget-threshold .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.budget-threshold .muted { color: #71808e; font-size: 12px; }
.budget-threshold .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.budget-threshold{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center}.budget-threshold h2{grid-column:1/-1}.budget-threshold strong{color:#15803d}.budget-threshold.over strong{color:#b91c1c}

</style>
