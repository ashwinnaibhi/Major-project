const UPCOMING_APPOINTMENT_STATUSES = new Set(['SCHEDULED', 'PENDING']);

function appointmentDateParts(appointment) {
  const value = String(appointment?.appointment_date || appointment?.date || '').trim();
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
  return { year, month, day, key: `${match[1]}-${match[2]}-${match[3]}` };
}

function appointmentStartMinutes(appointment) {
  const slot = String(appointment?.time_slot || '').trim();
  const match = slot.match(/(\d{1,2})(?::(\d{2}))?\s*(AM|PM)/i);
  if (match) {
    let hours = Number(match[1]) % 12;
    const minutes = Number(match[2] || 0);
    if (match[3].toUpperCase() === 'PM') hours += 12;
    if (hours > 23 || minutes > 59) return null;
    return hours * 60 + minutes;
  }

  // Legacy records sometimes store only a named time slot.
  if (/\bmorning\b/i.test(slot)) return 8 * 60;
  if (/\bafternoon\b/i.test(slot)) return 12 * 60;
  if (/\bevening\b/i.test(slot)) return 16 * 60;
  return null;
}

/** Return the nearest future appointment with a status the application treats as active. */
export function getNextUpcomingAppointment(appointments, now = new Date()) {
  if (!Array.isArray(appointments)) return null;
  const todayKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  const currentMinutes = now.getHours() * 60 + now.getMinutes();

  const eligible = appointments.flatMap((appointment) => {
    const status = String(appointment?.status || '').trim().toUpperCase();
    if (!UPCOMING_APPOINTMENT_STATUSES.has(status)) return [];
    const parts = appointmentDateParts(appointment);
    if (!parts || parts.key < todayKey) return [];
    const startMinutes = appointmentStartMinutes(appointment);
    if (parts.key === todayKey && (startMinutes == null || startMinutes <= currentMinutes)) return [];
    return [{ appointment, dateKey: parts.key, startMinutes: startMinutes ?? Number.POSITIVE_INFINITY }];
  });

  eligible.sort((left, right) => left.dateKey.localeCompare(right.dateKey)
    || left.startMinutes - right.startMinutes
    || Number(left.appointment.id || 0) - Number(right.appointment.id || 0));
  return eligible.length ? eligible[0].appointment : null;
}
