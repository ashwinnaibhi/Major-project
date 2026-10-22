import test from 'node:test';
import assert from 'node:assert/strict';
import { getNextUpcomingAppointment } from '../src/utils/appointments.js';

test('selects the nearest actual upcoming scheduled appointment by date and time', () => {
  const now = new Date(2026, 9, 22, 10, 0);
  const appointments = [
    { id: 1, appointment_date: '2026-10-22', time_slot: 'Morning (8 AM - 12 PM)', status: 'SCHEDULED' },
    { id: 2, appointment_date: '2026-10-24', time_slot: 'Morning (8 AM - 12 PM)', status: 'SCHEDULED' },
    { id: 3, appointment_date: '2026-10-22', time_slot: 'Evening (4 PM - 8 PM)', status: 'SCHEDULED' },
    { id: 4, appointment_date: '2026-10-23', time_slot: 'Morning (8 AM - 12 PM)', status: 'PENDING' }
  ];
  assert.equal(getNextUpcomingAppointment(appointments, now).id, 3);
});

test('excludes cancelled, completed, no-show, past, and unrecognized appointment states', () => {
  const now = new Date(2026, 9, 22, 10, 0);
  const appointments = [
    { id: 1, appointment_date: '2026-10-23', time_slot: 'Morning (8 AM - 12 PM)', status: 'CANCELLED' },
    { id: 2, appointment_date: '2026-10-23', time_slot: 'Morning (8 AM - 12 PM)', status: 'COMPLETED' },
    { id: 3, appointment_date: '2026-10-21', time_slot: 'Evening (4 PM - 8 PM)', status: 'SCHEDULED' },
    { id: 4, appointment_date: '2026-10-23', time_slot: 'Morning (8 AM - 12 PM)', status: 'NO_SHOW' },
    { id: 5, appointment_date: '2026-10-23', time_slot: 'Morning (8 AM - 12 PM)', status: 'UNKNOWN' }
  ];
  assert.equal(getNextUpcomingAppointment(appointments, now), null);
});

test('returns a clear no-appointment result for empty or missing input', () => {
  assert.equal(getNextUpcomingAppointment([], new Date(2026, 9, 22, 10, 0)), null);
  assert.equal(getNextUpcomingAppointment(null, new Date(2026, 9, 22, 10, 0)), null);
});

test('does not guess that an already-started or same-day unknown-time appointment is upcoming', () => {
  const now = new Date(2026, 9, 22, 10, 0);
  const appointments = [
    { id: 1, appointment_date: '2026-10-22', time_slot: 'Morning (8 AM - 12 PM)', status: 'SCHEDULED' },
    { id: 2, appointment_date: '2026-10-22', time_slot: 'TBD', status: 'SCHEDULED' }
  ];
  assert.equal(getNextUpcomingAppointment(appointments, now), null);
});
