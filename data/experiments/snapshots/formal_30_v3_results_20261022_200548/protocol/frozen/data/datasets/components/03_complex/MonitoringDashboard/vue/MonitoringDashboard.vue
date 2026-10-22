<template>
  <div class="monitoring-dashboard" :class="{ 'dark-mode': isDarkMode }">
    <!-- 顶部状态栏 -->
    <div class="status-bar">
      <div class="system-status">
        <span class="status-indicator" :class="systemHealth"></span>
        <span class="status-text">系统状态：{{ systemHealthText }}</span>
      </div>
      <div class="time-display">
        <span>📅 {{ currentDate }}</span>
        <span>⏰ {{ currentTime }}</span>
      </div>
      <div class="action-buttons">
        <button @click="toggleTheme" class="icon-btn">🌓</button>
        <button @click="exportReport" class="icon-btn">📊</button>
        <button @click="showSettings = true" class="icon-btn">⚙️</button>
      </div>
    </div>

    <!-- KPI 指标卡片 -->
    <div class="kpi-grid">
      <kpi-card
        v-for="kpi in kpiData"
        :key="kpi.id"
        :title="kpi.title"
        :value="kpi.value"
        :unit="kpi.unit"
        :trend="kpi.trend"
        :status="kpi.status"
        :icon="kpi.icon"
        @click="onKPIClick(kpi)"
      />
    </div>

    <!-- 图表区域 -->
    <div class="charts-grid">
      <div class="chart-card">
        <div class="chart-header">
          <h3>实时 CPU / 内存 使用率</h3>
          <div class="chart-controls">
            <button 
              v-for="period in timePeriods" 
              :key="period.value"
              :class="{ active: selectedPeriod === period.value }"
              @click="changePeriod(period.value)"
              class="period-btn"
            >
              {{ period.label }}
            </button>
          </div>
        </div>
        <real-time-chart
          ref="cpuChart"
          :data="cpuHistory"
          :height="250"
          :color="'#3b82f6'"
          :loading="isChartLoading"
        />
        <real-time-chart
          ref="memoryChart"
          :data="memoryHistory"
          :height="250"
          :color="'#10b981'"
          :loading="isChartLoading"
        />
      </div>

      <div class="chart-card">
        <h3>服务请求统计</h3>
        <request-chart
          :data="requestStats"
          :height="300"
          @bar-click="onBarClick"
        />
      </div>
    </div>

    <!-- 告警和事件区域 -->
    <div class="events-grid">
      <!-- 实时告警 -->
      <div class="alerts-panel">
        <div class="panel-header">
          <h3>🚨 实时告警</h3>
          <span class="alert-count">{{ activeAlerts.length }}</span>
          <button @click="clearAlerts" class="clear-btn" v-if="activeAlerts.length">清空</button>
        </div>
        <alert-list
          :alerts="activeAlerts"
          @acknowledge="acknowledgeAlert"
          @resolve="resolveAlert"
        />
      </div>

      <!-- 系统日志 -->
      <div class="logs-panel">
        <div class="panel-header">
          <h3>📋 系统日志</h3>
          <div class="log-filters">
            <select v-model="logFilter" @change="filterLogs">
              <option value="all">全部</option>
              <option value="info">信息</option>
              <option value="warning">警告</option>
              <option value="error">错误</option>
            </select>
            <button @click="clearLogs" class="clear-btn">清空</button>
          </div>
        </div>
        <log-list
          :logs="filteredLogs"
          :loading="isLogLoading"
          @log-click="onLogClick"
        />
      </div>
    </div>

    <!-- 服务健康检查 -->
    <div class="services-panel">
      <div class="panel-header">
        <h3>🔗 服务健康检查</h3>
        <button @click="refreshServices" class="refresh-btn" :disabled="isRefreshingServices">
          {{ isRefreshingServices ? '刷新中...' : '刷新' }}
        </button>
      </div>
      <service-grid
        :services="services"
        @service-click="onServiceClick"
      />
    </div>

    <!-- 设置模态框 -->
    <div v-if="showSettings" class="modal-overlay" @click.self="showSettings = false">
      <div class="modal-content">
        <div class="modal-header">
          <h3>系统设置</h3>
          <button class="close-btn" @click="showSettings = false">✕</button>
        </div>
        <settings-form
          :settings="settings"
          @save="saveSettings"
          @cancel="showSettings = false"
        />
      </div>
    </div>

    <!-- 通知浮层 -->
    <div v-if="notification.show" class="notification" :class="notification.type">
      <span>{{ notification.message }}</span>
      <button @click="hideNotification">✕</button>
    </div>
  </div>
