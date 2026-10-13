<template>
  <div class="weather-card" @click="handleCardClick">
    <div class="weather-header">
      <h3 class="city-name">{{ city }}</h3>
      <p class="date">{{ currentDate }}</p>
    </div>
    
    <div class="weather-main">
       <span class="weather-icon">{{ weatherIcon }}</span>
      <div class="temperature">
        <span class="temp-value">{{ temperature }}</span>
        <span class="temp-unit">°C</span>
      </div>
    </div>
    
    <div class="weather-desc">
      <p>{{ weatherDesc }}</p>
    </div>
    
    <div class="weather-details">
      <div class="detail-item">
        <span class="detail-label">湿度</span>
        <span class="detail-value">{{ humidity }}%</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">风速</span>
        <span class="detail-value">{{ windSpeed }} km/h</span>
      </div>
    </div>
  </div>
</template>

<script>
module.exports = {
  name: 'WeatherCard',
  props: {
    city: {
      type: String,
      required: true
    },
    temperature: {
      type: Number,
      required: true
    },
    weatherDesc: {
      type: String,
      default: '晴'
    },
    humidity: {
      type: Number,
      default: 50
    },
    windSpeed: {
      type: Number,
      default: 5
    }
  },
  data() {
    return {
      currentDate: this.getFormattedDate()
    };
  },
  computed: {
    weatherIcon() {
      // 根据天气描述返回对应图标
      const iconMap = {
        '晴': '☀️',
        '多云': '⛅',
        '阴': '☁️',
        '雨': '🌧️',
        '雪': '❄️'
      };
      return iconMap[this.weatherDesc] || '☀️';
    }
  },
  methods: {
    getFormattedDate() {
      const date = new Date();
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${year}.${month}.${day}`;
    },
    handleCardClick() {
      console.log(`查看 ${this.city} 天气详情`);
      // 预留点击事件，便于后续扩展
    }
  }
};
</script>

<style scoped>
.weather-card {
  width: 280px;
  padding: 20px;
  border-radius: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  margin: 10px;
}

.weather-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(102, 126, 234, 0.3);
}

.weather-header {
  margin-bottom: 20px;
}

.city-name {
  margin: 0 0 5px 0;
  font-size: 24px;
  font-weight: 600;
  line-height: 1.2;
}

.date {
  margin: 0;
  font-size: 14px;
  opacity: 0.8;
}

.weather-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 15px;
}

.weather-icon {
  font-size: 64px;
  line-height: 1;
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.temperature {
  display: flex;
  align-items: baseline;
}

.temp-value {
  font-size: 48px;
  font-weight: 700;
  line-height: 1;
}

.temp-unit {
  font-size: 24px;
  margin-left: 4px;
  opacity: 0.8;
}

.weather-desc {
  margin-bottom: 20px;
  font-size: 18px;
  text-align: center;
  opacity: 0.9;
}

.weather-details {
  display: flex;
  justify-content: space-around;
  padding-top: 15px;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
}

.detail-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.detail-label {
  font-size: 12px;
  opacity: 0.7;
  margin-bottom: 4px;
}

.detail-value {
  font-size: 16px;
  font-weight: 600;
}
</style>