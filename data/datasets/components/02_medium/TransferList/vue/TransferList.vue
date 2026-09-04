<template>
  <section class="transfer-list"><h2>项目角色分配</h2><input class="transfer-search" :value="query" @input="updateQuery" placeholder="筛选可用角色"><div class="transfer-grid"><div class="list-panel"><h3>可用</h3><button v-for="item in filteredAvailable" :key="item.id" :class="item.id === leftId ? 'selected' : ''" @click="selectLeft(item.id)">{{ item.name }}</button></div><div class="transfer-actions"><button @click="moveRight" :disabled="leftId === null">→</button><button @click="moveLeft" :disabled="rightId === null">←</button></div><div class="list-panel"><h3>已选</h3><button v-for="item in chosen" :key="item.id" :class="item.id === rightId ? 'selected' : ''" @click="selectRight(item.id)">{{ item.name }}</button></div></div></section>
</template>

<script>
module.exports = {
  name: 'TransferList',
  props: {
    initialAvailable: { type: Array, default: () => ([
          {
            "id": 1,
            "name": "设计"
          },
          {
            "id": 2,
            "name": "开发"
          },
          {
            "id": 3,
            "name": "测试"
          }
        ]) },
    initialChosen: { type: Array, default: () => ([
          {
            "id": 4,
            "name": "部署"
          }
        ]) }
  },
  data() {
    return {
        available: [],
        chosen: [],
        leftId: null,
        rightId: null,
        query: ""
    };
  },
  computed: {
    filteredAvailable() {
      const q = this.query.toLowerCase(); return this.available.filter(item => item.name.toLowerCase().indexOf(q) >= 0);
    }
  },
  created() {
    this.setValue('available', this.initialAvailable.map(item => Object.assign({}, item))); this.setValue('chosen', this.initialChosen.map(item => Object.assign({}, item)));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateQuery(event) {
      this.setValue('query', event.target.value);
    },
    selectLeft(id) {
      this.setValue('leftId', id);
    },
    selectRight(id) {
      this.setValue('rightId', id);
    },
    moveRight() {
      const id = this.leftId; const item = this.available.find(row => row.id === id); if (!item) return; this.setValue('available', this.available.filter(row => row.id !== id)); this.setValue('chosen', this.chosen.concat(item)); this.setValue('leftId', null); this.notify();
    },
    moveLeft() {
      const id = this.rightId; const item = this.chosen.find(row => row.id === id); if (!item) return; this.setValue('chosen', this.chosen.filter(row => row.id !== id)); this.setValue('available', this.available.concat(item)); this.setValue('rightId', null); this.notify();
    },
    notify() {
      this.emitEvent('change', this.chosen.slice());
    }
  }
};
</script>

<style scoped>

.transfer-list { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.transfer-list * { box-sizing: border-box; }
.transfer-list h2, .transfer-list h3, .transfer-list p { margin-top: 0; }
.transfer-list h2 { margin-bottom: 14px; font-size: 21px; }
.transfer-list button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.transfer-list button.primary { border-color: #2563eb; background: #2563eb; color: #fff; }
.transfer-list button:disabled { opacity: .45; cursor: not-allowed; }
.transfer-list input, .transfer-list select, .transfer-list textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.transfer-list .toolbar, .transfer-list .summary, .transfer-list .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.transfer-list .muted { color: #71808e; font-size: 12px; }
.transfer-list .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
.transfer-search{width:100%;margin-bottom:12px}.transfer-grid{display:grid;grid-template-columns:1fr 44px 1fr;gap:10px}.list-panel{min-height:190px;padding:10px;border:1px solid #d6dde4}.list-panel button{display:block;width:100%;margin:5px 0;text-align:left}.list-panel button.selected{background:#dbeafe;border-color:#2563eb}.transfer-actions{display:grid;align-content:center;gap:8px}

</style>
