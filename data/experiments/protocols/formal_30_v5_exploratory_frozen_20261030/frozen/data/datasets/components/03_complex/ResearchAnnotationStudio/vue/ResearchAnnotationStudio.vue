<template>
  <section class="research-annotation-studio"><header><div><small>覆盖率 {{ coverage }}% · 冲突 {{ conflicts.length }}</small><h2>{{ documentTitle }}</h2></div><button class="primary" @click="submit" :disabled="!canSubmit">提交语料</button></header><div class="annotation-layout"><main><article class="document">{{ documentText }}</article><div class="span-form"><label>起点<input type="number" :value="start" @input="setBoundary('start', $event)"></label><label>终点<input type="number" :value="end" @input="setBoundary('end', $event)"></label><output>“{{ selectedText }}”</output></div><div class="labels"><button v-for="label in labels" :key="label.id" :class="activeLabelId === label.id ? 'active' : ''" :style="'border-color:' + label.color" @click="chooseLabel(label.id)">{{ label.name }}</button></div><select :value="reviewer" @change="setReviewer"><option v-for="person in reviewers" :key="person" :value="person">{{ person }}</option></select><button @click="addAnnotation">创建标注</button></main><aside><h3>标注列表</h3><article v-for="item in annotations" :key="item.id" :class="(selectedId === item.id ? 'selected ' : '') + item.status" :style="annotationStyle(item)" @click="selectAnnotation(item.id)"><strong>{{ labelName(item.labelId) }} · {{ item.start }}–{{ item.end }}</strong><span>{{ annotationText(item) }}</span><small>{{ item.author }} · {{ item.status }}</small><div><button @click="resolve(item.id, 'accepted')">接受</button><button @click="resolve(item.id, 'rejected')">拒绝</button><button @click="removeAnnotation(item.id)">删除</button></div></article></aside><aside class="conflicts"><h3>冲突仲裁</h3><p v-if="!conflicts.length">暂无重叠冲突</p><button v-for="item in conflicts" :key="item.id" @click="selectAnnotation(item.id)">#{{ item.id }} {{ labelName(item.labelId) }}</button><h3>仲裁记录</h3><p v-for="entry in resolutions" :key="entry.id">#{{ entry.annotationId }} {{ entry.action }}</p></aside></div></section>
</template>

