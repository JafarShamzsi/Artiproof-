const { test } = require('node:test');
const assert = require('node:assert/strict');
const { calculateCls } = require('./cls.cjs');

const shift = (startTime, value, hadRecentInput = false) => ({ startTime, value, hadRecentInput });

test('exact 1000ms gap resets the session', () => {
  assert.equal(calculateCls([shift(0, 0.125), shift(1000, 0.25)]), 0.25);
});

test('exact 5000ms span resets even with every gap below 1000ms', () => {
  const shifts = Array.from({ length: 11 }, (_, i) => shift(i * 500, i === 0 ? 0.125 : i === 10 ? 0.25 : 0));
  assert.equal(calculateCls(shifts), 0.25);
});

test('just below the gap boundary stays in the same session', () => {
  assert.equal(calculateCls([shift(0, 0.125), shift(999.999, 0.25)]), 0.375);
});

test('just below the span boundary stays in the same session', () => {
  const shifts = Array.from({ length: 10 }, (_, i) => shift(i * 500, i === 0 ? 0.125 : 0));
  shifts.push(shift(4999.999, 0.25));
  assert.equal(calculateCls(shifts), 0.375);
});

test('ignores recent-input shifts without extending a session', () => {
  assert.equal(calculateCls([shift(0, 0.125), shift(500, 10, true), shift(1000, 0.25)]), 0.25);
});

test('keeps the maximum window, not the sum of separate windows', () => {
  assert.equal(calculateCls([shift(0, 0.25), shift(250, 0.125), shift(2000, 0.125)]), 0.375);
});

test('empty or wholly input-associated shifts have observed score zero', () => {
  assert.equal(calculateCls([]), 0);
  assert.equal(calculateCls([shift(100, 1, true)]), 0);
});
