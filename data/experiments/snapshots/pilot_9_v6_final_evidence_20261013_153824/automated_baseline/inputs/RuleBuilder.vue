<template>
  <main class="rule-builder">
    <header class="builder-header">
      <div><span class="eyebrow">自动化配置</span><h1>{{ title }}</h1><p>将业务条件组合为可执行规则</p></div>
      <div class="header-actions">
        <button type="button" class="secondary" @click="togglePreview">{{ previewOpen ? '关闭预览' : '预览表达式' }}</button>
        <button type="button" :disabled="readonly || invalidRuleCount > 0" @click="save">保存规则</button>
      </div>
    </header>
    <section class="builder-stats">
      <article><span>条件组</span><strong>{{ groups.length }}</strong></article>
      <article><span>规则数</span><strong>{{ ruleCount }}</strong></article>
      <article :class="{ warning: invalidRuleCount }"><span>待修正</span><strong>{{ invalidRuleCount }}</strong></article>
    </section>
    <section class="builder-workspace">
      <aside class="group-sidebar">
        <div class="sidebar-title"><strong>条件组</strong><button type="button" :disabled="readonly" @click="addGroup">+</button></div>
        <button
          v-for="group in groups"
          :key="group.id"
          type="button"
          class="group-tab"
          :class="{ active: selectedGroupId === group.id }"
          @click="selectGroup(group.id)"
        ><span>{{ group.name }}</span><small>{{ group.rules.length }} 条</small></button>
      </aside>
      <div v-if="selectedGroup" class="group-editor">
        <div class="group-toolbar">
          <input :value="selectedGroup.name" :disabled="readonly" @input="renameGroup($event.target.value)" />
          <select :value="selectedGroup.mode" :disabled="readonly" @change="changeMode($event.target.value)">
            <option value="all">满足全部</option><option value="any">满足任一</option>
          </select>
          <button type="button" :disabled="readonly || groups.length === 1" @click="removeGroup(selectedGroup.id)">删除组</button>
        </div>
        <div class="rule-list">
          <article v-for="(rule, index) in selectedGroup.rules" :key="rule.id" class="rule-row" :class="{ invalid: !rule.value }">
            <span class="rule-index">{{ index + 1 }}</span>
            <select :value="rule.field" :disabled="readonly" @change="updateRule(rule.id, 'field', $event.target.value)">
              <option v-for="field in availableFields" :key="field.key" :value="field.key">{{ field.label }}</option>
            </select>
            <select :value="rule.operator" :disabled="readonly" @change="updateRule(rule.id, 'operator', $event.target.value)">
              <option value="equals">等于</option><option value="contains">包含</option><option value="greater">大于</option>
            </select>
            <input :value="rule.value" :disabled="readonly" placeholder="比较值" @input="updateRule(rule.id, 'value', $event.target.value)" />
            <button type="button" :disabled="readonly" @click="removeRule(rule.id)">移除</button>
          </article>
        </div>
        <button type="button" class="add-rule" :disabled="readonly" @click="addRule">添加条件</button>
      </div>
      <div v-else class="empty-editor">请选择条件组</div>
    </section>
    <section v-if="previewOpen" class="expression-preview">
      <div><strong>逻辑表达式</strong><button type="button" @click="validate">重新校验</button></div>
      <code>{{ expression }}</code>
      <ul v-if="errors.length"><li v-for="error in errors" :key="error">{{ error }}</li></ul>
      <p v-else>表达式校验通过</p>
    </section>
    <footer class="builder-footer"><span>最近保存：{{ savedAt || '尚未保存' }}</span><span>{{ readonly ? '只读模式' : '自动保存已开启' }}</span></footer>
  </main>
</template>

