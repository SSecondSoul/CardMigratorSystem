<template>
  <div class="analytics-dashboard" :class="{ 'dark-mode': isDarkMode, 'compact': isCompactView }">
    <!-- 顶部导航栏 -->
    <div class="dashboard-navbar">
      <div class="logo-section">
        <span class="logo-icon">📈</span>
        <h1 class="logo-text">Analytics Pro</h1>
      </div>
      <div class="nav-controls">
        <button class="view-toggle" @click="toggleView">
          {{ isCompactView ? '📊 展开视图' : '📋 紧凑视图' }}
        </button>
        <button class="theme-toggle" @click="toggleTheme">
          {{ isDarkMode ? '☀️ 亮色' : '🌙 暗色' }}
        </button>
        <button class="refresh-btn" @click="manualRefresh" :disabled="isLoading">
          {{ isLoading ? '⏳ 加载中...' : '🔄 刷新数据' }}
        </button>
      </div>
    </div>

    <!-- 主要数据卡片区域 -->
    <div class="stats-grid">
      <stat-card
        v-for="stat in statistics"
        :key="stat.id"
        :title="stat.title"
        :value="stat.value"
        :change="stat.change"
        :icon="stat.icon"
        :loading="isLoading"
        @click="onStatClick(stat)"
      />
    </div>

    <!-- 图表与数据可视化区域 -->
    <div class="visualization-section">
      <div class="chart-container">
        <h3 class="section-title">
          <span>📊 实时访问趋势</span>
          <select v-model="selectedPeriod" @change="onPeriodChange" class="period-selector">
            <option value="7d">最近7天</option>
            <option value="30d">最近30天</option>
            <option value="90d">最近90天</option>
          </select>
        </h3>
        <trend-chart
          :data="chartData"
          :height="300"
          :loading="isLoading"
          @data-point-click="onDataPointClick"
        />
      </div>
      
      <div class="insights-panel">
        <h3 class="section-title">💡 智能洞察</h3>
        <insight-list
          :insights="insights"
          :loading="isLoading"
          @insight-click="onInsightClick"
        />
      </div>
    </div>

    <!-- 用户活动日志表格 -->
    <div class="activity-section">
      <div class="activity-header">
        <h3 class="section-title">📋 实时用户活动</h3>
        <div class="filter-controls">
          <input 
            v-model="searchQuery" 
            type="text" 
            placeholder="搜索用户或操作..."
            class="search-input"
            @input="onSearchChange"
          />
          <select v-model="activityFilter" @change="onFilterChange" class="filter-select">
            <option value="all">所有活动</option>
            <option value="login">登录</option>
            <option value="purchase">购买</option>
            <option value="view">浏览</option>
            <option value="share">分享</option>
          </select>
        </div>
      </div>
      <activity-table
        :activities="filteredActivities"
        :loading="isLoading"
        @row-click="onActivityClick"
      />
    </div>

    <!-- 加载遮罩层 -->
    <div v-if="isLoading" class="loading-overlay">
      <div class="spinner"></div>
      <p>正在加载最新数据...</p>
    </div>
  </div>
</template>

<script>
// 子组件1：统计卡片
const StatCard = {
  name: 'StatCard',
  props: ['title', 'value', 'change', 'icon', 'loading'],
  template: `
    <div class="stat-card" :class="{ 'loading': loading }" @click="$emit('click')">
      <div class="stat-icon">{{ icon }}</div>
      <div class="stat-content">
        <div class="stat-title">{{ title }}</div>
        <div class="stat-value">{{ formatValue(value) }}</div>
        <div class="stat-change" :class="changeClass">
          {{ changeIcon }} {{ Math.abs(change) }}%
        </div>
      </div>
    </div>
  `,
  computed: {
    changeClass() {
      if (this.change > 0) return 'positive';
      if (this.change < 0) return 'negative';
      return 'neutral';
    },
    changeIcon() {
      if (this.change > 0) return '▲';
      if (this.change < 0) return '▼';
      return '●';
    }
  },
  methods: {
    formatValue(value) {
      if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
      if (value >= 1000) return (value / 1000).toFixed(1) + 'K';
      return value.toString();
    }
  },
  emits: ['click']
};

