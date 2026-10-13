<template>
  <section class="procurement-bid-matrix"><header><div><small>权重合计 {{ weightTotal }}% · {{ reviewer }}</small><h2>{{ projectName }}</h2></div><div><select :value="reviewer" @change="setReviewer"><option v-for="person in reviewers" :key="person" :value="person">{{ person }}</option></select><button @click="toggleLock">{{ isLocked ? '解锁本评委' : '锁定本评委' }}</button></div></header><div class="matrix-wrap"><table><thead><tr><th>供应商</th><th>报价/万元</th><th v-for="criterion in criteria" :key="criterion.id"><span>{{ criterion.name }}</span><input type="number" :value="weights[criterion.id]" @input="updateWeight(criterion.id, $event)" :disabled="isLocked"></th><th>总分</th><th>排名</th></tr></thead><tbody><tr v-for="supplier in suppliers" :key="supplier.id" :class="selectedSupplierId === supplier.id ? 'selected' : ''"><th>{{ supplier.name }}</th><td>{{ supplier.price }}</td><td v-for="criterion in criteria" :key="criterion.id"><input type="number" :value="scores[supplier.id][criterion.id]" @input="updateScore(supplier.id, criterion.id, $event)" :disabled="isLocked"></td><td><strong>{{ supplierTotal(supplier.id) }}</strong></td><td>#{{ rankOf(supplier.id) }}</td></tr></tbody></table></div><div class="ranking"><article v-for="supplier, index in rankings" :key="supplier.id" :class="awardedSupplierId === supplier.id ? 'winner' : ''"><b>#{{ index + 1 }}</b><strong>{{ supplier.name }}</strong><span>{{ supplier.total }} 分</span><textarea :value="comments[supplier.id] || ''" @input="updateComment(supplier.id, $event)" placeholder="评审意见"></textarea><button @click="award(supplier.id)" :disabled="!canAward(supplier)">选定供应商</button></article></div><footer v-if="winner">已选定：{{ winner.name }}，综合得分 {{ winner.total }}</footer></section>
</template>

