<template>
  <aside class="disclosure-notice">
    <button type="button" :aria-expanded="open" @click="toggle">
      <span>{{ heading }}</span>
      <strong>{{ open ? '收起' : '查看' }}</strong>
    </button>
    <div v-if="open" class="notice-detail">
      <p>{{ detail }}</p>
      <small>{{ footnote }}</small>
    </div>
  </aside>
</template>

<script>
module.exports = {
  name: 'DisclosureNotice',
  props: {
    heading: { type: String, default: '数据使用说明' },
    detail: { type: String, default: '提交的数据仅用于本次迁移评估。' },
    footnote: { type: String, default: '可随时撤回授权' },
    initiallyOpen: { type: Boolean, default: false }
  },
  data() {
    return { open: this.initiallyOpen };
  },
  methods: {
    toggle() { this.open = !this.open; }
  }
};
</script>

<style scoped>
.disclosure-notice { width: 340px; border: 1px solid #d6d3d1; border-radius: 5px; background: #fffbeb; color: #422006; font-family: Arial, sans-serif; }
.disclosure-notice > button { width: 100%; display: flex; justify-content: space-between; gap: 16px; padding: 14px 16px; border: 0; background: transparent; color: inherit; cursor: pointer; text-align: left; }
.disclosure-notice button strong { color: #92400e; font-size: 12px; }
.notice-detail { padding: 0 16px 15px; border-top: 1px solid #fde68a; }
.notice-detail p { margin: 13px 0 7px; line-height: 1.5; }
.notice-detail small { color: #78716c; }
</style>
