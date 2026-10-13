<template>
  <section class="auction-control-room"><header><div><small>{{ roomName }} · {{ status }}</small><h2>{{ activeLot ? activeLot.title : '无拍品' }}</h2></div><output :class="seconds < 10 ? 'urgent' : ''">{{ clockLabel }}</output></header><nav><button v-for="lot in lots" :key="lot.id" :class="activeLotId === lot.id ? 'active' : ''" @click="switchLot(lot.id)">{{ lot.id }} {{ lot.title }}</button></nav><div class="auction-layout"><main><section class="price"><small>当前最高价</small><strong>¥{{ topBid ? topBid.amount : activeLot.reserve }}</strong><span>{{ topBid ? topBid.bidder : '尚无出价' }}</span></section><div class="bid-form"><select :value="bidder" @change="setBidder"><option v-for="person in bidders" :key="person" :value="person">{{ person }}</option></select><input type="number" :value="amount" @input="setAmount"><button class="primary" @click="placeBid" :disabled="!canBid">提交出价</button></div><div class="controls"><button @click="openLot">开始竞拍</button><button @click="togglePause" :disabled="status !== 'running' && status !== 'paused'">{{ status === 'paused' ? '继续' : '暂停' }}</button><button @click="closeLot">成交/流拍</button></div></main><aside><h3>实时出价队列</h3><article v-for="bid in activeBids" :key="bid.id" :class="isFlagged(bid.id, riskFlags) ? 'flagged' : ''"><strong>¥{{ bid.amount }}</strong><span>{{ bid.bidder }} · 剩余{{ bid.second }}秒</span><button @click="flagBid(bid.id)">{{ isFlagged(bid.id, riskFlags) ? '取消标记' : '风险标记' }}</button></article></aside></div><footer><span v-for="entry in audit" :key="entry.id">{{ entry.text }}</span></footer></section>
</template>

<script>
module.exports = {
  name: 'AuctionControlRoom',
  props: {
    roomName: { type: String, default: "当代艺术专场" },
    lots: { type: Array, default: () => ([
          {
            "id": "L01",
            "title": "山海之间",
            "reserve": 1200
          },
          {
            "id": "L02",
            "title": "蓝色构成",
            "reserve": 900
          },
          {
            "id": "L03",
            "title": "城市切片",
            "reserve": 1600
          }
        ]) },
    bidders: { type: Array, default: () => ([
          "B-108",
          "B-205",
          "B-311"
        ]) },
    initialSeconds: { type: Number, default: 45 },
    minIncrement: { type: Number, default: 100 }
  },
  data() {
    return {
        activeLotId: "L01",
        bidsByLot: {},
        bidder: "B-108",
        amount: 1300,
        seconds: 45,
        status: "preview",
        riskFlags: [],
        audit: [],
        timer: null
    };
  },
  computed: {
    activeLot() {
      return this.lots.find(item => item.id === this.activeLotId) || null;
    },
    activeBids() {
      return (this.bidsByLot[this.activeLotId] || []).slice().sort((a, b) => b.amount - a.amount);
    },
    topBid() {
      return this.activeBids[0] || null;
    },
    minimumBid() {
      return this.topBid ? this.topBid.amount + this.minIncrement : (this.activeLot ? this.activeLot.reserve : 0);
    },
    canBid() {
      return this.status === 'running' && this.seconds > 0 && this.amount >= this.minimumBid;
    },
    clockLabel() {
      return '00:' + String(this.seconds).padStart(2, '0');
    }
  },
  created() {
    const bids = {}; this.lots.forEach(lot => { bids[lot.id] = []; }); this.setValue('bidsByLot', bids); this.setValue('seconds', this.initialSeconds); this.setValue('amount', this.lots[0] ? this.lots[0].reserve + this.minIncrement : 0);
  },
  mounted() {
    this.startTimer();
  },
  beforeDestroy() {
    if (this.timer) clearInterval(this.timer);
  },
  methods: {
    setValue(key, value) { this[key] = value; },
    emitEvent(name, payload) { this.$emit(name, payload); },
    startTimer() {
      if (this.timer) return; const timer = setInterval(() => { if (this.status !== 'running') return; const next = Math.max(0, this.seconds - 1); this.setValue('seconds', next); if (next === 0) this.closeLot(); }, 1000); this.setValue('timer', timer);
    },
    switchLot(id) {
      this.setValue('activeLotId', id); this.setValue('seconds', this.initialSeconds); this.setValue('status', 'preview'); const lot = this.lots.find(item => item.id === id); this.setValue('amount', lot ? lot.reserve + this.minIncrement : 0);
    },
    openLot() {
      if (!this.activeLot) return; this.setValue('status', 'running'); this.setValue('seconds', this.initialSeconds); this.startTimer();
    },
    setBidder(event) {
      this.setValue('bidder', event.target.value);
    },
    setAmount(event) {
      this.setValue('amount', Number(event.target.value) || 0);
    },
    placeBid() {
      if (!this.canBid) return; const bid = { id: Date.now(), bidder: this.bidder, amount: this.amount, second: this.seconds }; const list = (this.bidsByLot[this.activeLotId] || []).concat(bid); this.setValue('bidsByLot', Object.assign({}, this.bidsByLot, { [this.activeLotId]: list })); this.setValue('seconds', Math.max(this.seconds, 12)); this.setValue('amount', this.amount + this.minIncrement); this.setValue('audit', [{ id: bid.id, text: this.bidder + ' 出价 ¥' + bid.amount }].concat(this.audit).slice(0, 8)); this.emitEvent('bid', bid);
    },
    togglePause() {
      this.setValue('status', this.status === 'paused' ? 'running' : 'paused');
    },
    flagBid(id) {
      const flags = this.riskFlags; this.setValue('riskFlags', flags.indexOf(id) >= 0 ? flags.filter(item => item !== id) : flags.concat(id)); this.emitEvent('flag', id);
    },
    closeLot() {
      if (this.status === 'closed') return; this.setValue('status', 'closed'); this.emitEvent('close', { lot: this.activeLotId, winner: this.topBid });
    },
    isFlagged(id, riskFlags) {
      return riskFlags.indexOf(id) >= 0;
    }
  }
};
</script>

