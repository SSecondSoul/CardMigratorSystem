<template>
  <section class="volume-control"><header><h2>播放音量</h2><strong>{{ volumeLabel }}</strong></header><input class="volume-slider" type="range" min="0" max="100" :value="volume" @input="updateVolume"><button class="primary" @click="toggleMute">{{ volume === 0 ? '恢复音量' : '静音' }}</button></section>
</template>

<script>
module.exports = {
  name: 'VolumeControl',
  props: {
    initialVolume: { type: Number, default: 45 }
  },
  data() {
    return {
        volume: 45,
        lastVolume: 45
    };
  },
  computed: {
    volumeLabel() {
      return this.volume === 0 ? '已静音' : this.volume + '%';
    }
  },
  created() {
    this.setValue('volume', this.initialVolume); this.setValue('lastVolume', this.initialVolume || 45);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateVolume(event) {
      const value = Number(event.target.value); this.setValue('volume', value); if (value > 0) this.setValue('lastVolume', value); this.emitEvent('change', value);
    },
    toggleMute() {
      const next = this.volume === 0 ? this.lastVolume : 0; this.setValue('volume', next); this.emitEvent('change', next);
    }
  }
};
</script>

<style scoped>

.volume-control { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.volume-control * { box-sizing: border-box; }
.volume-control h2, .volume-control h3, .volume-control p { margin-top: 0; }
.volume-control h2 { margin-bottom: 14px; font-size: 21px; }
.volume-control button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.volume-control button.primary { border-color: #0f766e; background: #0f766e; color: #fff; }
.volume-control button:disabled { opacity: .45; cursor: not-allowed; }
.volume-control input, .volume-control select, .volume-control textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.volume-control .toolbar, .volume-control .summary, .volume-control .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.volume-control .muted { color: #71808e; font-size: 12px; }
.volume-control .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
header{display:flex;justify-content:space-between}.volume-slider{width:100%;margin:12px 0;accent-color:#0f766e}

</style>
