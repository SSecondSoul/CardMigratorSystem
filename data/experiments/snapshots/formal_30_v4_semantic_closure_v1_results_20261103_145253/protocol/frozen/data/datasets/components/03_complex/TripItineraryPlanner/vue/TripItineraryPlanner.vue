<template>
  <section class="trip-itinerary-planner"><header><div><p class="muted">{{ saved ? '已保存' : '有未保存更改' }}</p><h2>{{ tripName }}</h2></div><button class="primary" @click="save">保存行程</button></header><div class="trip-layout"><nav><button v-for="day in days" :key="day.id" :class="day.id === activeDayId ? 'active' : ''" @click="selectDay(day.id)">{{ day.label }}<small>{{ dayCount(day.id) }} 项</small></button><label>预算<input type="number" :value="budgetLimit" @input="updateBudget"></label><p :class="remainingBudget < 0 ? 'over' : ''">余额 {{ remainingBudget }} 元</p></nav><main><h3>{{ activeDayLabel }}安排</h3><ol><li v-for="item, index in dayItems" :key="item.id" :class="isConflict(item.id) ? 'conflict' : ''"><time>{{ item.start }}<br>{{ item.end }}</time><div><strong>{{ item.place }}</strong><span>¥{{ item.cost }}</span><small v-if="isConflict(item.id)">时间冲突</small></div><div><button @click="moveItem(index, -1)" :disabled="index === 0">↑</button><button @click="moveItem(index, 1)" :disabled="index === dayItems.length - 1">↓</button><button @click="removeItem(item.id)">删除</button></div></li></ol><form @submit="addItem"><input type="time" :value="draft.start" @input="updateDraft('start', $event)"><input type="time" :value="draft.end" @input="updateDraft('end', $event)"><input :value="draft.place" @input="updateDraft('place', $event)" placeholder="地点"><input type="number" :value="draft.cost" @input="updateDraft('cost', $event)" placeholder="费用"><button class="primary" type="submit">添加</button></form></main></div></section>
</template>

<script>
module.exports = {
  name: 'TripItineraryPlanner',
  props: {
    tripName: { type: String, default: "杭州周末行" },
    days: { type: Array, default: () => ([
          {
            "id": "d1",
            "label": "周六"
          },
          {
            "id": "d2",
            "label": "周日"
          }
        ]) },
    initialItems: { type: Array, default: () => ([
          {
            "id": 1,
            "dayId": "d1",
            "start": "09:00",
            "end": "11:00",
            "place": "西湖",
            "cost": 0
          },
          {
            "id": 2,
            "dayId": "d1",
            "start": "10:30",
            "end": "12:00",
            "place": "博物馆",
            "cost": 30
          },
          {
            "id": 3,
            "dayId": "d2",
            "start": "14:00",
            "end": "17:00",
            "place": "湿地公园",
            "cost": 80
          }
        ]) }
  },
  data() {
    return {
        items: [],
        activeDayId: "d1",
        draft: {
          "start": "09:00",
          "end": "10:00",
          "place": "",
          "cost": 0
        },
        budgetLimit: 500,
        saved: false,
        nextId: 10
    };
  },
  computed: {
    dayItems() {
      return this.items.filter(item => item.dayId === this.activeDayId).slice().sort((a, b) => a.start.localeCompare(b.start));
    },
    totalCost() {
      return this.items.reduce((sum, item) => sum + item.cost, 0);
    },
    remainingBudget() {
      return this.budgetLimit - this.totalCost;
    },
    conflictIds() {
      const rows = this.dayItems; const ids = []; rows.forEach((item, index) => rows.slice(index + 1).forEach(other => { if (item.start < other.end && other.start < item.end) ids.push(item.id, other.id); })); return Array.from(new Set(ids));
    },
    activeDayLabel() {
      const day = this.days.find(item => item.id === this.activeDayId); return day ? day.label : '';
    }
  },
  created() {
    this.setValue('items', this.initialItems.map(item => Object.assign({}, item))); this.setValue('activeDayId', this.days[0] ? this.days[0].id : '');
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    selectDay(id) {
      this.setValue('activeDayId', id);
    },
    updateDraft(field, event) {
      this.setValue('draft', Object.assign({}, this.draft, { [field]: field === 'cost' ? Number(event.target.value) || 0 : event.target.value }));
    },
    addItem(event) {
      event.preventDefault(); const draft = this.draft; if (!draft.place.trim() || draft.start >= draft.end) return; const next = this.items.concat({ id: this.nextId, dayId: this.activeDayId, start: draft.start, end: draft.end, place: draft.place.trim(), cost: draft.cost }); this.setValue('items', next); this.setValue('nextId', this.nextId + 1); this.setValue('draft', { start: draft.end, end: '18:00', place: '', cost: 0 }); this.setValue('saved', false); this.notify(next);
    },
    removeItem(id) {
      const next = this.items.filter(item => item.id !== id); this.setValue('items', next); this.setValue('saved', false); this.notify(next);
    },
    moveItem(index, delta) {
      const rows = this.dayItems.slice(); const target = index + delta; if (target < 0 || target >= rows.length) return; const temp = rows[index].start; rows[index].start = rows[target].start; rows[target].start = temp; const mapped = {}; rows.forEach(item => mapped[item.id] = item); const next = this.items.map(item => mapped[item.id] ? Object.assign({}, mapped[item.id]) : item); this.setValue('items', next); this.setValue('saved', false); this.notify(next);
    },
    updateBudget(event) {
      this.setValue('budgetLimit', Number(event.target.value) || 0);
    },
    save() {
      this.setValue('saved', true); this.emitEvent('save', { items: this.items, budget: this.budgetLimit });
    },
    notify(items) {
      this.emitEvent('itinerary-change', items);
    },
    isConflict(id) {
      return this.conflictIds.indexOf(id) >= 0;
    },
    dayCount(id) {
      return this.items.filter(item => item.dayId === id).length;
    }
  }
};
</script>