// 子组件2：趋势图表（模拟高级图表）
const TrendChart = {
  name: 'TrendChart',
  props: ['data', 'height', 'loading'],
  template: `
    <div class="trend-chart" :class="{ 'chart-loading': loading }">
      <svg :width="'100%'" :height="height" viewBox="0 0 800 300" preserveAspectRatio="none">
        <!-- 网格线 -->
        <g v-for="i in 5" :key="i">
          <line 
            :x1="0" :y1="i * 60" :x2="800" :y2="i * 60" 
            stroke="#e2e8f0" stroke-width="0.5" stroke-dasharray="4,4"
          />
        </g>
        
        <!-- 面积填充 -->
        <polygon
          :points="areaPoints"
          fill="rgba(59, 130, 246, 0.1)"
          stroke="none"
        />
        
        <!-- 数据线条 -->
        <polyline
          :points="linePoints"
          fill="none"
          stroke="#3b82f6"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        
        <!-- 数据点 -->
        <g v-for="(point, idx) in data" :key="idx">
          <circle
            :cx="getX(idx)"
            :cy="getY(point.value)"
            r="4"
            fill="#ef4444"
            stroke="white"
            stroke-width="2"
            @mouseenter="hoveredIndex = idx"
            @mouseleave="hoveredIndex = null"
            @click.stop="onPointClick(idx, point)"
            style="cursor: pointer;"
          />
          <text
            v-if="hoveredIndex === idx"
            :x="getX(idx)"
            :y="getY(point.value) - 10"
            text-anchor="middle"
            font-size="10"
            fill="#475569"
          >
            {{ point.value }}
          </text>
        </g>
      </svg>
      <div class="chart-legend">
        <span class="legend-item">📈 访问量</span>
        <span class="legend-item">🖱️ 点击数据点查看详情</span>
      </div>
    </div>
  `,
  data() {
    return {
      hoveredIndex: null
    };
  },
  computed: {
    maxValue() {
      return Math.max(...this.data.map(d => d.value), 100);
    },
    minValue() {
      return Math.min(...this.data.map(d => d.value), 0);
    },
    linePoints() {
      return this.data.map((point, idx) => `${this.getX(idx)},${this.getY(point.value)}`).join(' ');
    },
    areaPoints() {
      const points = this.data.map((point, idx) => `${this.getX(idx)},${this.getY(point.value)}`);
      return `0,300 ${points.join(' ')} 800,300`;
    }
  },
  methods: {
    getX(index) {
      if (this.data.length <= 1) return 400;
      return (index / (this.data.length - 1)) * 800;
    },
    getY(value) {
      const range = this.maxValue - this.minValue;
      if (range === 0) return 150;
      return 300 - ((value - this.minValue) / range) * 280;
    },
    onPointClick(index, point) {
      this.$emit('data-point-click', {
        index,
        value: point.value,
        date: point.date,
        label: point.label
      });
    }
  },
  emits: ['data-point-click']
};

// 子组件3：洞察列表
const InsightList = {
  name: 'InsightList',
  props: ['insights', 'loading'],
  template: `
    <div class="insight-list" :class="{ 'loading': loading }">
      <div v-for="insight in insights" :key="insight.id" class="insight-item" @click="$emit('insight-click', insight)">
        <div class="insight-icon" :style="{ backgroundColor: insight.color }">
          {{ insight.icon }}
        </div>
        <div class="insight-content">
          <div class="insight-title">{{ insight.title }}</div>
          <div class="insight-desc">{{ insight.description }}</div>
          <div class="insight-meta">{{ insight.timestamp }}</div>
        </div>
        <div class="insight-trend" :class="insight.trend > 0 ? 'up' : 'down'">
          {{ insight.trend > 0 ? '+' : '' }}{{ insight.trend }}%
        </div>
      </div>
      <div v-if="insights.length === 0 && !loading" class="empty-insights">
        暂无智能洞察数据
      </div>
    </div>
  `,
  emits: ['insight-click']
};

