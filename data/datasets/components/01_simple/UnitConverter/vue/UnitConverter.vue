<template>
  <section class="unit-converter"><h2>{{ unitLabel }}</h2><div class="converter-grid"><input type="number" min="0" :value="value" @input="updateValue"><button @click="flip">⇄</button><output>{{ result }}</output></div></section>
</template>

<script>
module.exports = {
  name: 'UnitConverter',
  data() {
    return {
        value: 1,
        mode: "metric"
    };
  },
  computed: {
    result() {
      const converted = this.mode === 'metric' ? this.value * 3.28084 : this.value / 3.28084; return converted.toFixed(2);
    },
    unitLabel() {
      return this.mode === 'metric' ? '米 → 英尺' : '英尺 → 米';
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateValue(event) {
      this.setValue('value', Number(event.target.value) || 0);
    },
    flip() {
      this.setValue('mode', this.mode === 'metric' ? 'imperial' : 'metric');
    }
  }
};
</script>

<style scoped>

.unit-converter { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.unit-converter * { box-sizing: border-box; }
.unit-converter h2, .unit-converter h3, .unit-converter p { margin-top: 0; }
.unit-converter h2 { margin-bottom: 14px; font-size: 21px; }
.unit-converter button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.unit-converter button.primary { border-color: #047857; background: #047857; color: #fff; }
.unit-converter button:disabled { opacity: .45; cursor: not-allowed; }
.unit-converter input, .unit-converter select, .unit-converter textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.unit-converter .toolbar, .unit-converter .summary, .unit-converter .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.unit-converter .muted { color: #71808e; font-size: 12px; }
.unit-converter .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.converter-grid{display:grid;grid-template-columns:1fr 46px 1fr;gap:8px;align-items:center}.converter-grid output{padding:10px;background:#ecfdf5;font-weight:700}

</style>
