<template>
  <section class="media-review-studio">
    <header class="studio-header">
      <div>
        <p class="eyebrow">内容审阅</p>
        <h2>{{ title }}</h2>
      </div>
      <div class="reviewer-stack">
        <span v-for="reviewer in reviewers" :key="reviewer.id" :title="reviewer.name">
          {{ reviewerInitial(reviewer.name) }}
        </span>
      </div>
    </header>

    <div class="studio-layout">
      <aside class="asset-rail">
        <h3>媒体资产</h3>
        <button
          v-for="asset in assets"
          :key="asset.id"
          type="button"
          class="asset-item"
          :class="{ active: asset.id === selectedId, approved: asset.decision === 'approved' }"
          @click="selectAsset(asset.id)"
        >
          <span class="asset-kind">{{ asset.kind }}</span>
          <strong>{{ asset.name }}</strong>
          <small>{{ formatTime(asset.duration) }} · {{ asset.notes.length }} 条批注</small>
        </button>
      </aside>

      <main v-if="selectedAsset" class="review-stage">
        <div class="media-frame" :class="{ playing: isPlaying }">
          <div class="frame-art">{{ selectedAsset.kind === '视频' ? '▶' : '▧' }}</div>
          <div class="frame-caption">
            <strong>{{ selectedAsset.name }}</strong>
            <span>{{ isPlaying ? '正在播放' : '已暂停' }}</span>
          </div>
        </div>

        <div class="transport">
          <button type="button" class="play-button" @click="togglePlayback">
            {{ isPlaying ? '暂停' : '播放' }}
          </button>
          <input
            type="range"
            min="0"
            :max="selectedAsset.duration"
            :value="currentTime"
            @input="seek"
          >
          <output>{{ formatTime(currentTime) }} / {{ formatTime(selectedAsset.duration) }}</output>
        </div>

        <div class="decision-bar">
          <div>
            <span>审阅决定</span>
            <strong>{{ decisionText }}</strong>
          </div>
          <button type="button" :class="{ chosen: selectedAsset.decision === 'changes' }" @click="setDecision('changes')">退回修改</button>
          <button type="button" :class="{ chosen: selectedAsset.decision === 'approved' }" @click="setDecision('approved')">批准发布</button>
        </div>
      </main>

      <aside v-if="selectedAsset" class="note-panel">
        <div class="note-heading">
          <h3>时间点批注</h3>
          <div class="filter-group">
            <button type="button" :class="{ active: filter === 'all' }" @click="setFilter('all')">全部</button>
            <button type="button" :class="{ active: filter === 'open' }" @click="setFilter('open')">待处理</button>
          </div>
        </div>

        <form class="note-form" @submit.prevent="addNote">
          <label>在 {{ formatTime(currentTime) }} 添加批注</label>
          <textarea v-model.trim="noteText" rows="3" placeholder="描述需要调整的画面或声音"></textarea>
          <button type="submit" :disabled="!noteText">添加批注</button>
        </form>

        <div class="note-list">
          <article v-for="note in visibleNotes" :key="note.id" class="note-card" :class="{ resolved: note.resolved }">
            <button type="button" class="time-link" @click="jumpTo(note.time)">{{ formatTime(note.time) }}</button>
            <p>{{ note.text }}</p>
            <footer>
              <span>{{ note.author }}</span>
              <button type="button" @click="toggleResolved(note.id)">{{ note.resolved ? '重新打开' : '标记解决' }}</button>
              <button type="button" class="remove-note" @click="removeNote(note.id)">删除</button>
            </footer>
          </article>
          <p v-if="visibleNotes.length === 0" class="empty-notes">当前筛选下没有批注</p>
        </div>
      </aside>
    </div>
  </section>
</template>