// 子组件4：活动表格
const ActivityTable = {
  name: 'ActivityTable',
  props: ['activities', 'loading'],
  template: `
    <div class="activity-table-wrapper">
      <table class="activity-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>用户</th>
            <th>操作类型</th>
            <th>详细信息</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="activity in activities" :key="activity.id" @click="$emit('row-click', activity)" class="activity-row">
            <td class="time-cell">{{ formatTime(activity.timestamp) }}</td>
            <td class="user-cell">{{ activity.user }}</td>
            <td class="type-cell">
              <span :class="['activity-badge', activity.type]">{{ getTypeLabel(activity.type) }}</span>
            </td>
            <td class="detail-cell">{{ activity.detail }}</td>
            <td class="status-cell">
              <span :class="['status-badge', activity.status]">{{ getStatusLabel(activity.status) }}</span>
            </td>
          </tr>
          <tr v-if="activities.length === 0 && !loading">
            <td colspan="5" class="empty-cell">暂无活动记录</td>
          </tr>
        </tbody>
      </table>
    </div>
  `,
  methods: {
    formatTime(timestamp) {
      const date = new Date(timestamp);
      return date.toLocaleTimeString();
    },
    getTypeLabel(type) {
      const labels = { login: '登录', purchase: '购买', view: '浏览', share: '分享' };
      return labels[type] || type;
    },
    getStatusLabel(status) {
      const labels = { success: '成功', pending: '处理中', failed: '失败' };
      return labels[status] || status;
    }
  },
  emits: ['row-click']
};

