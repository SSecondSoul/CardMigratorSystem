<template>
  <section class="temperature-dial"><header><h2>室内温度</h2><strong>{{ value }}°C</strong></header><input type="range" :min="min" :max="max" :value="value" @input="update"><div class="scale"><span :style="fillStyle"></span></div><p>{{ comfort }}</p><button @click="reset">恢复推荐温度</button></section>
</template>

<script>
module.exports = {
  name: 'TemperatureDial',
  props: {
    min: { type: Number, default: 16 },
    max: { type: Number, default: 30 },
    recommended: { type: Number, default: 24 }
  },
  data() {
    return {
        value: 24
    };
  },
  computed: {
    comfort() {
      return this.value < 20 ? '偏冷' : this.value > 26 ? '偏热' : '舒适';
    },
    fillStyle() {
      return 'width:' + Math.round((this.value - this.min) / (this.max - this.min) * 100) + '%';
    }
  },
  created() {
    this.setValue('value', this.recommended);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    update(event) {
      const value = Number(event.target.value); this.setValue('value', value); this.emitEvent('change', value);
    },
    reset() {
      this.setValue('value', this.recommended);
    }
  }
};
</script>

<style scoped>

.temperature-dial{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.temperature-dial *{box-sizing:border-box}
.temperature-dial h2,.temperature-dial h3,.temperature-dial p{margin-top:0}
.temperature-dial button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.temperature-dial button.primary{border-color:#ea580c;background:#ea580c;color:#fff}
.temperature-dial button:disabled{opacity:.45;cursor:not-allowed}
.temperature-dial input,.temperature-dial select,.temperature-dial textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.temperature-dial .muted{color:#71808e;font-size:12px}
.temperature-dial .toolbar,.temperature-dial .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.temperature-dial header{display:flex;justify-content:space-between}.temperature-dial input{width:100%}.scale{height:7px;background:#e5e7eb}.scale span{display:block;height:100%;background:#ea580c}
</style>
