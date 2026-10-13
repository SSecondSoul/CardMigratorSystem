<template>
  <form class="reservation-form" @submit="submit">
    <header>
      <div>
        <span class="eyebrow">预约申请</span>
        <h2>{{ title }}</h2>
      </div>
      <span class="guest-summary">{{ guestLabel }}</span>
    </header>
    <div class="form-grid">
      <label>联系人<input :value="form.contact" @input="updateContact" /></label>
      <label>地点
        <select :value="form.location" @change="updateLocation">
          <option v-for="location in locations" :key="location" :value="location">{{ location }}</option>
        </select>
      </label>
      <label>日期<input type="date" :value="form.date" @input="updateDate" /></label>
      <label>人数<input type="number" min="1" max="12" :value="form.guests" @input="updateGuests" /></label>
    </div>
    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="confirmation" class="form-success">{{ confirmation }}</p>
    <footer>
      <button type="button" class="secondary" @click="reset">重置</button>
      <button type="submit">提交预约</button>
    </footer>
  </form>
</template>

<script>
module.exports = {
  name: 'ReservationForm',
  props: {
    title: { type: String, default: '会议室预约' },
    locations: { type: Array, default: function () { return ['东区 201', '西区 305', '共享空间']; } },
    initialDate: { type: String, default: '2026-09-08' },
    initialGuests: { type: Number, default: 2 }
  },
  data() {
    return {
      form: { contact: '', location: this.locations[0], date: this.initialDate, guests: this.initialGuests },
      error: '',
      confirmation: ''
    };
  },
  computed: {
    guestLabel() { return `${this.form.guests} 人 · ${this.form.location}`; }
  },
  methods: {
    updateContact(event) { this.form.contact = event.target.value; },
    updateLocation(event) { this.form.location = event.target.value; },
    updateDate(event) { this.form.date = event.target.value; },
    updateGuests(event) { this.form.guests = Number(event.target.value); },
    validate() {
      if (!this.form.contact.trim()) return '请填写联系人';
      if (!this.form.date) return '请选择日期';
      if (this.form.guests < 1) return '预约人数至少为 1';
      return '';
    },
    submit(event) {
      event.preventDefault();
      this.error = this.validate();
      if (this.error) return;
      this.confirmation = `已为 ${this.form.contact} 提交预约`;
      this.$emit('submit', Object.assign({}, this.form));
    },
    reset() {
      this.form = { contact: '', location: this.locations[0], date: this.initialDate, guests: this.initialGuests };
      this.error = '';
      this.confirmation = '';
      this.$emit('reset');
    }
  }
};
</script>

<style scoped>
.reservation-form { width: 520px; padding: 22px; border: 1px solid #cbd5e1; border-radius: 7px; background: #f8fafc; color: #172026; font-family: Arial, sans-serif; }
.reservation-form header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
.reservation-form h2 { margin: 3px 0 0; font-size: 21px; }
.eyebrow { color: #64748b; font-size: 12px; }
.guest-summary { padding: 6px 9px; background: #e0f2fe; color: #075985; font-size: 12px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.form-grid label { display: grid; gap: 6px; color: #475569; font-size: 13px; }
.form-grid input, .form-grid select { padding: 9px; border: 1px solid #94a3b8; border-radius: 4px; background: #ffffff; }
.form-error { color: #b91c1c; }
.form-success { color: #166534; }
.reservation-form footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
.reservation-form button { padding: 9px 14px; border: 1px solid #075985; border-radius: 4px; background: #075985; color: #ffffff; cursor: pointer; }
.reservation-form button.secondary { background: #ffffff; color: #334155; border-color: #94a3b8; }
</style>
