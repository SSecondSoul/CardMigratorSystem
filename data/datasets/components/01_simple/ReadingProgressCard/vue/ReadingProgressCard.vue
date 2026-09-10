<template>
  <section class="reading-progress-card"><h2>{{ title }}</h2><p>第 {{ currentPage }} / {{ totalPages }} 页 · {{ percent }}%</p><div class="bar"><span :style="barStyle"></span></div><div class="actions"><button @click="go(-1)" :disabled="currentPage === 1">上一页</button><button @click="go(1)" :disabled="currentPage === totalPages">下一页</button><button class="primary" @click="finish">读完</button></div></section>
</template>

<script>
module.exports = {
  name: 'ReadingProgressCard',
  props: {
    title: { type: String, default: "迁移系统设计" },
    totalPages: { type: Number, default: 12 }
  },
  data() {
    return {
        currentPage: 1
    };
  },
  computed: {
    percent() {
      return Math.round(this.currentPage / this.totalPages * 100);
    },
    barStyle() {
      return 'width:' + this.percent + '%';
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    go(delta) {
      this.setValue('currentPage', Math.max(1, Math.min(this.totalPages, this.currentPage + delta)));
    },
    finish() {
      this.setValue('currentPage', this.totalPages);
    }
  }
};
</script>

<style scoped>

.reading-progress-card{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.reading-progress-card *{box-sizing:border-box}
.reading-progress-card h2,.reading-progress-card h3,.reading-progress-card p{margin-top:0}
.reading-progress-card button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.reading-progress-card button.primary{border-color:#7c3aed;background:#7c3aed;color:#fff}
.reading-progress-card button:disabled{opacity:.45;cursor:not-allowed}
.reading-progress-card input,.reading-progress-card select,.reading-progress-card textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.reading-progress-card .muted{color:#71808e;font-size:12px}
.reading-progress-card .toolbar,.reading-progress-card .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.bar{height:9px;margin:14px 0;background:#e5e7eb}.bar span{display:block;height:100%;background:#7c3aed}
</style>
