<template>
  <section class="price-stepper"><div><h2>手冲咖啡豆</h2><span>¥{{ unitPrice }} / 袋</span></div><div class="step"><button @click="change(-1)" :disabled="quantity <= min">−</button><strong>{{ quantity }}</strong><button @click="change(1)" :disabled="quantity >= max">＋</button></div><output>合计 ¥{{ total }}</output></section>
</template>

<script>
module.exports = {
  name: 'PriceStepper',
  props: {
    unitPrice: { type: Number, default: 36 },
    min: { type: Number, default: 1 },
    max: { type: Number, default: 8 }
  },
  data() {
    return {
        quantity: 1
    };
  },
  computed: {
    total() {
      return (this.unitPrice * this.quantity).toFixed(2);
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    change(delta) {
      const next = Math.max(this.min, Math.min(this.max, this.quantity + delta)); this.setValue('quantity', next); this.emitEvent('change', next);
    }
  }
};
</script>

<style scoped>

.price-stepper{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.price-stepper *{box-sizing:border-box}
.price-stepper h2,.price-stepper h3,.price-stepper p{margin-top:0}
.price-stepper button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.price-stepper button.primary{border-color:#059669;background:#059669;color:#fff}
.price-stepper button:disabled{opacity:.45;cursor:not-allowed}
.price-stepper input,.price-stepper select,.price-stepper textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.price-stepper .muted{color:#71808e;font-size:12px}
.price-stepper .toolbar,.price-stepper .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.price-stepper{display:grid;grid-template-columns:1fr auto;gap:12px}.step{display:flex;align-items:center;gap:10px}.price-stepper output{grid-column:1/-1;padding:12px;background:#ecfdf5;font-size:20px}
</style>
