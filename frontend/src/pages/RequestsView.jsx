import React, { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '../api/config';
import axios from 'axios';
import { PlusCircle, Clock, AlertTriangle, CheckCircle, FileText, X } from 'lucide-react';

const RequestsView = ({ requestsList, onRequestCreated, currentUser }) => {
  const [requests, setRequests] = useState(Array.isArray(requestsList) ? requestsList : []);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({
    hospital_name: currentUser?.name || 'Hospital Facility',
    hospital_address: 'Main Facility',
    patient_name: 'Inpatient Department',
    contact_phone: currentUser?.phone || '',
    blood_group: 'A+',
    units_requested: 1,
    urgency: 'EMERGENCY',
    notes: ''
  });
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const token = currentUser?.token || (() => {
    try {
      return JSON.parse(localStorage.getItem('haemopulse_user') || '{}')?.token;
    } catch {
      return null;
    }
  })();

  const API_BASE = getApiBaseUrl();

  const fetchRequests = useCallback(async () => {
    if (Array.isArray(requestsList) && requestsList.length > 0) {
      setRequests(requestsList);
      return;
    }
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const res = await axios.get(`${API_BASE}/api/v1/requests`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRequests(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error("Failed to load blood requests", err);
      setRequests([]);
    } finally {
      setLoading(false);
    }
  }, [requestsList, token, API_BASE]);

  useEffect(() => {
    if (Array.isArray(requestsList)) {
      setRequests(requestsList);
    } else {
      fetchRequests();
    }
  }, [requestsList, fetchRequests]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');

    if (!token) {
      setErrorMsg('Sign in with an authorized hospital or administrator account to submit a blood requisition.');
      return;
    }

    try {
      const units = parseInt(formData.units_requested, 10);
      if (!Number.isInteger(units) || units <= 0) {
        setErrorMsg('Quantity must be at least 1 unit.');
        return;
      }

      if (typeof onRequestCreated === 'function') {
        const created = await onRequestCreated({
          hospital_name: formData.hospital_name,
          hospital_address: formData.hospital_address,
          patient_name: formData.patient_name || formData.notes || 'Inpatient',
          contact_phone: formData.contact_phone,
          blood_group: formData.blood_group,
          units_needed: units,
          urgency_level: formData.urgency.toUpperCase()
        });
        setSuccessMsg(`Requisition #${created?.id || 'NEW'} submitted successfully.`);
      } else {
        await axios.post(`${API_BASE}/api/v1/requests`, {
          hospital_name: formData.hospital_name,
          hospital_address: formData.hospital_address,
          patient_name: formData.patient_name || formData.notes || 'Inpatient',
          contact_phone: formData.contact_phone,
          blood_group: formData.blood_group,
          units_needed: units,
          urgency_level: formData.urgency.toUpperCase()
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setSuccessMsg('Requisition submitted successfully.');
        fetchRequests();
      }

      setShowModal(false);
      setFormData({
        hospital_name: currentUser?.name || 'Hospital Facility',
        hospital_address: 'Main Facility',
        patient_name: 'Inpatient Department',
        contact_phone: currentUser?.phone || '',
        blood_group: 'A+',
        units_requested: 1,
        urgency: 'EMERGENCY',
        notes: ''
      });
    } catch (err) {
      setErrorMsg(err.message || err.response?.data?.detail || 'Failed to submit requisition.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-blood-400 mb-1">
            <FileText className="w-4 h-4" />
            <span>Clinical Blood Supply Desk</span>
          </div>
          <h2 className="text-2xl font-black text-white">Hospital Blood Requisitions</h2>
          <p className="text-xs text-slate-400">Create, review, and track clinical blood requisitions across hospitals.</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="bg-blood-700 hover:bg-blood-600 text-white px-4 py-2.5 rounded-xl flex items-center space-x-2 text-xs font-bold transition shadow-sm"
        >
          <PlusCircle className="w-4 h-4" />
          <span>New Requisition</span>
        </button>
      </div>

      {successMsg && (
        <div className="p-4 bg-emerald-950/60 border border-emerald-800 text-emerald-300 rounded-xl flex items-center space-x-2 text-xs font-bold">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Requisitions Table */}
      <div className="rounded-2xl glass-panel border border-slate-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/90 text-slate-400 font-bold uppercase tracking-wider text-[10px] border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Req ID</th>
                <th className="py-3 px-4">Hospital</th>
                <th className="py-3 px-4">Blood Group</th>
                <th className="py-3 px-4">Units</th>
                <th className="py-3 px-4">Urgency</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {loading ? (
                <tr>
                  <td colSpan="7" className="text-center py-8 text-slate-500">Loading requisitions...</td>
                </tr>
              ) : requests.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center py-8 text-slate-500">No requisitions found.</td>
                </tr>
              ) : (
                requests.map((r, idx) => (
                  <tr key={r.id || idx} className="hover:bg-slate-900/40 transition">
                    <td className="py-3 px-4 font-mono font-bold text-white">REQ-{r.id || idx + 1}</td>
                    <td className="py-3 px-4 font-semibold text-slate-200">{r.hospital_name || r.hospital || 'Facility'}</td>
                    <td className="py-3 px-4">
                      <span className="inline-block bg-blood-950 text-blood-400 border border-blood-800 font-bold px-2 py-0.5 rounded text-[10px]">
                        {r.blood_group}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-bold text-white">{r.units_needed || r.units_requested || 1} Unit(s)</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        ['CRITICAL', 'EMERGENCY'].includes(String(r.urgency_level || r.urgency || '').toUpperCase())
                          ? 'bg-rose-950 text-rose-300 border-rose-800'
                          : 'bg-amber-950 text-amber-300 border-amber-800'
                      }`}>
                        {r.urgency_level || r.urgency || 'NORMAL'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="flex items-center space-x-1 text-slate-400">
                        <Clock className="w-3.5 h-3.5 text-blood-400" />
                        <span className="font-semibold text-slate-300">{r.status || 'PENDING'}</span>
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-[11px]">{r.request_date || r.created_at || 'Recently'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Creation Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4 text-xs">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-base font-bold text-white">Submit Blood Requisition</h3>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            {errorMsg && (
              <div className="p-3 bg-rose-950/60 text-rose-300 rounded-xl border border-rose-800 font-bold" role="alert">
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-3">
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Blood Group Required</label>
                <select
                  className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl p-2.5 text-xs font-bold focus:border-blood-500 outline-none"
                  value={formData.blood_group}
                  onChange={(e) => setFormData({ ...formData, blood_group: e.target.value })}
                >
                  {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(bg => (
                    <option key={bg} value={bg} className="bg-slate-900 text-white">{bg}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Quantity (Units)</label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  required
                  className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl p-2.5 text-xs font-bold focus:border-blood-500 outline-none"
                  value={formData.units_requested}
                  onChange={(e) => setFormData({ ...formData, units_requested: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Urgency Level</label>
                <select
                  className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl p-2.5 text-xs font-bold focus:border-blood-500 outline-none"
                  value={formData.urgency}
                  onChange={(e) => setFormData({ ...formData, urgency: e.target.value })}
                >
                  <option value="NORMAL" className="bg-slate-900 text-white">NORMAL (Elective Requisition)</option>
                  <option value="HIGH" className="bg-slate-900 text-white">HIGH (Urgent Surgery)</option>
                  <option value="EMERGENCY" className="bg-slate-900 text-white">EMERGENCY (Immediate Transfusion)</option>
                </select>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Patient or Ward Reference</label>
                <input
                  type="text"
                  required
                  className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl p-2.5 text-xs font-bold focus:border-blood-500 outline-none"
                  value={formData.patient_name}
                  onChange={(e) => setFormData({ ...formData, patient_name: e.target.value })}
                  placeholder="e.g. ICU Ward 4 / Patient Ref"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border border-slate-700 rounded-xl text-slate-300 hover:bg-slate-800 text-xs font-bold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blood-700 hover:bg-blood-600 text-white rounded-xl text-xs font-bold"
                >
                  Submit Requisition
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default RequestsView;
