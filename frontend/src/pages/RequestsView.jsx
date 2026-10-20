import React, { useState } from 'react';
import LocationFields from '../components/LocationFields';
import { FileText, Plus, CheckCircle, XCircle, Clock, ShieldAlert, Trash2 } from 'lucide-react';

export default function RequestsView({ requestsList = [], onRequestCreated, onRequestStatusChange, onRequestDeleted }) {
  const [showModal, setShowModal] = useState(false);
  const [formError, setFormError] = useState('');
  const [newReq, setNewReq] = useState({
    hospital: 'City General Hospital',
    hospital_address: '',
    contact_phone: '',
    district: '',
    taluk: '',
    latitude: null,
    longitude: null,
    blood: 'O+',
    units: 2,
    urgency: 'HIGH',
    patient: 'ICU Patient #101'
  });

  const handleCreate = async (e) => {
    e.preventDefault();
    setFormError('');
    if (!newReq.hospital.trim()) {
      setFormError('Hospital name is required.');
      return;
    }
    if (!newReq.hospital_address.trim()) {
      setFormError('Hospital address is required.');
      return;
    }
    if ((newReq.latitude === null || newReq.latitude === '') !== (newReq.longitude === null || newReq.longitude === '')) {
      setFormError('Enter both latitude and longitude, or leave both blank.');
      return;
    }

    const reqObj = {
      hospital_name: newReq.hospital.trim(),
      hospital: newReq.hospital.trim(),
      hospital_address: newReq.hospital_address.trim(),
      contact_phone: newReq.contact_phone.trim(),
      district: newReq.district || null,
      taluk: newReq.taluk || null,
      latitude: newReq.latitude === '' ? null : newReq.latitude,
      longitude: newReq.longitude === '' ? null : newReq.longitude,
      blood_group: newReq.blood,
      blood: newReq.blood,
      units_needed: parseInt(newReq.units, 10),
      units: parseInt(newReq.units, 10),
      urgency_level: newReq.urgency,
      urgency: newReq.urgency,
      patient_name: newReq.patient.trim(),
      patient: newReq.patient.trim(),
      status: 'PENDING',
      request_date: new Date().toISOString().slice(0, 16).replace('T', ' ')
    };

    try {
      if (onRequestCreated) await onRequestCreated(reqObj);
      setShowModal(false);
    } catch (error) {
      setFormError(error.message || 'The request could not be saved. Please retry.');
    }
  };

  const handleUpdateStatus = (id, newStatus) => {
    if (onRequestStatusChange) {
      onRequestStatusChange(id, newStatus);
    }
  };

  const handleDeleteRequest = (id) => {
    if (onRequestDeleted) {
      onRequestDeleted(id);
    }
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

      <div className="p-5 rounded-2xl glass-panel border border-slate-800">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Hospital Name</th>
                <th className="py-3 px-4">District / Taluk</th>
                <th className="py-3 px-4">Blood Group</th>
                <th className="py-3 px-4">Units Needed</th>
                <th className="py-3 px-4">Urgency Level</th>
                <th className="py-3 px-4">Patient / Reason</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">SQL Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {requestsList.map((req, idx) => (
                <tr key={req.id || req._id || idx} className="hover:bg-slate-900/40">
                  <td className="py-3 px-4 font-bold text-white">
                    {req.hospital_name || req.hospital}
                    <span className="mt-1 block max-w-xs truncate text-[10px] font-normal text-slate-500" title={req.hospital_address || ''}>{req.hospital_address || 'Address not recorded'}</span>
                  </td>
                  <td className="py-3 px-4 text-slate-300">
                    {[req.taluk, req.district].filter(Boolean).join(', ') || 'Not recorded'}
                    <span className="mt-1 block text-[10px] text-slate-500">{req.latitude != null && req.longitude != null ? 'Coordinates recorded' : 'Distance unavailable'}</span>
                  </td>
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
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
            <h3 className="text-lg font-extrabold text-white">Create Hospital Blood Request</h3>
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
                <textarea
                  rows={2}
                  value={newReq.hospital_address}
                  onChange={(e) => setNewReq({ ...newReq, hospital_address: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  placeholder="Hospital street address or emergency desk location"
                  required
                />
              </div>
              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Contact Phone</label>
                <input
                  type="tel"
                  value={newReq.contact_phone}
                  onChange={(e) => setNewReq({ ...newReq, contact_phone: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  placeholder="Optional contact number"
                />
              </div>
              <LocationFields value={newReq} onChange={setNewReq} requiredLocation showCoordinates showLocality={false} />
              {formError && <div role="alert" className="rounded-xl border border-rose-800 bg-rose-950/40 px-3 py-2 text-xs text-rose-200">{formError}</div>}

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

              <div className="flex items-center justify-end space-x-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-blood-600 hover:bg-blood-500 text-white font-bold"
                >
                  Submit Request
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
