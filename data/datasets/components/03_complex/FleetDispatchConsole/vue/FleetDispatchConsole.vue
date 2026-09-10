<template>
  <section class="fleet-dispatch-console"><header><div><small>待配送 {{ pendingUnits }} 件</small><h2>{{ depotName }}</h2></div><select :value="zone" @change="setZone"><option v-for="item in zones" :key="item" :value="item">{{ item }}</option></select></header><div class="dispatch-grid"><aside><h3>车辆</h3><button v-for="vehicle in vehicles" :key="vehicle.id" :class="(selectedVehicleId === vehicle.id ? 'selected ' : '') + vehicle.status" @click="chooseVehicle(vehicle.id)"><strong>{{ vehicle.id }} · {{ vehicle.driver }}</strong><span>容量 {{ vehicle.capacity }} · {{ vehicle.status }}</span><i>{{ vehicle.status === 'idle' ? '可派单' : '运输中' }}</i></button></aside><main><h3>订单池</h3><article v-for="order in visibleOrders" :key="order.id" :class="isSelected(order.id, selectedOrderIds) ? 'selected' : ''" @click="toggleOrder(order.id)"><b>P{{ order.priority }}</b><strong>{{ order.id }}</strong><span>{{ order.zone }}</span><em>{{ order.units }} 件</em></article><p v-if="!visibleOrders.length">当前区域无待分配订单</p></main><aside class="summary"><h3>派单摘要</h3><p>车辆：{{ selectedVehicle ? selectedVehicle.id : '未选择' }}</p><p>订单：{{ selectedOrderIds.length }}/{{ maxBatch }}</p><p>载荷：{{ selectedUnits }} / {{ selectedVehicle ? selectedVehicle.capacity : 0 }}</p><button class="primary" @click="confirmDispatch" :disabled="!canDispatch">确认派单</button><small>{{ alert }}</small></aside></div><section class="routes"><article v-for="route in dispatches" :key="route.id"><span>{{ route.vehicleId }} → {{ routeOrders(route) }}</span><strong>{{ route.units }} 件</strong><button @click="returnVehicle(route.vehicleId)">完成返仓</button></article></section></section>
</template>

