<template>
  <div class="dashboard" :class="{ 'dark-theme': isDarkMode }">
    <!-- 头部区域：标题与主题切换 -->
    <div class="dashboard-header">
      <h2 class="title">
        <span class="icon">📊</span> 智能仪表盘
      </h2>
      <div class="header-actions">
        <button class="theme-btn" @click="toggleTheme">
          {{ isDarkMode ? '☀️' : '🌙' }}
        </button>
        <button class="refresh-all" @click="refreshAllData" :disabled="isRefreshing">
          {{ isRefreshing ? '🔄 刷新中...' : '🔄 刷新所有' }}
        </button>
      </div>
    </div>

    <!-- 指标卡片区域 (子组件1) -->
    <div class="metrics-grid">
      <metric-card
        v-for="metric in metrics"
        :key="metric.id"
        :title="metric.title"
        :value="metric.value"
        :unit="metric.unit"
        :trend="metric.trend"
        :color="metric.color"
        @click="onMetricClick(metric)"
      />
    </div>

    <!-- 图表区域 (子组件2) -->
    <div class="chart-section">
      <h3 class="section-title">实时数据趋势</h3>
      <simulated-chart
        :data-points="chartData"
        :height="200"
        @point-click="onChartPointClick"
      />
    </div>

    <!-- 事件日志区域 (展示交互记录) -->
    <div class="event-log">
      <div class="log-header">
        <span>📝 事件日志</span>
        <button class="clear-log" @click="clearLogs">清空</button>
      </div>
      <div class="log-list">
        <div v-for="(log, idx) in eventLogs" :key="idx" class="log-item">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-text">{{ log.text }}</span>
        </div>
        <div v-if="eventLogs.length === 0" class="log-empty">暂无事件</div>
      </div>
    </div>
  </div>
</template>

<script>
// 子组件1：指标卡片
const MetricCard = {
  name: 'MetricCard',
  props: ['title', 'value', 'unit', 'trend', 'color'],
  template: `
    <div class="metric-card" :style="{ borderLeftColor: color }" @click="$emit('click')">
      <div class="metric-title">{{ title }}</div>
      <div class="metric-value">{{ value }}<span class="metric-unit">{{ unit }}</span></div>
      <div class="metric-trend" :class="trend > 0 ? 'up' : (trend < 0 ? 'down' : 'flat')">
        {{ trend > 0 ? '▲' : (trend < 0 ? '▼' : '●') }} {{ Math.abs(trend) }}%
      </div>
    </div>
  `,
  emits: ['click']
};

// 子组件2：模拟图表（简单折线图，使用 SVG 绘制）
const SimulatedChart = {
  name: 'SimulatedChart',
  props: ['dataPoints', 'height'],
  template: `
    <div class="chart-container" @click="handleChartClick">
      <svg :width="'100%'" :height="height" viewBox="0 0 500 200" preserveAspectRatio="none">
        <!-- 背景网格 -->
        <line v-for="y in [0, 50, 100, 150, 200]" :key="y" x1="0" :y1="y" x2="500" :y2="y" stroke="#ddd" stroke-width="0.5"/>
        <polyline
          :points="polylinePoints"
          fill="none"
          stroke="#3b82f6"
          stroke-width="2"
        />
        <circle
          v-for="(point, idx) in dataPoints"
          :key="idx"
          :cx="getX(idx)"
          :cy="getY(point)"
          r="4"
          fill="#ef4444"
          @click.stop="onPointClick(idx, point)"
        />
      </svg>
      <div class="chart-label">点击数据点查看详情</div>
    </div>
  `,
  computed: {
    polylinePoints() {
      return this.dataPoints.map((val, idx) => `${this.getX(idx)},${this.getY(val)}`).join(' ');
    }
  },
  methods: {
    getX(idx) {
      const step = 500 / (this.dataPoints.length - 1 || 1);
      return idx * step;
    },
    getY(value) {
      const min = Math.min(...this.dataPoints, 0);
      const max = Math.max(...this.dataPoints, 100);
      const range = max - min || 1;
      return 200 - ((value - min) / range) * 200;
    },
    handleChartClick(e) {
      // 避免冒泡到 circle 的点击
      if (e.target.tagName !== 'circle') {
        this.$emit('point-click', { type: 'chart_background', message: '点击了图表背景' });
      }
    },
    onPointClick(idx, val) {
      this.$emit('point-click', { type: 'data_point', index: idx, value: val });
    }
  },
  emits: ['point-click']
};