// 主组件
module.exports =  {
  name: 'AnalyticsDashboard',
  components: {
    StatCard,
    TrendChart,
    InsightList,
    ActivityTable
  },
  props: {
    userId: { type: String, default: 'anonymous' },
    apiEndpoint: { type: String, default: 'https://api.example.com/analytics' }
  },
  data() {
    return {
      isDarkMode: false,
      isCompactView: false,
      isLoading: false,
      selectedPeriod: '30d',
      searchQuery: '',
      activityFilter: 'all',
      
      // 统计数据
      statistics: [
        { id: 1, title: '总访问量', value: 28450, change: 12.5, icon: '👥' },
        { id: 2, title: '新增用户', value: 3240, change: -2.3, icon: '🆕' },
        { id: 3, title: '转化率', value: 3.8, change: 0.7, icon: '🎯' },
        { id: 4, title: '总收入', value: 187500, change: 18.9, icon: '💰' }
      ],
      
      // 图表数据
      chartData: [],
      
      // 智能洞察
      insights: [],
      
      // 活动记录
      activities: [],
      
      // 数据缓存
      dataCache: {
        '7d': null,
        '30d': null,
        '90d': null
      },
      
      // 事件日志（用于调试）
      eventHistory: []
    };
  },
  computed: {
    // 过滤后的活动记录（动态过滤）
    filteredActivities() {
      let filtered = [...this.activities];
      
      if (this.searchQuery) {
        const query = this.searchQuery.toLowerCase();
        filtered = filtered.filter(activity => 
          activity.user.toLowerCase().includes(query) ||
          activity.detail.toLowerCase().includes(query)
        );
      }
      
      if (this.activityFilter !== 'all') {
        filtered = filtered.filter(activity => activity.type === this.activityFilter);
      }
      
      return filtered;
    }
  },
  watch: {
    // 监听主题变化
    isDarkMode(newVal) {
      this.addEventToHistory('theme', `主题切换为 ${newVal ? '暗色' : '亮色'} 模式`);
      this.$emit('theme-changed', { darkMode: newVal, timestamp: Date.now() });
    },
    
    // 监听视图模式变化
    isCompactView(newVal) {
      this.addEventToHistory('view', `视图切换为 ${newVal ? '紧凑' : '展开'} 模式`);
    }
  },
  mounted() {
    this.initializeDashboard();
    this.startAutoRefresh();
    this.addEventToHistory('system', '仪表盘初始化完成');
  },
  beforeDestroy() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
    this.addEventToHistory('system', '仪表盘组件即将销毁');
  },
  methods: {
    // 初始化仪表盘
    async initializeDashboard() {
      this.isLoading = true;
      try {
        await Promise.all([
          this.loadChartData(),
          this.loadInsights(),
          this.loadActivities()
        ]);
        this.addEventToHistory('success', '所有数据加载成功');
      } catch (error) {
        this.addEventToHistory('error', `数据加载失败: ${error.message}`);
        this.$emit('error', { message: error.message, timestamp: Date.now() });
      } finally {
        this.isLoading = false;
      }
    },
    
    // 加载图表数据（模拟API调用）
    async loadChartData() {
      // 检查缓存
      if (this.dataCache[this.selectedPeriod]) {
        this.chartData = this.dataCache[this.selectedPeriod];
        this.addEventToHistory('cache', `使用缓存的 ${this.selectedPeriod} 图表数据`);
        return;
      }
      
      // 模拟异步API请求
      await new Promise(resolve => setTimeout(resolve, 800));
      
      // 生成模拟数据
      const days = this.selectedPeriod === '7d' ? 7 : (this.selectedPeriod === '30d' ? 30 : 90);
      const data = [];
      let baseValue = 1000;
      
      for (let i = 0; i < days; i++) {
        const variance = Math.sin(i * 0.2) * 200;
        const trend = i * 2;
        baseValue += Math.random() * 30 - 15;
        const value = Math.max(100, Math.floor(baseValue + variance + trend));
        
        const date = new Date();
        date.setDate(date.getDate() - (days - i));
        
        data.push({
          date: date.toISOString().split('T')[0],
          label: this.formatDateLabel(date, days),
          value: value
        });
      }
      
      this.chartData = data;
      this.dataCache[this.selectedPeriod] = data;
      this.addEventToHistory('fetch', `加载了 ${days} 天的图表数据`);
    },
    
    // 加载智能洞察
    async loadInsights() {
      await new Promise(resolve => setTimeout(resolve, 600));
      
      const insightsData = [
        {
          id: 1,
          title: '用户活跃度提升',
          description: '过去7天用户访问时长增加了23%，主要集中在移动端',
          icon: '🚀',
          color: '#10b981',
          trend: 23,
          timestamp: '2分钟前'
        },
        {
          id: 2,
          title: '转化率优化建议',
          description: '购物车放弃率较高，建议优化结账流程',
          icon: '🛒',
          color: '#f59e0b',
          trend: -5,
          timestamp: '15分钟前'
        },
        {
          id: 3,
          title: '新用户增长高峰',
          description: '社交媒体渠道带来大量新用户，增长42%',
          icon: '📱',
          color: '#3b82f6',
          trend: 42,
          timestamp: '1小时前'
        },
        {
          id: 4,
          title: '服务器响应优化',
          description: 'API响应时间降低15%，用户体验改善',
          icon: '⚡',
          color: '#8b5cf6',
          trend: 15,
          timestamp: '3小时前'
        }
      ];
      
      this.insights = insightsData;
    },
    
    // 加载活动记录
    async loadActivities() {
      await new Promise(resolve => setTimeout(resolve, 500));
      
      const activities = [];
      const users = ['张三', '李四', '王五', '赵六', '钱七'];
      const types = ['login', 'purchase', 'view', 'share'];
      const details = {
        login: ['登录成功', '登录失败', '异地登录'],
        purchase: ['购买商品A', '购买商品B', '订阅会员'],
        view: ['浏览首页', '查看详情页', '搜索关键词'],
        share: ['分享链接', '邀请好友', '发布评论']
      };
      
      for (let i = 0; i < 15; i++) {
        const type = types[Math.floor(Math.random() * types.length)];
        const status = Math.random() > 0.8 ? 'failed' : (Math.random() > 0.9 ? 'pending' : 'success');
        
        activities.push({
          id: Date.now() + i,
          timestamp: Date.now() - Math.random() * 3600000,
          user: users[Math.floor(Math.random() * users.length)],
          type: type,
          detail: details[type][Math.floor(Math.random() * details[type].length)],
          status: status
        });
      }
      
      // 按时间倒序排列
      this.activities = activities.sort((a, b) => b.timestamp - a.timestamp);
    },
    
    // 手动刷新所有数据
    async manualRefresh() {
      if (this.isLoading) return;
      
      this.isLoading = true;
      this.addEventToHistory('action', '用户手动刷新数据');
      
      try {
        // 清除当前周期的缓存
        this.dataCache[this.selectedPeriod] = null;
        
        await Promise.all([
          this.loadChartData(),
          this.loadInsights(),
          this.loadActivities()
        ]);
        
        this.addEventToHistory('success', '数据刷新完成');
        this.$emit('data-refreshed', { 
          timestamp: Date.now(), 
          period: this.selectedPeriod,
          statistics: this.statistics 
        });
      } catch (error) {
        this.addEventToHistory('error', `刷新失败: ${error.message}`);
        this.$emit('error', { message: error.message });
      } finally {
        this.isLoading = false;
      }
    },
    
    // 自动刷新（每30秒）
    startAutoRefresh() {
      this.refreshInterval = setInterval(() => {
        if (!this.isLoading) {
          this.autoRefresh();
        }
      }, 30000);
    },
    
    async autoRefresh() {
      this.addEventToHistory('system', '自动刷新数据');
      try {
        this.dataCache[this.selectedPeriod] = null;
        await this.loadChartData();
        await this.loadInsights();
        await this.loadActivities();
        this.addEventToHistory('success', '自动数据同步完成');
      } catch (error) {
        this.addEventToHistory('error', `自动刷新失败: ${error.message}`);
      }
    },
    
    // UI交互方法
    toggleTheme() {
      this.isDarkMode = !this.isDarkMode;
    },
    
    toggleView() {
      this.isCompactView = !this.isCompactView;
    },
    
    onPeriodChange() {
      this.addEventToHistory('filter', `切换时间段为: ${this.selectedPeriod}`);
      this.loadChartData();
    },
    
    onSearchChange() {
      this.addEventToHistory('filter', `搜索关键词: ${this.searchQuery || '清空'}`);
    },
    
    onFilterChange() {
      this.addEventToHistory('filter', `活动类型过滤: ${this.activityFilter}`);
    },
    
    // 事件处理方法
    onStatClick(stat) {
      this.addEventToHistory('click', `点击统计卡片: ${stat.title} (${stat.value})`);
      this.$emit('stat-click', { stat, timestamp: Date.now() });
    },
    
    onDataPointClick(data) {
      this.addEventToHistory('chart', `点击数据点: 日期 ${data.date}, 值 ${data.value}`);
      this.$emit('chart-point-click', data);
    },
    
    onInsightClick(insight) {
      this.addEventToHistory('insight', `查看洞察: ${insight.title}`);
      this.$emit('insight-click', insight);
    },
    
    onActivityClick(activity) {
      this.addEventToHistory('activity', `查看活动: ${activity.user} - ${activity.type}`);
      this.$emit('activity-click', activity);
    },
    
    // 辅助方法
    formatDateLabel(date, totalDays) {
      if (totalDays <= 30) {
        return `${date.getMonth() + 1}/${date.getDate()}`;
      }
      return `${date.getMonth() + 1}月`;
    },
    
    addEventToHistory(type, message) {
      const event = {
        type,
        message,
        timestamp: Date.now(),
        timeStr: new Date().toLocaleTimeString()
      };
      
      this.eventHistory.unshift(event);
      if (this.eventHistory.length > 50) {
        this.eventHistory.pop();
      }
      
      // 可选：控制台输出
      if (typeof console !== 'undefined') {
        console.log(`[${event.timeStr}] ${message}`);
      }
    }
  }
};
</script>

