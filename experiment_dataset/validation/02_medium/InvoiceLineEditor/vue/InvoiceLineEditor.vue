<template>
  <section class="invoice-line-editor"><h2>服务发票</h2><table><thead><tr><th>项目</th><th>数量</th><th>单价</th><th>小计</th><th></th></tr></thead><tbody><tr v-for="line in lines" :key="line.id"><td><input :value="line.description" @input="updateLine(line.id, 'description', $event)"></td><td><input type="number" :value="line.quantity" @input="updateLine(line.id, 'quantity', $event)"></td><td><input type="number" :value="line.price" @input="updateLine(line.id, 'price', $event)"></td><td>¥{{ line.quantity * line.price }}</td><td><button @click="removeLine(line.id)">删除</button></td></tr></tbody></table><div class="add-row"><input :value="draft" @input="updateDraft" placeholder="新增项目"><button @click="addLine">添加行</button></div><aside><label>折扣<input type="number" :value="discount" @input="updateDiscount"></label><span>未税 ¥{{ subtotal }}</span><span>税额 ¥{{ tax }}</span><strong>应付 ¥{{ payable }}</strong></aside></section>
</template>

<script>
module.exports = {
  name: 'InvoiceLineEditor',
  props: {
    initialLines: { type: Array, default: () => ([
          {
            "id": 1,
            "description": "设计服务",
            "quantity": 2,
            "price": 800
          },
          {
            "id": 2,
            "description": "部署支持",
            "quantity": 1,
            "price": 500
          }
        ]) },
    taxRate: { type: Number, default: 6 }
  },
  data() {
    return {
        lines: [],
        discount: 0,
        draft: "",
        nextId: 10
    };
  },
  computed: {
    subtotal() {
      return this.lines.reduce((sum, item) => sum + item.quantity * item.price, 0);
    },
    tax() {
      return this.subtotal * this.taxRate / 100;
    },
    payable() {
      return Math.max(0, this.subtotal + this.tax - this.discount);
    }
  },
  created() {
    this.setValue('lines', this.initialLines.map(item => Object.assign({}, item)));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateLine(id, field, event) {
      const value = field === 'description' ? event.target.value : Math.max(0, Number(event.target.value) || 0); this.setValue('lines', this.lines.map(item => item.id === id ? Object.assign({}, item, { [field]: value }) : item)); this.notify();
    },
    updateDraft(event) {
      this.setValue('draft', event.target.value);
    },
    addLine() {
      const text = this.draft.trim(); if (!text) return; this.setValue('lines', this.lines.concat({ id: this.nextId, description: text, quantity: 1, price: 0 })); this.setValue('nextId', this.nextId + 1); this.setValue('draft', ''); this.notify();
    },
    removeLine(id) {
      this.setValue('lines', this.lines.filter(item => item.id !== id)); this.notify();
    },
    updateDiscount(event) {
      this.setValue('discount', Math.max(0, Number(event.target.value) || 0)); this.notify();
    },
    notify() {
      this.emitEvent('change', { lines: this.lines, discount: this.discount });
    }
  }
};
</script>

<style scoped>

.invoice-line-editor{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.invoice-line-editor *{box-sizing:border-box}
.invoice-line-editor h2,.invoice-line-editor h3,.invoice-line-editor p{margin-top:0}
.invoice-line-editor button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.invoice-line-editor button.primary{border-color:#0f766e;background:#0f766e;color:#fff}
.invoice-line-editor button:disabled{opacity:.45;cursor:not-allowed}
.invoice-line-editor input,.invoice-line-editor select,.invoice-line-editor textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.invoice-line-editor .muted{color:#71808e;font-size:12px}
.invoice-line-editor .toolbar,.invoice-line-editor .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
table{width:100%;border-collapse:collapse}th,td{padding:7px;border-bottom:1px solid #e2e8f0}td input{width:100%}.add-row{display:flex;gap:8px;margin:10px 0}.add-row input{flex:1}aside{display:flex;justify-content:flex-end;align-items:center;gap:14px;padding:12px;background:#ecfdf5}aside label{display:flex;align-items:center;gap:5px}aside input{width:80px}
</style>
