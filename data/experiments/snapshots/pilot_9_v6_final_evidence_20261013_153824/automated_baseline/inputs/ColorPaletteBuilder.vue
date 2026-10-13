<template>
  <section class="color-palette-builder"><header><h2>品牌色板</h2><button @click="exportPalette">导出</button></header><div class="preview" :style="previewStyle"></div><div class="swatches"><article v-for="color, index in colors" :key="index" :style="'border-color:' + color"><i :style="'background:' + color"></i><code>{{ color }}</code><button @click="toggleLock(index)">{{ isLocked(index, locked) ? '解锁' : '锁定' }}</button><button @click="remove(index)" :disabled="isLocked(index, locked)">删除</button></article></div><div class="add-color"><input type="color" :value="draft" @input="updateDraft"><button class="primary" @click="add" :disabled="!canAdd">添加颜色</button></div></section>
</template>

<script>
module.exports = {
  name: 'ColorPaletteBuilder',
  props: {
    initialColors: { type: Array, default: () => ([
          "#2563eb",
          "#7c3aed",
          "#059669"
        ]) },
    maxColors: { type: Number, default: 6 }
  },
  data() {
    return {
        colors: [],
        draft: "#dc2626",
        locked: [],
        selectedIndex: 0
    };
  },
  computed: {
    previewStyle() {
      return 'background:linear-gradient(90deg,' + this.colors.join(',') + ')';
    },
    canAdd() {
      return this.colors.length < this.maxColors;
    }
  },
  created() {
    this.setValue('colors', this.initialColors.slice());
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateDraft(event) {
      this.setValue('draft', event.target.value);
    },
    add() {
      if (!this.canAdd) return; this.setValue('colors', this.colors.concat(this.draft)); this.notify();
    },
    remove(index) {
      if (this.locked.indexOf(index) >= 0) return; this.setValue('colors', this.colors.filter((item, i) => i !== index)); this.notify();
    },
    toggleLock(index) {
      const list = this.locked; this.setValue('locked', list.indexOf(index) >= 0 ? list.filter(item => item !== index) : list.concat(index));
    },
    isLocked(index, locked) {
      return locked.indexOf(index) >= 0;
    },
    notify() {
      this.emitEvent('change', this.colors.slice());
    },
    exportPalette() {
      this.emitEvent('export', this.colors.join(','));
    }
  }
};
</script>

<style scoped>

.color-palette-builder{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.color-palette-builder *{box-sizing:border-box}
.color-palette-builder h2,.color-palette-builder h3,.color-palette-builder p{margin-top:0}
.color-palette-builder button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.color-palette-builder button.primary{border-color:#9333ea;background:#9333ea;color:#fff}
.color-palette-builder button:disabled{opacity:.45;cursor:not-allowed}
.color-palette-builder input,.color-palette-builder select,.color-palette-builder textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.color-palette-builder .muted{color:#71808e;font-size:12px}
.color-palette-builder .toolbar,.color-palette-builder .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.preview{height:60px;margin:12px 0}.swatches{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.swatches article{display:grid;grid-template-columns:32px 1fr auto auto;gap:6px;align-items:center;padding:8px;border-left:5px solid}.swatches i{height:28px}.add-color{display:flex;gap:8px;margin-top:12px}
</style>
