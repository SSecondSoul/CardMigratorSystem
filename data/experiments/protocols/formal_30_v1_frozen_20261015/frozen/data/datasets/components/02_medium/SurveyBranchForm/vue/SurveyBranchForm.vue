<template>
  <form class="survey-branch-form" @submit="submit"><h2>{{ title }}</h2><div v-if="!submitted"><fieldset><legend>你的角色</legend><button type="button" :class="role === 'developer' ? 'selected' : ''" @click="selectRole('developer')">开发者</button><button type="button" :class="role === 'manager' ? 'selected' : ''" @click="selectRole('manager')">管理者</button></fieldset><fieldset v-if="role"><legend>{{ branchPrompt }}</legend><label v-for="tool in tools" :key="tool"><input type="checkbox" :checked="selectedTools.indexOf(tool) >= 0" @change="toggleTool(tool)"> {{ tool }}</label></fieldset><textarea :value="comment" @input="updateComment" placeholder="其他建议"></textarea><p v-if="error" class="error">{{ error }}</p><button class="primary" type="submit">提交问卷</button></div><div v-else class="survey-result"><strong>提交成功</strong><p>{{ summary }}</p><button type="button" @click="restart">重新填写</button></div></form>
</template>

<script>
module.exports = {
  name: 'SurveyBranchForm',
  props: {
    title: { type: String, default: "开发体验调研" },
    tools: { type: Array, default: () => ([
          "编辑器",
          "调试器",
          "终端"
        ]) }
  },
  data() {
    return {
        role: "",
        selectedTools: [],
        comment: "",
        submitted: false,
        error: ""
    };
  },
  computed: {
    branchPrompt() {
      return this.role === 'developer' ? '日常使用哪些工具？' : this.role === 'manager' ? '最关注哪类协作信息？' : '';
    },
    summary() {
      return this.role + ' / ' + (this.selectedTools.length ? this.selectedTools.join('、') : '未选择工具');
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    selectRole(role) {
      this.setValue('role', role); this.setValue('selectedTools', []);
    },
    toggleTool(tool) {
      const list = this.selectedTools; this.setValue('selectedTools', list.indexOf(tool) >= 0 ? list.filter(item => item !== tool) : list.concat(tool));
    },
    updateComment(event) {
      this.setValue('comment', event.target.value);
    },
    submit(event) {
      event.preventDefault(); if (!this.role) { this.setValue('error', '请选择角色'); return; } this.setValue('error', ''); this.setValue('submitted', true); this.emitEvent('submit', { role: this.role, tools: this.selectedTools.slice(), comment: this.comment });
    },
    restart() {
      this.setValue('role', ''); this.setValue('selectedTools', []); this.setValue('comment', ''); this.setValue('submitted', false);
    },
    isIncluded(list, value) {
      return list.indexOf(value) >= 0;
    }
  }
};
</script>

<style scoped>

.survey-branch-form { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.survey-branch-form * { box-sizing: border-box; }
.survey-branch-form h2, .survey-branch-form h3, .survey-branch-form p { margin-top: 0; }
.survey-branch-form h2 { margin-bottom: 14px; font-size: 21px; }
.survey-branch-form button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.survey-branch-form button.primary { border-color: #6d28d9; background: #6d28d9; color: #fff; }
.survey-branch-form button:disabled { opacity: .45; cursor: not-allowed; }
.survey-branch-form input, .survey-branch-form select, .survey-branch-form textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.survey-branch-form .toolbar, .survey-branch-form .summary, .survey-branch-form .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.survey-branch-form .muted { color: #71808e; font-size: 12px; }
.survey-branch-form .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
fieldset{margin:12px 0;padding:12px;border:1px solid #ddd6fe}fieldset label{margin-right:12px}fieldset button.selected{background:#ede9fe;border-color:#6d28d9}textarea{width:100%;min-height:80px}.error{color:#b42318}.survey-result{text-align:center;padding:28px;background:#f5f3ff}

</style>
