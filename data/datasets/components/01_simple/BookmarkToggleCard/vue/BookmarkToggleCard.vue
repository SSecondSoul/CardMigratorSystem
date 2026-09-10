<template>
  <article :class="'bookmark-toggle-card ' + (bookmarked ? 'saved' : '')"><div><span>研究资料</span><h2>{{ title }}</h2><p>{{ bookmarked ? '已加入稍后阅读' : '尚未收藏' }}</p></div><button @click="toggle">{{ bookmarked ? '★ 取消收藏' : '☆ 收藏' }}</button></article>
</template>

<script>
module.exports = {
  name: 'BookmarkToggleCard',
  props: {
    title: { type: String, default: "Vue 到 San 的迁移笔记" },
    initialBookmarked: { type: Boolean, default: false }
  },
  data() {
    return {
        bookmarked: false
    };
  },
  created() {
    this.setValue('bookmarked', this.initialBookmarked);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    toggle() {
      const next = !this.bookmarked; this.setValue('bookmarked', next); this.emitEvent('change', next);
    }
  }
};
</script>

<style scoped>

.bookmark-toggle-card{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.bookmark-toggle-card *{box-sizing:border-box}
.bookmark-toggle-card h2,.bookmark-toggle-card h3,.bookmark-toggle-card p{margin-top:0}
.bookmark-toggle-card button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.bookmark-toggle-card button.primary{border-color:#be185d;background:#be185d;color:#fff}
.bookmark-toggle-card button:disabled{opacity:.45;cursor:not-allowed}
.bookmark-toggle-card input,.bookmark-toggle-card select,.bookmark-toggle-card textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.bookmark-toggle-card .muted{color:#71808e;font-size:12px}
.bookmark-toggle-card .toolbar,.bookmark-toggle-card .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.bookmark-toggle-card{display:flex;justify-content:space-between;align-items:center}.bookmark-toggle-card.saved{border-color:#be185d;background:#fdf2f8}
</style>
