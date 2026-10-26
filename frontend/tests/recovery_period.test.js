import test from 'node:test';
import assert from 'node:assert/strict';
import {
  RECOVERY_PERIOD_MESSAGE,
  addThreeCalendarMonths,
  calculateRecoveryEligibility
} from '../src/utils/recoveryPeriod.js';

test('addThreeCalendarMonths correctly adds 3 calendar months with month-end clamping for April', () => {
  // Jan 31 + 3 months -> Apr 30 (April has only 30 days)
  assert.equal(addThreeCalendarMonths('2026-01-31'), '2026-04-30');
});

test('addThreeCalendarMonths clamps to Feb 29 in leap year (2024)', () => {
  // Nov 30, 2023 + 3 months -> Feb 29, 2024
  assert.equal(addThreeCalendarMonths('2023-11-30'), '2024-02-29');
});

test('addThreeCalendarMonths clamps to Feb 28 in non-leap year (2025)', () => {
  // Nov 30, 2024 + 3 months -> Feb 28, 2025
  assert.equal(addThreeCalendarMonths('2024-11-30'), '2025-02-28');
});

test('addThreeCalendarMonths clamps March 31 to June 30', () => {
  assert.equal(addThreeCalendarMonths('2026-03-31'), '2026-06-30');
});

test('addThreeCalendarMonths clamps August 31 to November 30', () => {
  assert.equal(addThreeCalendarMonths('2026-08-31'), '2026-11-30');
});

test('addThreeCalendarMonths preserves mid-month days and rolls over years', () => {
  assert.equal(addThreeCalendarMonths('2026-05-15'), '2026-08-15');
  assert.equal(addThreeCalendarMonths('2026-10-12'), '2027-01-12');
  assert.equal(addThreeCalendarMonths('2026-12-05'), '2027-03-05');
});

test('calculateRecoveryEligibility returns eligible for donors with no previous donations', () => {
  const res1 = calculateRecoveryEligibility(null);
  assert.equal(res1.eligible, true);
  assert.equal(res1.recoveryPeriodActive, false);
  assert.equal(res1.lastDonationDate, null);
  assert.equal(res1.earliestEligibleDate, null);

  const res2 = calculateRecoveryEligibility('');
  assert.equal(res2.eligible, true);
  assert.equal(res2.recoveryPeriodActive, false);
});

test('calculateRecoveryEligibility marks donor ineligible if less than 3 calendar months elapsed', () => {
  // Last donated 2026-04-10, evaluated on 2026-05-01
  const result = calculateRecoveryEligibility('2026-04-10', '2026-05-01');
  assert.equal(result.eligible, false);
  assert.equal(result.recoveryPeriodActive, true);
  assert.equal(result.lastDonationDate, '2026-04-10');
  assert.equal(result.earliestEligibleDate, '2026-07-10');
  assert.equal(result.message, RECOVERY_PERIOD_MESSAGE);
  assert.equal(
    result.message,
    'You must wait for the recovery period to complete before booking another blood donation appointment.'
  );
});

test('calculateRecoveryEligibility marks donor eligible when 3 calendar months have elapsed', () => {
  // Last donated 2026-01-15, evaluated on 2026-04-15
  const resultExact = calculateRecoveryEligibility('2026-01-15', '2026-04-15');
  assert.equal(resultExact.eligible, true);
  assert.equal(resultExact.recoveryPeriodActive, false);
  assert.equal(resultExact.earliestEligibleDate, '2026-04-15');

  // Last donated 2025-10-01, evaluated on 2026-04-15
  const resultPast = calculateRecoveryEligibility('2025-10-01', '2026-04-15');
  assert.equal(resultPast.eligible, true);
  assert.equal(resultPast.recoveryPeriodActive, false);
});
