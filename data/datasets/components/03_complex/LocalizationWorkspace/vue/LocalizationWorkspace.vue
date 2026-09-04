<template>
  <section class="localization-workspace"><header><div><p class="muted">{{ projectName }} · {{ currentLanguageName }}</p><h2>本地化翻译</h2></div><div class="actions"><select :value="language" @change="updateLanguage"><option v-for="item in languages" :key="item.code" :value="item.code">{{ item.name }}</option></select><button @click="toggleGlossary">术语表</button><button class="primary" @click="submitBatch">提交 {{ dirtyKeys.length }} 项</button></div></header><div class="locale-metrics"><span>审核 {{ progress }}%</span><span>缺失 {{ missingCount }} 项</span><span v-if="submittedAt">{{ submittedAt }}</span></div><div :class="'locale-layout ' + (showGlossary ? 'with-glossary' : '')"><aside class="entry-list"><input :value="query" @input="updateQuery" placeholder="搜索"><select :value="filter" @change="updateFilter"><option value="all">全部</option><option value="missing">缺失</option><option value="unreviewed">待审核</option></select><button v-for="record in visibleRecords" :key="record.key" :class="{ selected: record.key === selectedKey, reviewed: record.reviewed[language] }" @click="selectRecord(record.key)"><strong>{{ record.key }}</strong><span>{{ record.source }}</span><small>{{ translationFor(record) }}</small></button><p v-if="!visibleRecords.length" class="empty">无匹配文案</p></aside><main v-if="selectedRecord"><div class="source-panel"><span>源文案</span><strong>{{ selectedRecord.source }}</strong><small>{{ selectedRecord.key }}</small></div><label>目标译文<textarea :value="draft" @input="updateDraft"></textarea></label><div class="editor-actions"><span>{{ draft.length }} 字符</span><button class="primary" @click="markReviewed" :disabled="!draft">保存并审核</button></div></main><aside v-if="showGlossary" class="glossary"><h3>推荐术语</h3><button v-for="term in glossary" :key="term.source" @click="applyTerm(term)"><span>{{ term.source }}</span><strong>{{ term.target }}</strong></button></aside></div></section>
</template>

<script>
module.exports = {
  name: 'LocalizationWorkspace',
  props: {
    projectName: { type: String, default: "管理后台" },
    languages: { type: Array, default: () => ([
          {
            "code": "en",
            "name": "English"
          },
          {
            "code": "ja",
            "name": "日本語"
          }
        ]) },
    entries: { type: Array, default: () => ([
          {
            "key": "nav.home",
            "source": "首页",
            "translations": {
              "en": "Home",
              "ja": "ホーム"
            },
            "reviewed": {
              "en": true,
              "ja": false
            }
          },
          {
            "key": "action.save",
            "source": "保存",
            "translations": {
              "en": "Save",
              "ja": ""
            },
            "reviewed": {
              "en": false,
              "ja": false
            }
          },
          {
            "key": "message.empty",
            "source": "暂无数据",
            "translations": {
              "en": "No data",
              "ja": "データなし"
            },
            "reviewed": {
              "en": true,
              "ja": true
            }
          }
        ]) },
    glossary: { type: Array, default: () => ([
          {
            "source": "保存",
            "target": "Save"
          },
          {
            "source": "数据",
            "target": "data"
          }
        ]) }
  },
  data() {
    return {
        records: [],
        language: "en",
        query: "",
        filter: "all",
        selectedKey: "",
        draft: "",
        showGlossary: true,
        dirtyKeys: [],
        submittedAt: ""
    };
  },
  computed: {
    visibleRecords() {
      const q = this.query.toLowerCase(); return this.records.filter(item => (item.key.toLowerCase().indexOf(q) >= 0 || item.source.indexOf(this.query) >= 0) && (this.filter === 'all' || (this.filter === 'missing' ? !item.translations[this.language] : !item.reviewed[this.language])));
    },
    selectedRecord() {
      return this.records.find(item => item.key === this.selectedKey) || null;
    },
    progress() {
      const records = this.records; return records.length ? Math.round(records.filter(item => item.reviewed[this.language]).length / records.length * 100) : 0;
    },
    missingCount() {
      return this.records.filter(item => !item.translations[this.language]).length;
    },
    currentLanguageName() {
      const item = this.languages.find(row => row.code === this.language); return item ? item.name : '';
    }
  },
  created() {
    this.setValue('records', this.entries.map(item => ({ key: item.key, source: item.source, translations: Object.assign({}, item.translations), reviewed: Object.assign({}, item.reviewed) }))); this.setValue('language', this.languages[0] ? this.languages[0].code : ''); this.setValue('selectedKey', this.entries[0] ? this.entries[0].key : ''); this.loadDraft();
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateLanguage(event) {
      this.commitDraft(); this.setValue('language', event.target.value); this.loadDraft();
    },
    updateQuery(event) {
      this.setValue('query', event.target.value);
    },
    updateFilter(event) {
      this.setValue('filter', event.target.value);
    },
    selectRecord(key) {
      this.commitDraft(); this.setValue('selectedKey', key); this.loadDraft();
    },
    updateDraft(event) {
      this.setValue('draft', event.target.value);
    },
    loadDraft() {
      const record = this.records.find(item => item.key === this.selectedKey); this.setValue('draft', record ? record.translations[this.language] || '' : '');
    },
    commitDraft() {
      const key = this.selectedKey; if (!key) return; const language = this.language; const value = this.draft; this.setValue('records', this.records.map(item => item.key === key ? Object.assign({}, item, { translations: Object.assign({}, item.translations, { [language]: value }), reviewed: Object.assign({}, item.reviewed, { [language]: false }) }) : item)); if (this.dirtyKeys.indexOf(key) < 0) this.setValue('dirtyKeys', this.dirtyKeys.concat(key)); this.emitEvent('translation-change', { key, language, value });
    },
    markReviewed() {
      this.commitDraft(); const key = this.selectedKey; const language = this.language; this.setValue('records', this.records.map(item => item.key === key ? Object.assign({}, item, { reviewed: Object.assign({}, item.reviewed, { [language]: true }) }) : item)); this.emitEvent('review', { key, language });
    },
    applyTerm(term) {
      this.setValue('draft', this.draft + (this.draft ? ' ' : '') + term.target);
    },
    toggleGlossary() {
      this.setValue('showGlossary', !this.showGlossary);
    },
    submitBatch() {
      this.commitDraft(); this.setValue('submittedAt', new Date().toLocaleString('zh-CN', { hour12: false })); this.emitEvent('submit', { language: this.language, keys: this.dirtyKeys }); this.setValue('dirtyKeys', []);
    },
    translationFor(record) {
      return record.translations[this.language] || '未翻译';
    }
  }
};
</script>

