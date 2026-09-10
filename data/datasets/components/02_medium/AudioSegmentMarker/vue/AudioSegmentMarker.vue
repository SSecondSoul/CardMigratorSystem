<template>
  <section class="audio-segment-marker"><h2>访谈片段标注</h2><input class="scrubber" type="range" min="0" :max="duration" :value="position" @input="updatePosition"><div class="timeline"><span class="head" :style="headStyle"></span><button v-for="marker in markers" :key="marker.id" :class="marker.id === selectedId ? 'selected' : ''" :style="markerStyle(marker, duration)" @click="select(marker.id)">{{ marker.label }}</button></div><form @submit="add"><input type="number" :value="start" @input="updateField('start', $event)" placeholder="开始秒"><input type="number" :value="end" @input="updateField('end', $event)" placeholder="结束秒"><input :value="label" @input="updateField('label', $event)" placeholder="标签"><button class="primary" type="submit">添加</button></form><ul><li v-for="marker in markers" :key="marker.id">{{ marker.start }}–{{ marker.end }}s {{ marker.label }}<button @click="remove(marker.id)">删除</button></li></ul></section>
</template>

<script>
module.exports = {
  name: 'AudioSegmentMarker',
  props: {
    duration: { type: Number, default: 300 },
    initialMarkers: { type: Array, default: () => ([
          {
            "id": 1,
            "start": 20,
            "end": 55,
            "label": "引言"
          },
          {
            "id": 2,
            "start": 120,
            "end": 165,
            "label": "核心观点"
          }
        ]) }
  },
  data() {
    return {
        position: 0,
        markers: [],
        start: 0,
        end: 30,
        label: "",
        selectedId: null,
        nextId: 10
    };
  },
  computed: {
    headStyle() {
      return 'left:' + this.position / this.duration * 100 + '%';
    }
  },
  created() {
    this.setValue('markers', this.initialMarkers.map(item => Object.assign({}, item)));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updatePosition(event) {
      this.setValue('position', Number(event.target.value));
    },
    updateField(field, event) {
      this.setValue(field, field === 'label' ? event.target.value : Number(event.target.value) || 0);
    },
    add(event) {
      event.preventDefault(); if (!this.label.trim() || this.start >= this.end || this.end > this.duration) return; this.setValue('markers', this.markers.concat({ id: this.nextId, start: this.start, end: this.end, label: this.label.trim() })); this.setValue('nextId', this.nextId + 1); this.setValue('label', ''); this.notify();
    },
    remove(id) {
      this.setValue('markers', this.markers.filter(item => item.id !== id)); this.notify();
    },
    select(id) {
      this.setValue('selectedId', id);
    },
    markerStyle(marker, duration) {
      return 'left:' + marker.start / duration * 100 + '%;width:' + (marker.end - marker.start) / duration * 100 + '%';
    },
    notify() {
      this.emitEvent('markers-change', this.markers.slice());
    }
  }
};
</script>

<style scoped>

.audio-segment-marker{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.audio-segment-marker *{box-sizing:border-box}
.audio-segment-marker h2,.audio-segment-marker h3,.audio-segment-marker p{margin-top:0}
.audio-segment-marker button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.audio-segment-marker button.primary{border-color:#be185d;background:#be185d;color:#fff}
.audio-segment-marker button:disabled{opacity:.45;cursor:not-allowed}
.audio-segment-marker input,.audio-segment-marker select,.audio-segment-marker textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.audio-segment-marker .muted{color:#71808e;font-size:12px}
.audio-segment-marker .toolbar,.audio-segment-marker .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.scrubber{width:100%}.timeline{position:relative;height:70px;margin:10px 0;background:#f1f5f9}.timeline .head{position:absolute;top:0;bottom:0;width:2px;background:#be185d}.timeline button{position:absolute;top:20px;overflow:hidden;white-space:nowrap}.timeline button.selected{background:#fce7f3}form{display:grid;grid-template-columns:90px 90px 1fr auto;gap:8px}ul{padding:0;list-style:none}li{display:flex;justify-content:space-between;padding:6px}
</style>
