<template>
  <section class="otp-code-input"><h2>输入验证码</h2><input inputmode="numeric" :maxlength="length" :value="code" @input="updateCode" placeholder="仅输入数字"><p>{{ complete ? '验证码长度正确' : '还需 ' + remaining + ' 位' }}</p><div class="actions"><button @click="clear">清空</button><button class="primary" @click="verify" :disabled="!complete">验证</button></div><strong v-if="submitted">已提交验证</strong></section>
</template>

<script>
module.exports = {
  name: 'OtpCodeInput',
  props: {
    length: { type: Number, default: 6 }
  },
  data() {
    return {
        code: "",
        submitted: false
    };
  },
  computed: {
    remaining() {
      return Math.max(0, this.length - this.code.length);
    },
    complete() {
      return this.code.length === this.length;
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateCode(event) {
      this.setValue('code', event.target.value.replace(/\D/g, '').slice(0, this.length)); this.setValue('submitted', false);
    },
    clear() {
      this.setValue('code', ''); this.setValue('submitted', false);
    },
    verify() {
      if (!this.complete) return; this.setValue('submitted', true); this.emitEvent('complete', this.code);
    }
  }
};
</script>

<style scoped>

.otp-code-input{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.otp-code-input *{box-sizing:border-box}
.otp-code-input h2,.otp-code-input h3,.otp-code-input p{margin-top:0}
.otp-code-input button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.otp-code-input button.primary{border-color:#dc2626;background:#dc2626;color:#fff}
.otp-code-input button:disabled{opacity:.45;cursor:not-allowed}
.otp-code-input input,.otp-code-input select,.otp-code-input textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.otp-code-input .muted{color:#71808e;font-size:12px}
.otp-code-input .toolbar,.otp-code-input .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.otp-code-input input{width:100%;font-size:24px;letter-spacing:8px}.otp-code-input>strong{display:block;margin-top:10px;color:#15803d}
</style>
