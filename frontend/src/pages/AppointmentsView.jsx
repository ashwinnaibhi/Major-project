import React, { useCallback, useEffect, useState } from 'react';
import { CalendarCheck, Check, Clock, UserCheck, RefreshCw } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

export default function AppointmentsView({ currentUser, activeRole }) {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const canManage = ['ADMIN', 'STAFF'].includes(activeRole) && currentUser?.role === activeRole && Boolean(currentUser?.token);
  const canView = ['ADMIN', 'HOSPITAL', 'STAFF'].includes(activeRole) && currentUser?.role === activeRole && Boolean(currentUser?.token);

  const loadAppointments = useCallback(async () => {
    if (!canView) {
      setAppointments([]);
      setError('Sign in with an authorized administrator, hospital, or staff account to view persisted appointments.');
      return;
    }
    setLoading(true); setError('');
    try {
      const response = await fetch(`${API_BASE}/api/v1/appointments`, { headers: { Authorization: `Bearer ${currentUser.token}` } });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Appointment retrieval failed (HTTP ${response.status}).`);
      if (!Array.isArray(data)) throw new Error('The appointment API returned an unexpected response.');
      setAppointments(data);
    } catch (err) {
      setAppointments([]); setError(err.message || 'Appointments could not be loaded.');
    } finally { setLoading(false); }
  }, [canView, currentUser?.token]);

  useEffect(() => { loadAppointments(); }, [loadAppointments]);

  const updateStatus = async (appointment) => {
    if (!canManage || busyId !== null) return;
    setBusyId(appointment.id); setError(''); setNotice('');
    try {
      const response = await fetch(`${API_BASE}/api/v1/appointments/${appointment.id}/status?status=COMPLETED`, {
        method: 'PUT', headers: { Authorization: `Bearer ${currentUser.token}` }
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Appointment update failed (HTTP ${response.status}).`);
      setNotice(`Appointment #${appointment.id} status was saved as COMPLETED.`);
      await loadAppointments();
    } catch (err) { setError(err.message || 'Appointment update failed.'); }
    finally { setBusyId(null); }
  };

  return (
    <div className="space-y-6">
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-blood-400 mb-1"><CalendarCheck className="w-4 h-4" /><span>Database-backed scheduling</span></div>
          <h2 className="text-2xl font-black text-white">Donor Appointment Calendar</h2>
          <p className="text-xs text-slate-400">Records below are retrieved from the backend; status changes require an authorized staff or administrator account.</p>
        </div>
        <button type="button" onClick={loadAppointments} disabled={loading} className="shrink-0 rounded-lg bg-slate-800 border border-slate-700 p-2 text-slate-200 disabled:opacity-50" aria-label="Refresh appointments"><RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /></button>
      </div>

      {error && <div role="alert" className="rounded-xl border border-rose-800 bg-rose-950/60 p-3 text-xs text-rose-200">{error}</div>}
      {notice && <div role="status" className="rounded-xl border border-emerald-800 bg-emerald-950/50 p-3 text-xs text-emerald-200">{notice}</div>}

      <div className="p-5 rounded-2xl glass-panel border border-slate-800">
        {loading && <p className="p-4 text-xs text-slate-400">Loading persisted appointment records…</p>}
        {!loading && canView && appointments.length === 0 && <p className="p-8 text-center text-sm text-slate-400">No appointments are recorded in the database.</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800"><tr><th className="py-3 px-4">Donor Name</th><th className="py-3 px-4">Blood Group</th><th className="py-3 px-4">Appointment Date</th><th className="py-3 px-4">Time Slot</th><th className="py-3 px-4">Status</th><th className="py-3 px-4">Action</th></tr></thead>
            <tbody className="divide-y divide-slate-800/60">
              {appointments.map((item) => <tr key={item.id} className="hover:bg-slate-900/40">
                <td className="py-3 px-4 font-bold text-white"><span className="inline-flex items-center gap-2"><UserCheck className="w-4 h-4 text-blood-400" />{item.donor_name || 'Name not recorded'}</span></td>
                <td className="py-3 px-4 font-extrabold text-blood-400 text-sm">{item.blood_group || '—'}</td>
                <td className="py-3 px-4 text-slate-300 font-mono">{item.appointment_date || '—'}</td>
                <td className="py-3 px-4 text-slate-300"><span className="inline-flex items-center gap-1"><Clock className="w-3 h-3" />{item.time_slot || '—'}</span></td>
                <td className="py-3 px-4"><span className={`px-2 py-0.5 rounded text-[10px] font-bold ${item.status === 'COMPLETED' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-amber-950 text-amber-400 border border-amber-800'}`}>{item.status || 'UNKNOWN'}</span></td>
                <td className="py-3 px-4">{canManage && item.status === 'SCHEDULED' ? <button type="button" disabled={busyId !== null} onClick={() => updateStatus(item)} className="px-2.5 py-1 rounded bg-emerald-950 hover:bg-emerald-900 text-emerald-300 border border-emerald-800 text-[11px] font-semibold flex items-center gap-1 disabled:opacity-50"><Check className="w-3 h-3" />{busyId === item.id ? 'Saving…' : 'Mark appointment completed'}</button> : <span className="text-slate-500 text-[11px]">—</span>}</td>
              </tr>)}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[11px] text-slate-500">Changing appointment status records the appointment workflow only; it does not automatically create a verified donation record.</p>
      </div>
    </div>
  );
}
