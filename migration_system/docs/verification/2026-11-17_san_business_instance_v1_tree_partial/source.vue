<template>
  <section class="product-filter-panel"><header><h2>商品筛选</h2><strong>{{ resultCount }} 项</strong></header><div class="filters"><input :value="query" @input="updateQuery" placeholder="搜索商品"><select :value="category" @change="updateCategory"><option value="all">全部分类</option><option v-for="item in categories" :key="item" :value="item">{{ item }}</option></select><label>最高 ¥{{ maxPrice }}<input type="range" min="100" max="1000" step="50" :value="maxPrice" @input="updatePrice"></label><label><input type="checkbox" :checked="inStockOnly" @change="toggleStock"> 仅看有货</label><select :value="sort" @change="updateSort"><option value="name">按名称</option><option value="price">按价格</option></select><button @click="clear">清空</button></div><div class="products"><button v-for="product in visibleProducts" :key="product.id" :class="product.id === selectedId ? 'selected' : ''" @click="select(product.id)"><strong>{{ product.name }}</strong><span>¥{{ product.price }} · 库存 {{ product.stock }}</span></button></div><p v-if="!visibleProducts.length" class="empty">无匹配商品</p></section>
</template>

<script>
module.exports = {
  name: 'ProductFilterPanel',
  props: {
    products: { type: Array, default: () => ([
          {
            "id": 1,
            "name": "机械键盘",
            "category": "外设",
            "price": 499,
            "stock": 8
          },
          {
            "id": 2,
            "name": "显示器支架",
            "category": "办公",
            "price": 269,
            "stock": 0
          },
          {
            "id": 3,
            "name": "降噪耳机",
            "category": "音频",
            "price": 899,
            "stock": 4
          },
          {
            "id": 4,
            "name": "桌面灯",
            "category": "办公",
            "price": 159,
            "stock": 12
          }
        ]) },
    categories: { type: Array, default: () => ([
          "外设",
          "办公",
          "音频"
        ]) }
  },
  data() {
    return {
        query: "",
        category: "all",
        maxPrice: 1000,
        inStockOnly: false,
        sort: "name",
        selectedId: null
    };
  },
  computed: {
    visibleProducts() {
      const q = this.query.toLowerCase(); return this.products.filter(item => item.name.toLowerCase().indexOf(q) >= 0 && (this.category === 'all' || item.category === this.category) && item.price <= this.maxPrice && (!this.inStockOnly || item.stock > 0)).slice().sort((a, b) => this.sort === 'price' ? a.price - b.price : a.name.localeCompare(b.name, 'zh-CN'));
    },
    resultCount() {
      return this.visibleProducts.length;
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateQuery(event) {
      this.setValue('query', event.target.value);
    },
    updateCategory(event) {
      this.setValue('category', event.target.value);
    },
    updatePrice(event) {
      this.setValue('maxPrice', Number(event.target.value) || 0);
    },
    toggleStock(event) {
      this.setValue('inStockOnly', event.target.checked);
    },
    updateSort(event) {
      this.setValue('sort', event.target.value);
    },
    select(id) {
      this.setValue('selectedId', id); this.emitEvent('select', id);
    },
    clear() {
      this.setValue('query', ''); this.setValue('category', 'all'); this.setValue('maxPrice', 1000); this.setValue('inStockOnly', false);
    }
  }
};
</script>

<style scoped>

.product-filter-panel{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.product-filter-panel *{box-sizing:border-box}
.product-filter-panel h2,.product-filter-panel h3,.product-filter-panel p{margin-top:0}
.product-filter-panel button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.product-filter-panel button.primary{border-color:#2563eb;background:#2563eb;color:#fff}
.product-filter-panel button:disabled{opacity:.45;cursor:not-allowed}
.product-filter-panel input,.product-filter-panel select,.product-filter-panel textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.product-filter-panel .muted{color:#71808e;font-size:12px}
.product-filter-panel .toolbar,.product-filter-panel .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.filters{display:flex;gap:8px;flex-wrap:wrap}.filters label{display:flex;align-items:center;gap:6px}.products{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-top:14px}.products button{text-align:left}.products button span{display:block}.products button.selected{background:#dbeafe;border-color:#2563eb}.empty{text-align:center}
</style>
