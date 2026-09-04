<template>
  <section class="support-ticket-console"><header><div><p class="muted">{{ openCount }} 个处理中</p><h2>{{ inboxTitle }}</h2></div><div class="actions"><input :value="query" @input="updateQuery" placeholder="搜索"><select :value="statusFilter" @change="updateStatusFilter"><option value="all">全部状态</option><option value="open">处理中</option><option value="pending">等待客户</option><option value="closed">已关闭</option></select></div></header><div class="tag-strip"><button v-for="tag in allTags" :key="tag" :class="tag === selectedTag ? 'active' : ''" @click="filterTag(tag)">{{ tag }}</button></div><div class="ticket-layout"><aside class="ticket-list"><button v-for="ticket in visibleTickets" :key="ticket.id" :class="{ selected: ticket.id === selectedId, urgent: ticket.priority === 'urgent' }" @click="selectTicket(ticket.id)"><span><strong>#{{ ticket.id }} {{ ticket.subject }}</strong><small>{{ ticket.customer }} · {{ statusText(ticket.status) }}</small></span><i>{{ priorityText(ticket.priority) }}</i></button><p v-if="!visibleTickets.length" class="empty">无匹配工单</p></aside><main v-if="selectedTicket"><div class="conversation-head"><div><h3>{{ selectedTicket.subject }}</h3><span>{{ selectedTicket.customer }}</span></div><span :class="'sla ' + slaState">SLA {{ selectedTicket.age + nowTick }} 分钟</span></div><div class="messages"><article v-for="message in selectedTicket.messages" :key="message.id" :class="message.internal ? 'internal' : ''"><strong>{{ message.author }}</strong><p>{{ message.text }}</p></article></div><form class="reply-box" @submit="sendReply"><div><button v-for="text in cannedReplies" :key="text" type="button" @click="useCanned(text)">{{ text }}</button></div><textarea :value="replyDraft" @input="updateReply"></textarea><footer><label><input type="checkbox" :checked="internalNote" @change="toggleInternal"> 内部备注</label><button class="primary" type="submit" :disabled="!replyDraft">发送</button></footer></form></main><aside v-if="selectedTicket" class="ticket-properties"><h3>工单属性</h3><label>负责人<select :value="selectedTicket.assignee" @change="assignAgent"><option value="">未分配</option><option v-for="agent in agents" :key="agent" :value="agent">{{ agent }}</option></select></label><div><b v-for="tag in selectedTicket.tags" :key="tag">{{ tag }}</b></div><div><button @click="changeStatus('open')">处理中</button><button @click="changeStatus('pending')">等待</button><button @click="changeStatus('closed')">关闭</button></div><label>合并到<select :value="mergeTargetId || ''" @change="setMergeTarget"><option value="">选择工单</option><option v-for="ticket in mergeCandidates" :key="ticket.id" :value="ticket.id">#{{ ticket.id }}</option></select></label><button @click="mergeTicket" :disabled="!mergeTargetId">执行合并</button></aside></div></section>
</template>

