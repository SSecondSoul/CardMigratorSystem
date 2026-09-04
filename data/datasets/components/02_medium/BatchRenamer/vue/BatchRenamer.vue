<template>
  <section class="batch-renamer"><h2>批量重命名</h2><div class="rename-rules"><label>前缀<input :value="prefix" @input="updatePrefix"></label><label>起始序号<input type="number" min="1" :value="startAt" @input="updateStart"></label><button @click="togglePreview">{{ previewVisible ? '隐藏预览' : '显示预览' }}</button></div><p v-if="hasDuplicates" class="warning">新文件名存在冲突</p><table v-if="previewVisible"><thead><tr><th>原文件名</th><th>新文件名</th></tr></thead><tbody><tr v-for="item in previews" :key="item.oldName"><td>{{ item.oldName }}</td><td>{{ item.newName }}</td></tr></tbody></table><button class="primary" @click="apply" :disabled="hasDuplicates || !prefix">应用规则</button></section>
</template>

<script>
module.exports = {
  name: 'BatchRenamer',
  props: {
    files: { type: Array, default: () => ([
          "cover.png",
          "hero.png",
          "thumb.png"
        ]) }
  },
  data() {
    return {
        currentFiles: [],
        prefix: "asset",
        startAt: 1,
        previewVisible: true
    };
  },
  computed: {
    previews() {
      return this.currentFiles.map((oldName, index) => { const dot = oldName.lastIndexOf('.'); const ext = dot >= 0 ? oldName.slice(dot) : ''; return { oldName, newName: this.prefix + '-' + (this.startAt + index) + ext }; });
    },
    hasDuplicates() {
      const names = this.previews.map(item => item.newName); return new Set(names).size !== names.length;
    }
  },
  created() {
    this.setValue('currentFiles', this.files.slice());
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updatePrefix(event) {
      this.setValue('prefix', event.target.value);
    },
    updateStart(event) {
      this.setValue('startAt', Number(event.target.value) || 1);
    },
    togglePreview() {
      this.setValue('previewVisible', !this.previewVisible);
    },
    apply() {
      if (this.hasDuplicates || !this.prefix.trim()) return; const next = this.previews.map(item => item.newName); this.setValue('currentFiles', next); this.emitEvent('apply', next.slice());
    }
  }
};
</script>

<style scoped>

.batch-renamer { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.batch-renamer * { box-sizing: border-box; }
.batch-renamer h2, .batch-renamer h3, .batch-renamer p { margin-top: 0; }
.batch-renamer h2 { margin-bottom: 14px; font-size: 21px; }
.batch-renamer button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.batch-renamer button.primary { border-color: #c2410c; background: #c2410c; color: #fff; }
.batch-renamer button:disabled { opacity: .45; cursor: not-allowed; }
.batch-renamer input, .batch-renamer select, .batch-renamer textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.batch-renamer .toolbar, .batch-renamer .summary, .batch-renamer .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.batch-renamer .muted { color: #71808e; font-size: 12px; }
.batch-renamer .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.rename-rules{display:grid;grid-template-columns:1fr 150px auto;gap:10px;align-items:end}.rename-rules label{display:grid;gap:5px}table{width:100%;margin:14px 0;border-collapse:collapse}th,td{padding:8px;border:1px solid #e0e4e8;text-align:left}.warning{color:#b42318}

</style>
