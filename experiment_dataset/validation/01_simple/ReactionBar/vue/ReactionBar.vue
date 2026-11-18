<template>
  <section class="reaction-bar"><h2>这段内容有帮助吗？</h2><div class="reaction-actions"><button :class="selected === 'like' ? 'active' : ''" @click="react('like')">有帮助 {{ counts.like }}</button><button :class="selected === 'question' ? 'active' : ''" @click="react('question')">仍有疑问 {{ counts.question }}</button></div><p class="muted">共 {{ total }} 次反馈</p></section>
</template>

<script>
module.exports = {
  name: 'ReactionBar',
  data() {
    return {
        counts: {
          "like": 12,
          "question": 3
        },
        selected: ""
    };
  },
  computed: {
    total() {
      return this.counts.like + this.counts.question;
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    react(kind) {
      const counts = Object.assign({}, this.counts); const old = this.selected; if (old) counts[old] -= 1; const next = old === kind ? '' : kind; if (next) counts[next] += 1; this.setValue('counts', counts); this.setValue('selected', next);
    }
  }
};
</script>

<style scoped>

.reaction-bar { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.reaction-bar * { box-sizing: border-box; }
.reaction-bar h2, .reaction-bar h3, .reaction-bar p { margin-top: 0; }
.reaction-bar h2 { margin-bottom: 14px; font-size: 21px; }
.reaction-bar button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.reaction-bar button.primary { border-color: #be185d; background: #be185d; color: #fff; }
.reaction-bar button:disabled { opacity: .45; cursor: not-allowed; }
.reaction-bar input, .reaction-bar select, .reaction-bar textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.reaction-bar .toolbar, .reaction-bar .summary, .reaction-bar .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.reaction-bar .muted { color: #71808e; font-size: 12px; }
.reaction-bar .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.reaction-actions{display:flex;gap:8px}.reaction-actions .active{border-color:#be185d;background:#fce7f3;color:#9d174d}

</style>
