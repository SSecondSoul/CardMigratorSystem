<template>
  <section class="clinical-triage-board"><header><div><small>等待 {{ waitingCount }} 人 · 空床 {{ freeBeds.length }} 张</small><h2>{{ unitName }}</h2></div><div class="filters"><button v-for="level in ['all','red','orange','yellow','green']" :key="level" :class="filter === level ? 'active' : ''" @click="setFilter(level)">{{ level }}</button></div></header><div class="triage-layout"><aside class="queue"><button v-for="patient in queue" :key="patient.id" :class="(selectedPatientId === patient.id ? 'selected ' : '') + patient.level" @click="selectPatient(patient.id)"><b>{{ patient.level }}</b><strong>{{ patient.name }} · {{ patient.age }}岁</strong><span>血氧 {{ patient.oxygen }}% · 脉搏 {{ patient.pulse }}</span></button></aside><main v-if="selectedPatient"><h3>{{ selectedPatient.name }} 的体征</h3><div class="vitals"><label>血氧<input type="number" :value="selectedPatient.oxygen" @input="updateVital('oxygen', $event)"></label><label>脉搏<input type="number" :value="selectedPatient.pulse" @input="updateVital('pulse', $event)"></label><label>疼痛<input type="number" :value="selectedPatient.pain" @input="updateVital('pain', $event)"></label></div><select :value="clinician" @change="setClinician"><option v-for="person in clinicians" :key="person" :value="person">{{ person }}</option></select><h3>床位</h3><div class="beds"><button v-for="bed in beds" :key="bed.id" :class="(selectedBedId === bed.id ? 'selected ' : '') + bed.status" @click="chooseBed(bed.id)" :disabled="bed.status !== 'free'"><strong>{{ bed.id }}</strong><span>{{ bed.area }} · {{ bed.status }}</span></button></div><button class="primary" @click="assignBed" :disabled="!selectedBedId">确认收治</button><button @click="discharge">办理离院</button></main><main v-else class="empty">请选择患者查看详情</main><aside class="audit"><h3>审计记录</h3><ol><li v-for="entry in audit" :key="entry.id">{{ entry.clinician }} · {{ entry.action }}</li></ol></aside></div></section>
</template>