<style scoped>

.localization-workspace { max-width: 760px; margin: 18px auto; padding: 20px; border: 1px solid #cfd6dd; border-radius: 6px; background: #fff; color: #24313d; font-family: Arial, sans-serif; box-sizing: border-box; }
.localization-workspace * { box-sizing: border-box; }
.localization-workspace h2, .localization-workspace h3, .localization-workspace p { margin-top: 0; }
.localization-workspace h2 { margin-bottom: 14px; font-size: 21px; }
.localization-workspace button { padding: 7px 11px; border: 1px solid #aeb8c2; border-radius: 4px; background: #fff; color: #273746; cursor: pointer; }
.localization-workspace button.primary { border-color: #6d28d9; background: #6d28d9; color: #fff; }
.localization-workspace button:disabled { opacity: .45; cursor: not-allowed; }
.localization-workspace input, .localization-workspace select, .localization-workspace textarea { padding: 8px; border: 1px solid #b9c3cc; border-radius: 4px; font: inherit; }
.localization-workspace .toolbar, .localization-workspace .summary, .localization-workspace .actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.localization-workspace .muted { color: #71808e; font-size: 12px; }
.localization-workspace .empty { padding: 24px; color: #7c8792; text-align: center; border: 1px dashed #c8d0d8; }
header,.locale-metrics{display:flex;justify-content:space-between}.locale-metrics{padding:10px;background:#f5f3ff}.locale-layout{display:grid;grid-template-columns:220px 1fr;gap:12px;margin-top:12px}.locale-layout.with-glossary{grid-template-columns:220px 1fr 150px}.entry-list{max-height:450px;overflow:auto}.entry-list>button{display:grid;width:100%;margin:6px 0;text-align:left}.entry-list>button.selected{background:#ede9fe}.entry-list>button.reviewed{border-left:4px solid #15803d}.entry-list small{color:#77818e}.locale-layout main{padding:16px;background:#fafafa}.source-panel{display:grid;padding:12px;background:#f1f2f4}.locale-layout main label{display:grid;gap:6px;margin-top:14px}.locale-layout main textarea{min-height:160px}.editor-actions{display:flex;justify-content:space-between}.glossary{padding:10px;background:#f7f5fb}.glossary button{display:grid;width:100%;margin:6px 0}

</style>
