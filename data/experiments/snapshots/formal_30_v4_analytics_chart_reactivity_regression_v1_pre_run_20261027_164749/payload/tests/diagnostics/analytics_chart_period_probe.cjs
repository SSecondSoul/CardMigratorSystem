// Read-only San state probe for a standalone AnalyticsDashboard .san candidate.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const sourceFile = process.argv[2];
if (!sourceFile) throw new Error('Usage: node analytics_chart_period_probe.cjs <candidate.san>');
const source = fs.readFileSync(path.resolve(sourceFile), 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/);
if (!script) throw new Error('Missing San script block');
const context = {
  module: {exports: {}},
  require,
  console,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
};
vm.runInNewContext(script[1] + '\nmodule.exports.TrendChart = TrendChart;', context);
const TrendChart = context.module.exports.TrendChart;
const chart = new TrendChart();
for (const count of [30, 7, 90, 30]) {
  const data = Array.from({length: count}, (_, index) => ({value: 100 + index}));
  chart.data.set('data', data);
  const maxValue = chart.data.get('maxValue');
  const minValue = chart.data.get('minValue');
  const points = String(chart.data.get('linePoints') || '').trim().split(/\s+/);
  const areaPoints = String(chart.data.get('areaPoints') || '').trim().split(/\s+/);
  const finite = points.every(point => point.split(',').every(value => Number.isFinite(Number(value))));
  const aligned = points.every((point, index) => {
    const [x, y] = point.split(',').map(Number);
    return Math.abs(x - chart.getX(index, data.length)) < 0.5
      && Math.abs(y - chart.getY(data[index].value, maxValue, minValue)) < 0.5;
  });
  if (points.length !== count || areaPoints.length !== count + 2 || !finite || !aligned) {
    throw new Error(`Invalid ${count}-day chart: points=${points.length}, area=${areaPoints.length}, finite=${finite}, aligned=${aligned}`);
  }
  console.log(`${count}d: line=${points.length}, area=${areaPoints.length}, finite=${finite}, aligned=${aligned}`);
}
