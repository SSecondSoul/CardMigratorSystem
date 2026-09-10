<template>
  <section class="api-contract-workbench"><header><div><small>修订版 {{ savedRevision }} · {{ auth }}</small><h2>{{ serviceName }}</h2></div><button class="primary" @click="saveContract" :disabled="!canGenerate">保存契约</button></header><div class="api-layout"><aside><h3>端点</h3><button v-for="endpoint in endpoints" :key="endpoint.id" :class="selectedId === endpoint.id ? 'active' : ''" @click="selectEndpoint(endpoint.id)"><b>{{ endpoint.method }}</b><code>{{ endpoint.path }}</code><span>{{ endpoint.summary }}</span></button></aside><main v-if="selectedEndpoint"><div class="endpoint-form"><select :value="selectedEndpoint.method" @change="updateEndpoint('method', $event)"><option>GET</option><option>POST</option><option>PUT</option><option>DELETE</option></select><input :value="selectedEndpoint.path" @input="updateEndpoint('path', $event)"><input :value="selectedEndpoint.summary" @input="updateEndpoint('summary', $event)"></div><p>operationId: <code>{{ operationId }}</code></p><table><thead><tr><th>参数名</th><th>位置</th><th>类型</th><th>必填</th><th></th></tr></thead><tbody><tr v-for="parameter in selectedParameters" :key="parameter.id"><td><input :value="parameter.name" @input="updateParameter(parameter.id, 'name', $event)"></td><td><select :value="parameter.location" @change="updateParameter(parameter.id, 'location', $event)"><option>query</option><option>path</option><option>body</option><option>header</option></select></td><td><select :value="parameter.type" @change="updateParameter(parameter.id, 'type', $event)"><option>string</option><option>number</option><option>boolean</option><option>object</option></select></td><td><input type="checkbox" :checked="parameter.required" @change="updateParameter(parameter.id, 'required', $event)"></td><td><button @click="removeParameter(parameter.id)">删除</button></td></tr></tbody></table><button @click="addParameter">添加参数</button></main><aside class="preview"><h3>校验与生成</h3><select :value="auth" @change="setAuth"><option v-for="scheme in authSchemes" :key="scheme" :value="scheme">{{ scheme }}</option></select><ul><li v-for="issue in issues" :key="issue">{{ issue }}</li></ul><button @click="generateClient" :disabled="!canGenerate">生成调用代码</button><pre>{{ generated || '校验通过后生成客户端片段' }}</pre></aside></div></section>
</template>

