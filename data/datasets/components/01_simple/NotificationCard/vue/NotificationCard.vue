<template>
  <div class="notification-card" @click="markAsRead">
    <div class="card-icon" :class="{ unread: !isRead }">
      {{ icon }}
    </div>
    <div class="card-content">
      <div class="card-title">{{ title }}</div>
      <div class="card-message">{{ message }}</div>
      <div class="card-time">{{ formatTime }}</div>
    </div>
    <div v-if="!isRead" class="unread-dot"></div>
  </div>
</template>

<script>
module.exports = {
  name: 'NotificationCard',
  props: {
    title: {
      type: String,
      required: true
    },
    message: {
      type: String,
      required: true
    },
    time: {
      type: Number,
      default: () => Date.now()
    },
    icon: {
      type: String,
      default: '🔔'
    }
  },
  data() {
    return {
      isRead: false
    };
  },
  computed: {
    formatTime() {
      const date = new Date(this.time);
      const now = new Date();
      const diff = now - date;
      
      if (diff < 60000) return '刚刚';
      if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
      if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
      return `${Math.floor(diff / 86400000)}天前`;
    }
  },
  methods: {
    markAsRead() {
      if (!this.isRead) {
        this.isRead = true;
        this.$emit('read', this.title);
      }
    }
  }
};
</script>

<style scoped>
.notification-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  max-width: 360px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.notification-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.card-icon {
  font-size: 28px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
  border-radius: 50%;
  transition: all 0.2s;
}

.card-icon.unread {
  background: #3b82f6;
  color: white;
}

.card-content {
  flex: 1;
}

.card-title {
  font-weight: 600;
  font-size: 16px;
  color: #1e293b;
  margin-bottom: 4px;
}

.card-message {
  font-size: 14px;
  color: #64748b;
  margin-bottom: 6px;
  line-height: 1.4;
}

.card-time {
  font-size: 11px;
  color: #94a3b8;
}

.unread-dot {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 8px;
  height: 8px;
  background: #ef4444;
  border-radius: 50%;
}
</style>