// Browser-serializable pure helper, shared by the live runner and offline checks.
function calculateCls(shifts) {
  let max = 0, sum = 0, start = null, last = null;
  for (const shift of shifts.filter(s => !s.hadRecentInput)) {
    if (last === null || shift.startTime - last >= 1000 || shift.startTime - start >= 5000) {
      sum = 0;
      start = shift.startTime;
    }
    sum += shift.value;
    last = shift.startTime;
    max = Math.max(max, sum);
  }
  return max;
}

module.exports = { calculateCls };