<script>
module.exports = {
  name: 'ApiContractWorkbench',
  props: {
    serviceName: { type: String, default: "支付服务 API" },
    initialEndpoints: { type: Array, default: () => ([
          {
            "id": 1,
            "method": "POST",
            "path": "/payments",
            "summary": "创建支付"
          },
          {
            "id": 2,
            "method": "GET",
            "path": "/payments/:id",
            "summary": "查询支付"
          }
        ]) },
    authSchemes: { type: Array, default: () => ([
          "Bearer Token",
          "API Key",
          "None"
        ]) },
    responseCodes: { type: Array, default: () => ([
          200,
          201,
          400,
          404,
          500
        ]) },
    readonly: { type: Boolean, default: false }
  },
  data() {
    return {
        endpoints: [],
        selectedId: 1,
        parameters: {},
        schemas: {},
        auth: "Bearer Token",
        issues: [],
        generated: "",
        savedRevision: 0,
        nextParameterId: 10
    };
  },
  computed: {
    selectedEndpoint() {
      return this.endpoints.find(item => item.id === this.selectedId) || null;
    },
    selectedParameters() {
      return this.parameters[this.selectedId] || [];
    },
    operationId() {
      return this.selectedEndpoint ? (this.selectedEndpoint.method.toLowerCase() + this.selectedEndpoint.path.replace(/[^a-zA-Z0-9]+/g, '_')) : '';
    },
    canGenerate() {
      return !!this.selectedEndpoint && this.issues.length === 0;
    }
  },
  created() {
    this.setValue('endpoints', this.initialEndpoints.map(item => Object.assign({}, item))); const parameters = {}; let nextParameterId = 1; this.initialEndpoints.forEach(item => { const parameterId = item.id * 10; parameters[item.id] = [{ id: parameterId, name: item.method === 'GET' ? 'id' : 'amount', location: item.method === 'GET' ? 'path' : 'body', required: true, type: item.method === 'GET' ? 'string' : 'number' }]; nextParameterId = Math.max(nextParameterId, parameterId + 1); }); this.setValue('parameters', parameters); this.setValue('nextParameterId', nextParameterId); this.validateContract();
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    selectEndpoint(id) {
      this.setValue('selectedId', id); this.validateContract();
    },
    updateEndpoint(field, event) {
      if (this.readonly || !this.selectedEndpoint) return; this.setValue('endpoints', this.endpoints.map(item => item.id === this.selectedId ? Object.assign({}, item, { [field]: event.target.value }) : item)); this.validateContract(); this.emitEvent('change', this.selectedEndpoint);
    },
    setAuth(event) {
      this.setValue('auth', event.target.value);
    },
    addParameter() {
      if (this.readonly || !this.selectedEndpoint) return; const id = this.nextParameterId; const list = this.selectedParameters.concat({ id, name: '', location: 'query', required: false, type: 'string' }); this.setValue('parameters', Object.assign({}, this.parameters, { [this.selectedId]: list })); this.setValue('nextParameterId', id + 1); this.validateContract();
    },
    updateParameter(id, field, event) {
      const value = field === 'required' ? event.target.checked : event.target.value; const list = this.selectedParameters.map(item => item.id === id ? Object.assign({}, item, { [field]: value }) : item); this.setValue('parameters', Object.assign({}, this.parameters, { [this.selectedId]: list })); this.validateContract();
    },
    removeParameter(id) {
      const list = this.selectedParameters.filter(item => item.id !== id); this.setValue('parameters', Object.assign({}, this.parameters, { [this.selectedId]: list })); this.validateContract();
    },
    validateContract() {
      const issues = []; if (!this.selectedEndpoint) issues.push('请选择端点'); else { if (this.selectedEndpoint.path.charAt(0) !== '/') issues.push('路径必须以 / 开头'); if (!this.selectedEndpoint.summary.trim()) issues.push('缺少摘要'); const names = {}; this.selectedParameters.forEach(item => { if (!item.name) issues.push('参数名不能为空'); else if (names[item.name]) issues.push('参数名重复：' + item.name); names[item.name] = true; }); } this.setValue('issues', issues); this.emitEvent('validate', issues);
    },
    generateClient() {
      if (!this.canGenerate) return; const endpoint = this.selectedEndpoint; const code = 'client.' + endpoint.method.toLowerCase() + '(' + endpoint.path + ', payload)'; this.setValue('generated', code); this.emitEvent('generate', code);
    },
    saveContract() {
      if (!this.canGenerate) return; this.setValue('savedRevision', this.savedRevision + 1); this.emitEvent('save', { revision: this.savedRevision, endpoints: this.endpoints, parameters: this.parameters });
    }
  }
};
</script>

<style scoped>

.api-contract-workbench{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.api-contract-workbench *{box-sizing:border-box}
.api-contract-workbench h2,.api-contract-workbench h3,.api-contract-workbench p{margin-top:0}
.api-contract-workbench button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.api-contract-workbench button.primary{border-color:#2563eb;background:#2563eb;color:#fff}
.api-contract-workbench button:disabled{opacity:.45;cursor:not-allowed}
.api-contract-workbench input,.api-contract-workbench select,.api-contract-workbench textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.api-contract-workbench .muted{color:#71808e;font-size:12px}
.api-contract-workbench .toolbar,.api-contract-workbench .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.api-layout{display:grid;grid-template-columns:220px 1fr 230px;gap:12px}.api-layout>aside{padding:10px;background:#f8fafc}.api-layout>aside>button{display:grid;width:100%;text-align:left;margin-bottom:7px}.api-layout>aside>button.active{background:#e0f2fe;border-color:#0284c7}.endpoint-form{display:grid;grid-template-columns:90px 1fr 1fr;gap:7px}table{width:100%;border-collapse:collapse;margin:10px 0}th,td{padding:6px;border:1px solid #cbd5e1}td input,td select{width:100%;box-sizing:border-box}.preview select,.preview button{width:100%;margin-bottom:8px}.preview ul{padding-left:18px;color:#b91c1c}.preview pre{padding:10px;white-space:pre-wrap;background:#0f172a;color:#e2e8f0}
</style>
