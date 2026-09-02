<template>
  <section class="comparison-table">
    <header>
      <div><span class="eyebrow">方案对比</span><h2>{{ title }}</h2></div>
      <button type="button" @click="toggleDifferences">{{ showOnlyDifferences ? '显示全部' : '仅看差异' }}</button>
    </header>
    <div class="product-picker">
      <label v-for="product in products" :key="product.id">
        <input type="checkbox" :checked="selectedIds.indexOf(product.id) >= 0" @change="toggleProduct(product.id, $event)" />
        {{ product.name }}
      </label>
    </div>
    <p class="best-price">当前最低价：{{ bestPrice }} 元</p>
    <table>
      <thead><tr><th>指标</th><th v-for="product in selectedProducts" :key="product.id">{{ product.name }}</th></tr></thead>
      <tbody>
        <tr v-for="row in comparisonRows" :key="row.key">
          <th>{{ row.label }}</th>
          <td v-for="cell in row.cells" :key="cell.id">{{ cell.value }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="!selectedProducts.length" class="empty-state">至少选择一个方案</p>
  </section>
</template>

<script>
module.exports = {
  name: 'ComparisonTable',
  props: {
    title: { type: String, default: '云存储套餐' },
    products: {
      type: Array,
      default: function () {
        return [
          { id: 'basic', name: '基础版', price: 29, features: { storage: '100 GB', support: '工单', region: '单区域' } },
          { id: 'team', name: '团队版', price: 69, features: { storage: '500 GB', support: '在线', region: '双区域' } },
          { id: 'pro', name: '专业版', price: 129, features: { storage: '2 TB', support: '专属', region: '多区域' } }
        ];
      }
    }
  },
  data() {
    return { selectedIds: this.products.map((product) => product.id), showOnlyDifferences: false };
  },
  computed: {
    selectedProducts() { return this.products.filter((product) => this.selectedIds.indexOf(product.id) >= 0); },
    comparisonRows() {
      const definitions = [
        { key: 'price', label: '月费', read: (product) => `${product.price} 元` },
        { key: 'storage', label: '容量', read: (product) => product.features.storage },
        { key: 'support', label: '支持', read: (product) => product.features.support },
        { key: 'region', label: '部署', read: (product) => product.features.region }
      ];
      return definitions.map((row) => {
        const cells = this.selectedProducts.map((product) => ({ id: product.id, value: row.read(product) }));
        return { key: row.key, label: row.label, cells: cells, differs: new Set(cells.map((cell) => cell.value)).size > 1 };
      }).filter((row) => !this.showOnlyDifferences || row.differs);
    },
    bestPrice() {
      return this.selectedProducts.length ? Math.min.apply(null, this.selectedProducts.map((product) => product.price)) : '--';
    }
  },
  methods: {
    toggleProduct(id, event) {
      this.selectedIds = event.target.checked
        ? this.selectedIds.concat(id)
        : this.selectedIds.filter((item) => item !== id);
    },
    toggleDifferences() { this.showOnlyDifferences = !this.showOnlyDifferences; }
  }
};
</script>

<style scoped>
.comparison-table { width: 620px; padding: 22px; border: 1px solid #d1d5db; border-radius: 6px; background: #ffffff; color: #1f2937; font-family: Arial, sans-serif; }
.comparison-table header { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
.comparison-table h2 { margin: 3px 0 0; font-size: 21px; }
.eyebrow { color: #6b7280; font-size: 12px; }
.comparison-table button { padding: 8px 11px; border: 1px solid #6b7280; border-radius: 4px; background: #ffffff; cursor: pointer; }
.product-picker { display: flex; gap: 14px; margin: 18px 0 10px; }
.product-picker label { display: flex; gap: 6px; font-size: 13px; }
.best-price { color: #166534; font-weight: 700; }
.comparison-table table { width: 100%; border-collapse: collapse; }
.comparison-table th, .comparison-table td { padding: 10px; border: 1px solid #e5e7eb; text-align: left; }
.comparison-table thead { background: #f3f4f6; }
.empty-state { padding: 18px; text-align: center; color: #9ca3af; }
</style>
