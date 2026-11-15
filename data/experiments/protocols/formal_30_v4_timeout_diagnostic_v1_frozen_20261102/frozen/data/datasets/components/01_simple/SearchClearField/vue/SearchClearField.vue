<template>
  <section class="search-clear-field"><h2>快速搜索</h2><div class="search-box"><input :value="query" @input="updateQuery" :placeholder="placeholder"><button v-if="query" @click="clear">×</button></div><p>{{ query ? '正在搜索：' + query : '输入内容开始搜索' }}</p></section>
</template>

<script>
module.exports = {
  name: 'SearchClearField',
  props: {
    placeholder: { type: String, default: "搜索文档" }
  },
  data() {
    return {
        query: ""
    };
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateQuery(event) {
      this.setValue('query', event.target.value);
    },
    clear() {
      this.setValue('query', '');
    }
  }
};
</script>

<style scoped>

.search-clear-field { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.search-clear-field * { box-sizing: border-box; }
.search-clear-field h2, .search-clear-field h3, .search-clear-field p { margin-top: 0; }
.search-clear-field h2 { margin-bottom: 14px; font-size: 21px; }
.search-clear-field button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.search-clear-field button.primary { border-color: #0369a1; background: #0369a1; color: #fff; }
.search-clear-field button:disabled { opacity: .45; cursor: not-allowed; }
.search-clear-field input, .search-clear-field select, .search-clear-field textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.search-clear-field .toolbar, .search-clear-field .summary, .search-clear-field .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.search-clear-field .muted { color: #71808e; font-size: 12px; }
.search-clear-field .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.search-box{display:grid;grid-template-columns:1fr 40px;gap:6px}.search-box button{font-size:18px}

</style>
