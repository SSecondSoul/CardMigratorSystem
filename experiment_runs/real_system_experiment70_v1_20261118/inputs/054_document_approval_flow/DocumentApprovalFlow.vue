<template>
  <section class="document-approval-flow"><header><div><p class="muted">v{{ version }} · {{ updatedAt }}</p><h2>{{ documentTitle }}</h2><span>作者：{{ author }}</span></div><button @click="toggleHistory">版本历史</button></header><div class="approval-progress"><span :style="progressStyle"></span></div><div class="approval-steps"><article v-for="step, index in steps" :key="step.id" :class="step.status"><i>{{ index + 1 }}</i><div><strong>{{ step.name }}</strong><small>{{ statusText(step.status) }}</small></div></article></div><div class="approval-layout"><main><textarea class="document-content" :value="content" @input="updateContent" :disabled="status !== 'revision'"></textarea><div v-if="status === 'reviewing'" class="decision-panel"><h3>当前：{{ currentReviewer.name }}</h3><input :value="rejectionReason" @input="updateReason" placeholder="驳回原因"><button @click="reject" :disabled="!rejectionReason">要求修订</button><button class="primary" @click="approve">批准</button></div><div v-if="status === 'revision'" class="revision-panel"><strong>文档正在修订</strong><button class="primary" @click="submitRevision">提交新版本</button></div><div v-if="status === 'approved'" class="approved-panel">全部审批完成</div></main><aside><h3>评论</h3><form @submit="submitComment"><textarea :value="commentDraft" @input="updateComment"></textarea><button type="submit">发送</button></form><ol><li v-for="comment in comments" :key="comment.id"><small>v{{ comment.version }} · {{ comment.role }}</small><p>{{ comment.text }}</p></li></ol></aside></div><section v-if="showHistory" class="version-history"><article v-for="item in versions" :key="item.version"><strong>v{{ item.version }}</strong><span>{{ item.status }}</span></article><p v-if="!versions.length">暂无历史版本</p></section></section>
</template>

<script>
module.exports = {
  name: 'DocumentApprovalFlow',
  props: {
    documentTitle: { type: String, default: "数据治理方案" },
    author: { type: String, default: "研究小组" },
    reviewers: { type: Array, default: () => ([
          "导师审核",
          "合规审核",
          "最终签发"
        ]) },
    initialContent: { type: String, default: "本方案描述数据采集、清洗、标注与质量控制流程。" }
  },
  data() {
    return {
        version: 1,
        content: "",
        steps: [],
        activeStep: 0,
        status: "reviewing",
        commentDraft: "",
        comments: [],
        versions: [],
        rejectionReason: "",
        showHistory: false,
        updatedAt: ""
    };
  },
  computed: {
    currentReviewer() {
      return this.steps[this.activeStep] || null;
    },
    approvedCount() {
      return this.steps.filter(item => item.status === 'approved').length;
    },
    canDecide() {
      return this.status === 'reviewing' && !!this.currentReviewer;
    },
    progressStyle() {
      return 'width:' + Math.round(this.approvedCount / this.steps.length * 100) + '%';
    }
  },
  created() {
    this.setValue('content', this.initialContent); this.setValue('steps', this.reviewers.map((name, index) => ({ id: index + 1, name, status: index === 0 ? 'active' : 'pending' }))); this.refreshTime();
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    approve() {
      if (!this.canDecide) return; const index = this.activeStep; const steps = this.steps.map((item, itemIndex) => Object.assign({}, item, { status: itemIndex === index ? 'approved' : itemIndex === index + 1 ? 'active' : item.status })); this.setValue('steps', steps); if (index === steps.length - 1) this.setValue('status', 'approved'); else this.setValue('activeStep', index + 1); this.addComment('system', '步骤已批准'); this.refreshTime(); this.emitEvent('approve', { version: this.version, step: index });
    },
    updateReason(event) {
      this.setValue('rejectionReason', event.target.value);
    },
    reject() {
      const reason = this.rejectionReason.trim(); if (!this.canDecide || !reason) return; this.setValue('steps', this.steps.map((item, index) => index === this.activeStep ? Object.assign({}, item, { status: 'rejected' }) : item)); this.setValue('status', 'revision'); this.addComment('system', '需要修订：' + reason); this.setValue('rejectionReason', ''); this.emitEvent('reject', reason);
    },
    updateComment(event) {
      this.setValue('commentDraft', event.target.value);
    },
    submitComment(event) {
      event.preventDefault(); const text = this.commentDraft.trim(); if (!text) return; this.addComment('reviewer', text); this.setValue('commentDraft', '');
    },
    addComment(role, text) {
      this.setValue('comments', [{ id: Date.now(), role, text, version: this.version }].concat(this.comments));
    },
    updateContent(event) {
      this.setValue('content', event.target.value);
    },
    submitRevision() {
      if (this.status !== 'revision') return; this.setValue('versions', [{ version: this.version, content: this.content, status: this.status }].concat(this.versions)); const version = this.version + 1; this.setValue('version', version); this.setValue('steps', this.reviewers.map((name, index) => ({ id: index + 1, name, status: index === 0 ? 'active' : 'pending' }))); this.setValue('activeStep', 0); this.setValue('status', 'reviewing'); this.addComment('system', '已提交版本 v' + version); this.emitEvent('version', version);
    },
    toggleHistory() {
      this.setValue('showHistory', !this.showHistory);
    },
    refreshTime() {
      this.setValue('updatedAt', new Date().toLocaleString('zh-CN', { hour12: false }));
    },
    statusText(status) {
      return { pending: '等待', active: '审批中', approved: '已通过', rejected: '需修订' }[status] || status;
    }
  }
};
</script>

<style scoped>

.document-approval-flow { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.document-approval-flow * { box-sizing: border-box; }
.document-approval-flow h2, .document-approval-flow h3, .document-approval-flow p { margin-top: 0; }
.document-approval-flow h2 { margin-bottom: 14px; font-size: 21px; }
.document-approval-flow button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.document-approval-flow button.primary { border-color: #b45309; background: #b45309; color: #fff; }
.document-approval-flow button:disabled { opacity: .45; cursor: not-allowed; }
.document-approval-flow input, .document-approval-flow select, .document-approval-flow textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.document-approval-flow .toolbar, .document-approval-flow .summary, .document-approval-flow .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.document-approval-flow .muted { color: #71808e; font-size: 12px; }
.document-approval-flow .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
header{display:flex;justify-content:space-between}.approval-progress{height:7px;margin:14px 0;background:#e5e7eb}.approval-progress span{display:block;height:100%;background:#b45309}.approval-steps{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.approval-steps article{display:flex;gap:8px;padding:10px;background:#f8fafc}.approval-steps i{display:grid;width:26px;height:26px;place-items:center;border-radius:50%;background:#d9dee4}.approval-steps article.active i{background:#f59e0b}.approval-steps article.approved i{background:#15803d;color:#fff}.approval-layout{display:grid;grid-template-columns:1fr 250px;gap:14px;margin-top:14px}.document-content{width:100%;min-height:180px}.decision-panel,.revision-panel,.approved-panel{padding:12px;background:#fffbeb}.decision-panel{display:flex;gap:7px}.decision-panel input{flex:1}.approved-panel{background:#ecfdf5}aside{padding:12px;background:#f8fafc}aside textarea{width:100%}aside ol{padding:0;list-style:none}.version-history{display:flex;gap:8px;margin-top:12px}

</style>
