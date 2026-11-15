<template>
  <section class="playback-queue"><header><div><p class="muted">正在播放</p><h2>{{ currentTrack ? currentTrack.title : '尚未选择' }}</h2></div><button :class="loop ? 'active' : ''" @click="toggleLoop">循环 {{ loop ? '开' : '关' }}</button></header><ol><li v-for="track, index in queue" :key="track.id" :class="track.id === currentId ? 'playing' : ''"><button class="track-title" @click="play(track.id)">{{ track.title }}</button><span>{{ formatTime(track.duration) }}</span><button @click="moveUp(index)" :disabled="index === 0">↑</button><button @click="remove(track.id)">移除</button></li></ol><footer>总时长 {{ formatTime(totalDuration) }}</footer></section>
</template>

<script>
module.exports = {
  name: 'PlaybackQueue',
  props: {
    tracks: { type: Array, default: () => ([
          {
            "id": 1,
            "title": "晨间序曲",
            "duration": 185
          },
          {
            "id": 2,
            "title": "城市漫步",
            "duration": 214
          },
          {
            "id": 3,
            "title": "夜航",
            "duration": 197
          }
        ]) }
  },
  data() {
    return {
        queue: [],
        currentId: null,
        loop: false
    };
  },
  computed: {
    currentTrack() {
      return this.queue.find(item => item.id === this.currentId) || null;
    },
    totalDuration() {
      return this.queue.reduce((sum, item) => sum + item.duration, 0);
    }
  },
  created() {
    this.setValue('queue', this.tracks.map(item => Object.assign({}, item)));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    play(id) {
      this.setValue('currentId', id); this.emitEvent('play', id);
    },
    moveUp(index) {
      if (index < 1) return; const list = this.queue.slice(); const item = list.splice(index, 1)[0]; list.splice(index - 1, 0, item); this.setValue('queue', list); this.emitEvent('change', list.slice());
    },
    remove(id) {
      const list = this.queue.filter(item => item.id !== id); this.setValue('queue', list); if (this.currentId === id) this.setValue('currentId', null); this.emitEvent('change', list.slice());
    },
    toggleLoop() {
      this.setValue('loop', !this.loop);
    },
    formatTime(seconds) {
      const minutes = Math.floor(seconds / 60); return minutes + ':' + String(seconds % 60).padStart(2, '0');
    }
  }
};
</script>

<style scoped>

.playback-queue { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.playback-queue * { box-sizing: border-box; }
.playback-queue h2, .playback-queue h3, .playback-queue p { margin-top: 0; }
.playback-queue h2 { margin-bottom: 14px; font-size: 21px; }
.playback-queue button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.playback-queue button.primary { border-color: #be185d; background: #be185d; color: #fff; }
.playback-queue button:disabled { opacity: .45; cursor: not-allowed; }
.playback-queue input, .playback-queue select, .playback-queue textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.playback-queue .toolbar, .playback-queue .summary, .playback-queue .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.playback-queue .muted { color: #71808e; font-size: 12px; }
.playback-queue .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
header{display:flex;justify-content:space-between}header button.active{background:#fce7f3;border-color:#be185d}ol{padding-left:24px}li{display:grid;grid-template-columns:1fr 55px 38px auto;gap:7px;padding:8px}li.playing{background:#fdf2f8}.track-title{text-align:left;border:0}

</style>
