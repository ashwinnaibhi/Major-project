import React, { useState, useEffect } from 'react';
import { FileText, Plus, CheckCircle, XCircle, Clock, ShieldAlert, Trash2 } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

export default function RequestsView({ requestsList = [], onRequestCreated, onRequestStatusChange, onRequestDeleted, onRequestAssignmentsChange, currentUser }) {
  const [showModal, setShowModal] = useState(false);
  const [newReq, setNewReq] = useState({
    hospital: '', hospital_address: '', contact_phone: '', blood: 'O+', units: 2,
    urgency: 'HIGH', patient: '', hospital_user_id: '', assigned_admin_user_id: ''
  });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [noticeIsError, setNoticeIsError] = useState(false);
  const [assignees, setAssignees] = useState({ hospitals: [], admins: [] });
  const [assigneeLoadError, setAssigneeLoadError] = useState('');
  const [assignmentDrafts, setAssignmentDrafts] = useState({});
  const [notificationDetails, setNotificationDetails] = useState({});
  const [notificationBusy, setNotificationBusy] = useState({});
  const [notificationErrors, setNotificationErrors] = useState({});

  useEffect(() => {
    if (!currentUser?.token) return;
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/notification-assignees`, { headers: { Authorization: `Bearer ${currentUser.token}` } })
      .then(async (response) => { const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.detail || 'Assignment list unavailable.'); return data; })
      .then((data) => { if (!cancelled) setAssignees({ hospitals: data.hospitals || [], admins: data.admins || [] }); })
      .catch((error) => { if (!cancelled) setAssigneeLoadError(error.message); });
    return () => { cancelled = true; };
  }, [currentUser?.token]);

  const loadNotificationDetails = async (requestId) => {
    if (!currentUser?.token) {
      setNotificationErrors((prev) => ({ ...prev, [requestId]: 'Sign in to inspect notification status.' }));
      return;
    }
    setNotificationBusy((prev) => ({ ...prev, [requestId]: true }));
    setNotificationErrors((prev) => ({ ...prev, [requestId]: '' }));
    try {
      const response = await fetch(`${API_BASE}/api/v1/notifications/requests/${requestId}`, {
        headers: { Authorization: `Bearer ${currentUser.token}` }
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Could not load notification events (HTTP ${response.status}).`);
      setNotificationDetails((prev) => ({ ...prev, [requestId]: data }));
    } catch (error) {
      setNotificationErrors((prev) => ({ ...prev, [requestId]: error.message || 'Notification status is unavailable.' }));
    } finally {
      setNotificationBusy((prev) => ({ ...prev, [requestId]: false }));
    }
  };

  const retryNotification = async (requestId, notificationId) => {
    if (!currentUser?.token) return;
    setNotificationBusy((prev) => ({ ...prev, [requestId]: true }));
    setNotificationErrors((prev) => ({ ...prev, [requestId]: '' }));
    try {
      const response = await fetch(`${API_BASE}/api/v1/notifications/${notificationId}/retry`, {
        method: 'POST', headers: { Authorization: `Bearer ${currentUser.token}` }
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Retry could not be queued (HTTP ${response.status}).`);
      setNotice(data.message || `Notification #${notificationId} was returned to the queue.`);
      await loadNotificationDetails(requestId);
    } catch (error) {
      setNotificationErrors((prev) => ({ ...prev, [requestId]: error.message || 'Notification retry failed.' }));
    } finally {
      setNotificationBusy((prev) => ({ ...prev, [requestId]: false }));
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true); setNotice(''); setNoticeIsError(false);
    try {
      if (typeof onRequestCreated !== 'function') throw new Error('Request service is unavailable.');
      const saved = await onRequestCreated({
        hospital_name: newReq.hospital.trim(), hospital_address: newReq.hospital_address.trim(),
        contact_phone: newReq.contact_phone.trim(), blood_group: newReq.blood,
        units_needed: Number.parseInt(newReq.units, 10), urgency_level: newReq.urgency,
        patient_name: newReq.patient.trim(), destination_latitude: null, destination_longitude: null,
        hospital_user_id: newReq.hospital_user_id ? Number(newReq.hospital_user_id) : null,
        assigned_admin_user_id: newReq.assigned_admin_user_id ? Number(newReq.assigned_admin_user_id) : null
      });
      if (!saved || saved.id == null) throw new Error('The server did not confirm that the request was saved.');
      setNotice(`Request #${saved.id} was saved. ${saved.notification_summary?.message || 'Notification status is available in the notification monitor.'}`);
      setShowModal(false);
      setNewReq({ hospital: '', hospital_address: '', contact_phone: '', blood: 'O+', units: 2, urgency: 'HIGH', patient: '', hospital_user_id: '', assigned_admin_user_id: '' });
    } catch (error) {
      setNotice(error.message || 'The request could not be saved.'); setNoticeIsError(true);
    } finally { setBusy(false); }
  };

  const assignmentDraftFor = (req) => assignmentDrafts[req.id] || {
    hospital_user_id: req.hospital_user_id == null ? '' : String(req.hospital_user_id),
    assigned_admin_user_id: req.assigned_admin_user_id == null ? '' : String(req.assigned_admin_user_id)
  };

  const handleSaveAssignments = async (req) => {
    setNotice(''); setNoticeIsError(false);
    try {
      if (typeof onRequestAssignmentsChange !== 'function') throw new Error('Notification assignment service is unavailable.');
      const result = await onRequestAssignmentsChange(req.id, assignmentDraftFor(req));
      setNotice(result.message || `Notification routing for request #${req.id} was saved.`);
    } catch (error) {
      setNotice(error.message || 'Notification routing could not be saved.'); setNoticeIsError(true);
    }
  };

  const handleUpdateStatus = async (id, newStatus) => {
    setNotice(''); setNoticeIsError(false);
    try {
      if (typeof onRequestStatusChange !== 'function') throw new Error('Request status service is unavailable.');
      await onRequestStatusChange(id, newStatus);
      setNotice(`Request #${id} was updated to ${newStatus}.`);
    } catch (error) { setNotice(error.message || 'Request status update failed.'); setNoticeIsError(true); }
  };

  const handleDeleteRequest = async (id) => {
    if (!window.confirm(`Delete request #${id}? This cannot be undone.`)) return;
    setNotice(''); setNoticeIsError(false);
    try {
      if (typeof onRequestDeleted !== 'function') throw new Error('Request deletion service is unavailable.');
      await onRequestDeleted(id);
      setNotice(`Request #${id} was deleted.`);
    } catch (error) { setNotice(error.message || 'Request deletion failed.'); setNoticeIsError(true); }
  };

  return (
    <div className="space-y-6">
      
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-blood-400 mb-1">
            <FileText className="w-4 h-4" />
            <span>SQL Relational Database Requisitions</span>
          </div>
          <h2 className="text-2xl font-black text-white">Hospital Blood Requests (SQL CRUD)</h2>
          <p className="text-xs text-slate-400">Add, approve, fulfill, or dynamically delete hospital requisitions from SQL database.</p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-bold text-xs shadow-md glow-red flex items-center space-x-2"
        >
          <Plus className="w-4 h-4" />
          <span>New Hospital Requisition</span>
        </button>
      </div>

      {notice && <div role="status" className={`rounded-xl border p-3 text-xs ${noticeIsError ? 'border-rose-800 bg-rose-950/60 text-rose-200' : 'border-emerald-800 bg-emerald-950/50 text-emerald-200'}`}>{notice}</div>}

      <div className="p-5 rounded-2xl glass-panel border border-slate-800">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Hospital Name</th>
                <th className="py-3 px-4">Blood Group</th>
                <th className="py-3 px-4">Units Needed</th>
                <th className="py-3 px-4">Urgency Level</th>
                <th className="py-3 px-4">Patient / Reason</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Email notification state</th>
                <th className="py-3 px-4 min-w-[260px]">Responsible accounts</th>
                <th className="py-3 px-4">SQL Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {requestsList.map((req, idx) => (
                <tr key={req.id || req._id || idx} className="hover:bg-slate-900/40">
                  <td className="py-3 px-4 font-bold text-white">{req.hospital_name || req.hospital}</td>
                  <td className="py-3 px-4 font-extrabold text-blood-400 text-sm">{req.blood || req.blood_group}</td>
                  <td className="py-3 px-4 text-slate-200 font-semibold">{req.units || req.units_needed} units</td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold ${
                      (req.urgency || req.urgency_level) === 'EMERGENCY'
                        ? 'bg-blood-950 text-blood-400 border border-blood-800 animate-pulse'
                        : (req.urgency || req.urgency_level) === 'HIGH'
                        ? 'bg-amber-950 text-amber-400 border border-amber-800'
                        : 'bg-slate-800 text-slate-300'
                    }`}>
                      {req.urgency || req.urgency_level}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-400">{req.patient || req.patient_name}</td>
                  <td className="py-3 px-4 font-bold">
                    <span className={`${
                      req.status === 'APPROVED' ? 'text-emerald-400' :
                      req.status === 'FULFILLED' ? 'text-sky-400' : 'text-amber-400'
                    }`}>
                      {req.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 min-w-[220px] text-[10px] text-slate-300">
                    <div>{req.notification_summary?.message || (req.notification_status && Object.entries(req.notification_status).map(([status, count]) => `${status}: ${count}`).join(' · ')) || 'No notification events recorded yet.'}</div>
                    <button type="button" onClick={() => loadNotificationDetails(req.id)} disabled={Boolean(notificationBusy[req.id])}
                      className="mt-2 px-2 py-1 rounded border border-slate-700 bg-slate-900 text-slate-200 disabled:opacity-50">
                      {notificationBusy[req.id] ? 'Loading…' : notificationDetails[req.id] ? 'Refresh delivery events' : 'View delivery events'}
                    </button>
                    {notificationErrors[req.id] && <div role="alert" className="mt-1 text-rose-300">{notificationErrors[req.id]}</div>}
                    {notificationDetails[req.id] && <div className="mt-2 space-y-2">
                      <div>{Object.entries(notificationDetails[req.id].counts || {}).map(([status, count]) => `${status}: ${count}`).join(' · ') || 'No notification events.'}</div>
                      {(notificationDetails[req.id].notifications || []).map((event) => {
                        const retryable = event.status === 'FAILED' && /^HTTP_(429|408|425|5\d{2})$/.test(event.last_error_code || '');
                        return <div key={event.id} className="rounded border border-slate-800 bg-slate-950/60 p-2">
                          <div>{event.event_type.replaceAll('_', ' ')} — <strong>{event.status}</strong> (attempts: {event.attempt_count})</div>
                          {event.last_error_code && <div className="text-amber-300">{event.last_error_code}</div>}
                          {retryable && <button type="button" onClick={() => retryNotification(req.id, event.id)} disabled={Boolean(notificationBusy[req.id])}
                            className="mt-1 px-2 py-1 rounded bg-amber-950 text-amber-200 border border-amber-800 disabled:opacity-50">Retry transient failure</button>}
                        </div>;
                      })}
                    </div>}
                  </td>
                  <td className="py-3 px-4 min-w-[260px] space-y-2">
                    <label className="block text-[10px] text-slate-500">Hospital account</label>
                    <select value={assignmentDraftFor(req).hospital_user_id}
                      onChange={(e) => setAssignmentDrafts((prev) => ({ ...prev, [req.id]: { ...assignmentDraftFor(req), hospital_user_id: e.target.value } }))}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-[11px] text-white">
                      <option value="">Unassigned</option>
                      {assignees.hospitals.map((account) => <option key={account.id} value={String(account.id)}>{account.name} (#{account.id})</option>)}
                    </select>
                    <label className="block text-[10px] text-slate-500">Assigned admin (optional)</label>
                    <select value={assignmentDraftFor(req).assigned_admin_user_id}
                      onChange={(e) => setAssignmentDrafts((prev) => ({ ...prev, [req.id]: { ...assignmentDraftFor(req), assigned_admin_user_id: e.target.value } }))}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-[11px] text-white">
                      <option value="">Unassigned — requires review on acceptance</option>
                      {assignees.admins.map((account) => <option key={account.id} value={String(account.id)}>{account.name} (#{account.id})</option>)}
                    </select>
                    <button onClick={() => handleSaveAssignments(req)} className="px-2.5 py-1 rounded bg-sky-950 text-sky-200 border border-sky-800 text-[10px] font-semibold">Save notification routing</button>
                  </td>
                  <td className="py-3 px-4 flex items-center space-x-2">
                    {req.status === 'PENDING' && (
                      <>
                        <button
                          onClick={() => handleUpdateStatus(req.id || req._id, 'APPROVED')}
                          className="px-2.5 py-1 rounded bg-emerald-950 text-emerald-300 hover:bg-emerald-900 border border-emerald-800 text-[11px] font-semibold"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleUpdateStatus(req.id || req._id, 'REJECTED')}
                          className="px-2.5 py-1 rounded bg-rose-950 text-rose-300 hover:bg-rose-900 border border-rose-800 text-[11px]"
                        >
                          Reject
                        </button>
                      </>
                    )}
                    {req.status === 'APPROVED' && (
                      <button
                        onClick={() => handleUpdateStatus(req.id || req._id, 'FULFILLED')}
                        className="px-2 py-1 rounded bg-sky-950 text-sky-300 border border-sky-800 text-[11px]"
                      >
                        Mark Fulfilled
                      </button>
                    )}
                    <button
                      onClick={() => handleDeleteRequest(req.id || req._id)}
                      title="Delete Requisition from SQL DB"
                      className="p-1 rounded bg-rose-950 hover:bg-rose-900 text-rose-300 border border-rose-800 text-[11px]"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal for New Requisition */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center overflow-y-auto p-4" role="dialog" aria-modal="true" aria-labelledby="request-modal-title">
          <div className="my-auto w-full max-w-md max-h-[calc(100dvh-2rem)] overflow-y-auto overscroll-contain p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
            <h3 id="request-modal-title" className="text-lg font-extrabold text-white">Create Hospital Blood Request</h3>
            <form onSubmit={handleCreate} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Hospital Name</label>
                <input
                  type="text"
                  value={newReq.hospital}
                  onChange={(e) => setNewReq({ ...newReq, hospital: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  required
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Hospital Address *</label>
                <input type="text" value={newReq.hospital_address} onChange={(e) => setNewReq({ ...newReq, hospital_address: e.target.value })} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white" required />
              </div>
              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Contact Phone (optional)</label>
                <input type="tel" value={newReq.contact_phone} onChange={(e) => setNewReq({ ...newReq, contact_phone: e.target.value })} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-400 block mb-1 font-semibold">Blood Group</label>
                  <select
                    value={newReq.blood}
                    onChange={(e) => setNewReq({ ...newReq, blood: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  >
                    {['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'].map(b => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-slate-400 block mb-1 font-semibold">Units Needed</label>
                  <input
                    type="number" min="1" max="20"
                    value={newReq.units}
                    onChange={(e) => setNewReq({ ...newReq, units: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Urgency Level</label>
                <select
                  value={newReq.urgency}
                  onChange={(e) => setNewReq({ ...newReq, urgency: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                >
                  <option value="EMERGENCY">EMERGENCY (Critical Need)</option>
                  <option value="HIGH">HIGH (Urgent Surgery)</option>
                  <option value="NORMAL">NORMAL (Elective)</option>
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Patient Name / Ward</label>
                <input
                  type="text"
                  value={newReq.patient}
                  onChange={(e) => setNewReq({ ...newReq, patient: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  required
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Responsible hospital account {newReq.urgency === 'EMERGENCY' ? '*' : '(required for emergency notifications)'}</label>
                <select value={newReq.hospital_user_id} onChange={(e) => setNewReq({ ...newReq, hospital_user_id: e.target.value })}
                  required={newReq.urgency === 'EMERGENCY'} disabled={assignees.hospitals.length === 0}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white">
                  <option value="">Select a linked hospital account</option>
                  {assignees.hospitals.map((account) => <option key={account.id} value={account.id}>{account.name} (account #{account.id})</option>)}
                </select>
                {assigneeLoadError && <p className="mt-1 text-rose-300">{assigneeLoadError}</p>}
                {newReq.urgency === 'EMERGENCY' && assignees.hospitals.length === 0 && <p className="mt-1 text-amber-300">An active hospital account must exist and be selected. Do not use free-text names as account assignments.</p>}
              </div>
              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Assigned administrator (optional)</label>
                <select value={newReq.assigned_admin_user_id} onChange={(e) => setNewReq({ ...newReq, assigned_admin_user_id: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white">
                  <option value="">Leave unassigned for authorized resolution</option>
                  {assignees.admins.map((account) => <option key={account.id} value={account.id}>{account.name} (account #{account.id})</option>)}
                </select>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3">
                <button
                  type="button"
                  onClick={() => { if (!busy && window.confirm('Close this form and discard unsaved changes?')) setShowModal(false); }}
                  disabled={busy}
                  className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 font-semibold disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={busy}
                  className="px-4 py-2 rounded-xl bg-blood-600 hover:bg-blood-500 text-white font-bold disabled:opacity-50"
                >
                  {busy ? 'Saving…' : 'Submit Request'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