<style scoped>

.trip-itinerary-planner { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.trip-itinerary-planner * { box-sizing: border-box; }
.trip-itinerary-planner h2, .trip-itinerary-planner h3, .trip-itinerary-planner p { margin-top: 0; }
.trip-itinerary-planner h2 { margin-bottom: 14px; font-size: 21px; }
.trip-itinerary-planner button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.trip-itinerary-planner button.primary { border-color: #0369a1; background: #0369a1; color: #fff; }
.trip-itinerary-planner button:disabled { opacity: .45; cursor: not-allowed; }
.trip-itinerary-planner input, .trip-itinerary-planner select, .trip-itinerary-planner textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.trip-itinerary-planner .toolbar, .trip-itinerary-planner .summary, .trip-itinerary-planner .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.trip-itinerary-planner .muted { color: #71808e; font-size: 12px; }
.trip-itinerary-planner .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.trip-itinerary-planner > header{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}.trip-layout{display:flex;align-items:flex-start;gap:16px;flex-wrap:wrap}.trip-layout>nav,.trip-layout>main{min-width:0}.trip-layout>nav{display:grid;align-content:start;gap:7px;padding:10px;background:#f4f7f9;flex:1 1 140px}.trip-layout>main{flex:999 1 420px}.trip-layout>nav input{width:100%;min-width:0}.trip-layout>nav button.active{background:#e0f2fe;border-color:#0369a1}.trip-layout>nav button small{display:block}.over{color:#b91c1c}.trip-layout ol{padding:0;list-style:none}.trip-layout li{display:flex;align-items:flex-start;gap:10px;padding:11px;border-left:3px solid #7aa8c4;border-bottom:1px solid #e2e7eb;flex-wrap:wrap}.trip-layout li.conflict{border-left-color:#dc2626;background:#fef2f2}.trip-layout li>time{flex:0 0 54px}.trip-layout li>div:nth-child(2){min-width:0;flex:1 1 120px}.trip-layout li span,.trip-layout li small{display:block}.trip-layout li small{color:#b91c1c}.trip-layout li>div:last-child{display:flex;justify-content:flex-end;align-items:center;gap:6px;flex:0 1 auto;flex-wrap:wrap}.trip-layout form{display:flex;align-items:stretch;gap:8px;flex-wrap:wrap}.trip-layout form input{width:auto;min-width:0;flex:1 1 120px}.trip-layout form input:nth-child(3){flex:2 1 180px}.trip-layout form input:nth-child(4){flex:1 1 100px}.trip-layout form button{flex:0 1 auto}

</style>
