<template>
  <section :class="'session-timeout-notice ' + stateClass"><h2>{{ remaining ? '会话剩余 ' + remaining + ' 秒' : '会话已过期' }}</h2><p>{{ paused ? '计时已暂停' : '请及时保存当前工作' }}</p><div class="actions"><button @click="togglePause" :disabled="remaining === 0">{{ paused ? '继续' : '暂停' }}</button><button class="primary" @click="extend">延长会话</button></div></section>
</template>

<script>
module.exports = {
  name: 'SessionTimeoutNotice',
  props: {
    initialSeconds: { type: Number, default: 15 },
    warningAt: { type: Number, default: 5 }
  },
  data() {
    return {
        remaining: 15,
        paused: false
    };
  },
  computed: {
    stateClass() {
      return this.remaining === 0 ? 'expired' : this.remaining <= this.warningAt ? 'warning' : 'active';
    }
  },
  created() {
    this.setValue('remaining', this.initialSeconds);
  },
  mounted() {
    this._timer = setInterval(() => this.tick(), 1000);
  },
  beforeDestroy() {
    clearInterval(this._timer);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    tick() {
      if (this.paused || this.remaining <= 0) return; const next = this.remaining - 1; this.setValue('remaining', next); if (next === 0) this.emitEvent('expire');
    },
    togglePause() {
      this.setValue('paused', !this.paused);
    },
    extend() {
      this.setValue('remaining', this.initialSeconds); this.setValue('paused', false);
    }
  }
};
</script>

<style scoped>

.session-timeout-notice{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.session-timeout-notice *{box-sizing:border-box}
.session-timeout-notice h2,.session-timeout-notice h3,.session-timeout-notice p{margin-top:0}
.session-timeout-notice button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.session-timeout-notice button.primary{border-color:#b91c1c;background:#b91c1c;color:#fff}
.session-timeout-notice button:disabled{opacity:.45;cursor:not-allowed}
.session-timeout-notice input,.session-timeout-notice select,.session-timeout-notice textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.session-timeout-notice .muted{color:#71808e;font-size:12px}
.session-timeout-notice .toolbar,.session-timeout-notice .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.session-timeout-notice.warning{border-color:#d97706;background:#fffbeb}.session-timeout-notice.expired{border-color:#dc2626;background:#fef2f2}
</style>