<script>
module.exports = {
  name: 'FleetDispatchConsole',
  props: {
    depotName: { type: String, default: "城北配送中心" },
    initialVehicles: { type: Array, default: () => ([
          {
            "id": "V1",
            "driver": "李航",
            "capacity": 12,
            "status": "idle"
          },
          {
            "id": "V2",
            "driver": "周敏",
            "capacity": 8,
            "status": "idle"
          },
          {
            "id": "V3",
            "driver": "何青",
            "capacity": 16,
            "status": "route"
          }
        ]) },
    initialOrders: { type: Array, default: () => ([
          {
            "id": "O101",
            "zone": "东区",
            "units": 4,
            "priority": 2
          },
          {
            "id": "O102",
            "zone": "西区",
            "units": 7,
            "priority": 1
          },
          {
            "id": "O103",
            "zone": "东区",
            "units": 5,
            "priority": 3
          },
          {
            "id": "O104",
            "zone": "南区",
            "units": 3,
            "priority": 2
          }
        ]) },
    zones: { type: Array, default: () => ([
          "全部",
          "东区",
          "西区",
          "南区"
        ]) },
    maxBatch: { type: Number, default: 3 }
  },
  data() {
    return {
        vehicles: [],
        orders: [],
        selectedVehicleId: null,
        selectedOrderIds: [],
        zone: "全部",
        dispatches: [],
        alert: ""
    };
  },
  computed: {
    visibleOrders() {
      return this.orders.filter(order => order.status === 'pending' && (this.zone === '全部' || order.zone === this.zone)).sort((a, b) => a.priority - b.priority);
    },
    selectedVehicle() {
      return this.vehicles.find(item => item.id === this.selectedVehicleId) || null;
    },
    selectedUnits() {
      return this.orders.filter(item => this.selectedOrderIds.indexOf(item.id) >= 0).reduce((sum, item) => sum + item.units, 0);
    },
    canDispatch() {
      return !!this.selectedVehicle && this.selectedVehicle.status === 'idle' && this.selectedOrderIds.length > 0 && this.selectedOrderIds.length <= this.maxBatch && this.selectedUnits <= this.selectedVehicle.capacity;
    },
    pendingUnits() {
      return this.orders.filter(item => item.status === 'pending').reduce((sum, item) => sum + item.units, 0);
    }
  },
  created() {
    this.setValue('vehicles', this.initialVehicles.map(item => Object.assign({}, item))); this.setValue('orders', this.initialOrders.map(item => Object.assign({}, item, { status: 'pending' })));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    setZone(event) {
      this.setValue('zone', event.target.value); this.setValue('selectedOrderIds', []);
    },
    chooseVehicle(id) {
      this.setValue('selectedVehicleId', id); this.setValue('alert', '');
    },
    toggleOrder(id) {
      const list = this.selectedOrderIds; this.setValue('selectedOrderIds', list.indexOf(id) >= 0 ? list.filter(item => item !== id) : list.concat(id));
    },
    confirmDispatch() {
      if (!this.canDispatch) { this.setValue('alert', '请选择空闲车辆，并检查容量与批量上限'); return; } const ids = this.selectedOrderIds.slice(); const vehicleId = this.selectedVehicleId; this.setValue('orders', this.orders.map(order => ids.indexOf(order.id) >= 0 ? Object.assign({}, order, { status: 'assigned', vehicleId }) : order)); this.setValue('vehicles', this.vehicles.map(vehicle => vehicle.id === vehicleId ? Object.assign({}, vehicle, { status: 'route' }) : vehicle)); this.setValue('dispatches', [{ id: Date.now(), vehicleId, orderIds: ids, units: this.selectedUnits }].concat(this.dispatches)); this.setValue('selectedOrderIds', []); this.setValue('selectedVehicleId', null); this.emitEvent('dispatch', { vehicleId, orderIds: ids });
    },
    returnVehicle(id) {
      this.setValue('vehicles', this.vehicles.map(vehicle => vehicle.id === id ? Object.assign({}, vehicle, { status: 'idle' }) : vehicle)); this.setValue('orders', this.orders.map(order => order.vehicleId === id ? Object.assign({}, order, { status: 'delivered' }) : order)); this.emitEvent('return', id);
    },
    isSelected(id, selectedOrderIds) {
      return selectedOrderIds.indexOf(id) >= 0;
    },
    routeOrders(route) {
      return route.orderIds.join('、');
    }
  }
};
</script>

<style scoped>

.fleet-dispatch-console{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.fleet-dispatch-console *{box-sizing:border-box}
.fleet-dispatch-console h2,.fleet-dispatch-console h3,.fleet-dispatch-console p{margin-top:0}
.fleet-dispatch-console button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.fleet-dispatch-console button.primary{border-color:#0369a1;background:#0369a1;color:#fff}
.fleet-dispatch-console button:disabled{opacity:.45;cursor:not-allowed}
.fleet-dispatch-console input,.fleet-dispatch-console select,.fleet-dispatch-console textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.fleet-dispatch-console .muted{color:#71808e;font-size:12px}
.fleet-dispatch-console .toolbar,.fleet-dispatch-console .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.dispatch-grid{display:grid;grid-template-columns:200px 1fr 210px;gap:12px}.dispatch-grid>aside{padding:10px;background:#f8fafc}.dispatch-grid>aside>button{display:grid;width:100%;text-align:left;margin:7px 0}.dispatch-grid>aside>button.selected{border-color:#0284c7;background:#e0f2fe}.dispatch-grid>aside>button.route{opacity:.6}.dispatch-grid main article{display:grid;grid-template-columns:40px 1fr 70px 60px;gap:8px;padding:10px;border-bottom:1px solid #e2e8f0}.dispatch-grid main article.selected{background:#dbeafe}.dispatch-grid .summary p{display:flex;justify-content:space-between}.routes article{display:flex;gap:12px;align-items:center;padding:8px;margin-top:6px;background:#ecfeff}.routes article button{margin-left:auto}
</style>
