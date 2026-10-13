<template>
  <section class="form-rule-playground"><h2>{{ title }}</h2><div class="rule-strip"><label v-for="rule in rules" :key="rule.id"><input type="checkbox" :checked="isEnabled(rule.id, enabled)" @change="toggleRule(rule.id)"> {{ rule.label }}</label></div><form @submit="submit"><input :value="form.name" @input="updateField('name', $event)" placeholder="用户名"><input :value="form.email" @input="updateField('email', $event)" placeholder="邮箱"><input type="number" :value="form.age" @input="updateField('age', $event)" placeholder="年龄"><button class="primary" type="submit">验证并提交</button></form><ul v-if="submitted && errors.length"><li v-for="error in errors" :key="error">{{ error }}</li></ul><p v-if="submitted && valid" class="success">表单通过全部启用规则</p></section>
</template>

<script>
module.exports = {
  name: 'FormRulePlayground',
  props: {
    rules: { type: Array, default: () => ([
          {
            "id": "email",
            "label": "邮箱格式"
          },
          {
            "id": "adult",
            "label": "年龄不少于 18"
          },
          {
            "id": "name",
            "label": "用户名不少于 3 位"
          }
        ]) },
    title: { type: String, default: "账号规则测试" }
  },
  data() {
    return {
        form: {
          "name": "",
          "email": "",
          "age": 18
        },
        enabled: [
          "email",
          "adult",
          "name"
        ],
        submitted: false
    };
  },
  computed: {
    errors() {
      const errors = []; if (this.enabled.indexOf('name') >= 0 && this.form.name.trim().length < 3) errors.push('用户名至少 3 位'); if (this.enabled.indexOf('email') >= 0 && this.form.email.indexOf('@') < 0) errors.push('邮箱格式无效'); if (this.enabled.indexOf('adult') >= 0 && Number(this.form.age) < 18) errors.push('年龄必须不少于 18'); return errors;
    },
    valid() {
      return this.errors.length === 0;
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateField(field, event) {
      this.setValue('form', Object.assign({}, this.form, { [field]: event.target.value })); this.setValue('submitted', false);
    },
    toggleRule(id) {
      const list = this.enabled; this.setValue('enabled', list.indexOf(id) >= 0 ? list.filter(item => item !== id) : list.concat(id));
    },
    isEnabled(id, enabled) {
      return enabled.indexOf(id) >= 0;
    },
    submit(event) {
      event.preventDefault(); this.setValue('submitted', true); if (this.valid) this.emitEvent('submit', Object.assign({}, this.form));
    }
  }
};
</script>

<style scoped>

.form-rule-playground{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.form-rule-playground *{box-sizing:border-box}
.form-rule-playground h2,.form-rule-playground h3,.form-rule-playground p{margin-top:0}
.form-rule-playground button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.form-rule-playground button.primary{border-color:#dc2626;background:#dc2626;color:#fff}
.form-rule-playground button:disabled{opacity:.45;cursor:not-allowed}
.form-rule-playground input,.form-rule-playground select,.form-rule-playground textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.form-rule-playground .muted{color:#71808e;font-size:12px}
.form-rule-playground .toolbar,.form-rule-playground .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.rule-strip{display:flex;gap:10px;flex-wrap:wrap;padding:10px;background:#f8fafc}form{display:grid;grid-template-columns:1fr 1fr 100px auto;gap:8px;margin-top:12px}ul{color:#b91c1c}.success{color:#15803d}
</style>
