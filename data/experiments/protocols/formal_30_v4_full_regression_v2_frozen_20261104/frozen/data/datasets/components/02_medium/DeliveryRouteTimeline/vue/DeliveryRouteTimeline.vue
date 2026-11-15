<template>
  <section class="delivery-route-timeline"><header><h2>{{ routeName }}</h2><span>完成 {{ completedCount }}/{{ stops.length }}</span></header><div class="route-layout"><ol><li v-for="stop in stops" :key="stop.id" :class="stop.status" @click="select(stop.id)"><i></i><div><strong>{{ stop.name }}</strong><span>预计 +{{ stop.eta }} 分钟</span></div></li></ol><aside v-if="selectedStop"><h3>{{ selectedStop.name }}</h3><label>增加延误<input type="number" :value="delay" @input="updateDelay"></label><button @click="applyDelay">应用延误</button><button class="primary" @click="advance">到达并前往下一站</button></aside></div></section>
</template>

<script>
module.exports = {
  name: 'DeliveryRouteTimeline',
  props: {
    routeName: { type: String, default: "城西配送线" },
    initialStops: { type: Array, default: () => ([
          {
            "id": 1,
            "name": "分拨中心",
            "eta": 0,
            "status": "done"
          },
          {
            "id": 2,
            "name": "大学城",
            "eta": 25,
            "status": "active"
          },
          {
            "id": 3,
            "name": "科技园",
            "eta": 55,
            "status": "waiting"
          }
        ]) }
  },
  data() {
    return {
        stops: [],
        selectedId: 2,
        delay: 0
    };
  },
  computed: {
    completedCount() {
      return this.stops.filter(item => item.status === 'done').length;
    },
    selectedStop() {
      return this.stops.find(item => item.id === this.selectedId) || null;
    }
  },
  created() {
    this.setValue('stops', this.initialStops.map(item => Object.assign({}, item)));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    select(id) {
      this.setValue('selectedId', id);
    },
    advance() {
      const index = this.stops.findIndex(item => item.status === 'active'); if (index < 0) return; const next = this.stops.map((item, i) => Object.assign({}, item, { status: i === index ? 'done' : i === index + 1 ? 'active' : item.status })); this.setValue('stops', next); this.emitEvent('status', next);
    },
    updateDelay(event) {
      this.setValue('delay', Number(event.target.value) || 0);
    },
    applyDelay() {
      const selected = this.selectedStop; if (!selected || !this.delay) return; this.setValue('stops', this.stops.map(item => item.eta >= selected.eta ? Object.assign({}, item, { eta: item.eta + this.delay }) : item)); this.setValue('delay', 0);
    }
  }
};
</script>

<style scoped>

.delivery-route-timeline{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.delivery-route-timeline *{box-sizing:border-box}
.delivery-route-timeline h2,.delivery-route-timeline h3,.delivery-route-timeline p{margin-top:0}
.delivery-route-timeline button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.delivery-route-timeline button.primary{border-color:#0284c7;background:#0284c7;color:#fff}
.delivery-route-timeline button:disabled{opacity:.45;cursor:not-allowed}
.delivery-route-timeline input,.delivery-route-timeline select,.delivery-route-timeline textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.delivery-route-timeline .muted{color:#71808e;font-size:12px}
.delivery-route-timeline .toolbar,.delivery-route-timeline .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.route-layout{display:grid;grid-template-columns:1fr 220px;gap:16px}ol{padding:0;list-style:none}li{display:flex;gap:10px;padding:11px;border-left:4px solid #cbd5e1}li i{width:13px;height:13px;border-radius:50%;background:#cbd5e1}li.done{border-color:#16a34a}li.active{border-color:#0284c7;background:#f0f9ff}li span{display:block}aside{display:grid;gap:9px;padding:12px;background:#f8fafc}aside label{display:grid}
</style>
