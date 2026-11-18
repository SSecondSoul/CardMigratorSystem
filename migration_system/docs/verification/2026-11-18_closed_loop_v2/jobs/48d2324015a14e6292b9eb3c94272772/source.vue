<template>
  <section class="capacity-planning-board"><header><div><p class="muted">{{ saved ? '规划已保存' : '有未保存变更' }}</p><h2>{{ boardTitle }}</h2></div><div class="actions"><select :value="cycle" @change="updateCycle"><option v-for="item in cycles" :key="item" :value="item">{{ item }}</option></select><button class="primary" @click="save">保存</button></div></header><div class="capacity-summary"><span>总工作量 {{ totalPoints }} 点</span><select :value="skillFilter" @change="updateSkill"><option value="all">全部技能</option><option>前端</option><option>后端</option><option>测试</option></select></div><div class="planning-layout"><aside><h3>待分配 {{ unassigned.length }}</h3><button v-for="item in unassigned" :key="item.id" :class="isSelected(item.id) ? 'selected' : ''" @click="selectWork(item.id)"><strong>{{ item.title }}</strong><small>{{ item.points }} 点</small></button><p v-if="!unassigned.length" class="empty">全部已分配</p><section v-if="selectedWork"><h3>当前工作项</h3><p>{{ selectedWork.title }}</p><strong>{{ selectedWork.points }} 点</strong></section></aside><main><article v-for="lane in lanes" :key="lane.member.id" :class="'member-lane ' + laneClass(lane)"><header><div><strong>{{ lane.member.name }}</strong><small>{{ lane.member.skills.join(' / ') }}</small></div><div><button @click="changeCapacity(lane.member.id, -1)">−</button><span>{{ lane.load }}/{{ lane.member.capacity }}</span><button @click="changeCapacity(lane.member.id, 1)">＋</button><button @click="assign(lane.member.id)" :disabled="selectedWorkId === null">分配到此</button></div></header><div class="capacity-bar"><span :style="lane.bar"></span></div><div class="lane-items"><button v-for="item in lane.items" :key="item.id" :class="isSelected(item.id) ? 'selected' : ''" @click="selectWork(item.id)">{{ item.title }} · {{ item.points }}<i @click.stop="unassign(item.id)">×</i></button></div></article></main></div><footer><span v-for="entry in changeLog" :key="entry.id">{{ entry.message }}</span></footer></section>
</template>

