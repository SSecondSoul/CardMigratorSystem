<template>
  <section class="meeting-poll-scheduler"><header><h2>会议时间投票</h2><select :value="participant" @change="updateParticipant"><option v-for="name in participants" :key="name" :value="name">{{ name }}</option></select></header><div class="slots"><article v-for="slot in slots" :key="slot.id" :class="slot.id === bestId ? 'best' : ''"><strong>{{ slot.label }}</strong><span>{{ voteCount(slot.id, votes) }} 票</span><button :class="hasVote(slot.id, participant, votes) ? 'selected' : ''" @click="toggleVote(slot.id)">{{ hasVote(slot.id, participant, votes) ? '取消可参加' : '我可参加' }}</button><button @click="confirm(slot.id)">确定此时间</button></article></div><p v-if="confirmedId">已确定候选 #{{ confirmedId }}</p></section>
</template>

<script>
module.exports = {
  name: 'MeetingPollScheduler',
  props: {
    participants: { type: Array, default: () => ([
          "林晓",
          "周宁",
          "陈雨"
        ]) },
    slots: { type: Array, default: () => ([
          {
            "id": 1,
            "label": "周二 10:00"
          },
          {
            "id": 2,
            "label": "周三 14:00"
          },
          {
            "id": 3,
            "label": "周五 16:00"
          }
        ]) }
  },
  data() {
    return {
        participant: "林晓",
        votes: {},
        confirmedId: null
    };
  },
  computed: {
    bestId() {
      const votes = this.votes || {}; const rows = this.slots.slice().sort((a, b) => ((votes[b.id] || []).length - (votes[a.id] || []).length)); return rows[0] ? rows[0].id : null;
    }
  },
  created() {
    const votes = {}; this.slots.forEach(slot => votes[slot.id] = []); this.setValue('votes', votes); this.setValue('participant', this.participants[0] || '');
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    updateParticipant(event) {
      this.setValue('participant', event.target.value);
    },
    toggleVote(slotId) {
      const votes = Object.assign({}, this.votes); const list = votes[slotId].slice(); const index = list.indexOf(this.participant); votes[slotId] = index >= 0 ? list.filter(name => name !== this.participant) : list.concat(this.participant); this.setValue('votes', votes); this.emitEvent('vote', { slotId, participants: votes[slotId] });
    },
    hasVote(slotId, participant, votes) {
      return votes[slotId].indexOf(participant) >= 0;
    },
    voteCount(slotId, votes) {
      return votes[slotId].length;
    },
    confirm(id) {
      this.setValue('confirmedId', id); this.emitEvent('confirm', id);
    }
  }
};
</script>

<style scoped>

.meeting-poll-scheduler{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.meeting-poll-scheduler *{box-sizing:border-box}
.meeting-poll-scheduler h2,.meeting-poll-scheduler h3,.meeting-poll-scheduler p{margin-top:0}
.meeting-poll-scheduler button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.meeting-poll-scheduler button.primary{border-color:#0369a1;background:#0369a1;color:#fff}
.meeting-poll-scheduler button:disabled{opacity:.45;cursor:not-allowed}
.meeting-poll-scheduler input,.meeting-poll-scheduler select,.meeting-poll-scheduler textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.meeting-poll-scheduler .muted{color:#71808e;font-size:12px}
.meeting-poll-scheduler .toolbar,.meeting-poll-scheduler .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}.slots{display:grid;gap:8px}.slots article{display:grid;grid-template-columns:1fr 55px auto auto;gap:8px;align-items:center;padding:10px;border:1px solid #e2e8f0}.slots article.best{border-color:#0369a1;background:#f0f9ff}.slots button.selected{background:#dbeafe}
</style>
