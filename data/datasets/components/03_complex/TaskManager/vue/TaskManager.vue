<template>
  <div class="task-manager" :class="{ 'dark-theme': isDarkMode, 'compact-mode': isCompactMode }">
    <!-- 应用头部 -->
    <header class="app-header">
      <div class="logo-area">
        <span class="logo">✅</span>
        <h1 class="title">智能任务管家</h1>
        <span class="version">v3.0</span>
      </div>
      <div class="header-actions">
        <button class="icon-btn" @click="toggleCompactMode" :title="isCompactMode ? '展开模式' : '紧凑模式'">
          {{ isCompactMode ? '📐' : '📏' }}
        </button>
        <button class="icon-btn" @click="toggleTheme" :title="isDarkMode ? '亮色模式' : '暗色模式'">
          {{ isDarkMode ? '☀️' : '🌙' }}
        </button>
        <button class="icon-btn" @click="exportData" :title="'导出数据'">
          📥
        </button>
        <button class="icon-btn" @click="showSettings = true" :title="'设置'">
          ⚙️
        </button>
      </div>
    </header>

    <!-- 统计卡片区域 -->
    <div class="stats-section">
      <stat-card
        v-for="stat in statistics"
        :key="stat.id"
        :label="stat.label"
        :value="stat.value"
        :icon="stat.icon"
        :trend="stat.trend"
        :color="stat.color"
        @click="onStatClick(stat)"
      />
    </div>

    <!-- 主要操作区域 -->
    <div class="main-workspace">
      <!-- 左侧：任务列表 -->
      <div class="tasks-panel">
        <div class="panel-header">
          <h2>📋 任务列表</h2>
          <div class="task-controls">
            <button class="primary-btn" @click="openTaskModal">
              + 新建任务
            </button>
            <div class="search-box">
              <input
                v-model="searchKeyword"
                type="text"
                placeholder="搜索任务..."
                @input="onSearchChange"
              />
              <span class="search-icon">🔍</span>
            </div>
          </div>
        </div>

        <!-- 任务过滤标签 -->
        <div class="filter-tabs">
          <button
            v-for="filter in filters"
            :key="filter.value"
            class="filter-tab"
            :class="{ active: currentFilter === filter.value }"
            @click="setFilter(filter.value)"
          >
            {{ filter.label }}
            <span class="count">{{ getTaskCount(filter.value) }}</span>
          </button>
        </div>

        <!-- 任务列表（支持拖拽排序） -->
        <div class="task-list" @dragover.prevent @drop="onDropToEnd">
          <task-item
            v-for="(task, index) in filteredTasks"
            :key="task.id"
            :task="task"
            :index="index"
            :draggable="true"
            @toggle="toggleTaskStatus"
            @edit="editTask"
            @view="selectTask"
            @delete="deleteTask"
            @drag-start="onDragStart"
            @drag-end="onDragEnd"
            @drop-on="onDropOnTask"
          />
          <div v-if="filteredTasks.length === 0" class="empty-state">
            <span class="empty-icon">📭</span>
            <p>暂无任务，创建一个吧！</p>
          </div>
        </div>
      </div>

      <!-- 右侧：详情面板 -->
      <div class="detail-panel" v-if="selectedTask">
        <task-detail
          :task="selectedTask"
          @close="closeDetail"
          @update="updateTask"
          @comment="addComment"
        />
      </div>
    </div>

    <!-- 任务编辑模态框 -->
    <div v-if="isModalOpen" class="modal-overlay" @click.self="closeModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ editingTask ? '编辑任务' : '新建任务' }}</h3>
          <button class="close-btn" @click="closeModal">✕</button>
        </div>
        <task-form
          :key="editingTask ? editingTask.id : 'new-task'"
          :task="editingTask"
          :users="users"
          :tags="availableTags"
          @submit="handleTaskSubmit"
          @cancel="closeModal"
        />
      </div>
    </div>

    <!-- 设置模态框 -->
    <div v-if="showSettings" class="modal-overlay" @click.self="showSettings = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>⚙️ 系统设置</h3>
          <button class="close-btn" @click="showSettings = false">✕</button>
        </div>
        <settings-panel
          :settings="settings"
          @update="updateSettings"
        />
      </div>
    </div>

    <!-- 消息提示 -->
    <div v-if="notification.show" class="notification" :class="notification.type">
      <span>{{ notification.message }}</span>
      <button @click="hideNotification">✕</button>
    </div>
  </div>