<script>
module.exports = {
  name: 'CapacityPlanningBoard',
  props: {
    boardTitle: { type: String, default: "迭代容量规划" },
    cycles: { type: Array, default: () => ([
          "Sprint 21",
          "Sprint 22"
        ]) },
    initialMembers: { type: Array, default: () => ([
          {
            "id": 1,
            "name": "林晓",
            "capacity": 8,
            "skills": [
              "前端"
            ]
          },
          {
            "id": 2,
            "name": "周宁",
            "capacity": 10,
            "skills": [
              "后端"
            ]
          },
          {
            "id": 3,
            "name": "陈雨",
            "capacity": 6,
            "skills": [
              "测试"
            ]
          }
        ]) },
    initialWork: { type: Array, default: () => ([
          {
            "id": 1,
            "title": "登录页改造",
            "points": 5,
            "assigneeId": 1,
            "cycle": "Sprint 21"
          },
          {
            "id": 2,
            "title": "接口缓存",
            "points": 8,
            "assigneeId": null,
            "cycle": "Sprint 21"
          },
          {
            "id": 3,
            "title": "回归测试",
            "points": 3,
            "assigneeId": 3,
            "cycle": "Sprint 21"
          },
          {
            "id": 4,
            "title": "埋点方案",
            "points": 5,
            "assigneeId": null,
            "cycle": "Sprint 22"
          }
        ]) }
  },
  data() {
    return {
        members: [],
        workItems: [],
        cycle: "Sprint 21",
        selectedWorkId: null,
        skillFilter: "all",
        saved: true,
        changeLog: []
    };
  },
  computed: {
    cycleWork() {
      return this.workItems.filter(item => item.cycle === this.cycle);
    },
    unassigned() {
      return this.cycleWork.filter(item => item.assigneeId === null);
    },
    visibleMembers() {
      return this.skillFilter === 'all' ? this.members : this.members.filter(member => member.skills.indexOf(this.skillFilter) >= 0);
    },
    lanes() {
      return this.visibleMembers.map(member => { const items = this.cycleWork.filter(item => item.assigneeId === member.id); const load = items.reduce((sum, item) => sum + item.points, 0); return { member, items, load, percent: Math.round(load / member.capacity * 100), bar: 'width:' + Math.min(100, load / member.capacity * 100) + '%' }; });
    },
    selectedWork() {
      return this.workItems.find(item => item.id === this.selectedWorkId) || null;
    },
    totalPoints() {
      return this.cycleWork.reduce((sum, item) => sum + item.points, 0);
    }
  },
  created() {
    this.setValue('members', this.initialMembers.map(item => Object.assign({}, item, { skills: item.skills.slice() }))); this.setValue('workItems', this.initialWork.map(item => Object.assign({}, item))); this.setValue('cycle', this.cycles[0] || '');
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateCycle(event) {
      this.setValue('cycle', event.target.value); this.setValue('selectedWorkId', null);
    },
    updateSkill(event) {
      this.setValue('skillFilter', event.target.value);
    },
    selectWork(id) {
      this.setValue('selectedWorkId', id);
    },
    assign(memberId) {
      const id = this.selectedWorkId; if (id === null) return; this.setValue('workItems', this.workItems.map(item => item.id === id ? Object.assign({}, item, { assigneeId: memberId }) : item)); this.setValue('saved', false); this.log('已分配工作项'); this.emitEvent('assignment', { workId: id, memberId });
    },
    unassign(id) {
      this.setValue('workItems', this.workItems.map(item => item.id === id ? Object.assign({}, item, { assigneeId: null }) : item)); this.setValue('saved', false); this.log('工作项退回待分配池');
    },
    changeCapacity(memberId, delta) {
      this.setValue('members', this.members.map(member => member.id === memberId ? Object.assign({}, member, { capacity: Math.max(1, member.capacity + delta) }) : member)); this.setValue('saved', false); this.emitEvent('capacity', { memberId, delta });
    },
    save() {
      this.setValue('saved', true); this.log('规划已保存'); this.emitEvent('save', { members: this.members, workItems: this.workItems });
    },
    log(message) {
      this.setValue('changeLog', [{ id: Date.now(), message }].concat(this.changeLog).slice(0, 4));
    },
    laneClass(lane) {
      return lane.percent > 100 ? 'overloaded' : lane.percent > 80 ? 'near-limit' : '';
    },
    isSelected(id) {
      return this.selectedWorkId === id;
    },
    joinValues(values, separator) {
      return values.join(separator);
    }
  }
};
</script>

<style scoped>

.capacity-planning-board { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.capacity-planning-board * { box-sizing: border-box; }
.capacity-planning-board h2, .capacity-planning-board h3, .capacity-planning-board p { margin-top: 0; }
.capacity-planning-board h2 { margin-bottom: 14px; font-size: 21px; }
.capacity-planning-board button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.capacity-planning-board button.primary { border-color: #047857; background: #047857; color: #fff; }
.capacity-planning-board button:disabled { opacity: .45; cursor: not-allowed; }
.capacity-planning-board input, .capacity-planning-board select, .capacity-planning-board textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.capacity-planning-board .toolbar, .capacity-planning-board .summary, .capacity-planning-board .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.capacity-planning-board .muted { color: #71808e; font-size: 12px; }
.capacity-planning-board .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
header,.capacity-summary{display:flex;justify-content:space-between}.capacity-summary{padding:10px;background:#ecfdf5}.planning-layout{display:grid;grid-template-columns:175px 1fr;gap:14px;margin-top:12px}.planning-layout>aside{padding:10px;background:#f6f8f8}.planning-layout>aside>button{display:block;width:100%;margin:6px 0}.planning-layout button.selected{background:#d1fae5}.member-lane{margin-bottom:10px;padding:12px;border:1px solid #dce3df}.member-lane.near-limit{border-color:#d97706}.member-lane.overloaded{border-color:#dc2626;background:#fef2f2}.capacity-bar{height:6px;margin:8px 0;background:#e5e7eb}.capacity-bar span{display:block;height:100%;background:#047857}.lane-items{display:flex;gap:7px;flex-wrap:wrap}.lane-items i{margin-left:6px;color:#b91c1c}footer{display:flex;gap:8px;font-size:11px}

</style>