</template>

<script>
// 子组件1: KPI卡片
const KPICard = {
  name: 'KPICard',
  props: ['title', 'value', 'unit', 'trend', 'status', 'icon'],
  template: `
    <div class="kpi-card" :class="status" @click="$emit('click')">
      <div class="kpi-icon">{{ icon }}</div>
      <div class="kpi-content">
        <div class="kpi-title">{{ title }}</div>
        <div class="kpi-value">{{ value }}<span class="kpi-unit">{{ unit }}</span></div>
        <div class="kpi-trend" :class="trend >= 0 ? 'up' : 'down'">
          {{ trend >= 0 ? '▲' : '▼' }} {{ Math.abs(trend) }}%
        </div>
      </div>
    </div>
  `,
  emits: ['click']
};

// 子组件2: 实时图表
const RealTimeChart = {
  name: 'RealTimeChart',
  props: ['data', 'height', 'color', 'loading'],
  template: `
    <div class="chart-wrapper" :class="{ loading }">
      <svg :width="'100%'" :height="height" :viewBox="'0 0 ' + width + ' ' + height">
        <defs>
          <linearGradient :id="gradientId" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" :stop-color="color" stop-opacity="0.3"/>
            <stop offset="100%" :stop-color="color" stop-opacity="0.0"/>
          </linearGradient>
        </defs>
        
        <!-- 网格线 -->
        <g v-for="i in 4" :key="'grid-' + i">
          <line 
            :x1="0" :y1="i * (height / 4)" 
            :x2="width" :y2="i * (height / 4)"
            stroke="#e2e8f0" stroke-width="0.5" stroke-dasharray="3,3"
          />
        </g>
        
        <!-- 面积填充 -->
        <polygon
          :points="areaPoints"
          :fill="'url(#' + gradientId + ')'"
        />
        
        <!-- 数据线 -->
        <polyline
          :points="linePoints"
          fill="none"
          :stroke="color"
          stroke-width="2"
          stroke-linecap="round"
        />
        
        <!-- 数据点 -->
        <circle
          v-for="(point, idx) in dataPoints"
          :key="'point-' + idx"
          :cx="getX(idx)"
          :cy="getY(point)"
          r="3"
          :fill="color"
          stroke="white"
          stroke-width="2"
        />
      </svg>
    </div>
  `,
  data() {
    return {
      width: 600
    };
  },
  computed: {
    gradientId() {
      return `gradient-${this.color.replace('#', '')}`;
    },
    dataPoints() {
      return this.data.map(d => d.value);
    },
    maxValue() {
      return Math.max(...this.dataPoints, 100);
    },
    minValue() {
      return Math.min(...this.dataPoints, 0);
    },
    linePoints() {
      return this.dataPoints.map((val, idx) => `${this.getX(idx)},${this.getY(val)}`).join(' ');
    },
    areaPoints() {
      const points = this.dataPoints.map((val, idx) => `${this.getX(idx)},${this.getY(val)}`);
      return `0,${this.height} ${points.join(' ')} ${this.width},${this.height}`;
    }
  },
  mounted() {
    this.updateWidth();
    window.addEventListener('resize', this.updateWidth);
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.updateWidth);
  },
  methods: {
    updateWidth() {
      if (this.$el) {
        this.width = this.$el.clientWidth - 20;
      }
    },
    getX(index) {
      if (this.dataPoints.length <= 1) return this.width / 2;
      return (index / (this.dataPoints.length - 1)) * this.width;
    },
    getY(value) {
      const range = this.maxValue - this.minValue;
      if (range === 0) return this.height / 2;
      return this.height - ((value - this.minValue) / range) * this.height;
    }
  }
};

