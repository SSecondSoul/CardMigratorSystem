<template>
  <section class="schema-mapping-workbench"><header><div><p class="muted">{{ mappedCount }} 条规则</p><h2>{{ title }}</h2></div><div class="actions"><button @click="togglePreview">{{ previewMode ? '编辑' : '预览' }}</button><button @click="validateMappings">校验</button><button class="primary" @click="submit">提交</button></div></header><div class="mapping-layout"><aside><h3>源字段</h3><button v-for="field in unmappedSources" :key="field.key" :class="field.key === sourceKey ? 'selected' : ''" @click="selectSource(field.key)"><strong>{{ field.key }}</strong><small>{{ field.type }}</small></button></aside><main><article v-for="mapping in mappings" :key="mapping.id"><div><strong>{{ mapping.source }}</strong><small>{{ fieldType(mapping.source, sourceFields) }}</small></div><span>→</span><select :value="mapping.transform" @change="updateTransform(mapping.id, $event)" :disabled="previewMode"><option v-for="transform in transforms" :key="transform" :value="transform">{{ transform }}</option></select><span>→</span><div><strong>{{ mapping.target }}</strong><small>{{ fieldType(mapping.target, targetFields) }}</small></div><button v-if="!previewMode" @click="removeMapping(mapping.id)">删除</button></article><p v-if="!mappings.length" class="empty">选择字段建立映射</p><button class="connect" @click="connect" :disabled="!canConnect || previewMode">连接所选字段</button><section v-if="validated" :class="issues.length ? 'validation bad' : 'validation good'"><h3>{{ issues.length ? '发现问题' : '校验通过' }}</h3><ul><li v-for="issue in issues" :key="issue">{{ issue }}</li></ul></section></main><aside><h3>目标字段</h3><button v-for="field in unmappedTargets" :key="field.key" :class="field.key === targetKey ? 'selected' : ''" @click="selectTarget(field.key)"><strong>{{ field.key }}</strong><small>{{ field.type }}{{ field.required ? ' · 必填' : '' }}</small></button></aside></div></section>
</template>

<script>
module.exports = {
  name: 'SchemaMappingWorkbench',
  props: {
    title: { type: String, default: "客户数据映射" },
    sourceFields: { type: Array, default: () => ([
          {
            "key": "full_name",
            "type": "string"
          },
          {
            "key": "birth_year",
            "type": "number"
          },
          {
            "key": "email_addr",
            "type": "string"
          }
        ]) },
    targetFields: { type: Array, default: () => ([
          {
            "key": "name",
            "type": "string",
            "required": true
          },
          {
            "key": "age",
            "type": "number",
            "required": false
          },
          {
            "key": "email",
            "type": "string",
            "required": true
          }
        ]) },
    initialMappings: { type: Array, default: () => ([
          {
            "id": 1,
            "source": "full_name",
            "target": "name",
            "transform": "trim"
          }
        ]) }
  },
  data() {
    return {
        mappings: [],
        sourceKey: "",
        targetKey: "",
        issues: [],
        validated: false,
        previewMode: false,
        nextId: 10,
        transforms: [
          "none",
          "trim",
          "uppercase",
          "to-number"
        ]
    };
  },
  computed: {
    unmappedSources() {
      const used = this.mappings.map(item => item.source); return this.sourceFields.filter(field => used.indexOf(field.key) < 0);
    },
    unmappedTargets() {
      const used = this.mappings.map(item => item.target); return this.targetFields.filter(field => used.indexOf(field.key) < 0);
    },
    mappedCount() {
      return this.mappings.length;
    },
    canConnect() {
      return !!this.sourceKey && !!this.targetKey;
    }
  },
  created() {
    this.setValue('mappings', this.initialMappings.map(item => Object.assign({}, item)));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    selectSource(key) {
      this.setValue('sourceKey', key); this.setValue('validated', false);
    },
    selectTarget(key) {
      this.setValue('targetKey', key); this.setValue('validated', false);
    },
    connect() {
      if (!this.canConnect) return; this.setValue('mappings', this.mappings.concat({ id: this.nextId, source: this.sourceKey, target: this.targetKey, transform: 'none' })); this.setValue('nextId', this.nextId + 1); this.setValue('sourceKey', ''); this.setValue('targetKey', ''); this.setValue('validated', false);
    },
    removeMapping(id) {
      this.setValue('mappings', this.mappings.filter(item => item.id !== id)); this.setValue('validated', false);
    },
    updateTransform(id, event) {
      this.setValue('mappings', this.mappings.map(item => item.id === id ? Object.assign({}, item, { transform: event.target.value }) : item)); this.setValue('validated', false);
    },
    validateMappings() {
      const mappings = this.mappings; const issues = []; this.targetFields.filter(field => field.required).forEach(field => { if (!mappings.some(item => item.target === field.key)) issues.push('必填字段 ' + field.key + ' 未映射'); }); mappings.forEach(item => { const source = this.sourceFields.find(field => field.key === item.source); const target = this.targetFields.find(field => field.key === item.target); if (source && target && source.type !== target.type && item.transform !== 'to-number') issues.push(item.source + ' 与 ' + item.target + ' 类型不一致'); }); this.setValue('issues', issues); this.setValue('validated', true); this.emitEvent('validate', issues);
    },
    togglePreview() {
      this.setValue('previewMode', !this.previewMode);
    },
    submit() {
      this.validateMappings(); if (!this.issues.length) this.emitEvent('submit', this.mappings);
    },
    fieldType(key, list) {
      const field = list.find(item => item.key === key); return field ? field.type : '';
    }
  }
};
</script>

<style scoped>

.schema-mapping-workbench { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.schema-mapping-workbench * { box-sizing: border-box; }
.schema-mapping-workbench h2, .schema-mapping-workbench h3, .schema-mapping-workbench p { margin-top: 0; }
.schema-mapping-workbench h2 { margin-bottom: 14px; font-size: 21px; }
.schema-mapping-workbench button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.schema-mapping-workbench button.primary { border-color: #7c3aed; background: #7c3aed; color: #fff; }
.schema-mapping-workbench button:disabled { opacity: .45; cursor: not-allowed; }
.schema-mapping-workbench input, .schema-mapping-workbench select, .schema-mapping-workbench textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.schema-mapping-workbench .toolbar, .schema-mapping-workbench .summary, .schema-mapping-workbench .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.schema-mapping-workbench .muted { color: #71808e; font-size: 12px; }
.schema-mapping-workbench .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
header{display:flex;justify-content:space-between}.mapping-layout{display:grid;grid-template-columns:145px 1fr 145px;gap:12px;margin-top:14px}.mapping-layout>aside{padding:10px;background:#f6f5fb}.mapping-layout>aside button{display:block;width:100%;margin:6px 0;text-align:left}.mapping-layout>aside button.selected{background:#ede9fe;border-color:#7c3aed}.mapping-layout small{display:block}.mapping-layout main>article{display:grid;grid-template-columns:1fr 18px 100px 18px 1fr auto;align-items:center;gap:5px;padding:10px;border-bottom:1px solid #e3e2e9}.connect{display:block;margin:12px auto}.validation{padding:12px}.validation.bad{background:#fef2f2}.validation.good{background:#f0fdf4}

</style>
