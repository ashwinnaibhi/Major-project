import test from 'node:test';
import assert from 'node:assert/strict';

function normalizeEmergencyAction(action) {
  const clean = String(action || '').trim().toUpperCase();
  if (clean === 'ACCEPT') return 'ACCEPTED';
  if (clean === 'REJECT') return 'REJECTED';
  return clean;
}

test('normalizes ACCEPT to ACCEPTED', () => {
  assert.equal(normalizeEmergencyAction('ACCEPT'), 'ACCEPTED');
  assert.equal(normalizeEmergencyAction('accept'), 'ACCEPTED');
  assert.equal(normalizeEmergencyAction(' ACCEPT '), 'ACCEPTED');
});

test('normalizes REJECT to REJECTED', () => {
  assert.equal(normalizeEmergencyAction('REJECT'), 'REJECTED');
  assert.equal(normalizeEmergencyAction('reject'), 'REJECTED');
  assert.equal(normalizeEmergencyAction(' REJECT '), 'REJECTED');
});

test('preserves canonical actions ACCEPTED and REJECTED', () => {
  assert.equal(normalizeEmergencyAction('ACCEPTED'), 'ACCEPTED');
  assert.equal(normalizeEmergencyAction('REJECTED'), 'REJECTED');
});

test('emergency response payload creation sends canonical action', () => {
  const createPayload = (action) => ({ action: normalizeEmergencyAction(action) });
  assert.deepEqual(createPayload('ACCEPT'), { action: 'ACCEPTED' });
  assert.deepEqual(createPayload('REJECT'), { action: 'REJECTED' });
  assert.deepEqual(createPayload('ACCEPTED'), { action: 'ACCEPTED' });
  assert.deepEqual(createPayload('REJECTED'), { action: 'REJECTED' });
});
