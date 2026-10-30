<template>
    <div class="stock-card" @click="refreshPrice">
      <div class="stock-header">
        <div>
          <h3 class="stock-name">{{ name }}</h3>
          <p class="stock-code">{{ code }}</p>
        </div>
        <div class="stock-price">
          <span class="price-value">{{ price }}</span>
          <span class="price-unit">元</span>
        </div>
      </div>
      
      <div class="stock-change" :class="changeClass">
        <span class="change-icon">{{ changeIcon }}</span>
        <span class="change-value">{{ changePercent }}%</span>
      </div>
      
      <div class="stock-footer">
        <span class="update-time">点击刷新实时价格</span>
      </div>
    </div>
  </template>
  
  <script>
  module.exports = {
    name: 'StockCard',
    props: {
      name: {
        type: String,
        required: true
      },
      code: {
        type: String,
        required: true
      },
      initialPrice: {
        type: Number,
        required: true
      }
    },
    data() {
      return {
        price: this.initialPrice,
        lastPrice: this.initialPrice
      };
    },
    computed: {
      changePercent() {
        if (this.lastPrice === 0) return 0;
        const change = ((this.price - this.lastPrice) / this.lastPrice) * 100;
        return change.toFixed(2);
      },
      changeClass() {
        if (this.price > this.lastPrice) return 'positive';
        if (this.price < this.lastPrice) return 'negative';
        return 'neutral';
      },
      changeIcon() {
        if (this.price > this.lastPrice) return '▲';
        if (this.price < this.lastPrice) return '▼';
        return '●';
      }
    },
    methods: {
      refreshPrice() {
        // 保存旧价格
        const oldPrice = this.price;
        
        // 模拟价格波动（-2% 到 +2%）
        const change = (Math.random() - 0.5) * 4;
        const newPrice = this.price * (1 + change / 100);
        
        // 更新价格
        this.lastPrice = this.price;
        this.price = parseFloat(newPrice.toFixed(2));
        
        // 内部处理价格更新后的逻辑（封装在组件内部）
        this.handlePriceUpdate(oldPrice, this.price);
      },
      
      // 内部方法：处理价格更新后的逻辑
      handlePriceUpdate(oldPrice, newPrice) {
        // 可以在这里添加任何需要的内部逻辑，例如：
        console.log(`[${this.code}] 价格更新: ${oldPrice} -> ${newPrice} (涨跌幅: ${this.changePercent}%)`);
        
        // 也可以在这里触发其他内部状态变化、更新UI提示等
        // 例如添加一个临时提示效果（可扩展）
        this.showUpdateTip = true;
        setTimeout(() => { this.showUpdateTip = false; }, 1000);
      }
    }
  };
  </script>
  
  <style scoped>
  .stock-card {
    width: 280px;
    padding: 16px;
    border-radius: 16px;
    background: #ffffff;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }
  
  .stock-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  }
  
  .stock-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
  }
  
  .stock-name {
    margin: 0 0 4px 0;
    font-size: 18px;
    font-weight: 600;
    color: #1f2937;
  }
  
  .stock-code {
    margin: 0;
    font-size: 12px;
    color: #6b7280;
  }
  
  .stock-price {
    text-align: right;
  }
  
  .price-value {
    font-size: 24px;
    font-weight: 700;
    color: #1f2937;
  }
  
  .price-unit {
    font-size: 12px;
    color: #6b7280;
    margin-left: 2px;
  }
  
  .stock-change {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 12px;
    padding: 8px 0;
    border-top: 1px solid #f0f0f0;
    border-bottom: 1px solid #f0f0f0;
  }
  
  .change-icon {
    font-size: 16px;
    font-weight: bold;
  }
  
  .change-value {
    font-size: 18px;
    font-weight: 600;
  }
  
  .positive {
    color: #ef4444;
  }
  
  .negative {
    color: #10b981;
  }
  
  .neutral {
    color: #6b7280;
  }
  
  .stock-footer {
    font-size: 11px;
    color: #9ca3af;
    text-align: center;
  }
  </style>