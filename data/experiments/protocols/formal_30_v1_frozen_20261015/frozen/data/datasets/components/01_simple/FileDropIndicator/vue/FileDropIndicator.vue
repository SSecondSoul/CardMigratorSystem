<template>
  <section class="file-drop-indicator"><h2>上传封面</h2><div :class="'drop-zone ' + (dragging ? 'dragging' : '')" @dragenter="enter" @dragleave="leave"><strong>{{ hint }}</strong><span v-if="fileName">{{ fileName }}</span></div><div class="actions"><button class="primary" @click="selectDemo">选择示例文件</button><button @click="clear" :disabled="!fileName">清除</button></div></section>
</template>

<script>
module.exports = {
  name: 'FileDropIndicator',
  props: {
    extensions: { type: Array, default: () => ([
          "png",
          "jpg",
          "webp"
        ]) }
  },
  data() {
    return {
        dragging: false,
        fileName: "",
        accepted: false
    };
  },
  computed: {
    hint() {
      return this.fileName ? (this.accepted ? '文件可用' : '格式不支持') : '拖入图片文件';
    }
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    enter() {
      this.setValue('dragging', true);
    },
    leave() {
      this.setValue('dragging', false);
    },
    selectDemo() {
      this.setValue('fileName', 'cover.png'); this.setValue('accepted', this.extensions.indexOf('png') >= 0); this.emitEvent('select', { name: 'cover.png', accepted: this.accepted });
    },
    clear() {
      this.setValue('fileName', ''); this.setValue('accepted', false);
    }
  }
};
</script>

<style scoped>

.file-drop-indicator{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.file-drop-indicator *{box-sizing:border-box}
.file-drop-indicator h2,.file-drop-indicator h3,.file-drop-indicator p{margin-top:0}
.file-drop-indicator button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.file-drop-indicator button.primary{border-color:#0369a1;background:#0369a1;color:#fff}
.file-drop-indicator button:disabled{opacity:.45;cursor:not-allowed}
.file-drop-indicator input,.file-drop-indicator select,.file-drop-indicator textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.file-drop-indicator .muted{color:#71808e;font-size:12px}
.file-drop-indicator .toolbar,.file-drop-indicator .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.drop-zone{display:grid;place-items:center;min-height:140px;border:2px dashed #94a3b8}.drop-zone.dragging{border-color:#0369a1;background:#e0f2fe}.drop-zone span{display:block}
</style>
