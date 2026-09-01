<template>
  <section :class="['planner-card', { compact: isCompact }]">
    <header class="planner-header">
      <div>
        <h2>{{ title }}</h2>
        <p>{{ itemCount }} 个动作</p>
      </div>
      <button type="button" @click="toggleCompact">切换视图</button>
    </header>
    <div class="planner-input">
      <input :value="draft" @input="updateDraft" placeholder="新增动作" />
      <button type="button" @click="addItem">添加</button>
    </div>
    <ul class="planner-list">
      <li v-for="item in visibleItems" :key="item.id" :class="{ done: item.done }">
        <span>{{ item.label }}</span>
        <button type="button" @click="removeItem(item.id)">移除</button>
      </li>
    </ul>
    <p v-if="!visibleItems.length" class="empty-state">暂无动作</p>
    <footer class="planner-footer">强调色：{{ accent }}</footer>
  </section>
</template>

<script>
module.exports = {
  name: 'WorkoutPlanner',
  props: {
    title: { type: String, default: '训练计划' },
    initialItems: { type: Array, default: function () { return []; } },
    accent: { type: String, default: '#2563eb' }
  },
  data() {
    return {
      items: this.initialItems.length ? this.initialItems.slice() : [
        { id: 1, label: '深蹲', done: false },
        { id: 2, label: '俯卧撑', done: true }
      ],
      draft: '',
      isCompact: false,
      selectedFilter: 'all',
      nextId: 3
    };
  },
  computed: {
    visibleItems() {
      return this.selectedFilter === 'all' ? this.items : this.items.filter(item => item.done);
    },
    itemCount() {
      return this.items.length;
    }
  },
  mounted() {
    this.nextId = this.items.reduce((max, item) => Math.max(max, item.id), 0) + 1;
  },
  methods: {
    updateDraft(event) {
      this.draft = event.target.value;
    },
    addItem() {
      const label = this.draft.trim();
      if (!label) return;
      this.items = this.items.concat({ id: this.nextId++, label: label, done: false });
      this.draft = '';
      this.$emit('change', this.items);
    },
    removeItem(id) {
      this.items = this.items.filter(item => item.id !== id);
      this.$emit('change', this.items);
    },
    toggleCompact() {
      this.isCompact = !this.isCompact;
    }
  }
};
</script>

<style scoped>
.planner-card { width: 420px; padding: 20px; border: 1px solid #d8dee9; border-radius: 8px; background: #ffffff; color: #1f2937; font-family: Arial, sans-serif; }
.planner-card.compact { padding: 14px; }
.planner-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.planner-header h2 { margin: 0; font-size: 20px; }
.planner-header p { margin: 4px 0 0; color: #667085; }
.planner-input { display: grid; grid-template-columns: 1fr auto; gap: 8px; margin: 18px 0; }
.planner-input input { min-width: 0; padding: 9px; border: 1px solid #b8c2cc; border-radius: 5px; }
.planner-input button, .planner-header button { padding: 8px 12px; border: 0; border-radius: 5px; background: #2563eb; color: #ffffff; cursor: pointer; }
.planner-list { margin: 0; padding: 0; list-style: none; }
.planner-list li { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #edf0f4; }
.planner-list li.done span { color: #7c8798; text-decoration: line-through; }
.planner-list button { border: 0; background: transparent; color: #c2410c; cursor: pointer; }
.empty-state { padding: 18px; text-align: center; color: #7c8798; }
.planner-footer { margin-top: 14px; font-size: 12px; color: #667085; }
</style>
