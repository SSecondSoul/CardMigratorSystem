<template>
  <div class="expense-tracker" :class="{ 'dark-mode': isDarkMode }">
    <!-- 头部 -->
    <div class="header">
      <h2>💰 记账本</h2>
      <button class="theme-btn" @click="toggleTheme">
        {{ isDarkMode ? '☀️' : '🌙' }}
      </button>
    </div>

    <!-- 收支统计 -->
    <div class="balance-card">
      <div class="balance-item">
        <span class="balance-label">总收入</span>
        <span class="balance-value income">+¥{{ totalIncome }}</span>
      </div>
      <div class="balance-item">
        <span class="balance-label">总支出</span>
        <span class="balance-value expense">-¥{{ totalExpense }}</span>
      </div>
      <div class="balance-item">
        <span class="balance-label">结余</span>
        <span class="balance-value" :class="{ positive: balance >= 0, negative: balance < 0 }">
          ¥{{ balance }}
        </span>
      </div>
    </div>

    <!-- 添加记录表单 -->
    <div class="add-form">
      <select v-model="newType">
        <option value="income">收入</option>
        <option value="expense">支出</option>
      </select>
      <input 
        v-model="newAmount" 
        type="number" 
        placeholder="金额"
        @keyup.enter="addRecord"
      />
      <input 
        v-model="newCategory" 
        type="text" 
        placeholder="分类"
        @keyup.enter="addRecord"
      />
      <button @click="addRecord">添加</button>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <select v-model="filterType">
        <option value="all">全部</option>
        <option value="income">收入</option>
        <option value="expense">支出</option>
      </select>
      <select v-model="filterCategory">
        <option value="all">全部分类</option>
        <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
      </select>
      <button v-if="hasFilter" class="clear-filter" @click="clearFilter">清除</button>
    </div>

    <!-- 分类统计图表 -->
    <div class="chart-section" v-if="expenseByCategory.length > 0">
      <h3>支出分类统计</h3>
      <div class="chart-bars">
        <div 
          v-for="item in expenseByCategory" 
          :key="item.category" 
          class="chart-item"
        >
          <span class="chart-label">{{ item.category }}</span>
          <div class="bar-container">
            <div 
              class="bar" 
              :style="{ width: getBarWidth(item.amount) + '%' }"
            ></div>
            <span class="bar-value">¥{{ item.amount }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 记录列表 -->
    <div class="records-list">
      <div 
        v-for="record in filteredRecords" 
        :key="record.id" 
        class="record-item"
        :class="record.type"
      >
        <div class="record-info">
          <span class="record-category">{{ record.category }}</span>
          <span class="record-date">{{ formatDate(record.date) }}</span>
        </div>
        <div class="record-amount" :class="record.type">
          {{ record.type === 'income' ? '+' : '-' }}¥{{ record.amount }}
        </div>
        <button class="delete-btn" @click="deleteRecord(record.id)">删除</button>
      </div>
      
      <div v-if="filteredRecords.length === 0" class="empty-state">
        暂无记录，添加一笔吧
      </div>
    </div>

    <!-- 底部统计 -->
    <div class="footer" v-if="records.length > 0">
      <span>共 {{ filteredRecords.length }} 条记录</span>
      <button class="clear-all" @click="clearAll">清空全部</button>
    </div>
  </div>
</template>

<script>
module.exports = {
  name: 'ExpenseTracker',
  data() {
    return {
      isDarkMode: false,
      records: [],
      newType: 'expense',
      newAmount: '',
      newCategory: '',
      filterType: 'all',
      filterCategory: 'all'
    };
  },
  computed: {
    // 总收入
    totalIncome() {
      return this.records
        .filter(r => r.type === 'income')
        .reduce((sum, r) => sum + r.amount, 0);
    },
    // 总支出
    totalExpense() {
      return this.records
        .filter(r => r.type === 'expense')
        .reduce((sum, r) => sum + r.amount, 0);
    },
    // 结余
    balance() {
      return this.totalIncome - this.totalExpense;
    },
    // 所有分类
    categories() {
      const cats = [...new Set(this.records.map(r => r.category))];
      return cats.sort();
    },
    // 按分类统计支出
    expenseByCategory() {
      const categoryMap = new Map();
      this.records
        .filter(r => r.type === 'expense')
        .forEach(r => {
          const current = categoryMap.get(r.category) || 0;
          categoryMap.set(r.category, current + r.amount);
        });
      return Array.from(categoryMap.entries())
        .map(([category, amount]) => ({ category, amount }))
        .sort((a, b) => b.amount - a.amount);
    },
    // 最大支出金额（用于图表宽度计算）
    maxExpenseAmount() {
      if (this.expenseByCategory.length === 0) return 0;
      return Math.max(...this.expenseByCategory.map(item => item.amount));
    },
    // 筛选后的记录
    filteredRecords() {
      let result = [...this.records];
      
      if (this.filterType !== 'all') {
        result = result.filter(r => r.type === this.filterType);
      }
      
      if (this.filterCategory !== 'all') {
        result = result.filter(r => r.category === this.filterCategory);
      }
      
      return result.sort((a, b) => b.date - a.date);
    },
    // 是否有筛选条件
    hasFilter() {
      return this.filterType !== 'all' || this.filterCategory !== 'all';
    }
  },
  watch: {
    records: {
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
    // 添加记录
    addRecord() {
      const amount = parseFloat(this.newAmount);
      if (isNaN(amount) || amount <= 0) {
        alert('请输入有效的金额');
        return;
      }
      if (!this.newCategory.trim()) {
        alert('请输入分类');
        return;
      }
      
      this.records.push({
        id: Date.now(),
        type: this.newType,
        amount: amount,
        category: this.newCategory.trim(),
        date: Date.now()
      });
      
      // 清空表单
      this.newAmount = '';
      this.newCategory = '';
    },
    
    // 删除记录
    deleteRecord(id) {
      this.records = this.records.filter(r => r.id !== id);
    },
    
    // 清空全部
    clearAll() {
      if (confirm('确定要清空所有记录吗？')) {
        this.records = [];
      }
    },
    
    // 清除筛选
    clearFilter() {
      this.filterType = 'all';
      this.filterCategory = 'all';
    },
    
    // 获取图表宽度百分比
    getBarWidth(amount) {
      if (this.maxExpenseAmount === 0) return 0;
      return (amount / this.maxExpenseAmount) * 100;
    },
    
    // 格式化日期
    formatDate(timestamp) {
      const date = new Date(timestamp);
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const yesterday = new Date(today - 86400000);
      
      if (timestamp >= today) {
        return `今天 ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
      } else if (timestamp >= yesterday) {
        return '昨天';
      } else {
        return `${date.getMonth() + 1}/${date.getDate()}`;
      }
    },
    
    // 主题切换
    toggleTheme() {
      this.isDarkMode = !this.isDarkMode;
    },
    
    // 本地存储
    saveToLocal() {
      localStorage.setItem('expense_records', JSON.stringify(this.records));
    },
    
    loadFromLocal() {
      const saved = localStorage.getItem('expense_records');
      if (saved) {
        try {
          this.records = this.normalizeRecords(JSON.parse(saved));
        } catch(e) {
          this.records = this.getSampleRecords();
        }
      } else {
        this.records = this.getSampleRecords();
      }
    },
    
    normalizeRecords(records) {
      if (!Array.isArray(records)) {
        return this.getSampleRecords();
      }

      return records
        .map((record, index) => {
          if (!record || typeof record !== 'object') {
            return null;
          }

          const type = record.type === 'income' ? 'income' : (record.type === 'expense' ? 'expense' : null);
          const amount = Number(record.amount);
          const category = typeof record.category === 'string' ? record.category.trim() : '';
          const date = Number(record.date);
          const id = record.id != null ? record.id : Date.now() + index;

          if (!type || !Number.isFinite(amount) || amount <= 0 || !category || !Number.isFinite(date)) {
            return null;
          }

          return {
            id,
            type,
            amount,
            category,
            date
          };
        })
        .filter(Boolean);
    },
    
    getSampleRecords() {
      const now = Date.now();
      return [
        { id: 1, type: 'income', amount: 5000, category: '工资', date: now - 2 * 86400000 },
        { id: 2, type: 'expense', amount: 68, category: '餐饮', date: now - 1 * 86400000 },
        { id: 3, type: 'expense', amount: 120, category: '交通', date: now - 1 * 86400000 },
        { id: 4, type: 'expense', amount: 299, category: '购物', date: now },
        { id: 5, type: 'income', amount: 200, category: '红包', date: now }
      ];
    }
  }
};
</script>

<style scoped>
.expense-tracker {
  max-width: 550px;
  margin: 40px auto;
  padding: 24px;
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  transition: all 0.3s;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.expense-tracker.dark-mode {
  background: #1e293b;
  color: #e2e8f0;
}

/* 头部 */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header h2 {
  margin: 0;
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

/* 余额卡片 */
.balance-card {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 16px;
}

.dark-mode .balance-card {
  background: #0f172a;
}

.balance-item {
  flex: 1;
  text-align: center;
}

.balance-label {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.balance-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
}

.balance-value.income {
  color: #10b981;
}

.balance-value.expense {
  color: #ef4444;
}

.balance-value.positive {
  color: #10b981;
}

.balance-value.negative {
  color: #ef4444;
}

/* 添加表单 */
.add-form {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.add-form select,
.add-form input {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  font-size: 14px;
  background: white;
}

.dark-mode .add-form select,
.dark-mode .add-form input {
  background: #0f172a;
  border-color: #334155;
  color: #e2e8f0;
}

.add-form select {
  width: 80px;
}

.add-form input:first-of-type {
  width: 100px;
}

.add-form input:last-of-type {
  width: 120px;
}

.add-form button {
  padding: 10px 20px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.filter-bar select {
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: white;
  cursor: pointer;
}

.dark-mode .filter-bar select {
  background: #0f172a;
  border-color: #334155;
  color: #e2e8f0;
}

.clear-filter {
  padding: 8px 16px;
  background: #f1f5f9;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 12px;
}

/* 图表区域 */
.chart-section {
  margin-bottom: 24px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 16px;
}

.dark-mode .chart-section {
  background: #0f172a;
}

.chart-section h3 {
  margin: 0 0 16px 0;
  font-size: 14px;
}

.chart-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chart-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
}

.chart-label {
  width: 50px;
  font-weight: 500;
}

.bar-container {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.bar {
  height: 8px;
  background: #3b82f6;
  border-radius: 4px;
  transition: width 0.3s;
}

.bar-value {
  font-size: 12px;
  color: #64748b;
  min-width: 45px;
}

/* 记录列表 */
.records-list {
  margin-bottom: 16px;
  max-height: 350px;
  overflow-y: auto;
}

.record-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  margin-bottom: 8px;
  background: #f8fafc;
  border-radius: 12px;
  transition: all 0.2s;
}

.dark-mode .record-item {
  background: #0f172a;
}

.record-item.income {
  border-left: 4px solid #10b981;
}

.record-item.expense {
  border-left: 4px solid #ef4444;
}

.record-info {
  flex: 1;
}

.record-category {
  display: block;
  font-weight: 500;
  font-size: 14px;
  margin-bottom: 4px;
}

.record-date {
  font-size: 11px;
  color: #94a3b8;
}

.record-amount {
  font-weight: 700;
  font-size: 16px;
}

.record-amount.income {
  color: #10b981;
}

.record-amount.expense {
  color: #ef4444;
}

.delete-btn {
  padding: 4px 12px;
  background: #fee2e2;
  color: #ef4444;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  margin-left: 12px;
}

.dark-mode .delete-btn {
  background: #450a0a;
}

.empty-state {
  text-align: center;
  padding: 40px;
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

.clear-all {
  padding: 6px 12px;
  background: #f1f5f9;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
}

.dark-mode .clear-all {
  background: #334155;
  color: #e2e8f0;
}

/* 响应式 */
@media (max-width: 500px) {
  .expense-tracker {
    margin: 20px;
    padding: 16px;
  }
  
  .balance-card {
    flex-direction: column;
    gap: 12px;
  }
  
  .add-form {
    flex-direction: column;
  }
  
  .add-form select,
  .add-form input,
  .add-form button {
    width: 100%;
  }
}
</style>