<script>
module.exports = {
  name: 'MediaReviewStudio',
  props: {
    title: { type: String, default: '秋季发布片审阅' },
    reviewers: {
      type: Array,
      default: function () {
        return [
          { id: 1, name: '林晓' },
          { id: 2, name: '周宁' },
          { id: 3, name: '陈一' }
        ];
      }
    },
    initialAssets: {
      type: Array,
      default: function () {
        return [
          {
            id: 1,
            name: '品牌开场动画',
            kind: '视频',
            duration: 96,
            decision: 'pending',
            notes: [
              { id: 11, time: 18, text: '徽标出现节奏可以再快半秒。', author: '林晓', resolved: false },
              { id: 12, time: 64, text: '环境音已经通过版权核验。', author: '周宁', resolved: true }
            ]
          },
          {
            id: 2,
            name: '产品功能演示',
            kind: '视频',
            duration: 143,
            decision: 'changes',
            notes: [{ id: 21, time: 37, text: '此处操作路径与最新版不一致。', author: '陈一', resolved: false }]
          },
          { id: 3, name: '片尾封面', kind: '图片', duration: 12, decision: 'approved', notes: [] }
        ];
      }
    }
  },
  data() {
    return {
      assets: this.cloneAssets(this.initialAssets),
      selectedId: this.initialAssets.length ? this.initialAssets[0].id : null,
      currentTime: 0,
      isPlaying: false,
      noteText: '',
      filter: 'all',
      timer: null
    };
  },
  computed: {
    selectedAsset() {
      return this.assets.find((asset) => asset.id === this.selectedId) || null;
    },
    visibleNotes() {
      if (!this.selectedAsset) return [];
      return this.filter === 'open'
        ? this.selectedAsset.notes.filter((note) => !note.resolved)
        : this.selectedAsset.notes;
    },
    decisionText() {
      const labels = { pending: '等待决定', changes: '需要修改', approved: '可以发布' };
      return this.selectedAsset ? labels[this.selectedAsset.decision] : '';
    }
  },
  mounted() {
    this.timer = setInterval(this.tick, 1000);
  },
  beforeDestroy() {
    clearInterval(this.timer);
  },
  methods: {
    cloneAssets(assets) {
      return assets.map((asset) => Object.assign({}, asset, {
        notes: asset.notes.map((note) => Object.assign({}, note))
      }));
    },
    selectAsset(id) {
      this.selectedId = id;
      this.currentTime = 0;
      this.isPlaying = false;
      this.filter = 'all';
    },
    togglePlayback() {
      if (!this.selectedAsset) return;
      if (this.currentTime >= this.selectedAsset.duration) this.currentTime = 0;
      this.isPlaying = !this.isPlaying;
    },
    tick() {
      if (!this.isPlaying || !this.selectedAsset) return;
      this.currentTime = Math.min(this.currentTime + 1, this.selectedAsset.duration);
      if (this.currentTime >= this.selectedAsset.duration) this.isPlaying = false;
    },
    seek(event) {
      this.currentTime = Number(event.target.value);
    },
    jumpTo(time) {
      this.currentTime = time;
      this.isPlaying = false;
    },
    addNote() {
      const text = this.noteText.trim();
      if (!text || !this.selectedAsset) return;
      this.selectedAsset.notes.push({
        id: Date.now(),
        time: this.currentTime,
        text,
        author: this.reviewers.length ? this.reviewers[0].name : '审阅者',
        resolved: false
      });
      this.noteText = '';
      this.filter = 'all';
    },
    toggleResolved(id) {
      const note = this.selectedAsset.notes.find((item) => item.id === id);
      if (note) note.resolved = !note.resolved;
    },
    removeNote(id) {
      this.selectedAsset.notes = this.selectedAsset.notes.filter((note) => note.id !== id);
    },
    setFilter(filter) {
      this.filter = filter;
    },
    setDecision(decision) {
      this.selectedAsset.decision = decision;
      this.$emit('review-decision', { assetId: this.selectedId, decision });
    },
    reviewerInitial(name) {
      return String(name || '').slice(0, 1);
    },
    formatTime(value) {
      const seconds = Math.max(0, Number(value) || 0);
      const minutes = Math.floor(seconds / 60);
      return minutes + ':' + String(seconds % 60).padStart(2, '0');
    }
  }
};
</script>