</template>

<script>
// 子组件1：统计卡片
const StatCard = {
  name: 'StatCard',
  props: ['label', 'value', 'icon', 'trend', 'color'],
  template: `
    <div class="stat-card" @click="$emit('click')">
      <div class="stat-card-icon" :style="{ background: color }">
        {{ icon }}
      </div>
      <div class="stat-card-content">
        <div class="stat-card-label">{{ label }}</div>
        <div class="stat-card-value">{{ value }}</div>
        <div class="stat-card-trend" :class="trend >= 0 ? 'positive' : 'negative'">
          {{ trend >= 0 ? '↑' : '↓' }} {{ Math.abs(trend) }}%
        </div>
      </div>
    </div>
  `,
  emits: ['click']
};

// 子组件2：任务项
const TaskItem = {
  name: 'TaskItem',
  props: ['task', 'index', 'draggable'],
  template: `
    <div
      class="task-item"
      :class="{ completed: task.completed, urgent: task.priority === 'high' }"
      draggable="true"
      @dragstart="onDragStart"
      @dragover.prevent
      @drop.stop="onDrop"
      @dragend="onDragEnd"
    >
      <div class="task-checkbox" @click="$emit('toggle', task.id)">
        <span class="checkbox">{{ task.completed ? '☑' : '☐' }}</span>
      </div>
      <div class="task-content" @click="$emit('view', task)">
        <div class="task-title">{{ task.title }}</div>
        <div class="task-meta">
          <span class="task-priority" :class="task.priority">{{ getPriorityLabel(task.priority) }}</span>
          <span class="task-due-date">📅 {{ formatDate(task.dueDate) }}</span>
        </div>
        <div class="task-tags">
          <span v-for="tag in task.tags" :key="tag" class="task-tag">{{ tag }}</span>
        </div>
      </div>
      <div class="task-actions">
        <button class="task-action-btn" @click.stop="$emit('edit', task)">✏️</button>
        <button class="task-action-btn" @click.stop="$emit('delete', task.id)">🗑️</button>
      </div>
    </div>
  `,
  methods: {
    getPriorityLabel(priority) {
      const labels = { high: '高优先级', medium: '中优先级', low: '低优先级' };
      return labels[priority] || priority;
    },
    formatDate(date) {
      if (!date) return '无截止日期';
      const d = new Date(date);
      return `${d.getMonth() + 1}/${d.getDate()}`;
    },
    onDragStart(e) {
      if (!this.draggable) return;
      e.dataTransfer.setData('text/plain', this.index);
      e.dataTransfer.effectAllowed = 'move';
      this.$emit('drag-start', this.index);
    },
    onDrop() {
      this.$emit('drop-on', this.index);
    },
    onDragEnd() {
      this.$emit('drag-end');
    }
  },
  emits: ['toggle', 'edit', 'view', 'delete', 'drag-start', 'drop-on', 'drag-end']
};

