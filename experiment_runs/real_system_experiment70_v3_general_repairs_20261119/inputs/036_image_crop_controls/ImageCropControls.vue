<template>
  <section class="image-crop-controls"><h2>裁剪参数</h2><div class="crop-layout"><div class="canvas"><div class="crop-box" :style="cropStyle"></div></div><div class="controls"><label v-for="field in ['x','y','width','height']" :key="field">{{ field }}<input type="number" :value="crop[field]" @input="update(field, $event)"></label><label><input type="checkbox" :checked="locked" @change="toggleLock"> 锁定宽高比</label><button @click="reset">重置</button></div></div></section>
</template>

<script>
module.exports = {
  name: 'ImageCropControls',
  props: {
    canvas: { type: Object, default: () => ({
          "width": 640,
          "height": 360
        }) },
    initialCrop: { type: Object, default: () => ({
          "x": 10,
          "y": 10,
          "width": 45,
          "height": 55
        }) }
  },
  data() {
    return {
        crop: {},
        locked: false
    };
  },
  computed: {
    cropStyle() {
      return 'left:' + this.crop.x + '%;top:' + this.crop.y + '%;width:' + this.crop.width + '%;height:' + this.crop.height + '%';
    }
  },
  watch: {
    locked() {
      if (this.locked) this.setValue('crop', Object.assign({}, this.crop, { height: Math.round(this.crop.width * this.canvas.width / this.canvas.height) }));
    }
  },
  created() {
    this.setValue('crop', Object.assign({}, this.initialCrop));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    update(field, event) {
      let value = Math.max(0, Math.min(100, Number(event.target.value) || 0)); const crop = Object.assign({}, this.crop, { [field]: value }); if (this.locked && field === 'width') crop.height = Math.min(100, Math.round(value * this.canvas.width / this.canvas.height)); this.setValue('crop', crop); this.emitEvent('change', crop);
    },
    toggleLock(event) {
      this.setValue('locked', event.target.checked);
    },
    reset() {
      this.setValue('crop', Object.assign({}, this.initialCrop));
    }
  }
};
</script>

<style scoped>

.image-crop-controls{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.image-crop-controls *{box-sizing:border-box}
.image-crop-controls h2,.image-crop-controls h3,.image-crop-controls p{margin-top:0}
.image-crop-controls button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.image-crop-controls button.primary{border-color:#db2777;background:#db2777;color:#fff}
.image-crop-controls button:disabled{opacity:.45;cursor:not-allowed}
.image-crop-controls input,.image-crop-controls select,.image-crop-controls textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.image-crop-controls .muted{color:#71808e;font-size:12px}
.image-crop-controls .toolbar,.image-crop-controls .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.crop-layout{display:grid;grid-template-columns:1fr 190px;gap:14px}.canvas{position:relative;aspect-ratio:16/9;background:linear-gradient(135deg,#dbeafe,#fce7f3);overflow:hidden}.crop-box{position:absolute;border:3px solid #db2777;background:#fff4}.controls{display:grid;gap:7px}.controls label{display:grid;grid-template-columns:55px 1fr;align-items:center}
</style>