<style scoped>
.media-review-studio { max-width: 1180px; min-height: 620px; margin: 0 auto; color: #172033; background: #f5f7fa; border: 1px solid #dce1e8; font-family: Arial, sans-serif; }
.studio-header { display: flex; align-items: center; justify-content: space-between; padding: 20px 24px; background: #ffffff; border-bottom: 1px solid #dce1e8; }
.studio-header h2 { margin: 3px 0 0; font-size: 21px; }
.eyebrow { margin: 0; color: #657084; font-size: 12px; text-transform: uppercase; }
.reviewer-stack { display: flex; }
.reviewer-stack span { display: grid; width: 32px; height: 32px; margin-left: -7px; place-items: center; border: 2px solid #ffffff; border-radius: 50%; background: #264653; color: #ffffff; font-size: 12px; }
.studio-layout { display: grid; grid-template-columns: 210px minmax(360px, 1fr) 320px; min-height: 550px; }
.asset-rail { padding: 18px 14px; background: #ffffff; border-right: 1px solid #dce1e8; }
.asset-rail h3, .note-heading h3 { margin: 0 0 14px; font-size: 14px; }
.asset-item { display: grid; width: 100%; margin-bottom: 9px; padding: 11px; gap: 5px; text-align: left; border: 1px solid transparent; border-radius: 5px; background: #f4f6f8; color: #283548; cursor: pointer; }
.asset-item.active { border-color: #2a9d8f; background: #e8f5f2; }
.asset-item.approved .asset-kind { color: #237a57; }
.asset-kind { color: #7a8494; font-size: 11px; }
.asset-item small { color: #758094; }
.review-stage { display: flex; min-width: 0; padding: 22px; flex-direction: column; gap: 15px; }
.media-frame { display: flex; min-height: 320px; align-items: center; justify-content: center; position: relative; overflow: hidden; background: #18222d; color: #ffffff; box-shadow: inset 0 0 0 1px #0b1118; }
.media-frame.playing { box-shadow: inset 0 0 0 2px #2a9d8f; }
.frame-art { font-size: 70px; opacity: .78; }
.frame-caption { display: flex; right: 16px; bottom: 14px; left: 16px; position: absolute; justify-content: space-between; color: #dfe7ee; font-size: 12px; }
.transport { display: grid; grid-template-columns: 64px 1fr auto; align-items: center; gap: 12px; }
.transport input { width: 100%; accent-color: #2a9d8f; }
.transport output { color: #566174; font-size: 12px; font-variant-numeric: tabular-nums; }
.play-button { padding: 8px 10px; border: 0; border-radius: 4px; background: #264653; color: #ffffff; cursor: pointer; }
.decision-bar { display: grid; grid-template-columns: 1fr auto auto; align-items: center; padding: 13px; gap: 9px; border: 1px solid #d8dee6; background: #ffffff; }
.decision-bar div { display: flex; flex-direction: column; gap: 3px; }
.decision-bar span { color: #707b8d; font-size: 11px; }
.decision-bar button { padding: 8px 11px; border: 1px solid #c8d0da; border-radius: 4px; background: #ffffff; cursor: pointer; }
.decision-bar button.chosen { border-color: #e76f51; background: #fff0ec; color: #9f3622; }
.note-panel { padding: 18px; overflow: hidden; background: #ffffff; border-left: 1px solid #dce1e8; }
.note-heading { display: flex; align-items: flex-start; justify-content: space-between; }
.filter-group { display: flex; gap: 4px; }
.filter-group button { padding: 4px 7px; border: 0; border-radius: 3px; background: #edf0f4; color: #5e6878; font-size: 11px; cursor: pointer; }
.filter-group button.active { background: #264653; color: #ffffff; }
.note-form { display: grid; padding: 12px; gap: 8px; background: #f2f5f7; }
.note-form label { color: #5a6577; font-size: 12px; }
.note-form textarea { padding: 8px; resize: vertical; border: 1px solid #cbd3dc; border-radius: 3px; font: inherit; }
.note-form button { justify-self: end; padding: 7px 10px; border: 0; border-radius: 3px; background: #2a9d8f; color: #ffffff; cursor: pointer; }
.note-form button:disabled { opacity: .45; cursor: not-allowed; }
.note-list { max-height: 350px; margin-top: 13px; overflow: auto; }
.note-card { margin-bottom: 9px; padding: 11px; border-left: 3px solid #e9c46a; background: #fffaf0; }
.note-card.resolved { border-left-color: #7ebc89; background: #f2faf4; opacity: .72; }
.time-link { padding: 0; border: 0; background: transparent; color: #267a72; font-weight: 700; cursor: pointer; }
.note-card p { margin: 7px 0 10px; line-height: 1.45; font-size: 13px; }
.note-card footer { display: flex; align-items: center; gap: 7px; color: #697487; font-size: 11px; }
.note-card footer span { margin-right: auto; }
.note-card footer button { padding: 0; border: 0; background: transparent; color: #3d6470; font-size: 11px; cursor: pointer; }
.note-card footer .remove-note { color: #a33d31; }
.empty-notes { padding: 28px 8px; color: #818a98; text-align: center; font-size: 13px; }
@media (max-width: 900px) { .studio-layout { grid-template-columns: 180px 1fr; } .note-panel { grid-column: 1 / -1; border-top: 1px solid #dce1e8; border-left: 0; } }
</style>