module.exports =  {
  name: 'SmartDashboard',
  components: {
    MetricCard,
    SimulatedChart
  },
  props: {
    // 允许外部传入初始配置
    initialTheme: { type: Boolean, default: false },
    autoRefreshInterval: { type: Number, default: 10000 } // 毫秒
  },
  data() {
    return {
      isDarkMode: this.initialTheme,
      isRefreshing: false,
      metrics: [
        { id: 1, title: '总销售额', value: 12450, unit: '元', trend: 8.5, color: '#f97316' },
        { id: 2, title: '访问量', value: 3240, unit: '次', trend: -2.3, color: '#3b82f6' },
        { id: 3, title: '转化率', value: 3.2, unit: '%', trend: 0.4, color: '#10b981' },
        { id: 4, title: '活跃用户', value: 1870, unit: '人', trend: 12.1, color: '#8b5cf6' }
      ],
      chartData: [25, 40, 38, 55, 48, 62, 70, 58, 65, 72],
      eventLogs: [],
      refreshTimer: null
    };
  },
  computed: {
    // 计算属性用于动态样式（复杂动态类）
    dynamicClasses() {
      return {
        'dashboard': true,
        'dark-theme': this.isDarkMode,
        'refreshing': this.isRefreshing
      };
    }
  },
  watch: {
    // 监听主题变化，记录日志
    isDarkMode(newVal) {
      this.addLog('系统', `主题切换为 ${newVal ? '暗色' : '亮色'} 模式`);
    }
  },
  mounted() {
    this.addLog('系统', '仪表盘已加载');
    // 启动自动刷新定时器
    if (this.autoRefreshInterval > 0) {
      this.refreshTimer = setInterval(() => {
        this.refreshAllData();
      }, this.autoRefreshInterval);
      this.addLog('系统', `已开启自动刷新 (间隔 ${this.autoRefreshInterval/1000} 秒)`);
    }
    // 模拟初始数据加载
    this.simulateDataFetch();
  },
  beforeDestroy() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
      this.addLog('系统', '组件销毁，已清除自动刷新定时器');
    }
  },
  methods: {
    // 添加事件日志
    addLog(source, text) {
      const time = new Date().toLocaleTimeString();
      this.eventLogs.unshift({ time, text: `[${source}] ${text}` });
      if (this.eventLogs.length > 20) this.eventLogs.pop();
    },
    // 清空日志
    clearLogs() {
      this.eventLogs = [];
      this.addLog('用户', '清空了事件日志');
    },
    // 切换主题
    toggleTheme() {
      this.isDarkMode = !this.isDarkMode;
    },
    // 模拟异步数据获取
    async simulateDataFetch() {
      // 模拟延迟
      await new Promise(resolve => setTimeout(resolve, 500));
      // 随机更新指标数据（模拟真实数据变化）
      this.metrics = this.metrics.map(m => ({
        ...m,
        value: Math.floor(m.value * (0.9 + Math.random() * 0.2)),
        trend: parseFloat((Math.random() * 10 - 5).toFixed(1))
      }));
      // 更新图表数据
      const newChartData = this.chartData.map(() => Math.floor(Math.random() * 80 + 20));
      this.chartData = newChartData;
      return true;
    },
    // 刷新所有数据（异步操作，带状态管理）
    async refreshAllData() {
      if (this.isRefreshing) return;
      this.isRefreshing = true;
      this.addLog('系统', '开始刷新所有数据...');
      try {
        await this.simulateDataFetch();
        this.addLog('系统', '数据刷新完成');
        this.$emit('data-refreshed', { time: new Date().toISOString(), metrics: this.metrics });
      } catch (err) {
        this.addLog('错误', `刷新失败: ${err.message}`);
        this.$emit('error', err);
      } finally {
        this.isRefreshing = false;
      }
    },
    // 指标卡片点击事件
    onMetricClick(metric) {
      this.addLog('指标', `点击了 ${metric.title}，当前值 ${metric.value}${metric.unit}`);
      this.$emit('metric-click', metric);
    },
    // 图表点点击事件
    onChartPointClick(detail) {
      if (detail.type === 'data_point') {
        this.addLog('图表', `点击数据点: 索引 ${detail.index}，值 ${detail.value}`);
      } else {
        this.addLog('图表', detail.message);
      }
      this.$emit('chart-interaction', detail);
    }
  }
};
</script>