// 子组件3：任务详情
const TaskDetail = {
  name: 'TaskDetail',
  props: ['task'],
  template: `
    <div class="task-detail">
      <div class="detail-header">
        <h3>任务详情</h3>
        <div class="detail-actions">
          <button class="edit-detail" @click="$emit('update', task)">编辑</button>
          <button class="close-detail" @click="$emit('close')">✕</button>
        </div>
      </div>
      <div class="detail-content">
        <div class="detail-field">
          <label>标题</label>
          <div class="field-value">{{ task.title }}</div>
        </div>
        <div class="detail-field">
          <label>描述</label>
          <div class="field-value">{{ task.description || '无描述' }}</div>
        </div>
        <div class="detail-field">
          <label>优先级</label>
          <div class="field-value" :class="task.priority">{{ getPriorityLabel(task.priority) }}</div>
        </div>
        <div class="detail-field">
          <label>截止日期</label>
          <div class="field-value">{{ formatDate(task.dueDate) }}</div>
        </div>
        <div class="detail-field">
          <label>标签</label>
          <div class="field-value">
            <span v-for="tag in task.tags" :key="tag" class="detail-tag">{{ tag }}</span>
          </div>
        </div>
        <div class="detail-field">
          <label>评论</label>
          <div class="comments-section">
            <div v-for="(comment, idx) in task.comments" :key="idx" class="comment-item">
              <strong>{{ comment.user }}</strong>: {{ comment.text }}
              <small>{{ formatTime(comment.time) }}</small>
            </div>
            <div class="comment-input">
              <input v-model="newComment" type="text" placeholder="添加评论..." @keyup.enter="addComment" />
              <button @click="addComment">发送</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  data() {
    return {
      newComment: ''
    };
  },
  methods: {
    getPriorityLabel(priority) {
      const labels = { high: '高优先级', medium: '中优先级', low: '低优先级' };
      return labels[priority] || priority;
    },
    formatDate(date) {
      if (!date) return '无截止日期';
      const d = new Date(date);
      return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
    },
    formatTime(time) {
      const d = new Date(time);
      return d.toLocaleTimeString();
    },
    addComment() {
      if (this.newComment.trim()) {
        this.$emit('comment', { taskId: this.task.id, text: this.newComment });
        this.newComment = '';
      }
    }
  },
  emits: ['close', 'update', 'comment']
};

// 子组件4：任务表单
const TaskForm = {
  name: 'TaskForm',
  props: ['task', 'users', 'tags'],
  template: `
    <form @submit.prevent="handleSubmit" class="task-form">
      <div class="form-group">
        <label>任务标题 *</label>
        <input v-model="formData.title" type="text" required placeholder="输入任务标题" />
      </div>
      <div class="form-group">
        <label>任务描述</label>
        <textarea v-model="formData.description" rows="3" placeholder="详细描述..."></textarea>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>优先级</label>
          <select v-model="formData.priority">
            <option value="low">低优先级</option>
            <option value="medium">中优先级</option>
            <option value="high">高优先级</option>
          </select>
        </div>
        <div class="form-group">
          <label>截止日期</label>
          <input v-model="formData.dueDate" type="date" />
        </div>
      </div>
      <div class="form-group">
        <label>标签</label>
        <div class="tag-selector">
          <span
            v-for="tag in tags"
            :key="tag"
            class="selectable-tag"
            :class="{ selected: formData.tags.includes(tag) }"
            @click="toggleTag(tag)"
          >
            {{ tag }}
          </span>
        </div>
      </div>
      <div class="form-group">
        <label>负责人</label>
        <select v-model="formData.assignee">
          <option value="">未分配</option>
          <option v-for="user in users" :key="user.id" :value="user.name">{{ user.name }}</option>
        </select>
      </div>
      <div class="form-actions">
        <button type="button" class="cancel-btn" @click="$emit('cancel')">取消</button>
        <button type="submit" class="submit-btn">{{ task ? '更新' : '创建' }}</button>
      </div>
    </form>
  `,
  data() {
    return {
      formData: this.createFormData(this.task)
    };
  },
  watch: {
    task: {
      handler(task) {
        this.formData = this.createFormData(task);
      }
    }
  },
  methods: {
    createFormData(task) {
      return task ? { ...task, tags: [...(task.tags || [])] } : {
        title: '',
        description: '',
        priority: 'medium',
        dueDate: '',
        tags: [],
        assignee: ''
      };
    },
    toggleTag(tag) {
      if (this.formData.tags.includes(tag)) {
        this.formData.tags = this.formData.tags.filter(t => t !== tag);
      } else {
        this.formData.tags.push(tag);
      }
    },
    handleSubmit() {
      if (!this.formData.title.trim()) return;
      this.$emit('submit', this.formData);
    }
  },
  emits: ['submit', 'cancel']
};

// 子组件5：设置面板
const SettingsPanel = {
  name: 'SettingsPanel',
  props: ['settings'],
  template: `
    <div class="settings-panel">
      <div class="setting-group">
        <label>默认视图</label>
        <select :value="settings.defaultView" @change="$emit('update', 'defaultView', $event.target.value)">
          <option value="list">列表视图</option>
          <option value="board">看板视图</option>
        </select>
      </div>
      <div class="setting-group">
        <label>自动保存</label>
        <input type="checkbox" :checked="settings.autoSave" @change="$emit('update', 'autoSave', $event.target.checked)" />
      </div>
      <div class="setting-group">
        <label>通知提醒</label>
        <input type="checkbox" :checked="settings.notifications" @change="$emit('update', 'notifications', $event.target.checked)" />
      </div>
      <div class="setting-group">
        <label>数据同步间隔</label>
        <select :value="settings.syncInterval" @change="$emit('update', 'syncInterval', $event.target.value)">
          <option value="0">手动同步</option>
          <option value="30">30秒</option>
          <option value="60">1分钟</option>
          <option value="300">5分钟</option>
        </select>
      </div>
    </div>
  `,
  emits: ['update']
};

// 主组件
module.exports =  {
  name: 'TaskManager',
  components: {
    StatCard,
    TaskItem,
    TaskDetail,
    TaskForm,
    SettingsPanel
  },
  data() {
    return {
      // UI状态
      isDarkMode: false,
      isCompactMode: false,
      showSettings: false,
      isModalOpen: false,
      
      // 任务数据
      tasks: [],
      selectedTask: null,
      editingTask: null,
      
      // 过滤和搜索
      currentFilter: 'all',
      searchKeyword: '',
      
      // 拖拽相关
      dragStartIndex: null,
      
      // 系统数据
      users: [
        { id: 1, name: '张三' },
        { id: 2, name: '李四' },
        { id: 3, name: '王五' }
      ],
      availableTags: ['工作', '个人', '紧急', '学习', '休闲', '会议'],
      
      // 统计数据
      statistics: [
        { id: 1, label: '总任务', value: 0, icon: '📊', trend: 12, color: '#3b82f6' },
        { id: 2, label: '已完成', value: 0, icon: '✅', trend: 8, color: '#10b981' },
        { id: 3, label: '进行中', value: 0, icon: '🔄', trend: -3, color: '#f59e0b' },
        { id: 4, label: '逾期任务', value: 0, icon: '⚠️', trend: 5, color: '#ef4444' }
      ],
      
      // 过滤器选项
      filters: [
        { value: 'all', label: '全部' },
        { value: 'active', label: '进行中' },
        { value: 'completed', label: '已完成' },
        { value: 'overdue', label: '已逾期' },
        { value: 'urgent', label: '紧急' }
      ],
      
      // 系统设置
      settings: {
        defaultView: 'list',
        autoSave: true,
        notifications: true,
        syncInterval: 60
      },
      
      // 消息通知
      notification: {
        show: false,
        message: '',
        type: 'info'
      },
      
      // 定时器
      syncTimer: null,
      
      // 本地存储key
      storageKey: 'task_manager_data'
    };
  },
  computed: {
    // 过滤后的任务列表
    filteredTasks() {
      let result = [...this.tasks];
      
      // 状态过滤
      if (this.currentFilter !== 'all') {
        result = result.filter(task => {
          switch (this.currentFilter) {
            case 'active': return !task.completed && !this.isOverdue(task);
            case 'completed': return task.completed;
            case 'overdue': return this.isOverdue(task) && !task.completed;
            case 'urgent': return task.priority === 'high' && !task.completed;
            default: return true;
          }
        });
      }
      
      // 搜索过滤
      if (this.searchKeyword) {
        const keyword = this.searchKeyword.toLowerCase();
        result = result.filter(task =>
          task.title.toLowerCase().includes(keyword) ||
          (task.description && task.description.toLowerCase().includes(keyword))
        );
      }
      
      return result;
    }
  },
  watch: {
    // 监听任务变化，更新统计数据
    tasks: {
      handler() {
        this.updateStatistics();
        if (this.settings.autoSave) {
          this.saveToLocalStorage();
        }
      },
      deep: true
    },
    
    // 监听设置变化
    settings: {
      handler() {
        if (this.settings.autoSave) {
          this.saveToLocalStorage();
        }
        this.updateSyncInterval();
      },
      deep: true
    }
  },
  mounted() {
    this.loadInitialData();
    this.startAutoSync();
    this.showNotification('系统初始化完成', 'success');
  },
  beforeDestroy() {
    if (this.syncTimer) {
      clearInterval(this.syncTimer);
    }
    this.saveToLocalStorage();
  },
  methods: {
    // 初始化数据
    loadInitialData() {
      const saved = localStorage.getItem(this.storageKey);
      if (saved) {
        try {
          const data = JSON.parse(saved);
          this.tasks = data.tasks || this.getSampleTasks();
          this.settings = { ...this.settings, ...data.settings };
        } catch (e) {
          this.tasks = this.getSampleTasks();
        }
      } else {
        this.tasks = this.getSampleTasks();
      }
      this.updateStatistics();
    },
    
    // 获取示例任务
    getSampleTasks() {
      return [
        {
          id: 1,
          title: '完成项目报告',
          description: '编写Q4季度项目总结报告，包含数据分析和改进建议',
          priority: 'high',
          dueDate: new Date(Date.now() + 2 * 86400000).toISOString().split('T')[0],
          tags: ['工作', '紧急'],
          completed: false,
          comments: [],
          assignee: '张三'
        },
        {
          id: 2,
          title: '学习Vue高级特性',
          description: '深入学习Vue3组合式API和响应式原理',
          priority: 'medium',
          dueDate: new Date(Date.now() + 5 * 86400000).toISOString().split('T')[0],
          tags: ['学习'],
          completed: false,
          comments: [],
          assignee: '李四'
        },
        {
          id: 3,
          title: '团队会议',
          description: '周例会，讨论项目进展和下周计划',
          priority: 'medium',
          dueDate: new Date(Date.now() - 1 * 86400000).toISOString().split('T')[0],
          tags: ['工作', '会议'],
          completed: true,
          comments: [{ user: '张三', text: '会议纪要已更新', time: Date.now() - 86400000 }],
          assignee: '王五'
        }
      ];
    },
    
    // 更新统计数据
    updateStatistics() {
      const total = this.tasks.length;
      const completed = this.tasks.filter(t => t.completed).length;
      const active = this.tasks.filter(t => !t.completed && !this.isOverdue(t)).length;
      const overdue = this.tasks.filter(t => this.isOverdue(t) && !t.completed).length;
      
      this.statistics = [
        { ...this.statistics[0], value: total },
        { ...this.statistics[1], value: completed },
        { ...this.statistics[2], value: active },
        { ...this.statistics[3], value: overdue }
      ];
    },
    
    // 判断任务是否逾期
    isOverdue(task) {
      if (task.completed || !task.dueDate) return false;
      const dueDate = new Date(task.dueDate);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      return dueDate < today;
    },
    
    // 任务操作
    openTaskModal() {
      this.editingTask = null;
      this.isModalOpen = true;
    },
    
    editTask(task) {
      this.editingTask = { ...task };
      this.isModalOpen = true;
    },
    
    selectTask(task) {
      this.selectedTask = task;
    },
    
    handleTaskSubmit(formData) {
      if (this.editingTask) {
        const index = this.tasks.findIndex(t => t.id === this.editingTask.id);
        if (index !== -1) {
          this.tasks[index] = { ...this.tasks[index], ...formData, updatedAt: Date.now() };
          this.showNotification('任务更新成功', 'success');
        }
      } else {
        const newTask = {
          ...formData,
          id: Date.now(),
          completed: false,
          comments: [],
          createdAt: Date.now()
        };
        this.tasks.unshift(newTask);
        this.showNotification('任务创建成功', 'success');
      }
      this.closeModal();
    },
    
    toggleTaskStatus(taskId) {
      const task = this.tasks.find(t => t.id === taskId);
      if (task) {
        task.completed = !task.completed;
        this.showNotification(task.completed ? '任务已完成' : '任务已恢复', 'info');
      }
    },
    
    deleteTask(taskId) {
      if (confirm('确定删除此任务吗？')) {
        this.tasks = this.tasks.filter(t => t.id !== taskId);
        if (this.selectedTask?.id === taskId) {
          this.selectedTask = null;
        }
        this.showNotification('任务已删除', 'warning');
      }
    },
    
    updateTask(updatedData) {
      this.editTask(updatedData);
    },
    
    addComment(commentData) {
      const task = this.tasks.find(t => t.id === commentData.taskId);
      if (task) {
        task.comments = task.comments || [];
        task.comments.push({
          user: '当前用户',
          text: commentData.text,
          time: Date.now()
        });
        this.showNotification('评论已添加', 'success');
      }
    },
    
    closeDetail() {
      this.selectedTask = null;
    },
    
    // 拖拽排序
    onDragStart(index) {
      this.dragStartIndex = index;
    },
    
    onDropOnTask(dropIndex) {
      this.moveTask(this.dragStartIndex, dropIndex);
    },
    
    onDropToEnd() {
      this.moveTask(this.dragStartIndex, this.filteredTasks.length - 1, true);
    },
    
    onDragEnd() {
      this.dragStartIndex = null;
    },
    
    moveTask(fromFilteredIndex, toFilteredIndex, insertAfter = false) {
      if (fromFilteredIndex === null || fromFilteredIndex === undefined) return;
      
      const draggedTask = this.filteredTasks[fromFilteredIndex];
      const isMovingDown = fromFilteredIndex < toFilteredIndex;
      const targetTask = this.filteredTasks[toFilteredIndex];
      if (!draggedTask || !targetTask || draggedTask.id === targetTask.id) return;
      
      const originalIndex = this.tasks.findIndex(t => t.id === draggedTask.id);
      let targetOriginalIndex = this.tasks.findIndex(t => t.id === targetTask.id);
      
      if (originalIndex !== -1 && targetOriginalIndex !== -1) {
        const [movedTask] = this.tasks.splice(originalIndex, 1);
        if (originalIndex < targetOriginalIndex) {
          targetOriginalIndex -= 1;
        }
        if (insertAfter || isMovingDown) {
          targetOriginalIndex += 1;
        }
        this.tasks.splice(targetOriginalIndex, 0, movedTask);
        this.dragStartIndex = null;
        this.showNotification('任务顺序已更新', 'info');
      }
    },
    
    // 过滤和搜索
    setFilter(filter) {
      this.currentFilter = filter;
      this.showNotification(`已筛选：${this.filters.find(f => f.value === filter).label}`, 'info');
    },
    
    onSearchChange() {
      if (this.searchKeyword) {
        this.showNotification(`搜索：${this.searchKeyword}`, 'info');
      }
    },
    
    getTaskCount(filterValue) {
      switch (filterValue) {
        case 'all': return this.tasks.length;
        case 'active': return this.tasks.filter(t => !t.completed && !this.isOverdue(t)).length;
        case 'completed': return this.tasks.filter(t => t.completed).length;
        case 'overdue': return this.tasks.filter(t => this.isOverdue(t) && !t.completed).length;
        case 'urgent': return this.tasks.filter(t => t.priority === 'high' && !t.completed).length;
        default: return 0;
      }
    },
    
    // UI交互
    toggleTheme() {
      this.isDarkMode = !this.isDarkMode;
      this.showNotification(`已切换到${this.isDarkMode ? '暗色' : '亮色'}主题`, 'info');
    },
    
    toggleCompactMode() {
      this.isCompactMode = !this.isCompactMode;
      this.showNotification(`已切换到${this.isCompactMode ? '紧凑' : '展开'}模式`, 'info');
    },
    
    closeModal() {
      this.isModalOpen = false;
      this.editingTask = null;
    },
    
    // 统计卡片点击
    onStatClick(stat) {
      if (stat.id === 1) this.setFilter('all');
      else if (stat.id === 2) this.setFilter('completed');
      else if (stat.id === 3) this.setFilter('active');
      else if (stat.id === 4) this.setFilter('overdue');
      this.showNotification(`查看${stat.label}`, 'info');
    },
    
    // 设置相关
    updateSettings(key, value) {
      this.settings[key] = key === 'syncInterval' ? Number(value) : value;
      this.showNotification(`设置已更新：${key}`, 'success');
    },
    
    // 数据持久化
    saveToLocalStorage() {
      const data = {
        tasks: this.tasks,
        settings: this.settings,
        lastSave: Date.now()
      };
      localStorage.setItem(this.storageKey, JSON.stringify(data));
    },
    
    // 数据导出
    exportData() {
      const data = {
        tasks: this.tasks,
        statistics: this.statistics,
        exportTime: new Date().toISOString()
      };
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `task_export_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      this.showNotification('数据已导出', 'success');
    },
    
    // 自动同步
    startAutoSync() {
      this.updateSyncInterval();
    },
    
    updateSyncInterval() {
      if (this.syncTimer) {
        clearInterval(this.syncTimer);
      }
      if (this.settings.syncInterval > 0) {
        this.syncTimer = setInterval(() => {
          this.autoSync();
        }, this.settings.syncInterval * 1000);
      }
    },
    
    async autoSync() {
      this.showNotification('正在同步云端数据...', 'info');
      await new Promise(resolve => setTimeout(resolve, 500));
      this.showNotification('数据同步完成', 'success');
    },
    
    // 消息通知
    showNotification(message, type = 'info') {
      this.notification = {
        show: true,
        message,
        type
      };
      setTimeout(() => {
        this.hideNotification();
      }, 3000);
    },
    
    hideNotification() {
      this.notification.show = false;
    }
  }
};
</script>

