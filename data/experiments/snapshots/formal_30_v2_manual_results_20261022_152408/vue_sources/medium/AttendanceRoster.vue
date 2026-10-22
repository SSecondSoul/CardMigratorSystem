<template>
  <section class="attendance-roster"><header><h2>课程点名</h2><div class="summary"><span>出勤 {{ counts.present }}</span><span>迟到 {{ counts.late }}</span><span>缺席 {{ counts.absent }}</span></div></header><div class="toolbar"><select :value="filter" @change="updateFilter"><option value="all">全部</option><option value="present">出勤</option><option value="late">迟到</option><option value="absent">缺席</option></select><button @click="markAllPresent">全员签到</button></div><ul><li v-for="student in visibleRecords" :key="student.id" :class="student.status"><strong>{{ student.name }}</strong><button @click="cycleStatus(student.id)">{{ statusText(student.status) }}</button></li></ul><p v-if="!visibleRecords.length" class="empty">当前筛选无学生</p></section>
</template>

<script>
module.exports = {
  name: 'AttendanceRoster',
  props: {
    students: { type: Array, default: () => ([
          {
            "id": 1,
            "name": "林晓",
            "status": "present"
          },
          {
            "id": 2,
            "name": "周宁",
            "status": "late"
          },
          {
            "id": 3,
            "name": "陈雨",
            "status": "absent"
          },
          {
            "id": 4,
            "name": "孟然",
            "status": "present"
          }
        ]) }
  },
  data() {
    return {
        records: [],
        filter: "all"
    };
  },
  computed: {
    counts() {
      return this.records.reduce((result, item) => { result[item.status] += 1; return result; }, { present: 0, late: 0, absent: 0 });
    },
    visibleRecords() {
      return this.filter === 'all' ? this.records : this.records.filter(item => item.status === this.filter);
    }
  },
  created() {
    this.setValue('records', this.students.map(item => Object.assign({}, item)));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateFilter(event) {
      this.setValue('filter', event.target.value);
    },
    cycleStatus(id) {
      const order = ['present', 'late', 'absent']; const next = this.records.map(item => item.id === id ? Object.assign({}, item, { status: order[(order.indexOf(item.status) + 1) % order.length] }) : item); this.setValue('records', next); this.notify();
    },
    markAllPresent() {
      this.setValue('records', this.records.map(item => Object.assign({}, item, { status: 'present' }))); this.notify();
    },
    notify() {
      this.emitEvent('change', this.records.map(item => Object.assign({}, item)));
    },
    statusText(status) {
      return { present: '出勤', late: '迟到', absent: '缺席' }[status];
    }
  }
};
</script>

<style scoped>

.attendance-roster { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.attendance-roster * { box-sizing: border-box; }
.attendance-roster h2, .attendance-roster h3, .attendance-roster p { margin-top: 0; }
.attendance-roster h2 { margin-bottom: 14px; font-size: 21px; }
.attendance-roster button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.attendance-roster button.primary { border-color: #0f766e; background: #0f766e; color: #fff; }
.attendance-roster button:disabled { opacity: .45; cursor: not-allowed; }
.attendance-roster input, .attendance-roster select, .attendance-roster textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.attendance-roster .toolbar, .attendance-roster .summary, .attendance-roster .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.attendance-roster .muted { color: #71808e; font-size: 12px; }
.attendance-roster .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
header{display:flex;justify-content:space-between}.summary span{padding:5px 8px;background:#f0fdfa}.toolbar{margin:12px 0}ul{padding:0;list-style:none}li{display:flex;justify-content:space-between;padding:10px;border-bottom:1px solid #e2e8e7}li.late{border-left:4px solid #d97706}li.absent{border-left:4px solid #dc2626}

</style>