// 子组件3: 请求统计图表
const RequestChart = {
  name: 'RequestChart',
  props: ['data', 'height'],
  template: `
    <div class="request-chart">
      <svg :width="'100%'" :height="height" viewBox="0 0 800 300">
        <g v-for="(item, idx) in data" :key="idx">
          <rect
            :x="getX(idx)"
            y="0"
            :width="barWidth"
            :height="getHeight(item.count)"
            :fill="getColor(item.status)"
            @click="$emit('bar-click', item)"
            style="cursor: pointer;"
          />
          <text
            :x="getX(idx) + barWidth / 2"
            y="290"
            text-anchor="middle"
            font-size="10"
            fill="#64748b"
          >
            {{ item.hour }}
          </text>
        </g>
      </svg>
      <div class="chart-legend">
        <span v-for="status in statusTypes" :key="status.type" class="legend-item">
          <span class="legend-color" :style="{ background: status.color }"></span>
          {{ status.label }}
        </span>
      </div>
    </div>
  `,
  computed: {
    barWidth() {
      return 800 / this.data.length - 4;
    },
    maxCount() {
      return Math.max(...this.data.map(d => d.count), 100);
    },
    statusTypes() {
      return [
        { type: 'success', label: '成功', color: '#10b981' },
        { type: 'warning', label: '警告', color: '#f59e0b' },
        { type: 'error', label: '错误', color: '#ef4444' }
      ];
    }
  },
  methods: {
    getX(index) {
      return (index * 800) / this.data.length + 2;
    },
    getHeight(count) {
      return (count / this.maxCount) * 280;
    },
    getColor(status) {
      const colors = { success: '#10b981', warning: '#f59e0b', error: '#ef4444' };
      return colors[status] || '#3b82f6';
    }
  },
  emits: ['bar-click']
};

// 子组件4: 告警列表
const AlertList = {
  name: 'AlertList',
  props: ['alerts'],
  template: `
    <div class="alert-list">
      <div v-for="alert in alerts" :key="alert.id" class="alert-item" :class="alert.severity">
        <div class="alert-icon">
          {{ alert.severity === 'critical' ? '🔴' : (alert.severity === 'warning' ? '🟡' : '🔵') }}
        </div>
        <div class="alert-content">
          <div class="alert-title">{{ alert.title }}</div>
          <div class="alert-desc">{{ alert.description }}</div>
          <div class="alert-time">{{ formatTime(alert.timestamp) }}</div>
        </div>
        <div class="alert-actions">
          <button @click="$emit('acknowledge', alert.id)" class="alert-btn">确认</button>
          <button @click="$emit('resolve', alert.id)" class="alert-btn resolve">解决</button>
        </div>
      </div>
      <div v-if="alerts.length === 0" class="empty-alerts">
        ✅ 暂无告警，系统运行正常
      </div>
    </div>
  `,
  methods: {
    formatTime(timestamp) {
      const date = new Date(timestamp);
      return date.toLocaleTimeString();
    }
  },
  emits: ['acknowledge', 'resolve']
};

