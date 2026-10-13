<template>
  <label class="password-visibility-field"><span>{{ label }}</span><div class="secret-row"><input :type="inputType" :value="value" @input="updateValue"><button type="button" @click="toggleVisibility">{{ visible ? '隐藏' : '显示' }}</button></div><small>{{ value ? '已输入 ' + value.length + ' 个字符' : '尚未输入' }}</small></label>
</template>

<script>
module.exports = {
  name: 'PasswordVisibilityField',
  props: {
    label: { type: String, default: "接口密钥" }
  },
  data() {
    return {
        value: "",
        visible: false
    };
  },
  computed: {
    inputType() {
      return this.visible ? 'text' : 'password';
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateValue(event) {
      this.setValue('value', event.target.value);
    },
    toggleVisibility() {
      this.setValue('visible', !this.visible);
    }
  }
};
</script>

<style scoped>

.password-visibility-field { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.password-visibility-field * { box-sizing: border-box; }
.password-visibility-field h2, .password-visibility-field h3, .password-visibility-field p { margin-top: 0; }
.password-visibility-field h2 { margin-bottom: 14px; font-size: 21px; }
.password-visibility-field button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.password-visibility-field button.primary { border-color: #9333ea; background: #9333ea; color: #fff; }
.password-visibility-field button:disabled { opacity: .45; cursor: not-allowed; }
.password-visibility-field input, .password-visibility-field select, .password-visibility-field textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.password-visibility-field .toolbar, .password-visibility-field .summary, .password-visibility-field .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.password-visibility-field .muted { color: #71808e; font-size: 12px; }
.password-visibility-field .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.secret-row{display:grid;grid-template-columns:1fr auto;gap:7px}.password-visibility-field>span{display:block;margin-bottom:7px;font-weight:700}.password-visibility-field small{display:block;margin-top:7px;color:#71808e}

</style>
