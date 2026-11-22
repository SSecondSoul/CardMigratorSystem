<template>
  <section class="inline-rename"><h2>文件名称</h2><div v-if="!editing" class="read-row"><strong>{{ name }}</strong><button @click="begin">重命名</button></div><div v-else class="edit-row"><input :value="draft" @input="updateDraft"><button class="primary" @click="save">保存</button><button @click="cancel">取消</button><small v-if="error">{{ error }}</small></div></section>
</template>

<script>
module.exports = {
  name: 'InlineRename',
  props: {
    initialName: { type: String, default: "季度报告" }
  },
  data() {
    return {
        name: "季度报告",
        draft: "",
        editing: false,
        error: ""
    };
  },
  created() {
    this.setValue('name', this.initialName);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    begin() {
      this.setValue('draft', this.name); this.setValue('error', ''); this.setValue('editing', true);
    },
    updateDraft(event) {
      this.setValue('draft', event.target.value);
    },
    save() {
      const value = this.draft.trim(); if (!value) { this.setValue('error', '名称不能为空'); return; } this.setValue('name', value); this.setValue('editing', false);
    },
    cancel() {
      this.setValue('editing', false); this.setValue('error', '');
    }
  }
};
</script>

<style scoped>

.inline-rename { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.inline-rename * { box-sizing: border-box; }
.inline-rename h2, .inline-rename h3, .inline-rename p { margin-top: 0; }
.inline-rename h2 { margin-bottom: 14px; font-size: 21px; }
.inline-rename button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.inline-rename button.primary { border-color: #7c3aed; background: #7c3aed; color: #fff; }
.inline-rename button:disabled { opacity: .45; cursor: not-allowed; }
.inline-rename input, .inline-rename select, .inline-rename textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.inline-rename .toolbar, .inline-rename .summary, .inline-rename .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.inline-rename .muted { color: #71808e; font-size: 12px; }
.inline-rename .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.read-row,.edit-row{display:flex;align-items:center;gap:8px}.read-row strong{margin-right:auto}.edit-row input{flex:1}.edit-row small{width:100%;color:#b42318}

</style>
