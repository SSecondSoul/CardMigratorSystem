<template>
  <section class="star-rating-input"><h2>服务评分</h2><div @mouseleave="clearPreview"><button v-for="star in starValues" :key="star" :class="star <= displayRating ? 'active' : ''" @mouseenter="preview(star)" @click="choose(star)">★</button></div><p>{{ displayRating }} / {{ maxStars }} 星</p></section>
</template>

<script>
module.exports = {
  name: 'StarRatingInput',
  props: {
    maxStars: { type: Number, default: 5 },
    initialRating: { type: Number, default: 3 }
  },
  data() {
    return {
        rating: 3,
        hoverRating: 0
    };
  },
  computed: {
    starValues() {
      return Array.from({ length: this.maxStars }, (_, index) => index + 1);
    },
    displayRating() {
      return this.hoverRating || this.rating;
    }
  },
  created() {
    this.setValue('rating', this.initialRating);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    preview(value) {
      this.setValue('hoverRating', value);
    },
    clearPreview() {
      this.setValue('hoverRating', 0);
    },
    choose(value) {
      this.setValue('rating', value); this.emitEvent('change', value);
    }
  }
};
</script>

<style scoped>

.star-rating-input{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.star-rating-input *{box-sizing:border-box}
.star-rating-input h2,.star-rating-input h3,.star-rating-input p{margin-top:0}
.star-rating-input button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.star-rating-input button.primary{border-color:#d97706;background:#d97706;color:#fff}
.star-rating-input button:disabled{opacity:.45;cursor:not-allowed}
.star-rating-input input,.star-rating-input select,.star-rating-input textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.star-rating-input .muted{color:#71808e;font-size:12px}
.star-rating-input .toolbar,.star-rating-input .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.star-rating-input div{display:flex;gap:6px}.star-rating-input div button{border:0;font-size:28px;color:#cbd5e1}.star-rating-input div button.active{color:#d97706}
</style>
