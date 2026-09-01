<template>
  <article class="hydration-card" @click="increase">
    <header class="card-header">
      <span class="card-title">{{ title }}</span>
      <strong class="card-value">{{ value }} 毫升</strong>
    </header>
    <p class="card-message">{{ message }}</p>
    <button class="card-action" type="button">增加 250 毫升</button>
  </article>
</template>

<script>
module.exports = {
  name: 'HydrationCard',
  props: {
    title: { type: String, default: '今日饮水' },
    initialValue: { type: Number, default: 1200 }
  },
  data() {
    return {
      value: this.initialValue,
      step: 250,
      message: '保持规律补水'
    };
  },
  methods: {
    increase() {
      this.value += this.step;
    }
  }
};
</script>

<style scoped>
.hydration-card { width: 280px; padding: 18px; border-top: 4px solid #168aad; border-radius: 8px; background: #ffffff; box-shadow: 0 6px 18px rgba(20, 33, 43, 0.12); color: #172026; cursor: pointer; font-family: Arial, sans-serif; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.card-title { font-size: 14px; color: #52606d; }
.card-value { font-size: 24px; color: #168aad; }
.card-message { margin: 14px 0; font-size: 13px; color: #697784; }
.card-action { width: 100%; padding: 8px 10px; border: 0; border-radius: 5px; background: #168aad; color: #ffffff; cursor: pointer; }
</style>
