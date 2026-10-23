import React, { useState, useEffect, useCallback } from 'react';
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';
import StatCard from '../components/StatCard';
import MLPredictionBadge from '../components/MLPredictionBadge';
import { Plus, FileText, CheckCircle2, Clock, MapPin, AlertCircle, Building2, X } from 'lucide-react';

export default function HospitalDashboard({ donorsList = [], requestsList = [], onRequestCreated, currentUser }) {
  const [showReqModal, setShowReqModal] = useState(false);
  const [newRequest, setNewRequest] = useState({
    hospital_name: '',
    hospital_address: '',
    contact_phone: '',
    blood_group: 'O-',
    units: 2,
    urgency: 'EMERGENCY',
    patient: '',
    destination_latitude: '',
    destination_longitude: '',
    assigned_admin_user_id: ''
  });
  const [formError, setFormError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [availableAdmins, setAvailableAdmins] = useState([]);
  const [assignmentNotice, setAssignmentNotice] = useState('');
  const [successNotice, setSuccessNotice] = useState('');

  const updateField = (field, value) => { setNewRequest((previous) => ({ ...previous, [field]: value })); setIsDirty(true); };

  useEffect(() => {
    if (!currentUser?.token) return;
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/notification-assignees`, { headers: { Authorization: `Bearer ${currentUser.token}` } })
      .then(async (response) => { const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.detail || 'Assignment list unavailable.'); return data; })
      .then((data) => { if (!cancelled) setAvailableAdmins(data.admins || []); })
      .catch((error) => { if (!cancelled) setAssignmentNotice(error.message); });
    return () => { cancelled = true; };
  }, [currentUser?.token]);
  const resetRequestForm = () => { setNewRequest({ hospital_name: '', hospital_address: '', contact_phone: '', blood_group: 'O-', units: 2, urgency: 'EMERGENCY', patient: '', destination_latitude: '', destination_longitude: '', assigned_admin_user_id: '' }); setIsDirty(false); };
  const closeRequestModal = useCallback(() => {
    if (isSubmitting) return;
    if (isDirty && !window.confirm('Discard the unsaved blood request?')) return;
    setShowReqModal(false); setFormError(''); setIsDirty(false);
  }, [isDirty, isSubmitting]);

  useEffect(() => {
    if (!showReqModal) return undefined;
    const onKeyDown = (event) => { if (event.key === 'Escape') closeRequestModal(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showReqModal, closeRequestModal]);

  const pendingCount = requestsList.filter(r => (r.status || 'PENDING') === 'PENDING').length;
  const fulfilledCount = requestsList.filter(r => r.status === 'APPROVED' || r.status === 'ALLOCATED').length;
  const emergencyCount = requestsList.filter(r => (r.urgency || r.urgency_level) === 'EMERGENCY').length;

  const handleCreateRequest = async (e) => {
    e.preventDefault();
    setFormError('');
    if (!newRequest.hospital_name.trim()) { setFormError('Hospital name is required.'); return; }
    if (!newRequest.hospital_address.trim()) { setFormError('Hospital address is required.'); return; }
    if (!Number.isInteger(Number(newRequest.units)) || Number(newRequest.units) <= 0 || Number(newRequest.units) > 1000) { setFormError('Units must be a whole number between 1 and 1,000.'); return; }
    if (!newRequest.patient.trim()) { setFormError('Patient or ward reference is required.'); return; }
    const hasLat = String(newRequest.destination_latitude).trim() !== '';
    const hasLon = String(newRequest.destination_longitude).trim() !== '';
    if (hasLat !== hasLon) { setFormError('Enter both destination latitude and longitude, or leave both blank.'); return; }
    const latitude = hasLat ? Number(newRequest.destination_latitude) : null;
    const longitude = hasLon ? Number(newRequest.destination_longitude) : null;
    if (hasLat && (!Number.isFinite(latitude) || latitude < -90 || latitude > 90 || !Number.isFinite(longitude) || longitude < -180 || longitude > 180)) { setFormError('Enter valid coordinates (latitude −90 to 90, longitude −180 to 180).'); return; }

    setIsSubmitting(true);
    try {
      if (typeof onRequestCreated !== 'function') throw new Error('Request creation service is unavailable.');
      const saved = await onRequestCreated({
        hospital_name: newRequest.hospital_name.trim(),
        hospital_address: newRequest.hospital_address.trim(),
        contact_phone: newRequest.contact_phone.trim(),
        blood_group: newRequest.blood_group,
        units_needed: Number(newRequest.units),
        urgency_level: newRequest.urgency,
        patient_name: newRequest.patient.trim(),
        destination_latitude: latitude,
        destination_longitude: longitude,
        assigned_admin_user_id: newRequest.assigned_admin_user_id ? Number(newRequest.assigned_admin_user_id) : null
      });
      if (!saved || saved.id == null) throw new Error('The backend did not confirm a persisted request ID.');
      setIsDirty(false);
      setSuccessNotice(saved.notification_summary?.message || `Request #${saved.id} was saved. The notification queue status should be checked in the request monitor.`);
      setShowReqModal(false);
      resetRequestForm();
    } catch (error) {
      setFormError(error.message || 'The request could not be saved. No success has been assumed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {successNotice && <div role="status" className="rounded-xl border border-emerald-800 bg-emerald-950/50 p-3 text-xs text-emerald-200">{successNotice}</div>}
      {assignmentNotice && <div role="status" className="rounded-xl border border-amber-800 bg-amber-950/40 p-3 text-xs text-amber-200">{assignmentNotice}</div>}
      {/* Hospital Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard 
          title="Active Requisitions" 
          value={`${requestsList.length} Total`} 
          subtitle={`${pendingCount} Pending Verification`} 
          icon={FileText} 
          color="blood" 
        />
        <StatCard 
          title="Fulfilled Requests" 
          value={`${fulfilledCount} Allocated`} 
          subtitle="Processed by staff" 
          icon={CheckCircle2} 
          color="emerald" 
        />
        <StatCard 
          title="Emergency Priority" 
          value={`${emergencyCount} Calls`} 
          subtitle="Critical priority" 
          icon={AlertCircle} 
          color="amber" 
        />
        <StatCard 
          title="Nearby Matched Donors" 
          value={`${donorsList.length} Registered`} 
          subtitle="Ready for emergency dispatch" 
          icon={MapPin} 
          color="blue" 
        />
      </div>

      {/* Main Focus: Hospital Blood Requisitions Section */}
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div>
            <div className="flex items-center space-x-2 text-xs font-semibold text-blood-400 mb-1">
              <Building2 className="w-4 h-4" />
              <span>Hospital Operations Center</span>
            </div>
            <h2 className="text-2xl font-black text-white">Hospital Blood Requisitions</h2>
            <p className="text-xs text-slate-400">Submit urgent and routine blood requests; updates sync in real-time with Blood Bank staff.</p>
          </div>

          <button
            onClick={() => { setFormError(''); setIsDirty(false); setShowReqModal(true); }}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-bold text-xs shadow-lg glow-red flex items-center space-x-2 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>New Emergency Requisition</span>
          </button>
        </div>

        {/* Requisitions Table */}
        <div className="overflow-x-auto">
          {requestsList.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-xs">
              No requisitions created yet. Click "New Emergency Requisition" to request blood units.
            </div>
          ) : (
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Req ID</th>
                  <th className="py-2.5 px-3">Hospital Name</th>
                  <th className="py-2.5 px-3">Hospital Address</th>
                  <th className="py-2.5 px-3">Blood Group</th>
                  <th className="py-2.5 px-3">Units</th>
                  <th className="py-2.5 px-3">Urgency</th>
                  <th className="py-2.5 px-3">Patient / Ward</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {requestsList.map((req, idx) => {
                  const reqId = req.id || req._id || `REQ-${idx + 1}`;
                  const isApproved = req.status === 'APPROVED';
                  const isAllocated = req.status === 'ALLOCATED';
                  const isRejected = req.status === 'REJECTED';

                  return (
                    <tr key={reqId} className="hover:bg-slate-900/40">
                      <td className="py-2.5 px-3 font-mono text-slate-400">{reqId}</td>
                      <td className="py-2.5 px-3 font-bold text-white">
                        {req.hospital_name || req.hospital}
                        {req.contact_phone && (
                          <span className="block text-[10px] text-slate-400 font-mono">{req.contact_phone}</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400 max-w-xs truncate" title={req.hospital_address || ''}>
                        {req.hospital_address || 'Address on file'}
                      </td>
                      <td className="py-2.5 px-3 font-extrabold text-blood-400 text-sm">
                        {req.blood || req.blood_group}
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-white">
                        {req.units || req.units_needed} units
                      </td>
                      <td className="py-2.5 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold ${
                          (req.urgency || req.urgency_level) === 'EMERGENCY'
                            ? 'bg-blood-950 text-blood-400 border border-blood-800 animate-pulse'
                            : 'bg-amber-950 text-amber-400 border border-amber-800'
                        }`}>
                          {req.urgency || req.urgency_level}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">{req.patient || req.patient_name}</td>
                      <td className="py-2.5 px-3 font-bold">
                        <span className={`${
                          isApproved ? 'text-emerald-400' :
                          isAllocated ? 'text-sky-400' :
                          isRejected ? 'text-rose-400' : 'text-amber-400'
                        }`}>
                          {req.status || 'PENDING'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Modal for Creating Extended Blood Requisition */}
      {showReqModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-start md:items-center justify-center overflow-y-auto p-3 sm:p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) closeRequestModal(); }}>
          <div role="dialog" aria-modal="true" aria-labelledby="hospital-request-title" className="my-2 w-full max-w-lg max-h-[calc(100dvh-1rem)] overflow-y-auto overscroll-contain p-5 sm:p-6 rounded-2xl glass-panel border border-slate-800 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <h3 id="hospital-request-title" className="text-lg font-extrabold text-white">Create Hospital Blood Request</h3>
              <button type="button" onClick={closeRequestModal} disabled={isSubmitting} aria-label="Back to hospital dashboard" className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 disabled:opacity-50"><X className="w-4 h-4" /></button>
            </div>

            {formError && (
              <div className="p-3 rounded-xl bg-rose-950/80 border border-rose-800 text-rose-300 text-xs font-semibold">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreateRequest} className="space-y-3 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Hospital Name *</label>
                  <input
                    type="text"
                    required
                    value={newRequest.hospital_name}
                    onChange={(e) => updateField('hospital_name', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-blood-500"
                  />
                </div>

                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Contact Phone Number</label>
                  <input
                    type="tel"
                    value={newRequest.contact_phone}
                    onChange={(e) => updateField('contact_phone', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-blood-500"
                    placeholder="+1-800-555-0101"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-300 block mb-1 font-semibold">Hospital Address (Delivery / Trauma Desk) *</label>
                <textarea
                  required
                  rows={2}
                  value={newRequest.hospital_address}
                  onChange={(e) => updateField('hospital_address', e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-blood-500"
                  placeholder="e.g. 100 Healthcare Blvd, Suite 400, Trauma Wing Desk"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div><label htmlFor="destination-latitude" className="text-slate-300 block mb-1 font-semibold">Destination latitude (optional)</label><input id="destination-latitude" type="number" min="-90" max="90" step="any" value={newRequest.destination_latitude} onChange={(event) => updateField('destination_latitude', event.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white" placeholder="12.9716" /></div>
                <div><label htmlFor="destination-longitude" className="text-slate-300 block mb-1 font-semibold">Destination longitude (optional)</label><input id="destination-longitude" type="number" min="-180" max="180" step="any" value={newRequest.destination_longitude} onChange={(event) => updateField('destination_longitude', event.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white" placeholder="77.5946" /></div>
              </div>
              <p className="text-[10px] text-slate-500">Only enter coordinates confirmed for this hospital destination; they are used by the radius filter.</p>

              <div>
                <label className="text-slate-300 block mb-1 font-semibold">Assigned administrator (optional)</label>
                <select value={newRequest.assigned_admin_user_id} onChange={(e) => updateField('assigned_admin_user_id', e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white">
                  <option value="">Leave unassigned for authorized resolution</option>
                  {availableAdmins.map((account) => <option key={account.id} value={account.id}>{account.name} (account #{account.id})</option>)}
                </select>
                <p className="text-[10px] text-slate-500 mt-1">Acceptance notifications are sent only to this assigned admin; no account is selected automatically.</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Blood Group Required *</label>
                  <select
                    value={newRequest.blood_group}
                    onChange={(e) => updateField('blood_group', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-blood-400 font-bold focus:outline-none"
                  >
                    {['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'].map(b => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Units Required (Min 1) *</label>
                  <input
                    type="number" 
                    min="1" 
                    max="50"
                    required
                    value={newRequest.units}
                    onChange={(e) => updateField('units', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Urgency Level *</label>
                  <select
                    value={newRequest.urgency}
                    onChange={(e) => updateField('urgency', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none"
                  >
                    <option value="EMERGENCY">EMERGENCY (Immediate Dispatch)</option>
                    <option value="HIGH">HIGH (Urgent Surgery)</option>
                    <option value="NORMAL">NORMAL (Elective Requisition)</option>
                  </select>
                </div>

                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Patient Name / Ward Details *</label>
                  <input
                    type="text"
                    required
                    value={newRequest.patient}
                    onChange={(e) => updateField('patient', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none"
                    placeholder="e.g. ICU Ward Bed #4"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={closeRequestModal}
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 font-semibold disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-extrabold shadow-md glow-red disabled:opacity-50"
                >
                  {isSubmitting ? 'Saving request…' : 'Submit & Sync with Staff'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
