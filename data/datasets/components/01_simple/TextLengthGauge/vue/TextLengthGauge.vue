<template>
  <label class="text-length-gauge">
    <span class="gauge-title">{{ label }}</span>
    <textarea :maxlength="maxLength" :value="text" @input="updateText"></textarea>
    <span class="gauge-meta">还可输入 {{ remaining }} 字</span>
    <span class="gauge-track">
      <span class="gauge-fill" :style="{ width: progress + '%' }"></span>
    </span>
  </label>
</template>

<script>
module.exports = {
  name: 'TextLengthGauge',
  props: {
    label: { type: String, default: '摘要' },
    initialText: { type: String, default: '' },
    maxLength: { type: Number, default: 80 }
  },
  data() {
    return { text: this.initialText.slice(0, this.maxLength) };
  },
  computed: {
    remaining() { return Math.max(0, this.maxLength - this.text.length); },
    progress() { return Math.round((this.text.length / this.maxLength) * 100); }
  },
  methods: {
    updateText(event) { this.text = event.target.value; }
  }
};
</script>

<style scoped>
.text-length-gauge { width: 320px; display: grid; gap: 9px; padding: 18px; border: 1px solid #d7dce2; border-radius: 5px; background: #ffffff; color: #1f2937; font-family: Arial, sans-serif; }
.gauge-title { font-weight: 700; }
.text-length-gauge textarea { min-height: 72px; resize: vertical; padding: 10px; border: 1px solid #9ca3af; border-radius: 4px; font: inherit; }
.gauge-meta { text-align: right; color: #64748b; font-size: 12px; }
.gauge-track { height: 6px; overflow: hidden; background: #e5e7eb; }
.gauge-fill { display: block; height: 100%; background: #0369a1; transition: width 0.2s ease; }
</style>