<script>
module.exports = {
  name: 'RuleBuilder',
  props: {
    title: { type: String, default: '客户分群规则' },
    availableFields: {
      type: Array,
      default: function () { return [{ key: 'region', label: '地区' }, { key: 'score', label: '活跃分' }, { key: 'tag', label: '标签' }]; }
    },
    initialGroups: {
      type: Array,
      default: function () {
        return [
          { id: 1, name: '基础条件', mode: 'all', rules: [{ id: 1, field: 'region', operator: 'equals', value: '西南' }] },
          { id: 2, name: '行为条件', mode: 'any', rules: [{ id: 2, field: 'score', operator: 'greater', value: '80' }] }
        ];
      }
    },
    readonly: { type: Boolean, default: false }
  },
  data() {
    const groups = JSON.parse(JSON.stringify(this.initialGroups));
    return {
      groups: groups,
      selectedGroupId: groups.length ? groups[0].id : 0,
      previewOpen: false,
      errors: [],
      nextGroupId: 3,
      nextRuleId: 3,
      savedAt: '',
      autosaveTimer: null,
      draftName: '',
      testPayload: {}
    };
  },
  computed: {
    selectedGroup() { return this.groups.find((group) => group.id === this.selectedGroupId); },
    ruleCount() { return this.groups.reduce((sum, group) => sum + group.rules.length, 0); },
    invalidRuleCount() { return this.groups.reduce((sum, group) => sum + group.rules.filter((rule) => !String(rule.value).trim()).length, 0); },
    expression() {
      return this.groups.map((group) => {
        const joiner = group.mode === 'all' ? ' AND ' : ' OR ';
        return `(${group.rules.map((rule) => `${rule.field} ${rule.operator} "${rule.value}"`).join(joiner)})`;
      }).join(' AND ');
    }
  },
  mounted() { this.validate(); this.scheduleAutosave(); },
  beforeDestroy() { clearTimeout(this.autosaveTimer); },
  methods: {
    selectGroup(id) { this.selectedGroupId = id; },
    addGroup() {
      const group = { id: this.nextGroupId++, name: `条件组 ${this.groups.length + 1}`, mode: 'all', rules: [] };
      this.groups.push(group); this.selectedGroupId = group.id; this.changed();
    },
    removeGroup(id) {
      this.groups = this.groups.filter((group) => group.id !== id);
      this.selectedGroupId = this.groups.length ? this.groups[0].id : 0; this.changed();
    },
    renameGroup(value) { this.selectedGroup.name = value; this.changed(); },
    changeMode(value) { this.selectedGroup.mode = value; this.changed(); },
    addRule() {
      this.selectedGroup.rules.push({ id: this.nextRuleId++, field: this.availableFields[0].key, operator: 'equals', value: '' });
      this.changed();
    },
    removeRule(id) { this.selectedGroup.rules = this.selectedGroup.rules.filter((rule) => rule.id !== id); this.changed(); },
    updateRule(id, key, value) {
      const rule = this.selectedGroup.rules.find((item) => item.id === id);
      this.$set(rule, key, value); this.changed();
    },
    validate() {
      const errors = [];
      this.groups.forEach((group) => {
        if (!group.name.trim()) errors.push('条件组名称不能为空');
        group.rules.forEach((rule) => { if (!String(rule.value).trim()) errors.push(`${group.name} 存在空比较值`); });
      });
      this.errors = errors;
      return !errors.length;
    },
    changed() { this.validate(); this.scheduleAutosave(); },
    scheduleAutosave() {
      clearTimeout(this.autosaveTimer);
      if (!this.readonly) this.autosaveTimer = setTimeout(() => { this.savedAt = '自动保存完成'; }, 400);
    },
    save() {
      if (!this.validate()) return;
      this.savedAt = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
      this.$emit('save', { groups: JSON.parse(JSON.stringify(this.groups)), expression: this.expression });
    },
    togglePreview() { this.previewOpen = !this.previewOpen; }
  }
};
</script>

<style scoped>
.rule-builder { width: 820px; padding: 24px; border: 1px solid #cbd5e1; border-radius: 7px; background: #f8fafc; color: #172026; font-family: Arial, sans-serif; }
.builder-header { display: flex; justify-content: space-between; gap: 24px; }
.builder-header h1 { margin: 3px 0; font-size: 24px; }
.builder-header p, .eyebrow { color: #64748b; font-size: 12px; }
.header-actions { display: flex; gap: 8px; }
.rule-builder button { padding: 8px 11px; border: 1px solid #334155; border-radius: 4px; background: #334155; color: #ffffff; cursor: pointer; }
.rule-builder button.secondary, .group-toolbar button, .rule-row button { background: #ffffff; color: #334155; border-color: #94a3b8; }
.builder-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 20px 0; }
.builder-stats article { padding: 12px; border-left: 3px solid #0f766e; background: #ffffff; }
.builder-stats article.warning { border-left-color: #dc2626; }
.builder-stats span { display: block; color: #64748b; font-size: 12px; }
.builder-stats strong { font-size: 22px; }
.builder-workspace { display: grid; grid-template-columns: 180px 1fr; min-height: 310px; border: 1px solid #d1d5db; background: #ffffff; }
.group-sidebar { padding: 12px; border-right: 1px solid #e2e8f0; background: #f1f5f9; }
.sidebar-title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.group-tab { width: 100%; display: flex; justify-content: space-between; margin-bottom: 6px; background: #ffffff !important; color: #334155 !important; border-color: #cbd5e1 !important; text-align: left; }
.group-tab.active { border-color: #0f766e !important; background: #ccfbf1 !important; }
.group-editor { padding: 16px; }
.group-toolbar { display: grid; grid-template-columns: 1fr auto auto; gap: 8px; }
.group-toolbar input, .group-toolbar select, .rule-row input, .rule-row select { padding: 8px; border: 1px solid #94a3b8; }
.rule-list { display: grid; gap: 8px; margin: 16px 0; }
.rule-row { display: grid; grid-template-columns: 28px 1fr 1fr 1fr auto; gap: 7px; padding: 9px; border: 1px solid #e2e8f0; }
.rule-row.invalid { border-color: #fca5a5; background: #fff1f2; }
.rule-index { display: grid; place-items: center; color: #64748b; }
.add-rule { background: #0f766e !important; border-color: #0f766e !important; }
.empty-editor { display: grid; place-items: center; color: #94a3b8; }
.expression-preview { margin-top: 16px; padding: 14px; border: 1px solid #a7f3d0; background: #ecfdf5; }
.expression-preview > div { display: flex; justify-content: space-between; }
.expression-preview code { display: block; margin: 12px 0; white-space: normal; color: #065f46; }
.expression-preview ul { color: #b91c1c; }
.builder-footer { display: flex; justify-content: space-between; margin-top: 14px; color: #64748b; font-size: 12px; }
</style>
