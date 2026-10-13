<template>
  <section class="status-switch" :class="{ enabled: enabled }">
    <div class="status-copy">
      <strong>{{ label }}</strong>
      <span>{{ enabled ? '已启用' : '已停用' }}</span>
    </div>
    <button type="button" :aria-pressed="enabled" @click="toggle">
      {{ enabled ? '关闭' : '开启' }}
    </button>
  </section>
</template>

<script>
module.exports = {
  name: 'StatusSwitch',
  props: {
    label: { type: String, default: '自动同步' },
    initialEnabled: { type: Boolean, default: false }
  },
  data() {
    return { enabled: this.initialEnabled };
  },
  methods: {
    toggle() {
      this.enabled = !this.enabled;
      this.$emit('change', this.enabled);
    }
  }
};
</script>

<style scoped>
.status-switch { width: 300px; display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 18px; border: 1px solid #cbd5e1; border-left: 5px solid #64748b; border-radius: 6px; background: #ffffff; color: #172026; font-family: Arial, sans-serif; }
.status-switch.enabled { border-left-color: #15803d; background: #f0fdf4; }
.status-copy { display: grid; gap: 5px; }
.status-copy span { color: #64748b; font-size: 13px; }
.status-switch button { min-width: 62px; padding: 8px 12px; border: 1px solid #94a3b8; border-radius: 16px; background: #ffffff; cursor: pointer; }
.status-switch.enabled button { border-color: #15803d; color: #166534; }
</style>
