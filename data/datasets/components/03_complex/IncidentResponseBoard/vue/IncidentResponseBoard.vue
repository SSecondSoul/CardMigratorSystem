<template>
  <section class="incident-response-board"><header class="incident-head"><div><span :class="'severity ' + severity">{{ severity }}</span><small>{{ incidentId }}</small><h2>{{ serviceName }}异常</h2></div><div><strong>{{ elapsedLabel }}</strong><button @click="escalate" :disabled="status === 'resolved'">升级</button></div></header><div class="stage-track"><div v-for="stage, index in stages" :key="stage" :class="{ active: index === stageIndex, done: index < stageIndex }"><i></i><span>{{ statusText(stage) }}</span></div></div><div class="response-grid"><main><div class="owner-card"><div><span>事件负责人</span><strong>{{ owner || '尚未认领' }}</strong></div><button @click="claim">{{ owner ? '释放' : '认领' }}</button></div><section class="check-panel"><h3>处置检查项 {{ completedChecks }}/{{ checklist.length }}</h3><label v-for="item in checklist" :key="item.id" :class="item.done ? 'done' : ''"><input type="checkbox" :checked="item.done" @change="toggleCheck(item.id)"> {{ item.text }}</label></section><div class="actions"><button @click="advance">推进阶段</button><button class="primary" @click="resolve" :disabled="!canResolve">关闭事件</button></div></main><aside><h3>响应时间线</h3><form @submit="addNote"><textarea :value="note" @input="updateNote" placeholder="记录处置进展"></textarea><button type="submit">添加</button></form><ol><li v-for="entry in timeline" :key="entry.id"><time>{{ entry.time }}</time><span>{{ entry.text }}</span></li></ol></aside></div></section>
</template>

<script>
module.exports = {
  name: 'IncidentResponseBoard',
  props: {
    incidentId: { type: String, default: "INC-2048" },
    serviceName: { type: String, default: "支付网关" },
    initialSeverity: { type: String, default: "P1" }
  },
  data() {
    return {
        status: "detected",
        severity: "P1",
        owner: "",
        elapsed: 0,
        checklist: [
          {
            "id": 1,
            "text": "确认监控告警",
            "done": true
          },
          {
            "id": 2,
            "text": "隔离异常节点",
            "done": false
          },
          {
            "id": 3,
            "text": "通知业务负责人",
            "done": false
          }
        ],
        timeline: [
          {
            "id": 1,
            "time": "09:20",
            "text": "监控触发错误率告警"
          }
        ],
        note: "",
        timer: null,
        stages: [
          "detected",
          "triage",
          "mitigation",
          "resolved"
        ]
    };
  },
  computed: {
    stageIndex() {
      return this.stages.indexOf(this.status);
    },
    completedChecks() {
      return this.checklist.filter(item => item.done).length;
    },
    canResolve() {
      return !!this.owner && this.completedChecks === this.checklist.length;
    },
    elapsedLabel() {
      return Math.floor(this.elapsed / 60) + 'h ' + (this.elapsed % 60) + 'm';
    }
  },
  created() {
    this.setValue('severity', this.initialSeverity);
  },
  mounted() {
    this._timer = setInterval(() => this.setValue('elapsed', this.elapsed + 1), 60000);
  },
  beforeDestroy() {
    clearInterval(this._timer);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    claim() {
      this.setValue('owner', this.owner ? '' : '当前值班员'); this.addTimeline(this.owner ? '事件已认领' : '已取消认领');
    },
    advance() {
      const index = this.stageIndex; if (index >= this.stages.length - 1) return; const next = this.stages[index + 1]; this.setValue('status', next); this.addTimeline('推进至' + this.statusText(next)); this.emitEvent('status-change', next);
    },
    toggleCheck(id) {
      this.setValue('checklist', this.checklist.map(item => item.id === id ? Object.assign({}, item, { done: !item.done }) : item));
    },
    updateNote(event) {
      this.setValue('note', event.target.value);
    },
    addNote(event) {
      event.preventDefault(); const text = this.note.trim(); if (!text) return; this.addTimeline(text); this.setValue('note', '');
    },
    escalate() {
      const next = this.severity === 'P2' ? 'P1' : 'P0'; this.setValue('severity', next); this.addTimeline('严重度升级为 ' + next); this.emitEvent('escalate', next);
    },
    resolve() {
      if (!this.canResolve) return; this.setValue('status', 'resolved'); this.addTimeline('事件已关闭'); this.emitEvent('resolve', { id: this.incidentId, elapsed: this.elapsed });
    },
    addTimeline(text) {
      const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }); this.setValue('timeline', [{ id: Date.now(), time: now, text }].concat(this.timeline));
    },
    statusText(status) {
      return { detected: '已发现', triage: '排查中', mitigation: '处置中', resolved: '已恢复' }[status];
    }
  }
};
</script>

<style scoped>

.incident-response-board { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.incident-response-board * { box-sizing: border-box; }
.incident-response-board h2, .incident-response-board h3, .incident-response-board p { margin-top: 0; }
.incident-response-board h2 { margin-bottom: 14px; font-size: 21px; }
.incident-response-board button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.incident-response-board button.primary { border-color: #b91c1c; background: #b91c1c; color: #fff; }
.incident-response-board button:disabled { opacity: .45; cursor: not-allowed; }
.incident-response-board input, .incident-response-board select, .incident-response-board textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.incident-response-board .toolbar, .incident-response-board .summary, .incident-response-board .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.incident-response-board .muted { color: #71808e; font-size: 12px; }
.incident-response-board .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.incident-head{display:flex;justify-content:space-between}.severity{padding:4px 7px;background:#fee2e2;color:#991b1b}.severity.P0{background:#991b1b;color:#fff}.stage-track{display:grid;grid-template-columns:repeat(4,1fr);margin:18px 0}.stage-track div{display:grid;gap:5px;text-align:center}.stage-track i{height:6px;background:#d9dee3}.stage-track .active i,.stage-track .done i{background:#b91c1c}.response-grid{display:grid;grid-template-columns:1fr 280px;gap:14px}.owner-card{display:flex;justify-content:space-between;padding:14px;background:#f8fafc}.check-panel{margin:12px 0;padding:14px;border:1px solid #e2e5e9}.check-panel label{display:block;padding:7px}.check-panel label.done{text-decoration:line-through;color:#77818b}aside{padding:12px;background:#f8fafc}aside textarea{width:100%}aside ol{padding:0;list-style:none}aside li{display:grid;grid-template-columns:48px 1fr;gap:7px;padding:8px 0}

</style>