// 子组件5: 日志列表
const LogList = {
  name: 'LogList',
  props: ['logs', 'loading'],
  template: `
    <div class="log-list">
      <div v-if="loading" class="log-loading">加载日志中...</div>
      <div v-else>
        <div v-for="log in logs" :key="log.id" class="log-item" @click="$emit('log-click', log)">
          <span class="log-time">{{ formatTime(log.timestamp) }}</span>
          <span class="log-level" :class="log.level">{{ log.level.toUpperCase() }}</span>
          <span class="log-message">{{ log.message }}</span>
          <span class="log-source">{{ log.source }}</span>
        </div>
        <div v-if="logs.length === 0" class="empty-logs">
          暂无日志记录
        </div>
      </div>
    </div>
  `,
  methods: {
    formatTime(timestamp) {
      const date = new Date(timestamp);
      return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}`;
    }
  },
  emits: ['log-click']
};

// 子组件6: 服务网格
const ServiceGrid = {
  name: 'ServiceGrid',
  props: ['services'],
  template: `
    <div class="service-grid">
      <div v-for="service in services" :key="service.id" class="service-card" @click="$emit('service-click', service)">
        <div class="service-header">
          <span class="service-name">{{ service.name }}</span>
          <span class="service-status" :class="service.status">
            {{ getStatusText(service.status) }}
          </span>
        </div>
        <div class="service-metrics">
          <div class="metric">
            <span class="metric-label">响应时间</span>
            <span class="metric-value">{{ service.responseTime }}ms</span>
          </div>
          <div class="metric">
            <span class="metric-label">可用性</span>
            <span class="metric-value">{{ service.availability }}%</span>
          </div>
        </div>
        <div class="service-progress">
          <div class="progress-bar" :style="{ width: service.availability + '%', background: getProgressColor(service.availability) }"></div>
        </div>
      </div>
    </div>
  `,
  methods: {
    getStatusText(status) {
      const texts = { healthy: '健康', warning: '警告', down: '离线' };
      return texts[status] || status;
    },
    getProgressColor(availability) {
      if (availability >= 95) return '#10b981';
      if (availability >= 80) return '#f59e0b';
      return '#ef4444';
    }
  },
  emits: ['service-click']
};

// 子组件7: 设置表单
const SettingsForm = {
  name: 'SettingsForm',
  props: ['settings'],
  template: `
    <form @submit.prevent="handleSubmit" class="settings-form">
      <div class="form-group">
        <label>刷新间隔 (秒)</label>
        <input type="number" v-model="localSettings.refreshInterval" min="1" max="60" />
      </div>
      <div class="form-group">
        <label>告警阈值 (%)</label>
        <input type="number" v-model="localSettings.alertThreshold" min="0" max="100" />
      </div>
      <div class="form-group">
        <label>日志保留天数</label>
        <select v-model="localSettings.logRetention">
          <option value="1">1天</option>
          <option value="7">7天</option>
          <option value="30">30天</option>
        </select>
      </div>
      <div class="form-group">
        <label>
          <input type="checkbox" v-model="localSettings.autoRefresh" />
          自动刷新数据
        </label>
      </div>
      <div class="form-group">
        <label>
          <input type="checkbox" v-model="localSettings.desktopNotifications" />
          桌面通知
        </label>
      </div>
      <div class="form-actions">
        <button type="button" @click="$emit('cancel')" class="cancel-btn">取消</button>
        <button type="submit" class="submit-btn">保存设置</button>
      </div>
    </form>
  `,
  data() {
    return {
      localSettings: { ...this.settings }
    };
  },
  methods: {
    handleSubmit() {
      this.$emit('save', this.localSettings);
    }
  },
  emits: ['save', 'cancel']
};

// 主组件
module.exports =  {
  name: 'MonitoringDashboard',
  components: {
    'kpi-card': KPICard,
    'real-time-chart': RealTimeChart,
    'request-chart': RequestChart,
    'alert-list': AlertList,
    'log-list': LogList,
    'service-grid': ServiceGrid,
    'settings-form': SettingsForm
  },
  data() {
    return {
      // UI状态
      isDarkMode: false,
      showSettings: false,
      selectedPeriod: '1h',
      isChartLoading: false,
      isLogLoading: false,
      isRefreshingServices: false,
      
      // 时间相关
      currentDate: '',
      currentTime: '',
      timePeriods: [
        { value: '1h', label: '1小时' },
        { value: '6h', label: '6小时' },
        { value: '24h', label: '24小时' }
      ],
      
      // KPI数据
      kpiData: [
        { id: 1, title: 'CPU使用率', value: 45, unit: '%', trend: -5, status: 'healthy', icon: '💻' },
        { id: 2, title: '内存使用率', value: 62, unit: '%', trend: 8, status: 'warning', icon: '🧠' },
        { id: 3, title: '请求成功率', value: 98.5, unit: '%', trend: 1.2, status: 'healthy', icon: '✅' },
        { id: 4, title: '平均响应时间', value: 156, unit: 'ms', trend: -12, status: 'healthy', icon: '⚡' }
      ],
      
      // 图表数据
      cpuHistory: [],
      memoryHistory: [],
      requestStats: [],
      
      // 告警数据
      activeAlerts: [],
      alertHistory: [],
      
      // 日志数据
      systemLogs: [],
      logFilter: 'all',
      
      // 服务数据
      services: [],
      
      // 系统设置
      settings: {
        refreshInterval: 5,
        alertThreshold: 80,
        logRetention: '7',
        autoRefresh: true,
        desktopNotifications: false
      },
      
      // 通知
      notification: {
        show: false,
        message: '',
        type: 'info'
      },
      
      // 定时器
      refreshTimer: null,
      timeTimer: null,
      notificationTimer: null,
      
      // 模拟数据生成器
      dataGenerator: null,
      
      // 告警ID计数器
      alertIdCounter: 100
    };
  },
  computed: {
    systemHealth() {
      const avgCpu = this.kpiData[0].value;
      if (avgCpu > 80) return 'critical';
      if (avgCpu > 60) return 'warning';
      return 'healthy';
    },
    systemHealthText() {
      const texts = { healthy: '健康', warning: '警告', critical: '严重' };
      return texts[this.systemHealth];
    },
    filteredLogs() {
      if (this.logFilter === 'all') return this.systemLogs;
      return this.systemLogs.filter(log => log.level === this.logFilter);
    }
  },
  watch: {
    settings: {
      handler(newVal) {
        if (newVal.autoRefresh && !this.refreshTimer) {
          this.startAutoRefresh();
        } else if (!newVal.autoRefresh && this.refreshTimer) {
          this.stopAutoRefresh();
        }
        localStorage.setItem('dashboard_settings', JSON.stringify(newVal));
      },
      deep: true
    }
  },
  mounted() {
    this.initData();
    this.startTimeUpdate();
    this.startDataSimulation();
    if (this.settings.autoRefresh) {
      this.startAutoRefresh();
    }
    this.showNotification('监控仪表盘已启动', 'success');
  },
  beforeDestroy() {
    this.stopAutoRefresh();
    this.stopTimeUpdate();
    this.stopDataSimulation();
    if (this.notificationTimer) {
      clearTimeout(this.notificationTimer);
      this.notificationTimer = null;
    }
  },
  methods: {
    // 初始化数据
    initData() {
      this.updateDateTime();
      this.initChartData();
      this.initRequestStats();
      this.initAlerts();
      this.initLogs();
      this.initServices();
      this.loadSettings();
    },
    
    initChartData() {
      const now = Date.now();
      for (let i = 0; i < 60; i++) {
        this.cpuHistory.push({
          time: now - (60 - i) * 60000,
          value: 30 + Math.random() * 40
        });
        this.memoryHistory.push({
          time: now - (60 - i) * 60000,
          value: 40 + Math.random() * 30
        });
      }
    },
    
    initRequestStats() {
      this.requestStats = [];
      for (let i = 0; i < 12; i++) {
        const hour = `${i.toString().padStart(2, '0')}:00`;
        const total = Math.floor(500 + Math.random() * 500);
        this.requestStats.push({
          hour,
          count: total,
          success: Math.floor(total * (0.9 + Math.random() * 0.09)),
          warning: Math.floor(total * (0.05 + Math.random() * 0.03)),
          error: Math.floor(total * (0.02 + Math.random() * 0.02)),
          status: Math.random() > 0.9 ? 'error' : (Math.random() > 0.8 ? 'warning' : 'success')
        });
      }
    },
    
    initAlerts() {
      this.activeAlerts = [
        {
          id: 1,
          title: 'CPU使用率过高',
          description: 'CPU使用率已超过80%阈值，建议扩容',
          severity: 'warning',
          timestamp: Date.now() - 1800000
        },
        {
          id: 2,
          title: 'API响应超时',
          description: '用户服务API响应时间超过3秒',
          severity: 'critical',
          timestamp: Date.now() - 3600000
        }
      ];
    },
    
    initLogs() {
      const levels = ['info', 'warning', 'error'];
      const messages = [
        '用户登录成功', '数据库查询慢', 'API请求失败', '缓存命中', 
        '服务重启', '配置更新', '磁盘空间不足', '网络延迟增加'
      ];
      const sources = ['API Gateway', 'Auth Service', 'Database', 'Cache', 'Worker'];
      
      for (let i = 0; i < 50; i++) {
        const level = levels[Math.floor(Math.random() * levels.length)];
        this.systemLogs.push({
          id: i,
          level,
          message: messages[Math.floor(Math.random() * messages.length)],
          source: sources[Math.floor(Math.random() * sources.length)],
          timestamp: Date.now() - Math.random() * 86400000
        });
      }
      this.systemLogs.sort((a, b) => b.timestamp - a.timestamp);
    },
    
    initServices() {
      this.services = [
        { id: 1, name: 'API Gateway', status: 'healthy', responseTime: 45, availability: 99.9 },
        { id: 2, name: 'Auth Service', status: 'healthy', responseTime: 67, availability: 99.8 },
        { id: 3, name: 'User Service', status: 'warning', responseTime: 234, availability: 95.2 },
        { id: 4, name: 'Payment Service', status: 'healthy', responseTime: 89, availability: 99.5 },
        { id: 5, name: 'Database', status: 'healthy', responseTime: 12, availability: 99.99 },
        { id: 6, name: 'Cache Service', status: 'warning', responseTime: 156, availability: 97.3 }
      ];
    },
    
    loadSettings() {
      const saved = localStorage.getItem('dashboard_settings');
      if (saved) {
        try {
          const loaded = JSON.parse(saved);
          this.settings = { ...this.settings, ...loaded };
        } catch (e) {
          console.error('加载设置失败', e);
        }
      }
    },
    
    // 数据模拟
    startDataSimulation() {
      this.dataGenerator = setInterval(() => {
        this.simulateDataUpdate();
      }, 2000);
    },
    
    stopDataSimulation() {
      if (this.dataGenerator) {
        clearInterval(this.dataGenerator);
      }
    },
    
    simulateDataUpdate() {
      // 更新KPI数据
      this.kpiData[0].value = Math.max(5, Math.min(95, this.kpiData[0].value + (Math.random() - 0.5) * 3));
      this.kpiData[1].value = Math.max(30, Math.min(90, this.kpiData[1].value + (Math.random() - 0.5) * 2));
      this.kpiData[2].value = Math.max(95, Math.min(100, this.kpiData[2].value + (Math.random() - 0.5) * 0.5));
      this.kpiData[3].value = Math.max(50, Math.min(500, this.kpiData[3].value + (Math.random() - 0.5) * 10));
      
      // 更新图表数据
      const newCpuValue = 30 + Math.random() * 50;
      const newMemoryValue = 40 + Math.random() * 40;
      
      this.cpuHistory.push({ time: Date.now(), value: newCpuValue });
      this.memoryHistory.push({ time: Date.now(), value: newMemoryValue });
      
      if (this.cpuHistory.length > 60) this.cpuHistory.shift();
      if (this.memoryHistory.length > 60) this.memoryHistory.shift();
      
      // 检查并生成告警
      if (newCpuValue > 85 && Math.random() > 0.7) {
        this.addAlert('CPU使用率异常', `CPU使用率达到 ${newCpuValue.toFixed(1)}%`, 'critical');
      }
      if (newMemoryValue > 85 && Math.random() > 0.8) {
        this.addAlert('内存使用率过高', `内存使用率达到 ${newMemoryValue.toFixed(1)}%`, 'warning');
      }
      
      // 添加随机日志
      if (Math.random() > 0.7) {
        const levels = ['info', 'warning', 'error'];
        const level = levels[Math.floor(Math.random() * levels.length)];
        this.addLog(level, `系统运行状态更新`, 'Monitor');
      }
    },
    
    // 刷新所有数据（异步操作）
    async refreshAllData() {
      this.isChartLoading = true;
      this.isRefreshingServices = true;
      
      this.showNotification('正在刷新数据...', 'info');
      
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      this.initRequestStats();
      this.initServices();
      
      this.isChartLoading = false;
      this.isRefreshingServices = false;
      this.showNotification('数据刷新完成', 'success');
    },
    
    refreshServices() {
      this.refreshAllData();
    },
    
    // 自动刷新
    startAutoRefresh() {
      this.stopAutoRefresh();
      this.refreshTimer = setInterval(() => {
        this.refreshAllData();
      }, this.settings.refreshInterval * 1000);
    },
    
    stopAutoRefresh() {
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer);
        this.refreshTimer = null;
      }
    },
    
    // 时间更新
    startTimeUpdate() {
      this.timeTimer = setInterval(() => {
        this.updateDateTime();
      }, 1000);
    },
    
    stopTimeUpdate() {
      if (this.timeTimer) {
        clearInterval(this.timeTimer);
      }
    },
    
    updateDateTime() {
      const now = new Date();
      this.currentDate = now.toLocaleDateString('zh-CN');
      this.currentTime = now.toLocaleTimeString('zh-CN');
    },
    
    // 图表操作
    changePeriod(period) {
      this.selectedPeriod = period;
      this.showNotification(`切换到 ${period} 视图`, 'info');
    },
    
    // 告警操作
    addAlert(title, description, severity) {
      const newAlert = {
        id: ++this.alertIdCounter,
        title,
        description,
        severity,
        timestamp: Date.now()
      };
      this.activeAlerts.unshift(newAlert);
      this.showNotification(`新告警: ${title}`, 'warning');
      
      if (this.settings.desktopNotifications && Notification.permission === 'granted') {
        new Notification(title, { body: description });
      }
    },
    
    acknowledgeAlert(alertId) {
      const alert = this.activeAlerts.find(a => a.id === alertId);
      if (alert) {
        alert.acknowledged = true;
        this.showNotification(`已确认告警: ${alert.title}`, 'info');
      }
    },
    
    resolveAlert(alertId) {
      const index = this.activeAlerts.findIndex(a => a.id === alertId);
      if (index !== -1) {
        const resolved = this.activeAlerts.splice(index, 1)[0];
        this.alertHistory.push({ ...resolved, resolvedAt: Date.now() });
        this.showNotification(`已解决告警: ${resolved.title}`, 'success');
      }
    },
    
    clearAlerts() {
      this.activeAlerts = [];
      this.showNotification('已清空所有告警', 'info');
    },
    
    // 日志操作
    addLog(level, message, source) {
      const newLog = {
        id: Date.now(),
        level,
        message,
        source,
        timestamp: Date.now()
      };
      this.systemLogs.unshift(newLog);
      if (this.systemLogs.length > 500) {
        this.systemLogs = this.systemLogs.slice(0, 500);
      }
    },
    
    filterLogs() {
      this.showNotification(`筛选日志: ${this.logFilter}`, 'info');
    },
    
    clearLogs() {
      this.systemLogs = [];
      this.showNotification('日志已清空', 'info');
    },
    
    // 事件处理
    onKPIClick(kpi) {
      this.showNotification(`查看详情: ${kpi.title}`, 'info');
      this.addLog('info', `查看KPI指标: ${kpi.title}`, 'Dashboard');
    },
    
    onBarClick(data) {
      this.showNotification(`查看时段: ${data.hour} 请求量 ${data.count}`, 'info');
    },
    
    onLogClick(log) {
      this.showNotification(`日志详情: ${log.message}`, 'info');
    },
    
    onServiceClick(service) {
      this.showNotification(`服务详情: ${service.name} (${service.status})`, 'info');
    },
    
    // 导出报告
    exportReport() {
      const report = {
        exportTime: new Date().toISOString(),
        kpi: this.kpiData,
        alerts: this.activeAlerts,
        services: this.services,
        summary: {
          totalAlerts: this.activeAlerts.length,
          healthyServices: this.services.filter(s => s.status === 'healthy').length,
          avgCpu: this.kpiData[0].value,
          avgMemory: this.kpiData[1].value
        }
      };
      
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `monitoring_report_${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      this.showNotification('报告导出成功', 'success');
    },
    
    // 设置相关
    saveSettings(settings) {
      this.stopAutoRefresh();
      this.settings = { ...settings };
      if (this.settings.autoRefresh) {
        this.startAutoRefresh();
      }
      this.showSettings = false;
      this.showNotification('设置已保存', 'success');
    },
    
    // UI交互
    toggleTheme() {
      this.isDarkMode = !this.isDarkMode;
      this.showNotification(`已切换到${this.isDarkMode ? '暗色' : '亮色'}模式`, 'info');
    },
    
    showNotification(message, type) {
      if (this.notificationTimer) {
        clearTimeout(this.notificationTimer);
      }
      this.notification = {
        show: true,
        message,
        type
      };
      this.notificationTimer = setTimeout(() => {
        this.hideNotification();
        this.notificationTimer = null;
      }, 3000);
    },
    
    hideNotification() {
      this.notification.show = false;
    },
    
    // 请求桌面通知权限
    requestNotificationPermission() {
      if ('Notification' in window && this.settings.desktopNotifications) {
        Notification.requestPermission();
      }
    }
  }
};
</script>

