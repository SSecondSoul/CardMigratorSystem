<template>
  <section :class="'stock-reservation-badge ' + level"><h2>演示设备库存</h2><strong>可用 {{ remaining }}</strong><span>已预留 {{ reserved }}</span><div class="actions"><button @click="release" :disabled="reserved === 0">释放</button><button class="primary" @click="reserve" :disabled="remaining === 0">预留一件</button></div></section>
</template>

<script>
module.exports = {
  name: 'StockReservationBadge',
  props: {
    available: { type: Number, default: 12 },
    warningAt: { type: Number, default: 3 }
  },
  data() {
    return {
        reserved: 0
    };
  },
  computed: {
    remaining() {
      return this.available - this.reserved;
    },
    level() {
      return this.remaining === 0 ? 'empty' : this.remaining <= this.warningAt ? 'low' : 'ok';
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    reserve() {
      this.setValue('reserved', Math.min(this.available, this.reserved + 1));
    },
    release() {
      this.setValue('reserved', Math.max(0, this.reserved - 1));
    }
  }
};
</script>

<style scoped>

.stock-reservation-badge{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.stock-reservation-badge *{box-sizing:border-box}
.stock-reservation-badge h2,.stock-reservation-badge h3,.stock-reservation-badge p{margin-top:0}
.stock-reservation-badge button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.stock-reservation-badge button.primary{border-color:#0f766e;background:#0f766e;color:#fff}
.stock-reservation-badge button:disabled{opacity:.45;cursor:not-allowed}
.stock-reservation-badge input,.stock-reservation-badge select,.stock-reservation-badge textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.stock-reservation-badge .muted{color:#71808e;font-size:12px}
.stock-reservation-badge .toolbar,.stock-reservation-badge .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.stock-reservation-badge>strong{display:block;font-size:32px}.stock-reservation-badge.low>strong{color:#d97706}.stock-reservation-badge.empty>strong{color:#dc2626}.stock-reservation-badge .actions{margin-top:12px}
</style>