<script>
module.exports = {
  name: 'SupportTicketConsole',
  props: {
    inboxTitle: { type: String, default: "客户支持收件箱" },
    agents: { type: Array, default: () => ([
          "林晓",
          "周宁",
          "陈雨"
        ]) },
    initialTickets: { type: Array, default: () => ([
          {
            "id": 101,
            "subject": "无法完成付款",
            "customer": "安然",
            "priority": "urgent",
            "status": "open",
            "assignee": "林晓",
            "tags": [
              "支付"
            ],
            "age": 18,
            "messages": [
              {
                "id": 1,
                "author": "客户",
                "text": "付款页面一直提示失败。",
                "internal": false
              }
            ]
          },
          {
            "id": 102,
            "subject": "申请导出数据",
            "customer": "北辰",
            "priority": "normal",
            "status": "pending",
            "assignee": "周宁",
            "tags": [
              "数据"
            ],
            "age": 55,
            "messages": [
              {
                "id": 2,
                "author": "客户",
                "text": "请问如何导出历史数据？",
                "internal": false
              }
            ]
          },
          {
            "id": 103,
            "subject": "账号权限异常",
            "customer": "知夏",
            "priority": "high",
            "status": "open",
            "assignee": "",
            "tags": [
              "权限"
            ],
            "age": 32,
            "messages": [
              {
                "id": 3,
                "author": "客户",
                "text": "管理员菜单突然消失。",
                "internal": false
              }
            ]
          }
        ]) },
    cannedReplies: { type: Array, default: () => ([
          "已收到，我们正在处理。",
          "问题已修复，请刷新后重试。"
        ]) }
  },
  data() {
    return {
        tickets: [],
        selectedId: null,
        query: "",
        statusFilter: "all",
        replyDraft: "",
        internalNote: false,
        selectedTag: "",
        mergeTargetId: null,
        nowTick: 0,
        timer: null
    };
  },
  computed: {
    visibleTickets() {
      const q = this.query.toLowerCase(); const rank = { urgent: 0, high: 1, normal: 2 }; return this.tickets.filter(ticket => (this.statusFilter === 'all' || ticket.status === this.statusFilter) && (!this.selectedTag || ticket.tags.indexOf(this.selectedTag) >= 0) && (ticket.subject.toLowerCase().indexOf(q) >= 0 || ticket.customer.toLowerCase().indexOf(q) >= 0)).slice().sort((a, b) => (rank[a.priority] || 3) - (rank[b.priority] || 3));
    },
    selectedTicket() {
      return this.tickets.find(ticket => ticket.id === this.selectedId) || null;
    },
    openCount() {
      return this.tickets.filter(ticket => ticket.status === 'open').length;
    },
    slaState() {
      const ticket = this.selectedTicket; if (!ticket) return 'none'; const age = ticket.age + this.nowTick; return age >= 60 ? 'breached' : age >= 45 ? 'warning' : 'safe';
    },
    allTags() {
      return Array.from(new Set(this.tickets.reduce((all, ticket) => all.concat(ticket.tags), [])));
    },
    mergeCandidates() {
      return this.tickets.filter(ticket => ticket.id !== this.selectedId && ticket.status !== 'closed');
    }
  },
  created() {
    this.setValue('tickets', this.initialTickets.map(ticket => Object.assign({}, ticket, { tags: ticket.tags.slice(), messages: ticket.messages.map(message => Object.assign({}, message)) }))); this.setValue('selectedId', this.initialTickets[0] ? this.initialTickets[0].id : null);
  },
  mounted() {
    this._timer = setInterval(() => this.setValue('nowTick', this.nowTick + 1), 60000);
  },
  beforeDestroy() {
    clearInterval(this._timer);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateQuery(event) {
      this.setValue('query', event.target.value);
    },
    updateStatusFilter(event) {
      this.setValue('statusFilter', event.target.value);
    },
    filterTag(tag) {
      this.setValue('selectedTag', this.selectedTag === tag ? '' : tag);
    },
    selectTicket(id) {
      this.setValue('selectedId', id); this.setValue('replyDraft', ''); this.setValue('mergeTargetId', null);
    },
    updateReply(event) {
      this.setValue('replyDraft', event.target.value);
    },
    toggleInternal(event) {
      this.setValue('internalNote', event.target.checked);
    },
    useCanned(text) {
      this.setValue('replyDraft', text);
    },
    sendReply(event) {
      event.preventDefault(); const text = this.replyDraft.trim(); const id = this.selectedId; if (!text || id === null) return; const message = { id: Date.now(), author: this.internalNote ? '内部备注' : '客服', text, internal: this.internalNote }; this.setValue('tickets', this.tickets.map(ticket => ticket.id === id ? Object.assign({}, ticket, { messages: ticket.messages.concat(message), status: this.internalNote ? ticket.status : 'pending' }) : ticket)); this.setValue('replyDraft', ''); this.emitEvent('reply', { ticketId: id, message });
    },
    changeStatus(status) {
      const id = this.selectedId; this.setValue('tickets', this.tickets.map(ticket => ticket.id === id ? Object.assign({}, ticket, { status }) : ticket)); this.emitEvent('status', { ticketId: id, status });
    },
    assignAgent(event) {
      const assignee = event.target.value; const id = this.selectedId; this.setValue('tickets', this.tickets.map(ticket => ticket.id === id ? Object.assign({}, ticket, { assignee }) : ticket)); this.emitEvent('assign', { ticketId: id, assignee });
    },
    setMergeTarget(event) {
      this.setValue('mergeTargetId', Number(event.target.value) || null);
    },
    mergeTicket() {
      const sourceId = this.selectedId; const targetId = this.mergeTargetId; if (!targetId) return; const source = this.tickets.find(ticket => ticket.id === sourceId); this.setValue('tickets', this.tickets.map(ticket => ticket.id === targetId ? Object.assign({}, ticket, { messages: ticket.messages.concat(source.messages) }) : ticket).filter(ticket => ticket.id !== sourceId)); this.setValue('selectedId', targetId); this.emitEvent('merge', { sourceId, targetId });
    },
    priorityRank(priority) {
      return { urgent: 0, high: 1, normal: 2 }[priority] || 3;
    },
    priorityText(priority) {
      return { urgent: '紧急', high: '高', normal: '普通' }[priority];
    },
    statusText(status) {
      return { open: '处理中', pending: '等待客户', closed: '已关闭' }[status];
    }
  }
};
</script>

<style scoped>

.support-ticket-console { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.support-ticket-console * { box-sizing: border-box; }
.support-ticket-console h2, .support-ticket-console h3, .support-ticket-console p { margin-top: 0; }
.support-ticket-console h2 { margin-bottom: 14px; font-size: 21px; }
.support-ticket-console button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.support-ticket-console button.primary { border-color: #2563eb; background: #2563eb; color: #fff; }
.support-ticket-console button:disabled { opacity: .45; cursor: not-allowed; }
.support-ticket-console input, .support-ticket-console select, .support-ticket-console textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.support-ticket-console .toolbar, .support-ticket-console .summary, .support-ticket-console .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.support-ticket-console .muted { color: #71808e; font-size: 12px; }
.support-ticket-console .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
header{display:flex;justify-content:space-between}.tag-strip{display:flex;gap:6px;margin:10px 0}.tag-strip button.active{background:#dbeafe}.ticket-layout{display:grid;grid-template-columns:210px 1fr 175px;min-height:480px;border:1px solid #dce2e8}.ticket-list{border-right:1px solid #dce2e8}.ticket-list>button{display:flex;width:100%;justify-content:space-between;border:0;border-bottom:1px solid #e6e9ec;text-align:left}.ticket-list>button.selected{background:#eff6ff}.ticket-list>button.urgent{border-left:4px solid #dc2626}.ticket-list small{display:block}.ticket-layout main{display:flex;flex-direction:column;padding:12px}.conversation-head{display:flex;justify-content:space-between}.sla.warning{background:#fef3c7}.sla.breached{background:#fee2e2}.messages{flex:1}.messages article{max-width:80%;padding:10px;background:#eff6ff}.messages article.internal{background:#fff7ed}.reply-box textarea{width:100%}.reply-box footer{display:flex;justify-content:space-between}.ticket-properties{padding:12px;border-left:1px solid #dce2e8;background:#f8fafc}.ticket-properties label{display:grid;margin:10px 0}.ticket-properties b{display:inline-block;margin:4px;padding:4px;background:#e2e8f0}

</style>
