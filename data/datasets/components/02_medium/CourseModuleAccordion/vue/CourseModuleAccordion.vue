<template>
  <section class="course-module-accordion"><header><h2>课程进度 {{ progress }}%</h2><label><input type="checkbox" :checked="unfinishedOnly" @change="toggleFilter"> 仅未完成</label></header><article v-for="module in modules" :key="module.id"><button class="module-head" @click="toggleModule(module.id)"><strong>{{ module.title }}</strong><span>{{ isOpen(module.id, openIds) ? '收起' : '展开' }}</span></button><div v-if="isOpen(module.id, openIds)" class="lessons"><label v-for="lesson in visibleLessons(module.lessons, completedIds, unfinishedOnly)" :key="lesson.id" :class="isCompleted(lesson.id, completedIds) ? 'done' : ''"><input type="checkbox" :checked="isCompleted(lesson.id, completedIds)" @change="toggleLesson(lesson.id)"> {{ lesson.title }}</label></div></article></section>
</template>

<script>
module.exports = {
  name: 'CourseModuleAccordion',
  props: {
    modules: { type: Array, default: () => ([
          {
            "id": 1,
            "title": "模板迁移",
            "lessons": [
              {
                "id": 11,
                "title": "指令转换"
              },
              {
                "id": 12,
                "title": "循环与条件"
              }
            ]
          },
          {
            "id": 2,
            "title": "脚本迁移",
            "lessons": [
              {
                "id": 21,
                "title": "响应式数据"
              },
              {
                "id": 22,
                "title": "生命周期"
              }
            ]
          }
        ]) },
    initiallyOpen: { type: Number, default: 1 }
  },
  data() {
    return {
        openIds: [],
        completedIds: [],
        unfinishedOnly: false
    };
  },
  computed: {
    totalLessons() {
      return this.modules.reduce((sum, module) => sum + module.lessons.length, 0);
    },
    progress() {
      return Math.round(this.completedIds.length / (this.totalLessons || 1) * 100);
    }
  },
  created() {
    this.setValue('openIds', [this.initiallyOpen]);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    toggleModule(id) {
      const open = this.openIds; this.setValue('openIds', open.indexOf(id) >= 0 ? open.filter(item => item !== id) : open.concat(id));
    },
    isOpen(id, openIds) {
      return openIds.indexOf(id) >= 0;
    },
    toggleLesson(id) {
      const completed = this.completedIds; this.setValue('completedIds', completed.indexOf(id) >= 0 ? completed.filter(item => item !== id) : completed.concat(id)); this.emitEvent('progress', this.completedIds);
    },
    isCompleted(id, completedIds) {
      return completedIds.indexOf(id) >= 0;
    },
    toggleFilter(event) {
      this.setValue('unfinishedOnly', event.target.checked);
    },
    visibleLessons(lessons, completedIds, unfinishedOnly) {
      return unfinishedOnly ? lessons.filter(item => completedIds.indexOf(item.id) < 0) : lessons;
    }
  }
};
</script>

<style scoped>

.course-module-accordion{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.course-module-accordion *{box-sizing:border-box}
.course-module-accordion h2,.course-module-accordion h3,.course-module-accordion p{margin-top:0}
.course-module-accordion button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.course-module-accordion button.primary{border-color:#4f46e5;background:#4f46e5;color:#fff}
.course-module-accordion button:disabled{opacity:.45;cursor:not-allowed}
.course-module-accordion input,.course-module-accordion select,.course-module-accordion textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.course-module-accordion .muted{color:#71808e;font-size:12px}
.course-module-accordion .toolbar,.course-module-accordion .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.course-module-accordion article{border:1px solid #e2e8f0}.module-head{display:flex;width:100%;justify-content:space-between;border:0}.lessons{display:grid;padding:10px}.lessons label{padding:7px}.lessons label.done{text-decoration:line-through;color:#64748b}
</style>