<style scoped>
/* 基础样式 + 暗色主题动态类 */
.dashboard {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background: #f8fafc;
  color: #0f172a;
  border-radius: 24px;
  padding: 24px;
  transition: background 0.3s, color 0.3s;
  box-shadow: 0 20px 35px -10px rgba(0,0,0,0.1);
  max-width: 900px;
  margin: 20px auto;
}

.dashboard.dark-theme {
  background: #1e293b;
  color: #f1f5f9;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.title {
  margin: 0;
  font-size: 1.8rem;
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-actions {
  display: flex;
  gap: 12px;
}
.theme-btn, .refresh-all {
  padding: 8px 16px;
  border: none;
  border-radius: 40px;
  font-size: 0.9rem;
  cursor: pointer;
  background: #e2e8f0;
  transition: 0.2s;
}
.dark-theme .theme-btn, .dark-theme .refresh-all {
  background: #334155;
  color: #e2e8f0;
}
.refresh-all:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 指标卡片网格 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}
.metric-card {
  background: rgba(255,255,255,0.9);
  border-left: 6px solid;
  border-radius: 16px;
  padding: 12px 16px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.dark-theme .metric-card {
  background: #0f172a;
}
.metric-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 20px rgba(0,0,0,0.1);
}
.metric-title {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #475569;
}
.dark-theme .metric-title {
  color: #94a3b8;
}
.metric-value {
  font-size: 1.8rem;
  font-weight: 700;
  margin: 8px 0;
}
.metric-unit {
  font-size: 0.9rem;
  margin-left: 4px;
}
.metric-trend {
  font-size: 0.8rem;
}
.metric-trend.up { color: #10b981; }
.metric-trend.down { color: #ef4444; }
.metric-trend.flat { color: #f59e0b; }

/* 图表区域 */
.chart-section {
  background: rgba(255,255,255,0.7);
  border-radius: 20px;
  padding: 16px;
  margin-bottom: 24px;
}
.dark-theme .chart-section {
  background: #0f172a;
}
.section-title {
  margin-bottom: 16px;
  font-size: 1.2rem;
}
.chart-container {
  cursor: pointer;
}
.chart-label {
  text-align: center;
  font-size: 0.75rem;
  margin-top: 8px;
  color: #64748b;
}

/* 事件日志 */
.event-log {
  background: rgba(0,0,0,0.05);
  border-radius: 20px;
  padding: 12px;
}
.dark-theme .event-log {
  background: #0f172a;
}
.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: bold;
}
.clear-log {
  background: none;
  border: none;
  cursor: pointer;
  color: #ef4444;
  font-size: 0.8rem;
}
.log-list {
  max-height: 150px;
  overflow-y: auto;
  font-size: 0.8rem;
}
.log-item {
  display: flex;
  gap: 12px;
  padding: 4px 0;
  border-bottom: 1px solid rgba(0,0,0,0.1);
}
.log-time {
  font-family: monospace;
  color: #64748b;
}
.log-empty {
  text-align: center;
  color: #94a3b8;
  padding: 12px;
}
</style>