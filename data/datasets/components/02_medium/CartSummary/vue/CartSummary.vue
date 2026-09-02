<template>
  <section class="cart-summary">
    <header>
      <div><span class="eyebrow">采购清单</span><h2>{{ title }}</h2></div>
      <strong>{{ itemCount }} 件</strong>
    </header>
    <ul>
      <li v-for="item in items" :key="item.id">
        <div><strong>{{ item.name }}</strong><small>{{ currency }}{{ formatMoney(item.price) }}</small></div>
        <div class="quantity-control">
          <button type="button" @click="changeQuantity(item.id, -1)">-</button>
          <span>{{ item.quantity }}</span>
          <button type="button" @click="changeQuantity(item.id, 1)">+</button>
        </div>
        <button type="button" class="remove" @click="removeItem(item.id)">移除</button>
      </li>
    </ul>
    <p v-if="!items.length" class="empty-state">购物车为空</p>
    <div class="coupon-row">
      <input :value="coupon" placeholder="优惠码" @input="updateCoupon" />
      <button type="button" @click="applyCoupon">应用</button>
      <span>{{ message }}</span>
    </div>
    <dl>
      <div><dt>小计</dt><dd>{{ currency }}{{ formatMoney(subtotal) }}</dd></div>
      <div><dt>优惠</dt><dd>-{{ currency }}{{ formatMoney(discount) }}</dd></div>
      <div><dt>税费</dt><dd>{{ currency }}{{ formatMoney(tax) }}</dd></div>
      <div class="total"><dt>合计</dt><dd>{{ currency }}{{ formatMoney(total) }}</dd></div>
    </dl>
    <footer><button type="button" class="clear" @click="clear">清空</button><button type="button" @click="checkout">结算</button></footer>
  </section>
</template>

<script>
module.exports = {
  name: 'CartSummary',
  props: {
    title: { type: String, default: '实验耗材' },
    initialItems: {
      type: Array,
      default: function () {
        return [
          { id: 1, name: '移动硬盘', price: 399, quantity: 1 },
          { id: 2, name: '数据线', price: 39, quantity: 2 }
        ];
      }
    },
    taxRate: { type: Number, default: 0.06 },
    currency: { type: String, default: '¥' }
  },
  data() {
    return { items: this.initialItems.map((item) => Object.assign({}, item)), coupon: '', discountRate: 0, message: '' };
  },
  computed: {
    itemCount() { return this.items.reduce((sum, item) => sum + item.quantity, 0); },
    subtotal() { return this.items.reduce((sum, item) => sum + item.price * item.quantity, 0); },
    discount() { return this.subtotal * this.discountRate; },
    tax() { return (this.subtotal - this.discount) * this.taxRate; },
    total() { return this.subtotal - this.discount + this.tax; }
  },
  methods: {
    changeQuantity(id, delta) {
      const item = this.items.find((entry) => entry.id === id);
      item.quantity = Math.max(1, item.quantity + delta);
    },
    removeItem(id) { this.items = this.items.filter((item) => item.id !== id); },
    updateCoupon(event) { this.coupon = event.target.value.toUpperCase(); },
    applyCoupon() {
      this.discountRate = this.coupon === 'LAB10' ? 0.1 : 0;
      this.message = this.discountRate ? '已减免 10%' : '优惠码无效';
    },
    formatMoney(value) { return Number(value).toFixed(2); },
    clear() { this.items = []; this.message = ''; },
    checkout() { this.$emit('checkout', { items: this.items, total: this.total }); }
  }
};
</script>

<style scoped>
.cart-summary { width: 520px; padding: 22px; border: 1px solid #d1d5db; border-radius: 6px; background: #ffffff; color: #1f2937; font-family: Arial, sans-serif; }
.cart-summary header { display: flex; justify-content: space-between; align-items: flex-start; }
.cart-summary h2 { margin: 3px 0 0; font-size: 21px; }
.eyebrow { color: #6b7280; font-size: 12px; }
.cart-summary ul { padding: 0; list-style: none; }
.cart-summary li { display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid #e5e7eb; }
.cart-summary li small { display: block; margin-top: 4px; color: #6b7280; }
.quantity-control { display: flex; align-items: center; gap: 8px; }
.quantity-control button, .remove { border: 1px solid #9ca3af; background: #ffffff; cursor: pointer; }
.remove { color: #b91c1c; }
.coupon-row { display: grid; grid-template-columns: 1fr auto; gap: 8px; margin: 16px 0; }
.coupon-row input { padding: 8px; border: 1px solid #9ca3af; }
.coupon-row span { grid-column: 1 / -1; color: #166534; font-size: 12px; }
.cart-summary dl div { display: flex; justify-content: space-between; margin: 8px 0; }
.cart-summary dl .total { padding-top: 10px; border-top: 2px solid #111827; font-weight: 700; }
.cart-summary footer { display: flex; justify-content: space-between; }
.cart-summary footer button, .coupon-row button { padding: 8px 12px; border: 1px solid #1d4ed8; background: #1d4ed8; color: #ffffff; cursor: pointer; }
.cart-summary footer button.clear { background: #ffffff; color: #334155; border-color: #9ca3af; }
.empty-state { padding: 18px; text-align: center; color: #9ca3af; }
</style>