<script>
module.exports = {
  name: 'ClinicalTriageBoard',
  props: {
    unitName: { type: String, default: "急诊分诊台" },
    initialPatients: { type: Array, default: () => ([
          {
            "id": 1,
            "name": "王婷",
            "age": 32,
            "pulse": 118,
            "oxygen": 91,
            "pain": 7
          },
          {
            "id": 2,
            "name": "赵晨",
            "age": 67,
            "pulse": 88,
            "oxygen": 96,
            "pain": 3
          },
          {
            "id": 3,
            "name": "陈宇",
            "age": 19,
            "pulse": 105,
            "oxygen": 98,
            "pain": 5
          }
        ]) },
    initialBeds: { type: Array, default: () => ([
          {
            "id": "A01",
            "area": "复苏区",
            "status": "free"
          },
          {
            "id": "B03",
            "area": "观察区",
            "status": "free"
          },
          {
            "id": "B04",
            "area": "观察区",
            "status": "occupied"
          }
        ]) },
    clinicians: { type: Array, default: () => ([
          "林医生",
          "高护士",
          "周医生"
        ]) },
    oxygenCritical: { type: Number, default: 92 }
  },
  data() {
    return {
        patients: [],
        beds: [],
        selectedPatientId: null,
        selectedBedId: null,
        clinician: "林医生",
        audit: [],
        filter: "all"
    };
  },
  computed: {
    queue() {
      const ranks = { red: 1, orange: 2, yellow: 3, green: 4 }; return this.patients.filter(item => item.status !== 'discharged' && (this.filter === 'all' || item.level === this.filter)).slice().sort((a, b) => ranks[a.level] - ranks[b.level]);
    },
    selectedPatient() {
      return this.patients.find(item => item.id === this.selectedPatientId) || null;
    },
    freeBeds() {
      return this.beds.filter(item => item.status === 'free');
    },
    waitingCount() {
      return this.patients.filter(item => item.status === 'waiting').length;
    }
  },
  created() {
    this.setValue('patients', this.initialPatients.map(item => Object.assign({}, item, { level: this.triageLevel(item), status: 'waiting' }))); this.setValue('beds', this.initialBeds.map(item => Object.assign({}, item)));
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    triageLevel(patient) {
      if (patient.oxygen <= this.oxygenCritical || patient.pulse >= 130) return 'red'; if (patient.pain >= 7 || patient.pulse >= 115) return 'orange'; if (patient.pain >= 4) return 'yellow'; return 'green';
    },
    selectPatient(id) {
      this.setValue('selectedPatientId', id); this.setValue('selectedBedId', null);
    },
    setFilter(value) {
      this.setValue('filter', value);
    },
    updateVital(field, event) {
      if (!this.selectedPatient) return; const value = Number(event.target.value) || 0; this.setValue('patients', this.patients.map(patient => patient.id === this.selectedPatientId ? Object.assign({}, patient, { [field]: value, level: this.triageLevel(Object.assign({}, patient, { [field]: value })) }) : patient)); this.record('更新体征 ' + field); this.emitEvent('triage', this.selectedPatient);
    },
    chooseBed(id) {
      this.setValue('selectedBedId', id);
    },
    assignBed() {
      if (!this.selectedPatient || !this.selectedBedId) return; const patientId = this.selectedPatientId; const bedId = this.selectedBedId; this.setValue('patients', this.patients.map(item => item.id === patientId ? Object.assign({}, item, { status: 'assigned', bedId, clinician: this.clinician }) : item)); this.setValue('beds', this.beds.map(item => item.id === bedId ? Object.assign({}, item, { status: 'occupied', patientId }) : item)); this.record('分配床位 ' + bedId); this.emitEvent('assign', { patientId, bedId });
    },
    discharge() {
      if (!this.selectedPatient) return; const bedId = this.selectedPatient.bedId; const patientId = this.selectedPatientId; this.setValue('patients', this.patients.map(item => item.id === patientId ? Object.assign({}, item, { status: 'discharged' }) : item)); if (bedId) this.setValue('beds', this.beds.map(item => item.id === bedId ? Object.assign({}, item, { status: 'free', patientId: null }) : item)); this.record('患者离院'); this.emitEvent('discharge', patientId);
    },
    setClinician(event) {
      this.setValue('clinician', event.target.value);
    },
    record(action) {
      this.setValue('audit', [{ id: Date.now(), action, patientId: this.selectedPatientId, clinician: this.clinician }].concat(this.audit).slice(0, 6));
    }
  }
};
</script>

<style scoped>

.clinical-triage-board{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.clinical-triage-board *{box-sizing:border-box}
.clinical-triage-board h2,.clinical-triage-board h3,.clinical-triage-board p{margin-top:0}
.clinical-triage-board button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.clinical-triage-board button.primary{border-color:#dc2626;background:#dc2626;color:#fff}
.clinical-triage-board button:disabled{opacity:.45;cursor:not-allowed}
.clinical-triage-board input,.clinical-triage-board select,.clinical-triage-board textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.clinical-triage-board .muted{color:#71808e;font-size:12px}
.clinical-triage-board .toolbar,.clinical-triage-board .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.filters{display:flex;gap:4px}.filters button.active{background:#0f172a;color:white}.triage-layout{display:grid;grid-template-columns:220px 1fr 190px;gap:12px}.queue>button{display:grid;width:100%;text-align:left;margin-bottom:7px;border-left:7px solid}.queue>button.red{border-left-color:#dc2626}.queue>button.orange{border-left-color:#f97316}.queue>button.yellow{border-left-color:#eab308}.queue>button.green{border-left-color:#16a34a}.queue>button.selected{background:#f1f5f9}.vitals{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.vitals label{display:grid}.beds{display:flex;gap:8px;margin:10px 0}.beds button{display:grid}.beds button.selected{border-color:#dc2626}.beds button.occupied{opacity:.45}.audit{padding:10px;background:#f8fafc}.audit ol{padding-left:20px}
</style>