<script>
module.exports = {
  name: 'ProcurementBidMatrix',
  props: {
    projectName: { type: String, default: "园区安防采购评审" },
    suppliers: { type: Array, default: () => ([
          {
            "id": "S1",
            "name": "远见科技",
            "price": 86
          },
          {
            "id": "S2",
            "name": "安域系统",
            "price": 92
          },
          {
            "id": "S3",
            "name": "云盾智能",
            "price": 79
          }
        ]) },
    criteria: { type: Array, default: () => ([
          {
            "id": "tech",
            "name": "技术",
            "weight": 40
          },
          {
            "id": "service",
            "name": "服务",
            "weight": 25
          },
          {
            "id": "delivery",
            "name": "交付",
            "weight": 15
          },
          {
            "id": "price",
            "name": "价格",
            "weight": 20
          }
        ]) },
    reviewers: { type: Array, default: () => ([
          "评委甲",
          "评委乙",
          "评委丙"
        ]) },
    passingScore: { type: Number, default: 70 }
  },
  data() {
    return {
        weights: {},
        scores: {},
        reviewer: "评委甲",
        lockedReviewers: [],
        selectedSupplierId: null,
        comments: {},
        awardedSupplierId: null
    };
  },
  computed: {
    weightTotal() {
      const weights = this.weights || {}; return this.criteria.reduce((sum, item) => sum + Number(weights[item.id] || 0), 0);
    },
    rankings() {
      const scores = this.scores || {}; const weights = this.weights || {}; return this.suppliers.map(supplier => { const row = scores[supplier.id] || {}; const weighted = this.criteria.reduce((sum, criterion) => sum + Number(row[criterion.id] || 0) * Number(weights[criterion.id] || 0), 0) / (this.weightTotal || 1); return Object.assign({}, supplier, { total: weighted.toFixed(1) }); }).sort((a, b) => Number(b.total) - Number(a.total));
    },
    winner() {
      return this.rankings.find(item => item.id === this.awardedSupplierId) || null;
    },
    isLocked() {
      return this.lockedReviewers.indexOf(this.reviewer) >= 0;
    }
  },
  created() {
    const weights = {}; this.criteria.forEach(item => { weights[item.id] = item.weight; }); const scores = {}; this.suppliers.forEach((supplier, sIndex) => { scores[supplier.id] = {}; this.criteria.forEach((criterion, cIndex) => { scores[supplier.id][criterion.id] = 72 + (sIndex * 7 + cIndex * 5) % 24; }); }); this.setValue('weights', weights); this.setValue('scores', scores);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    setReviewer(event) {
      this.setValue('reviewer', event.target.value);
    },
    updateWeight(id, event) {
      if (this.isLocked) return; this.setValue('weights', Object.assign({}, this.weights, { [id]: Number(event.target.value) || 0 })); this.emitEvent('score', { weights: this.weights, scores: this.scores });
    },
    updateScore(supplierId, criterionId, event) {
      if (this.isLocked) return; const row = Object.assign({}, this.scores[supplierId], { [criterionId]: Math.max(0, Math.min(100, Number(event.target.value) || 0)) }); this.setValue('scores', Object.assign({}, this.scores, { [supplierId]: row })); this.setValue('selectedSupplierId', supplierId);
    },
    toggleLock() {
      const list = this.lockedReviewers; this.setValue('lockedReviewers', list.indexOf(this.reviewer) >= 0 ? list.filter(item => item !== this.reviewer) : list.concat(this.reviewer)); this.emitEvent('lock', { reviewer: this.reviewer, locked: !this.isLocked });
    },
    updateComment(supplierId, event) {
      this.setValue('comments', Object.assign({}, this.comments, { [supplierId]: event.target.value }));
    },
    award(supplierId) {
      const supplier = this.rankings.find(item => item.id === supplierId); if (!supplier || Number(supplier.total) < this.passingScore || this.weightTotal !== 100) return; this.setValue('awardedSupplierId', supplierId); this.emitEvent('award', supplier);
    },
    rankOf(id) {
      return this.rankings.findIndex(item => item.id === id) + 1;
    },
    supplierTotal(id) {
      const supplier = this.rankings.find(item => item.id === id); return supplier ? supplier.total : '0.0';
    },
    canAward(supplier) {
      return Number(this.supplierTotal(supplier.id)) >= this.passingScore && this.weightTotal === 100;
    }
  }
};
</script>

<style scoped>

.procurement-bid-matrix{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.procurement-bid-matrix *{box-sizing:border-box}
.procurement-bid-matrix h2,.procurement-bid-matrix h3,.procurement-bid-matrix p{margin-top:0}
.procurement-bid-matrix button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.procurement-bid-matrix button.primary{border-color:#0f766e;background:#0f766e;color:#fff}
.procurement-bid-matrix button:disabled{opacity:.45;cursor:not-allowed}
.procurement-bid-matrix input,.procurement-bid-matrix select,.procurement-bid-matrix textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.procurement-bid-matrix .muted{color:#71808e;font-size:12px}
.procurement-bid-matrix .toolbar,.procurement-bid-matrix .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.matrix-wrap{overflow:auto;margin:12px 0}table{width:100%;border-collapse:collapse}th,td{padding:8px;border:1px solid #cbd5e1;text-align:center}thead th input,tbody td input{width:60px}tbody tr.selected{background:#f0fdfa}.ranking{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.ranking article{display:grid;grid-template-columns:35px 1fr auto;gap:7px;align-items:center;padding:10px;background:#f8fafc}.ranking textarea{grid-column:1/-1}.ranking button{grid-column:1/-1}.ranking article.winner{background:#dcfce7;box-shadow:0 0 0 2px #16a34a}footer{margin-top:10px;padding:12px;background:#dcfce7;color:#166534}
</style>