<style scoped>
/* 主容器 */
.monitoring-dashboard {
  max-width: 1600px;
  margin: 0 auto;
  padding: 20px;
  background: #f1f5f9;
  min-height: 100vh;
  transition: all 0.3s ease;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.monitoring-dashboard.dark-mode {
  background: #0f172a;
  color: #e2e8f0;
}

/* 状态栏 */
.status-bar {
  background: white;
  border-radius: 12px;
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.dark-mode .status-bar {
  background: #1e293b;
}

.system-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.status-indicator.healthy {
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
}

.status-indicator.warning {
  background: #f59e0b;
  box-shadow: 0 0 8px #f59e0b;
}

.status-indicator.critical {
  background: #ef4444;
  box-shadow: 0 0 8px #ef4444;
}

.time-display {
  display: flex;
  gap: 16px;
  font-family: monospace;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.icon-btn {
  padding: 6px 12px;
  background: #f1f5f9;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.dark-mode .icon-btn {
  background: #334155;
  color: #e2e8f0;
}

.icon-btn:hover {
  transform: translateY(-2px);
}

/* KPI网格 */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.kpi-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.dark-mode .kpi-card {
  background: #1e293b;
}

.kpi-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.kpi-card.healthy {
  border-left: 4px solid #10b981;
}

.kpi-card.warning {
  border-left: 4px solid #f59e0b;
}

.kpi-card.critical {
  border-left: 4px solid #ef4444;
}

.kpi-icon {
  font-size: 32px;
}

.kpi-content {
  flex: 1;
}

.kpi-title {
  font-size: 14px;
  color: #64748b;
  margin-bottom: 4px;
}

.kpi-value {
  font-size: 28px;
  font-weight: 700;
}

.kpi-unit {
  font-size: 14px;
  margin-left: 4px;
}

.kpi-trend {
  font-size: 12px;
  margin-top: 4px;
}

.kpi-trend.up {
  color: #10b981;
}

.kpi-trend.down {
  color: #ef4444;
}

/* 图表区域 */
.charts-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

.chart-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.dark-mode .chart-card {
  background: #1e293b;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.chart-header h3 {
  margin: 0;
  font-size: 16px;
}

.chart-controls {
  display: flex;
  gap: 8px;
}

.period-btn {
  padding: 4px 12px;
  background: #f1f5f9;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.dark-mode .period-btn {
  background: #334155;
  color: #e2e8f0;
}

.period-btn.active {
  background: #3b82f6;
  color: white;
}

.chart-wrapper {
  position: relative;
  margin-bottom: 16px;
}

.chart-wrapper.loading {
  opacity: 0.5;
}

/* 请求图表 */
.request-chart {
  margin-top: 16px;
}

.chart-legend {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-top: 16px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}

/* 事件区域 */
.events-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

.alerts-panel, .logs-panel {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.dark-mode .alerts-panel,
.dark-mode .logs-panel {
  background: #1e293b;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
}

.alert-count {
  background: #ef4444;
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}

.clear-btn {
  padding: 4px 8px;
  background: none;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.log-filters {
  display: flex;
  gap: 8px;
}

.log-filters select {
  padding: 4px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
}

/* 告警列表 */
.alert-list {
  max-height: 300px;
  overflow-y: auto;
}

.alert-item {
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 8px;
  display: flex;
  gap: 12px;
  background: #f8fafc;
}

.dark-mode .alert-item {
  background: #334155;
}

.alert-item.critical {
  border-left: 4px solid #ef4444;
}

.alert-item.warning {
  border-left: 4px solid #f59e0b;
}

.alert-item.info {
  border-left: 4px solid #3b82f6;
}

.alert-icon {
  font-size: 20px;
}

.alert-content {
  flex: 1;
}

.alert-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.alert-desc {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}

.alert-time {
  font-size: 10px;
  color: #94a3b8;
}

.alert-actions {
  display: flex;
  gap: 8px;
}

.alert-btn {
  padding: 4px 8px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.alert-btn.resolve {
  background: #10b981;
  color: white;
}

.empty-alerts {
  text-align: center;
  padding: 40px;
  color: #94a3b8;
}

/* 日志列表 */
.log-list {
  max-height: 300px;
  overflow-y: auto;
}

.log-item {
  padding: 8px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  gap: 12px;
  align-items: center;
  cursor: pointer;
  font-size: 12px;
}

.log-item:hover {
  background: #f8fafc;
}

.log-time {
  font-family: monospace;
  color: #64748b;
}

.log-level {
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 10px;
}

.log-level.info {
  background: #dbeafe;
  color: #1e40af;
}

.log-level.warning {
  background: #fef3c7;
  color: #92400e;
}

.log-level.error {
  background: #fee2e2;
  color: #991b1b;
}

.log-message {
  flex: 1;
}

.log-source {
  color: #94a3b8;
  font-size: 10px;
}

/* 服务面板 */
.services-panel {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.dark-mode .services-panel {
  background: #1e293b;
}

.refresh-btn {
  padding: 4px 12px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.service-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.service-card {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.service-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.service-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.service-name {
  font-weight: 600;
}

.service-status {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.service-status.healthy {
  background: #dcfce7;
  color: #166534;
}

.service-status.warning {
  background: #fef3c7;
  color: #92400e;
}

.service-status.down {
  background: #fee2e2;
  color: #991b1b;
}

.service-metrics {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.metric {
  text-align: center;
}

.metric-label {
  font-size: 11px;
  color: #64748b;
  display: block;
  margin-bottom: 4px;
}

.metric-value {
  font-weight: 600;
  font-size: 14px;
}

.service-progress {
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
  height: 6px;
}

.progress-bar {
  height: 100%;
  transition: width 0.3s;
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
  border-radius: 12px;
  width: 400px;
  max-width: 90%;
}

.dark-mode .modal-content {
  background: #1e293b;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e2e8f0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
}

.settings-form {
  padding: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
}

.form-group input[type="number"],
.form-group select {
  width: 100%;
  padding: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.form-group input[type="checkbox"] {
  margin-right: 8px;
}

.form-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 20px;
}

.cancel-btn, .submit-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.cancel-btn {
  background: #f1f5f9;
}

.submit-btn {
  background: #3b82f6;
  color: white;
}

/* 通知 */
.notification {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 12px 20px;
  border-radius: 8px;
  display: flex;
  gap: 12px;
  align-items: center;
  z-index: 2000;
  animation: slideIn 0.3s ease;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
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
}

/* 响应式 */
@media (max-width: 1024px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
  
  .events-grid {
    grid-template-columns: 1fr;
  }
  
  .service-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .status-bar {
    flex-direction: column;
    gap: 12px;
  }
  
  .kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }
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
</style>