// Recompute preserved observations without changing them or contacting a server.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { calculateCls } = require('./cls.cjs');

const files = process.argv.slice(2);
assert.ok(files.length > 0, 'Pass preserved report.json paths');
const samples = files.flatMap(file => {
  const report = JSON.parse(fs.readFileSync(file, 'utf8'));
  return report.runs.map(run => {
    assert.ok(Array.isArray(run.metrics.shifts), `${file}: ${run.label} has no raw shifts`);
    const previous = run.metrics.observedCls;
    const corrected = run.metrics.supported.includes('layout-shift')
      ? calculateCls(run.metrics.shifts) : null;
    return { file, label: run.label, previous, corrected, unchanged: previous === corrected };
  });
});
assert.ok(samples.length > 0, 'No preserved samples found');
console.log(JSON.stringify({ count: samples.length,
  changed: samples.filter(sample => !sample.unchanged).length, samples }, null, 2));
