<template>
  <section class="breadcrumb-navigator"><h2>目录定位</h2><nav><button @click="navigate(-1)">根目录</button><span v-for="item, index in pathItems" :key="index"><b>/</b><button :class="index === pathItems.length - 1 ? 'current' : ''" @click="navigate(index)">{{ item }}</button></span></nav><div class="location-card"><span class="muted">当前位置 · 深度 {{ depth }}</span><strong>{{ current }}</strong></div><form @submit="addLevel"><input :value="draft" @input="updateDraft" placeholder="新建子目录"><button class="primary" type="submit">进入新层级</button></form><div class="actions"><button @click="removeLast" :disabled="!pathItems.length">返回上级</button><button @click="reset">恢复路径</button></div></section>
</template>

<script>
module.exports = {
  name: 'BreadcrumbNavigator',
  props: {
    initialPath: { type: Array, default: () => ([
          "项目",
          "文档",
          "设计稿"
        ]) }
  },
  data() {
    return {
        pathItems: [],
        draft: ""
    };
  },
  computed: {
    current() {
      return this.pathItems.length ? this.pathItems[this.pathItems.length - 1] : '根目录';
    },
    depth() {
      return this.pathItems.length;
    }
  },
  created() {
    this.setValue('pathItems', this.initialPath.slice());
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateDraft(event) {
      this.setValue('draft', event.target.value);
    },
    navigate(index) {
      const next = this.pathItems.slice(0, index + 1); this.setValue('pathItems', next); this.emitEvent('navigate', next.slice());
    },
    addLevel(event) {
      event.preventDefault(); const value = this.draft.trim(); if (!value) return; const next = this.pathItems.concat(value); this.setValue('pathItems', next); this.setValue('draft', ''); this.emitEvent('change', next.slice());
    },
    removeLast() {
      if (!this.pathItems.length) return; const next = this.pathItems.slice(0, -1); this.setValue('pathItems', next); this.emitEvent('change', next.slice());
    },
    reset() {
      this.setValue('pathItems', this.initialPath.slice()); this.setValue('draft', '');
    }
  }
};
</script>

<style scoped>

.breadcrumb-navigator { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.breadcrumb-navigator * { box-sizing: border-box; }
.breadcrumb-navigator h2, .breadcrumb-navigator h3, .breadcrumb-navigator p { margin-top: 0; }
.breadcrumb-navigator h2 { margin-bottom: 14px; font-size: 21px; }
.breadcrumb-navigator button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.breadcrumb-navigator button.primary { border-color: #1d4ed8; background: #1d4ed8; color: #fff; }
.breadcrumb-navigator button:disabled { opacity: .45; cursor: not-allowed; }
.breadcrumb-navigator input, .breadcrumb-navigator select, .breadcrumb-navigator textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.breadcrumb-navigator .toolbar, .breadcrumb-navigator .summary, .breadcrumb-navigator .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.breadcrumb-navigator .muted { color: #71808e; font-size: 12px; }
.breadcrumb-navigator .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
nav{display:flex;align-items:center;gap:4px;flex-wrap:wrap}nav span{display:flex;align-items:center;gap:4px}nav button{border:0;padding:4px}nav button.current{color:#1d4ed8;font-weight:700}.location-card{display:grid;padding:18px;margin:14px 0;background:#eff6ff}.location-card strong{font-size:24px}form{display:grid;grid-template-columns:1fr auto;gap:8px}

</style>
