<template>
  <fieldset class="choice-chips">
    <legend>通知频率</legend>
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      :class="{ selected: selected === option.value }"
      @click="select(option.value)"
    >{{ option.label }}</button>
    <p>当前选择：{{ selectedLabel }}</p>
  </fieldset>
</template>

<script>
module.exports = {
  name: 'ChoiceChips',
  props: {
    options: {
      type: Array,
      default: function () {
        return [
          { value: 'instant', label: '即时' },
          { value: 'daily', label: '每日' },
          { value: 'off', label: '关闭' }
        ];
      }
    },
    initialValue: { type: String, default: 'daily' }
  },
  data() {
    const option = this.options.find((item) => item.value === this.initialValue);
    return {
      selected: this.initialValue,
      selectedLabel: option ? option.label : '未选择'
    };
  },
  methods: {
    select(value) {
      const option = this.options.find((item) => item.value === value);
      this.selected = value;
      this.selectedLabel = option ? option.label : '未选择';
    }
  }
};
</script>

<style scoped>
.choice-chips { width: 320px; display: flex; flex-wrap: wrap; gap: 8px; padding: 16px; border: 1px solid #cbd5e1; border-radius: 6px; font-family: Arial, sans-serif; }
.choice-chips legend { padding: 0 6px; font-weight: 700; }
.choice-chips button { padding: 7px 12px; border: 1px solid #94a3b8; border-radius: 18px; background: #ffffff; color: #334155; cursor: pointer; }
.choice-chips button.selected { border-color: #0f766e; background: #ccfbf1; color: #115e59; }
.choice-chips p { flex-basis: 100%; margin: 8px 0 0; color: #64748b; font-size: 13px; }
</style>
