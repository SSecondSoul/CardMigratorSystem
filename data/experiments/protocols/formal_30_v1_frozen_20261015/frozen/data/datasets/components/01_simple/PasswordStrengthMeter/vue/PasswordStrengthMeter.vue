<template>
  <section class="password-strength-meter"><h2>{{ label }}</h2><div class="field-row"><input type="password" :value="password" @input="updatePassword" placeholder="输入密码"><button @click="clear" :disabled="!password">清空</button></div><div class="meter"><span :class="'level-' + strength" :style="barStyle"></span></div><p>{{ strengthLabel }} · 至少 {{ minLength }} 位</p></section>
</template>

<script>
module.exports = {
  name: 'PasswordStrengthMeter',
  props: {
    label: { type: String, default: "设置访问密码" },
    minLength: { type: Number, default: 8 }
  },
  data() {
    return {
        password: ""
    };
  },
  computed: {
    strength() {
      let score = 0; const value = this.password; if (value.length >= this.minLength) score += 1; if (/[A-Z]/.test(value)) score += 1; if (/[0-9]/.test(value)) score += 1; return score;
    },
    strengthLabel() {
      return ['未输入', '较弱', '一般', '较强'][this.strength];
    },
    barStyle() {
      return 'width:' + (this.strength * 33.33) + '%';
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updatePassword(event) {
      this.setValue('password', event.target.value);
    },
    clear() {
      this.setValue('password', '');
    }
  }
};
</script>

<style scoped>

.password-strength-meter { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.password-strength-meter * { box-sizing: border-box; }
.password-strength-meter h2, .password-strength-meter h3, .password-strength-meter p { margin-top: 0; }
.password-strength-meter h2 { margin-bottom: 14px; font-size: 21px; }
.password-strength-meter button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.password-strength-meter button.primary { border-color: #2563eb; background: #2563eb; color: #fff; }
.password-strength-meter button:disabled { opacity: .45; cursor: not-allowed; }
.password-strength-meter input, .password-strength-meter select, .password-strength-meter textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.password-strength-meter .toolbar, .password-strength-meter .summary, .password-strength-meter .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.password-strength-meter .muted { color: #71808e; font-size: 12px; }
.password-strength-meter .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.field-row{display:grid;grid-template-columns:1fr auto;gap:8px}.meter{height:8px;background:#e6ebf0;overflow:hidden}.meter span{display:block;height:100%;background:#2563eb;transition:.2s}.level-1{opacity:.45}.level-2{opacity:.7}.level-3{opacity:1}

</style>
