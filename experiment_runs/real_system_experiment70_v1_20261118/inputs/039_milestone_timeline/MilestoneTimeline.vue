<template>
  <section class="milestone-timeline">
    <header>
      <div><span class="eyebrow">里程碑</span><h2>{{ title }}</h2></div>
      <strong>{{ completedCount }}/{{ milestones.length }} 完成</strong>
    </header>
    <form v-if="!readonly" class="milestone-entry" @submit="addMilestone">
      <input :value="draft" placeholder="新增里程碑" @input="updateDraft" />
      <button type="submit">添加</button>
    </form>
    <ol>
      <li v-for="(milestone, index) in milestones" :key="milestone.id" :class="milestone.status">
        <button type="button" class="status-dot" @click="cycleStatus(milestone.id)">{{ index + 1 }}</button>
        <div><strong>{{ milestone.label }}</strong><small>{{ statusText(milestone.status) }}</small></div>
        <div v-if="!readonly" class="row-actions">
          <button type="button" :disabled="index === 0" @click="moveUp(index)">上移</button>
          <button type="button" @click="removeMilestone(milestone.id)">删除</button>
        </div>
      </li>
    </ol>
    <p v-if="!milestones.length" class="empty-state">尚未安排里程碑</p>
  </section>
</template>

<script>
module.exports = {
  name: 'MilestoneTimeline',
  props: {
    title: { type: String, default: '发布计划' },
    initialMilestones: {
      type: Array,
      default: function () {
        return [
          { id: 1, label: '需求冻结', status: 'done' },
          { id: 2, label: '联调验收', status: 'active' },
          { id: 3, label: '灰度发布', status: 'pending' }
        ];
      }
    },
    readonly: { type: Boolean, default: false }
  },
  data() {
    return { milestones: this.initialMilestones.map((item) => Object.assign({}, item)), draft: '', nextId: 4 };
  },
  computed: {
    completedCount() { return this.milestones.filter((item) => item.status === 'done').length; }
  },
  methods: {
    updateDraft(event) { this.draft = event.target.value; },
    addMilestone(event) {
      event.preventDefault();
      if (!this.draft.trim()) return;
      this.milestones.push({ id: this.nextId++, label: this.draft.trim(), status: 'pending' });
      this.draft = '';
      this.notify();
    },
    cycleStatus(id) {
      const order = ['pending', 'active', 'done'];
      const milestone = this.milestones.find((item) => item.id === id);
      milestone.status = order[(order.indexOf(milestone.status) + 1) % order.length];
      this.notify();
    },
    moveUp(index) {
      if (index < 1) return;
      const item = this.milestones.splice(index, 1)[0];
      this.milestones.splice(index - 1, 0, item);
      this.notify();
    },
    removeMilestone(id) {
      this.milestones = this.milestones.filter((item) => item.id !== id);
      this.notify();
    },
    statusText(status) { return { pending: '待开始', active: '进行中', done: '已完成' }[status]; },
    notify() { this.$emit('change', this.milestones.map((item) => Object.assign({}, item))); }
  }
};
</script>

<style scoped>
.milestone-timeline { width: 520px; padding: 22px; border: 1px solid #d1d5db; border-radius: 6px; background: #ffffff; color: #1f2937; font-family: Arial, sans-serif; }
.milestone-timeline header { display: flex; justify-content: space-between; align-items: flex-start; }
.milestone-timeline h2 { margin: 3px 0 0; font-size: 21px; }
.eyebrow { color: #6b7280; font-size: 12px; }
.milestone-entry { display: flex; gap: 8px; margin: 18px 0; }
.milestone-entry input { flex: 1; padding: 9px; border: 1px solid #9ca3af; }
.milestone-entry button, .row-actions button { padding: 7px 10px; border: 1px solid #6b7280; background: #ffffff; cursor: pointer; }
.milestone-timeline ol { display: grid; gap: 0; margin: 0; padding: 0; list-style: none; }
.milestone-timeline li { display: grid; grid-template-columns: 34px 1fr auto; align-items: center; gap: 10px; padding: 12px 0; border-bottom: 1px solid #e5e7eb; }
.status-dot { width: 28px; height: 28px; border: 0; border-radius: 50%; background: #d1d5db; cursor: pointer; }
.active .status-dot { background: #fbbf24; }
.done .status-dot { background: #16a34a; color: #ffffff; }
.milestone-timeline li small { display: block; margin-top: 3px; color: #6b7280; }
.row-actions { display: flex; gap: 5px; }
.empty-state { text-align: center; color: #9ca3af; }
</style>