<script>
module.exports = {
  name: 'ResearchAnnotationStudio',
  props: {
    documentTitle: { type: String, default: "访谈记录 07" },
    documentText: { type: String, default: "受访者认为公共交通改善了通勤效率，但高峰时段的换乘体验仍然需要优化。" },
    labels: { type: Array, default: () => ([
          {
            "id": "benefit",
            "name": "积极影响",
            "color": "#16a34a"
          },
          {
            "id": "problem",
            "name": "问题",
            "color": "#dc2626"
          },
          {
            "id": "suggestion",
            "name": "建议",
            "color": "#2563eb"
          }
        ]) },
    reviewers: { type: Array, default: () => ([
          "标注员A",
          "标注员B"
        ]) },
    minAnnotations: { type: Number, default: 2 }
  },
  data() {
    return {
        annotations: [
          {
            "id": 1,
            "start": 5,
            "end": 15,
            "labelId": "benefit",
            "author": "标注员A",
            "status": "accepted"
          },
          {
            "id": 2,
            "start": 21,
            "end": 35,
            "labelId": "problem",
            "author": "标注员B",
            "status": "pending"
          }
        ],
        start: 0,
        end: 4,
        activeLabelId: "benefit",
        reviewer: "标注员A",
        selectedId: null,
        resolutions: [],
        submitted: false,
        nextId: 10
    };
  },
  computed: {
    selectedText() {
      return this.documentText.slice(this.start, this.end);
    },
    conflicts() {
      return this.annotations.filter((item, index, list) => list.some((other, otherIndex) => otherIndex !== index && Math.max(item.start, other.start) < Math.min(item.end, other.end) && item.labelId !== other.labelId));
    },
    selectedAnnotation() {
      return this.annotations.find(item => item.id === this.selectedId) || null;
    },
    coverage() {
      const covered = {}; this.annotations.forEach(item => { for (let index = item.start; index < item.end; index += 1) covered[index] = true; }); return Math.round(Object.keys(covered).length / (this.documentText.length || 1) * 100);
    },
    canSubmit() {
      return this.annotations.length >= this.minAnnotations && this.conflicts.length === 0 && !this.submitted;
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    setBoundary(field, event) {
      const value = Math.max(0, Math.min(this.documentText.length, Number(event.target.value) || 0)); this.setValue(field, value);
    },
    chooseLabel(id) {
      this.setValue('activeLabelId', id);
    },
    setReviewer(event) {
      this.setValue('reviewer', event.target.value);
    },
    addAnnotation() {
      if (this.start >= this.end || !this.selectedText.trim()) return; const item = { id: this.nextId, start: this.start, end: this.end, labelId: this.activeLabelId, author: this.reviewer, status: 'pending' }; this.setValue('annotations', this.annotations.concat(item)); this.setValue('nextId', this.nextId + 1); this.setValue('selectedId', item.id); this.setValue('submitted', false); this.emitEvent('annotate', item);
    },
    selectAnnotation(id) {
      const item = this.annotations.find(annotation => annotation.id === id); this.setValue('selectedId', id); if (item) { this.setValue('start', item.start); this.setValue('end', item.end); this.setValue('activeLabelId', item.labelId); }
    },
    resolve(id, action) {
      this.setValue('annotations', this.annotations.map(item => item.id === id ? Object.assign({}, item, { status: action }) : item)); this.setValue('resolutions', [{ id: Date.now(), annotationId: id, action, reviewer: this.reviewer }].concat(this.resolutions)); this.emitEvent('resolve', { id, action });
    },
    removeAnnotation(id) {
      this.setValue('annotations', this.annotations.filter(item => item.id !== id)); if (this.selectedId === id) this.setValue('selectedId', null);
    },
    submit() {
      if (!this.canSubmit) return; this.setValue('submitted', true); this.emitEvent('submit', this.annotations);
    },
    labelName(id) {
      const label = this.labels.find(item => item.id === id); return label ? label.name : id;
    },
    annotationStyle(item) {
      const label = this.labels.find(entry => entry.id === item.labelId); return 'border-left-color:' + (label ? label.color : '#64748b');
    },
    annotationText(item) {
      return this.documentText.slice(item.start, item.end);
    }
  }
};
</script>

<style scoped>

.research-annotation-studio{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.research-annotation-studio *{box-sizing:border-box}
.research-annotation-studio h2,.research-annotation-studio h3,.research-annotation-studio p{margin-top:0}
.research-annotation-studio button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.research-annotation-studio button.primary{border-color:#9333ea;background:#9333ea;color:#fff}
.research-annotation-studio button:disabled{opacity:.45;cursor:not-allowed}
.research-annotation-studio input,.research-annotation-studio select,.research-annotation-studio textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.research-annotation-studio .muted{color:#71808e;font-size:12px}
.research-annotation-studio .toolbar,.research-annotation-studio .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.annotation-layout{display:grid;grid-template-columns:1fr 300px 180px;gap:12px}.document{padding:24px;font-size:18px;line-height:2;background:#fffbeb}.span-form{display:grid;grid-template-columns:90px 90px 1fr;gap:8px;margin:12px 0}.span-form label{display:grid}.span-form output{padding:8px;background:#f8fafc}.labels{display:flex;gap:7px;margin-bottom:8px}.labels button{border-left-width:6px}.labels button.active{background:#e0f2fe}.annotation-layout>aside{max-height:430px;overflow:auto}.annotation-layout>aside article{display:grid;padding:9px;margin-bottom:7px;border-left:6px solid #64748b;background:#f8fafc}.annotation-layout>aside article.selected{box-shadow:0 0 0 2px #93c5fd}.annotation-layout>aside article.rejected{opacity:.5}.conflicts{padding:10px;background:#fef2f2}.conflicts button{display:block;width:100%;margin:5px 0}
</style>
