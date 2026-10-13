<template>
  <section class="kanban-column-board"><header><h2>内容制作看板</h2><div class="actions"><button @click="move(-1)" :disabled="!selectedTask">← 左移</button><button @click="move(1)" :disabled="!selectedTask">右移 →</button></div></header><div class="board"><article v-for="column in boardColumns" :key="column.id"><h3>{{ column.label }} · {{ column.count }}</h3><button v-for="task in column.tasks" :key="task.id" :class="task.id === selectedId ? 'selected' : ''" @click="select(task.id)">{{ task.title }}</button></article></div><form @submit="add"><input :value="draft" @input="updateDraft" placeholder="新增待处理任务"><button class="primary" type="submit">添加</button></form></section>
</template>

<script>
module.exports = {
  name: 'KanbanColumnBoard',
  props: {
    initialTasks: { type: Array, default: () => ([
          {
            "id": 1,
            "title": "需求拆解",
            "status": "todo"
          },
          {
            "id": 2,
            "title": "组件实现",
            "status": "doing"
          },
          {
            "id": 3,
            "title": "人工复核",
            "status": "done"
          }
        ]) },
    columns: { type: Array, default: () => ([
          {
            "id": "todo",
            "label": "待处理"
          },
          {
            "id": "doing",
            "label": "进行中"
          },
          {
            "id": "done",
            "label": "已完成"
          }
        ]) }
  },
  data() {
    return {
        tasks: [],
        selectedId: null,
        draft: "",
        nextId: 10
    };
  },
  computed: {
    boardColumns() {
      return this.columns.map(column => {
        const tasks = this.tasks.filter(item => item.status === column.id);
        return Object.assign({}, column, { tasks, count: tasks.length });
      });
    },
    selectedTask() {
      return this.tasks.find(item => item.id === this.selectedId) || null;
    }
  },
  created() {
    this.setValue('tasks', this.initialTasks.map(item => Object.assign({}, item)));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    select(id) {
      this.setValue('selectedId', id);
    },
    move(delta) {
      const task = this.selectedTask; if (!task) return; const index = this.columns.findIndex(item => item.id === task.status); const target = this.columns[index + delta]; if (!target) return; this.setValue('tasks', this.tasks.map(item => item.id === task.id ? Object.assign({}, item, { status: target.id }) : item)); this.emitEvent('move', { id: task.id, status: target.id });
    },
    updateDraft(event) {
      this.setValue('draft', event.target.value);
    },
    add(event) {
      event.preventDefault(); const title = this.draft.trim(); if (!title) return; const task = { id: this.nextId, title, status: 'todo' }; this.setValue('tasks', this.tasks.concat(task)); this.setValue('nextId', this.nextId + 1); this.setValue('draft', ''); this.emitEvent('add', task);
    }
  }
};
</script>

<style scoped>

.kanban-column-board{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.kanban-column-board *{box-sizing:border-box}
.kanban-column-board h2,.kanban-column-board h3,.kanban-column-board p{margin-top:0}
.kanban-column-board button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.kanban-column-board button.primary{border-color:#7c3aed;background:#7c3aed;color:#fff}
.kanban-column-board button:disabled{opacity:.45;cursor:not-allowed}
.kanban-column-board input,.kanban-column-board select,.kanban-column-board textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.kanban-column-board .muted{color:#71808e;font-size:12px}
.kanban-column-board .toolbar,.kanban-column-board .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.board{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.board article{min-height:190px;padding:10px;background:#f8fafc}.board article>button{display:block;width:100%;margin:6px 0;text-align:left}.board button.selected{background:#ede9fe;border-color:#7c3aed}form{display:flex;gap:8px;margin-top:12px}form input{flex:1}
</style>
