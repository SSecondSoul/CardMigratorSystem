<template>
  <div class="todo-app" :class="{ 'dark-mode': isDarkMode }">
    <!-- 头部 -->
    <div class="app-header">
      <h1>📋 待办清单 Pro</h1>
      <button class="theme-btn" @click="toggleTheme">
        {{ isDarkMode ? '☀️' : '🌙' }}
      </button>
    </div>

    <!-- 统计卡片 (3个计算属性) -->
    <div class="stats-grid">
      <div class="stat-card" @click="currentFilter = 'all'">
        <div class="stat-value">{{ totalCount }}</div>
        <div class="stat-label">全部</div>
      </div>
      <div class="stat-card" @click="currentFilter = 'active'">
        <div class="stat-value">{{ activeCount }}</div>
        <div class="stat-label">未完成</div>
      </div>
      <div class="stat-card" @click="currentFilter = 'completed'">
        <div class="stat-value">{{ completedCount }}</div>
        <div class="stat-label">已完成</div>
      </div>
    </div>

    <!-- 添加区域 -->
    <div class="add-section">
      <input 
        :value="newTitle"
        type="text" 
        placeholder="任务标题..."
        @input="onTitleInput"
        @keyup.enter="addTodo"
      />
      <select :value="newPriority" @change="onPriorityChange">
        <option value="high">🔴 高优先级</option>
        <option value="medium">🟡 中优先级</option>
        <option value="low">🟢 低优先级</option>
      </select>
      <button type="button" @click="addTodo">添加</button>
    </div>

    <!-- 任务列表 -->
    <div class="todo-list">
      <todo-item
        v-for="todo in filteredTodos"
        :key="todo.id"
        :todo="todo"
        @toggle="toggleTodo"
        @delete="deleteTodo"
      ></todo-item>
      <div v-if="filteredTodos.length === 0" class="empty-state">
        暂无任务
      </div>
    </div>

    <!-- 底部操作 -->
    <div class="footer" v-if="todos.length > 0">
      <span>📊 共 {{ totalCount }} 项，剩余 {{ activeCount }} 项</span>
      <button v-if="completedCount > 0" class="clear-btn" @click="clearCompleted">
        清除已完成
      </button>
    </div>
  </div>
</template>

<script>
// 子组件：TodoItem
const TodoItem = {
  name: 'TodoItem',
  props: ['todo'],
  template: `
    <div class="todo-item" :class="itemClass">
      <input 
        type="checkbox" 
        :checked="todo.completed"
        @change="handleToggle"
      />
      <div class="todo-content">
        <span class="todo-title">{{ todo.title }}</span>
        <span class="todo-priority" :class="todo.priority">
          {{ priorityText }}
        </span>
      </div>
      <button class="delete-btn" @click="handleDelete">删除</button>
    </div>
  `,
  methods: {
    handleToggle() {
      this.$emit('toggle', this.todo.id);
    },
    handleDelete() {
      this.$emit('delete', this.todo.id);
    }
  },
  computed: {
    itemClass() {
      const classNames = [];
      if (this.todo && this.todo.completed) {
        classNames.push('completed');
      }
      if (this.todo && this.todo.priority) {
        classNames.push(this.todo.priority);
      }
      return classNames.join(' ');
    },
    priorityText() {
      const map = { high: '高', medium: '中', low: '低' };
      return map[this.todo.priority];
    }
  }
};


