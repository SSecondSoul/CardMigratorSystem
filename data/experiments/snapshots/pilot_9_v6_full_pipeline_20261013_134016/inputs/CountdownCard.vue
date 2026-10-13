<template>
  <div class="countdown-card">
    <div class="card-header">
      <span class="emoji">⏰</span>
      <h3>{{ title }}</h3>
    </div>
    
    <div class="time-display">
      <div class="time-unit">
        <span class="number">{{ days }}</span>
        <span class="label">天</span>
      </div>
      <div class="time-unit">
        <span class="number">{{ hours }}</span>
        <span class="label">时</span>
      </div>
      <div class="time-unit">
        <span class="number">{{ minutes }}</span>
        <span class="label">分</span>
      </div>
      <div class="time-unit">
        <span class="number">{{ seconds }}</span>
        <span class="label">秒</span>
      </div>
    </div>
    
    <div class="card-footer">
      <button class="reset-btn" @click="resetTarget">重置</button>
    </div>
  </div>
</template>

<script>
module.exports = {
  name: 'CountdownCard',
  props: {
    title: {
      type: String,
      default: '倒计时'
    },
    targetDate: {
      type: String,
      default: () => {
        return new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
      }
    }
  },
  data() {
    return {
      currentTime: Date.now(),
      timer: null,
      internalTargetDate: this.targetDate
    };
  },
  computed: {
    targetTime() {
      return new Date(this.internalTargetDate).getTime();
    },
    remainingTime() {
      const diff = this.targetTime - this.currentTime;
      return Math.max(0, diff);
    },
    days() {
      return Math.floor(this.remainingTime / (1000 * 60 * 60 * 24));
    },
    hours() {
      return Math.floor((this.remainingTime % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    },
    minutes() {
      return Math.floor((this.remainingTime % (1000 * 60 * 60)) / (1000 * 60));
    },
    seconds() {
      return Math.floor((this.remainingTime % (1000 * 60)) / 1000);
    }
  },
  watch: {
    targetDate(newValue) {
      this.internalTargetDate = newValue;
    }
  },
  mounted() {
    this.startTimer();
  },
  beforeDestroy() {
    this.stopTimer();
  },
  methods: {
    startTimer() {
      this.timer = setInterval(() => {
        this.currentTime = Date.now();
      }, 1000);
    },
    stopTimer() {
      if (this.timer) {
        clearInterval(this.timer);
        this.timer = null;
      }
    },
    resetTarget() {
      const newTarget = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
      this.internalTargetDate = newTarget;
      this.currentTime = Date.now();
      this.$emit('reset', newTarget);
      console.log('倒计时已重置');
    }
  }
};
</script>

<style scoped>
.countdown-card {
  width: 320px;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 20px;
  color: white;
  text-align: center;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 20px;
}

.card-header .emoji {
  font-size: 28px;
}

.card-header h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.time-display {
  display: flex;
  justify-content: space-around;
  margin-bottom: 24px;
}

.time-unit {
  text-align: center;
}

.time-unit .number {
  display: block;
  font-size: 32px;
  font-weight: 700;
  line-height: 1.2;
}

.time-unit .label {
  font-size: 12px;
  opacity: 0.8;
}

.card-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  padding-top: 16px;
}

.reset-btn {
  padding: 8px 20px;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 30px;
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.reset-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-2px);
}
</style>