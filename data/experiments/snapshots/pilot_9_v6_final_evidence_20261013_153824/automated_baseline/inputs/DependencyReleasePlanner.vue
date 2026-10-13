<template>
  <section class="dependency-release-planner"><header><div><small>{{ environment }} · {{ releaseStatus }}</small><h2>{{ releaseName }}</h2></div><select :value="environment" @change="setEnvironment"><option v-for="env in environments" :key="env" :value="env">{{ env }}</option></select></header><div class="release-layout"><aside><h3>未编排服务</h3><button v-for="service in unplanned" :key="service.id" :class="selectedServiceId === service.id ? 'selected' : ''" @click="chooseService(service.id)"><strong>{{ service.id }}</strong><span>{{ service.version }} · {{ service.health }}</span></button><h3>依赖边</h3><p v-for="edge in dependencies" :key="edge.from + edge.to">{{ edge.from }} → {{ edge.to }}</p></aside><main><section v-for="wave, index in waves" :key="index" class="wave"><header><h3>波次 {{ index + 1 }}</h3><button @click="assignWave(index)" :disabled="!selectedServiceId">放入此波次</button></header><article v-for="id in wave" :key="id"><strong>{{ serviceLabel(id) }}</strong><button @click="removeFromWave(id)">移出</button></article></section></main><aside class="gate"><h3>发布门禁</h3><p :class="unplanned.length ? 'bad' : 'good'">未编排 {{ unplanned.length }}</p><p :class="dependencyViolations.length ? 'bad' : 'good'">依赖冲突 {{ dependencyViolations.length }}</p><p>审批 {{ approvals.length }}/{{ requiredApprovals }}</p><button @click="approve('技术负责人')">技术审批</button><button @click="approve('运维负责人')">运维审批</button><button class="primary" @click="release" :disabled="!canRelease">执行发布</button><button @click="rollback" :disabled="releaseStatus !== 'released'">回滚</button></aside></div></section>
</template>

<script>
module.exports = {
  name: 'DependencyReleasePlanner',
  props: {
    releaseName: { type: String, default: "秋季平台发布" },
    initialServices: { type: Array, default: () => ([
          {
            "id": "web",
            "version": "2.4.0"
          },
          {
            "id": "api",
            "version": "3.1.0"
          },
          {
            "id": "billing",
            "version": "1.8.2"
          },
          {
            "id": "notify",
            "version": "1.3.5"
          }
        ]) },
    dependencies: { type: Array, default: () => ([
          {
            "from": "web",
            "to": "api"
          },
          {
            "from": "api",
            "to": "billing"
          },
          {
            "from": "api",
            "to": "notify"
          }
        ]) },
    environments: { type: Array, default: () => ([
          "测试",
          "预发",
          "生产"
        ]) },
    requiredApprovals: { type: Number, default: 2 }
  },
  data() {
    return {
        services: [],
        waves: [
          [],
          [],
          []
        ],
        selectedServiceId: null,
        environment: "测试",
        approvals: [],
        releaseStatus: "planning",
        history: []
    };
  },
  computed: {
    plannedIds() {
      return this.waves.reduce((out, wave) => out.concat(wave), []);
    },
    unplanned() {
      return this.services.filter(service => this.plannedIds.indexOf(service.id) < 0);
    },
    dependencyViolations() {
      const position = {}; this.waves.forEach((wave, index) => wave.forEach(id => { position[id] = index; })); return this.dependencies.filter(edge => position[edge.from] !== undefined && (position[edge.to] === undefined || position[edge.to] > position[edge.from]));
    },
    canRelease() {
      return this.unplanned.length === 0 && this.dependencyViolations.length === 0 && this.approvals.length >= this.requiredApprovals && this.releaseStatus !== 'released';
    }
  },
  created() {
    this.setValue('services', this.initialServices.map(item => Object.assign({}, item, { health: 'ready' })));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    chooseService(id) {
      this.setValue('selectedServiceId', id);
    },
    assignWave(index) {
      if (!this.selectedServiceId) return; const id = this.selectedServiceId; this.setValue('waves', this.waves.map((wave, waveIndex) => waveIndex === index ? wave.filter(item => item !== id).concat(id) : wave.filter(item => item !== id))); this.setValue('selectedServiceId', null); this.setValue('approvals', []); this.emitEvent('plan', this.waves);
    },
    removeFromWave(id) {
      this.setValue('waves', this.waves.map(wave => wave.filter(item => item !== id))); this.setValue('approvals', []);
    },
    approve(role) {
      if (this.approvals.indexOf(role) >= 0) return; this.setValue('approvals', this.approvals.concat(role)); this.emitEvent('approve', this.approvals);
    },
    setEnvironment(event) {
      this.setValue('environment', event.target.value); this.setValue('approvals', []);
    },
    release() {
      if (!this.canRelease) return; this.setValue('history', [{ id: Date.now(), environment: this.environment, waves: this.waves.map(wave => wave.slice()) }].concat(this.history)); this.setValue('releaseStatus', 'released'); this.emitEvent('release', this.history[0]);
    },
    rollback() {
      if (!this.history.length) return; this.setValue('releaseStatus', 'rolled-back'); this.emitEvent('rollback', this.history[0]);
    },
    serviceLabel(id) {
      const service = this.services.find(item => item.id === id); return service ? service.id + '@' + service.version : id;
    }
  }
};
</script>

<style scoped>

.dependency-release-planner{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.dependency-release-planner *{box-sizing:border-box}
.dependency-release-planner h2,.dependency-release-planner h3,.dependency-release-planner p{margin-top:0}
.dependency-release-planner button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.dependency-release-planner button.primary{border-color:#4f46e5;background:#4f46e5;color:#fff}
.dependency-release-planner button:disabled{opacity:.45;cursor:not-allowed}
.dependency-release-planner input,.dependency-release-planner select,.dependency-release-planner textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.dependency-release-planner .muted{color:#71808e;font-size:12px}
.dependency-release-planner .toolbar,.dependency-release-planner .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.release-layout{display:grid;grid-template-columns:180px 1fr 190px;gap:12px}.release-layout>aside{padding:10px;background:#f8fafc}.release-layout>aside>button{display:grid;width:100%;margin:6px 0;text-align:left}.release-layout>aside>button.selected{background:#e0e7ff}.release-layout main{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.wave{min-height:260px;padding:9px;border:1px dashed #818cf8}.wave header{display:block}.wave article{display:flex;justify-content:space-between;padding:8px;margin-top:7px;background:#eef2ff}.gate button{width:100%;margin:4px 0}.good{color:#15803d}.bad{color:#b91c1c}
</style>
