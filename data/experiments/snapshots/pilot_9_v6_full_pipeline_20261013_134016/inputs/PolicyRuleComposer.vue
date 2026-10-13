<template>
  <section class="policy-rule-composer"><header><div><small>v{{ publishedVersion || '草稿' }}</small><h2>{{ policyName }}</h2></div><button class="primary" @click="publish" :disabled="!canPublish">发布策略</button></header><div class="policy-layout"><main><div class="join-row">规则组之间 <button @click="toggleJoin">{{ groupJoin }}</button></div><article v-for="group in groups" :key="group.id" class="rule-group"><h3>规则组 {{ group.id }} <button @click="toggleGroup(group.id)">{{ group.operator }}</button></h3><div v-for="condition in group.conditions" :key="condition.id" class="condition"><select :value="condition.field" @change="updateCondition(group.id, condition.id, 'field', $event)"><option v-for="field in fields" :key="field" :value="field">{{ field }}</option></select><select :value="condition.comparator" @change="updateCondition(group.id, condition.id, 'comparator', $event)"><option value="equals">等于</option><option value="less">小于</option></select><input :value="condition.value" @input="updateCondition(group.id, condition.id, 'value', $event)"><button @click="removeCondition(group.id, condition.id)">删除</button></div><button @click="addCondition(group.id)">添加条件</button></article></main><aside><h3>测试上下文</h3><label v-for="field in fields" :key="field">{{ field }}<input :value="context[field]" @input="setContext(field, $event)"></label><button @click="testPolicy">运行判定</button><output :class="testResult ? 'pass' : 'deny'">{{ decisionLabel }}</output><ul><li v-for="trace in testTrace" :key="trace.id">组 {{ trace.id }}：{{ trace.passed ? '通过' : '未通过' }}</li></ul></aside></div><footer>条件 {{ conditionCount }} 条 · 无效 {{ invalidConditions.length }} 条 · 效果 {{ effect }}</footer></section>
</template>

<script>
module.exports = {
  name: 'PolicyRuleComposer',
  props: {
    policyName: { type: String, default: "研发仓库访问策略" },
    initialGroups: { type: Array, default: () => ([
          {
            "id": 1,
            "operator": "AND",
            "conditions": [
              {
                "id": 11,
                "field": "role",
                "comparator": "equals",
                "value": "developer"
              },
              {
                "id": 12,
                "field": "hour",
                "comparator": "less",
                "value": "20"
              }
            ]
          },
          {
            "id": 2,
            "operator": "OR",
            "conditions": [
              {
                "id": 21,
                "field": "network",
                "comparator": "equals",
                "value": "office"
              }
            ]
          }
        ]) },
    fields: { type: Array, default: () => ([
          "role",
          "hour",
          "network"
        ]) },
    effect: { type: String, default: "allow" },
    publishable: { type: Boolean, default: true }
  },
  data() {
    return {
        groups: [],
        context: {
          "role": "developer",
          "hour": "16",
          "network": "office"
        },
        groupJoin: "AND",
        testResult: null,
        testTrace: [],
        publishedVersion: 0,
        nextConditionId: 100
    };
  },
  computed: {
    conditionCount() {
      return this.groups.reduce((sum, group) => sum + group.conditions.length, 0);
    },
    invalidConditions() {
      return this.groups.reduce((out, group) => out.concat(group.conditions.filter(item => !item.field || !item.value)), []);
    },
    decisionLabel() {
      return this.testResult === null ? '尚未测试' : this.testResult ? '允许访问' : '拒绝访问';
    },
    canPublish() {
      return this.publishable && this.invalidConditions.length === 0 && this.testResult !== null;
    }
  },
  created() {
    this.setValue('groups', this.initialGroups.map(group => Object.assign({}, group, { conditions: group.conditions.map(item => Object.assign({}, item)) })));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    setContext(field, event) {
      this.setValue('context', Object.assign({}, this.context, { [field]: event.target.value })); this.setValue('testResult', null);
    },
    toggleJoin() {
      this.setValue('groupJoin', this.groupJoin === 'AND' ? 'OR' : 'AND'); this.setValue('testResult', null);
    },
    toggleGroup(id) {
      this.setValue('groups', this.groups.map(group => group.id === id ? Object.assign({}, group, { operator: group.operator === 'AND' ? 'OR' : 'AND' }) : group)); this.setValue('testResult', null);
    },
    updateCondition(groupId, conditionId, field, event) {
      this.setValue('groups', this.groups.map(group => group.id !== groupId ? group : Object.assign({}, group, { conditions: group.conditions.map(condition => condition.id === conditionId ? Object.assign({}, condition, { [field]: event.target.value }) : condition) }))); this.setValue('testResult', null); this.emitEvent('change', this.groups);
    },
    addCondition(groupId) {
      const id = this.nextConditionId; this.setValue('groups', this.groups.map(group => group.id === groupId ? Object.assign({}, group, { conditions: group.conditions.concat({ id, field: 'role', comparator: 'equals', value: '' }) }) : group)); this.setValue('nextConditionId', id + 1);
    },
    removeCondition(groupId, conditionId) {
      this.setValue('groups', this.groups.map(group => group.id === groupId ? Object.assign({}, group, { conditions: group.conditions.filter(item => item.id !== conditionId) }) : group));
    },
    evaluateCondition(condition) {
      const actual = this.context[condition.field]; if (condition.comparator === 'less') return Number(actual) < Number(condition.value); return String(actual) === String(condition.value);
    },
    testPolicy() {
      const traces = this.groups.map(group => { const values = group.conditions.map(condition => this.evaluateCondition(condition)); return { id: group.id, passed: group.operator === 'AND' ? values.every(Boolean) : values.some(Boolean) }; }); const passed = this.groupJoin === 'AND' ? traces.every(item => item.passed) : traces.some(item => item.passed); this.setValue('testTrace', traces); this.setValue('testResult', passed); this.emitEvent('test', { passed, traces });
    },
    publish() {
      if (!this.canPublish) return; this.setValue('publishedVersion', this.publishedVersion + 1); this.emitEvent('publish', { version: this.publishedVersion, groups: this.groups, effect: this.effect });
    }
  }
};
</script>

<style scoped>

.policy-rule-composer{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.policy-rule-composer *{box-sizing:border-box}
.policy-rule-composer h2,.policy-rule-composer h3,.policy-rule-composer p{margin-top:0}
.policy-rule-composer button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.policy-rule-composer button.primary{border-color:#b45309;background:#b45309;color:#fff}
.policy-rule-composer button:disabled{opacity:.45;cursor:not-allowed}
.policy-rule-composer input,.policy-rule-composer select,.policy-rule-composer textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.policy-rule-composer .muted{color:#71808e;font-size:12px}
.policy-rule-composer .toolbar,.policy-rule-composer .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.policy-layout{display:grid;grid-template-columns:1fr 240px;gap:14px}.join-row{padding:10px;background:#fffbeb}.rule-group{margin:10px 0;padding:12px;border:1px solid #fcd34d}.condition{display:grid;grid-template-columns:110px 90px 1fr auto;gap:6px;margin:7px 0}.policy-layout aside{padding:12px;background:#f8fafc}.policy-layout label{display:grid;margin:8px 0}.policy-layout output{display:block;padding:12px;margin-top:10px;text-align:center}.policy-layout output.pass{background:#dcfce7;color:#166534}.policy-layout output.deny{background:#fee2e2;color:#991b1b}footer{margin-top:10px;color:#64748b}
</style>