<style scoped>
/* 主容器 */
.task-manager {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
  background: #f7f9fc;
  min-height: 100vh;
  transition: all 0.3s ease;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.task-manager.dark-theme {
  background: #1a1a2e;
  color: #e0e0e0;
}

.task-manager.compact-mode {
  padding: 12px;
}

/* 头部 */
.app-header {
  background: white;
  border-radius: 12px;
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.dark-theme .app-header {
  background: #16213e;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  font-size: 32px;
}

.title {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.version {
  font-size: 12px;
  color: #94a3b8;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.icon-btn {
  padding: 8px 12px;
  background: #f1f5f9;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 18px;
  transition: all 0.2s;
}

.dark-theme .icon-btn {
  background: #1e293b;
}

.icon-btn:hover {
  transform: translateY(-2px);
}

/* 统计卡片 */
.stats-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.dark-theme .stat-card {
  background: #16213e;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.stat-card-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.stat-card-content {
  flex: 1;
}

.stat-card-label {
  font-size: 14px;
  color: #64748b;
  margin-bottom: 4px;
}

.stat-card-value {
  font-size: 28px;
  font-weight: 700;
}

.stat-card-trend {
  font-size: 12px;
  font-weight: 600;
  margin-top: 4px;
}

.stat-card-trend.positive {
  color: #10b981;
}

.stat-card-trend.negative {
  color: #ef4444;
}

/* 主要工作区 */
.main-workspace {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 24px;
}

.tasks-panel, .detail-panel {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.dark-theme .tasks-panel,
.dark-theme .detail-panel {
  background: #16213e;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 16px;
}

.panel-header h2 {
  font-size: 20px;
  margin: 0;
}

.task-controls {
  display: flex;
  gap: 12px;
  align-items: center;
}

.primary-btn {
  padding: 8px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  transition: transform 0.2s;
}

.primary-btn:hover {
  transform: translateY(-2px);
}

.search-box {
  position: relative;
}

.search-box input {
  padding: 8px 12px 8px 32px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  width: 200px;
}

.dark-theme .search-box input {
  background: #1e293b;
  border-color: #334155;
  color: #e0e0e0;
}

.search-icon {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
}

/* 过滤标签 */
.filter-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.filter-tab {
  padding: 6px 12px;
  background: #f1f5f9;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.dark-theme .filter-tab {
  background: #1e293b;
  color: #e0e0e0;
}

.filter-tab.active {
  background: #667eea;
  color: white;
}

.filter-tab .count {
  margin-left: 4px;
  font-size: 12px;
  opacity: 0.7;
}

/* 任务列表 */
.task-list {
  max-height: 600px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-item {
  background: #f8fafc;
  border-radius: 10px;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: all 0.2s;
  cursor: grab;
}

.dark-theme .task-item {
  background: #1e293b;
}

.task-item:active {
  cursor: grabbing;
}

.task-item.completed .task-title {
  text-decoration: line-through;
  opacity: 0.6;
}

.task-item.urgent {
  border-left: 4px solid #ef4444;
}

.task-checkbox {
  cursor: pointer;
}

.checkbox {
  font-size: 20px;
}

.task-content {
  flex: 1;
  cursor: pointer;
}

.task-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.task-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  margin-bottom: 4px;
}

.task-priority {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.task-priority.high {
  background: #fee2e2;
  color: #991b1b;
}

.task-priority.medium {
  background: #fef3c7;
  color: #92400e;
}

.task-priority.low {
  background: #dcfce7;
  color: #166534;
}

.task-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.task-tag {
  font-size: 10px;
  padding: 2px 6px;
  background: #e2e8f0;
  border-radius: 4px;
}

.task-actions {
  display: flex;
  gap: 8px;
}

.task-action-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: background 0.2s;
}

.task-action-btn:hover {
  background: #e2e8f0;
}

/* 任务详情 */
.task-detail {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.detail-header h3 {
  margin: 0;
}

.close-detail {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
}

.detail-content {
  flex: 1;
}

.detail-field {
  margin-bottom: 16px;
}

.detail-field label {
  font-weight: 600;
  font-size: 12px;
  color: #64748b;
  display: block;
  margin-bottom: 4px;
}

.field-value {
  font-size: 14px;
}

.detail-tag {
  display: inline-block;
  padding: 4px 8px;
  background: #e2e8f0;
  border-radius: 4px;
  font-size: 12px;
  margin-right: 4px;
}

.comments-section {
  max-height: 200px;
  overflow-y: auto;
}

.comment-item {
  padding: 8px;
  background: #f1f5f9;
  border-radius: 8px;
  margin-bottom: 8px;
  font-size: 12px;
}

.comment-item small {
  color: #94a3b8;
  margin-left: 8px;
}

.comment-input {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.comment-input input {
  flex: 1;
  padding: 6px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.comment-input button {
  padding: 6px 12px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

/* 模态框 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 16px;
  width: 500px;
  max-width: 90%;
  max-height: 80vh;
  overflow-y: auto;
}

.dark-theme .modal-content {
  background: #1e293b;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
}

/* 表单 */
.task-form {
  padding: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  font-size: 14px;
}

.form-group input,
.form-group textarea,
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
}

.dark-theme .form-group input,
.dark-theme .form-group textarea,
.dark-theme .form-group select {
  background: #1e293b;
  border-color: #334155;
  color: #e0e0e0;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.tag-selector {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.selectable-tag {
  padding: 4px 12px;
  background: #f1f5f9;
  border-radius: 20px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.selectable-tag.selected {
  background: #667eea;
  color: white;
}

.form-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 20px;
}

.cancel-btn {
  padding: 8px 16px;
  background: #f1f5f9;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.submit-btn {
  padding: 8px 16px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

/* 设置面板 */
.settings-panel {
  padding: 20px;
}

.setting-group {
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.setting-group label {
  font-weight: 500;
}

.setting-group select {
  padding: 6px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

/* 消息提示 */
.notification {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 12px 20px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 2000;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  animation: slideIn 0.3s ease;
}

.notification.success {
  background: #10b981;
  color: white;
}

.notification.error {
  background: #ef4444;
  color: white;
}

.notification.warning {
  background: #f59e0b;
  color: white;
}

.notification.info {
  background: #3b82f6;
  color: white;
}

.notification button {
  background: none;
  border: none;
  color: white;
  cursor: pointer;
  font-size: 16px;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #94a3b8;
}

.empty-icon {
  font-size: 48px;
  display: block;
  margin-bottom: 16px;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* 响应式 */
@media (max-width: 768px) {
  .main-workspace {
    grid-template-columns: 1fr;
  }
  
  .stats-section {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .panel-header {
    flex-direction: column;
  }
  
  .task-controls {
    width: 100%;
    flex-direction: column;
  }
  
  .search-box input {
    width: 100%;
  }
}
</style>