<style scoped>

.auction-control-room{max-width:760px;margin:18px auto;padding:20px;border:1px solid #cfd6dd;border-radius:8px;background:#fff;color:#24313d;font-family:Arial,sans-serif;box-sizing:border-box}
.auction-control-room *{box-sizing:border-box}
.auction-control-room h2,.auction-control-room h3,.auction-control-room p{margin-top:0}
.auction-control-room button{padding:7px 11px;border:1px solid #aeb8c2;border-radius:5px;background:#fff;color:#273746;cursor:pointer}
.auction-control-room button.primary{border-color:#be123c;background:#be123c;color:#fff}
.auction-control-room button:disabled{opacity:.45;cursor:not-allowed}
.auction-control-room input,.auction-control-room select,.auction-control-room textarea{padding:8px;border:1px solid #b9c3cc;border-radius:5px;font:inherit}
.auction-control-room .muted{color:#71808e;font-size:12px}
.auction-control-room .toolbar,.auction-control-room .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
header{display:flex;justify-content:space-between}header output{font:700 34px monospace;padding:8px 16px;background:#0f172a;color:white}header output.urgent{background:#be123c}nav{display:flex;gap:7px;margin:10px 0}nav button.active{background:#ffe4e6;border-color:#be123c}.auction-layout{display:grid;grid-template-columns:1fr 300px;gap:14px}.auction-layout main{padding:18px;text-align:center;background:#fff1f2}.price strong,.price span{display:block}.price strong{font-size:42px}.bid-form{display:grid;grid-template-columns:1fr 1fr auto;gap:8px;margin:16px 0}.controls{display:flex;justify-content:center;gap:8px}.auction-layout aside article{display:grid;grid-template-columns:90px 1fr auto;padding:9px;border-bottom:1px solid #e2e8f0}.auction-layout aside article.flagged{background:#fef2f2;color:#b91c1c}footer{display:flex;gap:6px;overflow:auto;margin-top:10px}footer span{white-space:nowrap;padding:5px;background:#f8fafc}
</style>
