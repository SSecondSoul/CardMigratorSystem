<template>
  <section class="sort-cycle-button"><span>{{ fieldLabel }}</span><button :class="direction" @click="cycle">{{ buttonLabel }}</button></section>
</template>

<script>
module.exports = {
  name: 'SortCycleButton',
  props: {
    fieldLabel: { type: String, default: "更新时间" }
  },
  data() {
    return {
        direction: "none"
    };
  },
  computed: {
    buttonLabel() {
      return this.direction === 'none' ? '不排序' : this.direction === 'asc' ? '升序 ↑' : '降序 ↓';
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    cycle() {
      const order = ['none', 'asc', 'desc']; const index = order.indexOf(this.direction); const next = order[(index + 1) % order.length]; this.setValue('direction', next); this.emitEvent('change', next);
    }
  }
};
</script>

<style scoped>

.sort-cycle-button { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.sort-cycle-button * { box-sizing: border-box; }
.sort-cycle-button h2, .sort-cycle-button h3, .sort-cycle-button p { margin-top: 0; }
.sort-cycle-button h2 { margin-bottom: 14px; font-size: 21px; }
.sort-cycle-button button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.sort-cycle-button button.primary { border-color: #475569; background: #475569; color: #fff; }
.sort-cycle-button button:disabled { opacity: .45; cursor: not-allowed; }
.sort-cycle-button input, .sort-cycle-button select, .sort-cycle-button textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.sort-cycle-button .toolbar, .sort-cycle-button .summary, .sort-cycle-button .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sort-cycle-button .muted { color: #71808e; font-size: 12px; }
.sort-cycle-button .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.sort-cycle-button{display:flex;align-items:center;justify-content:space-between}.sort-cycle-button button.asc{border-color:#15803d;color:#15803d}.sort-cycle-button button.desc{border-color:#b91c1c;color:#b91c1c}

</style>
