<template>
  <section class="quiz-navigator">
    <header>
      <div><span class="eyebrow">知识测验</span><h2>{{ title }}</h2></div>
      <span>{{ answeredCount }}/{{ questions.length }}</span>
    </header>
    <div class="quiz-progress"><span :style="{ width: progress + '%' }"></span></div>
    <div v-if="!finished" class="question-panel">
      <small>第 {{ currentIndex + 1 }} 题</small>
      <h3>{{ currentQuestion.prompt }}</h3>
      <div class="option-list">
        <button
          v-for="option in currentQuestion.options"
          :key="option"
          type="button"
          :class="{ selected: answers[currentQuestion.id] === option }"
          @click="choose(option)"
        >{{ option }}</button>
      </div>
      <footer>
        <button type="button" :disabled="currentIndex === 0" @click="previous">上一题</button>
        <button v-if="currentIndex < questions.length - 1" type="button" @click="next">下一题</button>
        <button v-else type="button" @click="finish">提交答案</button>
      </footer>
    </div>
    <div v-else class="result-panel">
      <strong>{{ score }} / {{ questions.length }}</strong>
      <p>测验已完成，可重新作答。</p>
      <button type="button" @click="restart">重新开始</button>
    </div>
  </section>
</template>

<script>
module.exports = {
  name: 'QuizNavigator',
  props: {
    title: { type: String, default: '迁移基础检查' },
    questions: {
      type: Array,
      default: function () {
        return [
          { id: 1, prompt: 'Vue 的事件简写是什么？', options: ['@', '#', '&'], answer: '@' },
          { id: 2, prompt: 'San 使用哪种方式读取数据？', options: ['this.data.get', 'this.state', 'this.value'], answer: 'this.data.get' },
          { id: 3, prompt: '组件输入类型声明对应什么？', options: ['dataTypes', 'filters', 'mixins'], answer: 'dataTypes' }
        ];
      }
    }
  },
  data() {
    return { currentIndex: 0, answers: {}, finished: false };
  },
  computed: {
    currentQuestion() { return this.questions[this.currentIndex]; },
    answeredCount() { return Object.keys(this.answers).length; },
    score() { return this.questions.filter((question) => this.answers[question.id] === question.answer).length; },
    progress() { return Math.round((this.answeredCount / this.questions.length) * 100); }
  },
  methods: {
    choose(option) { this.$set(this.answers, this.currentQuestion.id, option); },
    previous() { this.currentIndex = Math.max(0, this.currentIndex - 1); },
    next() { this.currentIndex = Math.min(this.questions.length - 1, this.currentIndex + 1); },
    finish() { this.finished = true; },
    restart() { this.currentIndex = 0; this.answers = {}; this.finished = false; }
  }
};
</script>

<style scoped>
.quiz-navigator { width: 520px; padding: 22px; border: 1px solid #d1d5db; border-radius: 7px; background: #fdfdfd; color: #1f2937; font-family: Arial, sans-serif; }
.quiz-navigator header { display: flex; justify-content: space-between; align-items: flex-start; }
.quiz-navigator h2 { margin: 3px 0 0; font-size: 21px; }
.eyebrow, .question-panel small { color: #6b7280; font-size: 12px; }
.quiz-progress { height: 6px; margin: 16px 0 20px; background: #e5e7eb; }
.quiz-progress span { display: block; height: 100%; background: #7c3aed; transition: width 0.2s ease; }
.question-panel h3 { min-height: 48px; }
.option-list { display: grid; gap: 8px; }
.option-list button { padding: 10px; border: 1px solid #c4b5fd; border-radius: 4px; background: #ffffff; cursor: pointer; text-align: left; }
.option-list button.selected { border-color: #7c3aed; background: #ede9fe; }
.question-panel footer { display: flex; justify-content: space-between; margin-top: 18px; }
.question-panel footer button, .result-panel button { padding: 8px 12px; border: 1px solid #6d28d9; background: #6d28d9; color: #ffffff; cursor: pointer; }
.result-panel { padding: 30px; text-align: center; background: #f5f3ff; }
.result-panel strong { font-size: 30px; color: #5b21b6; }
</style>
