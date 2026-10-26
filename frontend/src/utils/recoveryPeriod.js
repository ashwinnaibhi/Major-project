/**
 * HaemoPulse 3-Calendar-Month Recovery Period Utility
 * Implements clinical recovery validation for blood donation appointments.
 * Handles month-end clamping and leap years correctly.
 */

export const RECOVERY_PERIOD_MESSAGE =
  'You must wait for the recovery period to complete before booking another blood donation appointment.';

export const ACTIVE_APPOINTMENT_MESSAGE =
  'You already have an active blood donation appointment. Please complete or cancel your existing appointment before booking another.';

export const ACTIVE_APPOINTMENT_STATUSES = ['SCHEDULED', 'PENDING', 'CONFIRMED', 'APPROVED'];

/**
 * Adds exactly three calendar months to a given date string or Date object.
 * Clamps to month-end when the target month has fewer days than the start day.
 * Example:
 *   2026-01-31 -> 2026-04-30
 *   2025-11-30 -> 2026-02-28
 *   2023-11-30 -> 2024-02-29 (leap year)
 *   2026-03-31 -> 2026-06-30
 *
 * @param {string | Date} dateInput
 * @returns {string | null} YYYY-MM-DD string
 */
export function addThreeCalendarMonths(dateInput) {
  if (!dateInput) return null;
  const str = typeof dateInput === 'string'
    ? dateInput.trim().slice(0, 10)
    : dateInput.toISOString().slice(0, 10);

  const parts = str.split('-').map(Number);
  if (parts.length !== 3 || parts.some(isNaN)) return null;
  const [year, month, day] = parts;

  // month is 1-indexed (1 = Jan, 12 = Dec)
  const targetMonthRaw = month + 3;
  const targetYear = year + Math.floor((targetMonthRaw - 1) / 12);
  const targetMonth = ((targetMonthRaw - 1) % 12) + 1;

  // Find max days in target month via Date(year, monthIndex, 0)
  const maxDays = new Date(targetYear, targetMonth, 0).getDate();
  const clampedDay = Math.min(day, maxDays);

  return `${targetYear}-${String(targetMonth).padStart(2, '0')}-${String(clampedDay).padStart(2, '0')}`;
}

/**
 * Calculates recovery eligibility given a last completed donation date and current date.
 *
 * @param {string | null | undefined} lastDonationDate
 * @param {string | Date} [currentDateInput]
 * @returns {{ eligible: boolean, recoveryPeriodActive: boolean, lastDonationDate: string | null, earliestEligibleDate: string | null, message: string }}
 */
export function calculateRecoveryEligibility(lastDonationDate, currentDateInput) {
  if (!lastDonationDate) {
    return {
      eligible: true,
      recoveryPeriodActive: false,
      lastDonationDate: null,
      earliestEligibleDate: null,
      message: 'Eligible to book an appointment.'
    };
  }

  const cleanLastDate = String(lastDonationDate).trim().slice(0, 10);
  const earliestEligible = addThreeCalendarMonths(cleanLastDate);
  if (!earliestEligible) {
    return {
      eligible: true,
      recoveryPeriodActive: false,
      lastDonationDate: cleanLastDate,
      earliestEligibleDate: null,
      message: 'Eligible to book an appointment.'
    };
  }

  const nowStr = currentDateInput
    ? (typeof currentDateInput === 'string' ? currentDateInput.trim().slice(0, 10) : currentDateInput.toISOString().slice(0, 10))
    : new Date().toISOString().slice(0, 10);

  // Eligible only if current date is on or after earliest eligible date
  const isEligible = nowStr >= earliestEligible;

  return {
    eligible: isEligible,
    recoveryPeriodActive: !isEligible,
    lastDonationDate: cleanLastDate,
    earliestEligibleDate: earliestEligible,
    message: isEligible ? 'Eligible to book an appointment.' : RECOVERY_PERIOD_MESSAGE
  };
}