module.exports = {
  name: 'TodoListPro',
  components: {
    'todo-item': TodoItem
  },
  data() {
    return {
      isDarkMode: false,
      todos: [],
      newTitle: '',
      newPriority: 'medium',
      currentFilter: 'all'  // all, active, completed
    };
  },
  methods: {
    handleToggle() {
      this.$emit('toggle', this.todo.id);
    },
    handleDelete() {
      this.$emit('delete', this.todo.id);
    }
  },
  computed: {
    totalCount() {
      return this.todos.length;
    },
    activeCount() {
      return this.todos.filter(t => !t.completed).length;
    },
    completedCount() {
      return this.todos.filter(t => t.completed).length;
    },
    filteredTodos() {
      if (this.currentFilter === 'active') {
        return this.todos.filter(t => !t.completed);
      }
      if (this.currentFilter === 'completed') {
        return this.todos.filter(t => t.completed);
      }
      return this.todos;
    }
  },
  watch: {
    todos: {
      handler() {
        this.saveToLocal();
      },
      deep: true
    }
  },
  mounted() {
    this.loadFromLocal();
  },
  methods: {
    onTitleInput(event) {
      this.newTitle = event.target.value;
    },
    onPriorityChange(event) {
      this.newPriority = event.target.value;
    },
    addTodo() {
      const title = this.newTitle.trim();
      if (!title) {
        return;
      }

      this.todos = this.todos.concat({
        id: Date.now(),
        title,
        priority: this.newPriority,
        completed: false,
        createdAt: Date.now()
      });

      this.newTitle = '';
      this.currentFilter = 'all';
    },
    toggleTodo(id) {
      const todo = this.todos.find(t => t.id === id);
      if (todo) {
        todo.completed = !todo.completed;
      }
    },
    deleteTodo(id) {
      this.todos = this.todos.filter(t => t.id !== id);
    },
    clearCompleted() {
      this.todos = this.todos.filter(t => !t.completed);
    },
    toggleTheme() {
      this.isDarkMode = !this.isDarkMode;
    },
    saveToLocal() {
      localStorage.setItem('todo_pro_list', JSON.stringify(this.todos));
    },
    loadFromLocal() {
      const saved = localStorage.getItem('todo_pro_list');
      if (saved) {
        try {
          this.todos = JSON.parse(saved);
        } catch(e) {
          this.todos = this.getSampleTodos();
        }
      } else {
        this.todos = this.getSampleTodos();
      }
    },
    getSampleTodos() {
      return [
        { id: 1, title: '完成项目报告', priority: 'high', completed: false, createdAt: Date.now() },
        { id: 2, title: '学习Vue组件', priority: 'medium', completed: false, createdAt: Date.now() },
        { id: 3, title: '团队周会', priority: 'low', completed: true, createdAt: Date.now() }
      ];
    }
  }
};
</script>

<style scoped>
.todo-app {
  max-width: 600px;
  margin: 40px auto;
  padding: 24px;
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  transition: all 0.3s;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.todo-app.dark-mode {
  background: #1e293b;
  color: #e2e8f0;
}

/* 头部 */
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.app-header h1 {
  margin: 0;
  font-size: 24px;
}

.theme-btn {
  padding: 8px 16px;
  background: #f1f5f9;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 16px;
}

.dark-mode .theme-btn {
  background: #334155;
}

/* 统计卡片 */
.stats-grid {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  flex: 1;
  text-align: center;
  padding: 16px;
  background: #f8fafc;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.dark-mode .stat-card {
  background: #0f172a;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-value {
  display: block;
  font-size: 28px;
  font-weight: 700;
  color: #3b82f6;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
}

.dark-mode .stat-label {
  color: #94a3b8;
}

/* 添加区域 */
.add-section {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.add-section input {
  flex: 2;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  font-size: 14px;
}

.add-section select {
  flex: 1;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: white;
  cursor: pointer;
}

.dark-mode .add-section input,
.dark-mode .add-section select {
  background: #0f172a;
  border-color: #334155;
  color: #e2e8f0;
}

.add-section button {
  padding: 12px 20px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-weight: 600;
}

/* 任务列表 */
.todo-list {
  margin-bottom: 20px;
  max-height: 400px;
  overflow-y: auto;
}

.todo-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  margin-bottom: 8px;
  background: #f8fafc;
  border-radius: 12px;
  transition: all 0.2s;
}

.dark-mode .todo-item {
  background: #0f172a;
}

.todo-item.completed {
  opacity: 0.6;
}

.todo-item.completed .todo-title {
  text-decoration: line-through;
}

.todo-item.high {
  border-left: 4px solid #ef4444;
}

.todo-item.medium {
  border-left: 4px solid #f59e0b;
}

.todo-item.low {
  border-left: 4px solid #10b981;
}

.todo-content {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.todo-title {
  font-size: 14px;
  font-weight: 500;
}

.todo-priority {
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 10px;
  font-weight: 600;
}

.todo-priority.high {
  background: #fee2e2;
  color: #991b1b;
}

.todo-priority.medium {
  background: #fef3c7;
  color: #92400e;
}

.todo-priority.low {
  background: #dcfce7;
  color: #166534;
}

.delete-btn {
  padding: 4px 12px;
  background: #fee2e2;
  color: #ef4444;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
}

.dark-mode .delete-btn {
  background: #450a0a;
}

.empty-state {
  text-align: center;
  padding: 48px;
  color: #94a3b8;
}

/* 底部 */
.footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
  font-size: 13px;
}

.dark-mode .footer {
  border-top-color: #334155;
}

.clear-btn {
  padding: 8px 16px;
  background: #f1f5f9;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
}

.dark-mode .clear-btn {
  background: #334155;
  color: #e2e8f0;
}

/* 响应式 */
@media (max-width: 500px) {
  .todo-app {
    margin: 20px;
    padding: 16px;
  }
  
  .add-section {
    flex-direction: column;
  }
  
  .stats-grid {
    gap: 8px;
  }
  
  .stat-card {
    padding: 12px;
  }
  
  .stat-value {
    font-size: 20px;
  }
}
</style>