<style scoped>
/* 主容器样式 */
.analytics-dashboard {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
  background: #f8fafc;
  color: #1e293b;
  transition: all 0.3s ease;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.analytics-dashboard.dark-mode {
  background: #0f172a;
  color: #e2e8f0;
}

.analytics-dashboard.compact {
  padding: 12px;
}

/* 导航栏 */
.dashboard-navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 16px 20px;
  background: white;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.dark-mode .dashboard-navbar {
  background: #1e293b;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  font-size: 28px;
}

.logo-text {
  font-size: 20px;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.nav-controls {
  display: flex;
  gap: 12px;
}

.nav-controls button {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
  background: #f1f5f9;
  color: #475569;
}

.dark-mode .nav-controls button {
  background: #334155;
  color: #cbd5e1;
}

.nav-controls button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 统计卡片网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
}

.stat-card {
  background: white;
  border-radius: 16px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.dark-mode .stat-card {
  background: #1e293b;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 20px rgba(0,0,0,0.1);
}

.stat-card.loading {
  opacity: 0.6;
  pointer-events: none;
}

.stat-icon {
  font-size: 32px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
  border-radius: 12px;
}

.stat-content {
  flex: 1;
}

.stat-title {
  font-size: 14px;
  color: #64748b;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 4px;
}

.dark-mode .stat-value {
  color: #f1f5f9;
}

.stat-change {
  font-size: 12px;
  font-weight: 600;
}

.stat-change.positive {
  color: #10b981;
}

.stat-change.negative {
  color: #ef4444;
}

.stat-change.neutral {
  color: #f59e0b;
}

/* 可视化区域 */
.visualization-section {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 24px;
  margin-bottom: 32px;
}

.chart-container, .insights-panel {
  background: white;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.dark-mode .chart-container,
.dark-mode .insights-panel {
  background: #1e293b;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  font-size: 18px;
  font-weight: 600;
}

.period-selector {
  padding: 6px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: white;
  cursor: pointer;
}

.dark-mode .period-selector {
  background: #334155;
  border-color: #475569;
  color: #e2e8f0;
}

/* 趋势图表 */
.trend-chart {
  position: relative;
}

.trend-chart.chart-loading {
  opacity: 0.6;
  pointer-events: none;
}

.chart-legend {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  gap: 20px;
  font-size: 12px;
  color: #64748b;
}

/* 洞察列表 */
.insight-list {
  max-height: 320px;
  overflow-y: auto;
}

.insight-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.insight-item:hover {
  background: #f8fafc;
}

.dark-mode .insight-item:hover {
  background: #334155;
}

.insight-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 16px;
}

.insight-content {
  flex: 1;
}

.insight-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.insight-desc {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}

.insight-meta {
  font-size: 10px;
  color: #94a3b8;
}

.insight-trend {
  font-size: 14px;
  font-weight: 600;
}

.insight-trend.up {
  color: #10b981;
}

.insight-trend.down {
  color: #ef4444;
}

/* 活动区域 */
.activity-section {
  background: white;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.dark-mode .activity-section {
  background: #1e293b;
}

.activity-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.filter-controls {
  display: flex;
  gap: 12px;
}

.search-input, .filter-select {
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
}

.dark-mode .search-input,
.dark-mode .filter-select {
  background: #334155;
  border-color: #475569;
  color: #e2e8f0;
}

/* 活动表格 */
.activity-table-wrapper {
  overflow-x: auto;
}

.activity-table {
  width: 100%;
  border-collapse: collapse;
}

.activity-table th {
  text-align: left;
  padding: 12px;
  background: #f8fafc;
  font-weight: 600;
  font-size: 14px;
  border-bottom: 2px solid #e2e8f0;
}

.dark-mode .activity-table th {
  background: #334155;
  border-bottom-color: #475569;
}

.activity-row {
  cursor: pointer;
  transition: background 0.2s;
}

.activity-row:hover {
  background: #f8fafc;
}

.dark-mode .activity-row:hover {
  background: #334155;
}

.activity-table td {
  padding: 12px;
  border-bottom: 1px solid #e2e8f0;
  font-size: 14px;
}

.activity-badge {
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.activity-badge.login { background: #dbeafe; color: #1e40af; }
.activity-badge.purchase { background: #dcfce7; color: #166534; }
.activity-badge.view { background: #fef3c7; color: #92400e; }
.activity-badge.share { background: #f3e8ff; color: #6b21a5; }

.status-badge {
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.status-badge.success { background: #dcfce7; color: #166534; }
.status-badge.pending { background: #fef3c7; color: #92400e; }
.status-badge.failed { background: #fee2e2; color: #991b1b; }

.empty-cell {
  text-align: center;
  padding: 40px;
  color: #94a3b8;
}

/* 加载遮罩 */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.spinner {
  width: 48px;
  height: 48px;
  border: 4px solid #f3f4f6;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-overlay p {
  margin-top: 16px;
  color: white;
  font-size: 14px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .visualization-section {
    grid-template-columns: 1fr;
  }
  
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .dashboard-navbar {
    flex-direction: column;
    gap: 12px;
  }
  
  .nav-controls {
    width: 100%;
    justify-content: center;
  }
  
  .section-title {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>