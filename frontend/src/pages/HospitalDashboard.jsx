import React, { useState } from 'react';
import StatCard from '../components/StatCard';
import MLPredictionBadge from '../components/MLPredictionBadge';
import { Building2, Plus, Search, ShieldAlert, FileText, CheckCircle2, Clock, MapPin, Send } from 'lucide-react';

export default function HospitalDashboard({ donorsList = [], requestsList = [], onRequestCreated }) {
  const [hospitalInfo] = useState({
    name: 'City General Hospital',
    license: 'HOSP-LIC-2024-8891',
    address: '100 Healthcare Blvd, Suite 400',
    contact: 'Dr. Alice Smith (+1-800-555-0101)'
  });

  const [showReqModal, setShowReqModal] = useState(false);
  const [newRequest, setNewRequest] = useState({
    blood_group: 'O-',
    units: 2,
    urgency: 'EMERGENCY',
    patient: 'Emergency Trauma Ward #12'
  });

  const handleCreateRequest = async (e) => {
    e.preventDefault();
    const reqObj = {
      id: `REQ-${Math.floor(100 + Math.random() * 900)}`,
      hospital_name: hospitalInfo.name,
      hospital: hospitalInfo.name,
      blood_group: newRequest.blood_group,
      blood: newRequest.blood_group,
      units_needed: parseInt(newRequest.units),
      units: parseInt(newRequest.units),
      urgency_level: newRequest.urgency,
      urgency: newRequest.urgency,
      patient_name: newRequest.patient,
      patient: newRequest.patient,
      status: 'PENDING',
      request_date: new Date().toISOString().slice(0, 16).replace('T', ' ')
    };

    if (onRequestCreated) {
      onRequestCreated(reqObj);
    }
    setShowReqModal(false);
  };

  return (
    <div className="space-y-6">
      
      {/* Hospital Banner */}
      <div className="p-6 rounded-2xl glass-panel bg-gradient-to-r from-slate-900 via-slate-900 to-blood-950/40 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="w-14 h-14 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center text-blood-400">
            <Building2 className="w-7 h-7" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-2xl font-black text-white">{hospitalInfo.name}</h2>
              <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 font-mono">
                {hospitalInfo.license}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">{hospitalInfo.address} &bull; {hospitalInfo.contact}</p>
          </div>
        </div>

        <button
          onClick={() => setShowReqModal(true)}
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-bold text-xs shadow-lg glow-red flex items-center space-x-2 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>New Emergency Requisition</span>
        </button>
      </div>

      {/* Hospital Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Active Requisitions" value={`${requestsList.length} Requests`} subtitle={`${requestsList.filter(r => (r.urgency || r.urgency_level) === 'EMERGENCY').length} Emergency Pending`} icon={FileText} color="blood" />
        <StatCard title="Fulfilled Requests" value={`${requestsList.filter(r => r.status === 'FULFILLED' || r.status === 'APPROVED').length} Fulfilled`} subtitle="100% fulfill rate" icon={CheckCircle2} color="emerald" />
        <StatCard title="Nearby High Donors" value={`${donorsList.length} Registered`} subtitle="Within 10 km radius" icon={MapPin} color="blue" />
        <StatCard title="Avg Response Dispatch" value="14 Mins" subtitle="Prioritized by ML" icon={Clock} color="amber" />
      </div>

      {/* Main Grid: Hospital Requisitions & Recommended Donors */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Hospital Requisitions Table */}
        <div className="lg:col-span-2 p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 className="text-sm font-bold text-white">Your Blood Requisitions</h3>
            <span className="text-xs text-slate-400">Track real-time status across system</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Req ID</th>
                  <th className="py-2.5 px-3">Blood Group</th>
                  <th className="py-2.5 px-3">Units</th>
                  <th className="py-2.5 px-3">Urgency</th>
                  <th className="py-2.5 px-3">Patient / Ward</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {requestsList.map((req, idx) => (
                  <tr key={req.id || req._id || idx} className="hover:bg-slate-900/40">
                    <td className="py-2.5 px-3 font-mono text-slate-400">{req.id || req._id || `REQ-${idx+1}`}</td>
                    <td className="py-2.5 px-3 font-extrabold text-blood-400 text-sm">{req.blood || req.blood_group}</td>
                    <td className="py-2.5 px-3 font-semibold text-white">{req.units || req.units_needed} units</td>
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
                      <span className={req.status === 'APPROVED' || req.status === 'FULFILLED' ? 'text-emerald-400' : 'text-amber-400'}>
                        {req.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Prioritized Donor Recommendation List */}
        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <ShieldAlert className="w-4 h-4 text-blood-400" />
              <span>ML High-Availability Donors</span>
            </h3>
          </div>

          <div className="space-y-3">
            {donorsList.slice(0, 4).map((d) => (
              <div key={d.id} className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">{d.name} ({d.blood})</span>
                  <MLPredictionBadge category={d.category || 'HIGH'} score={d.availabilityScore || 91.5} />
                </div>
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span>Dist: {d.distance || 4.0} km</span>
                  <a href={`tel:${d.phone}`} className="text-blood-400 font-semibold hover:underline">
                    {d.phone}
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* Modal for Creating Blood Requisition */}
      {showReqModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
            <h3 className="text-lg font-extrabold text-white">Create Hospital Blood Request</h3>
            <form onSubmit={handleCreateRequest} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Blood Group Required</label>
                <select
                  value={newRequest.blood_group}
                  onChange={(e) => setNewRequest({ ...newRequest, blood_group: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                >
                  {['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'].map(b => (
                    <option key={b} value={b}>{b}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Units Required</label>
                <input
                  type="number" min="1" max="20"
                  value={newRequest.units}
                  onChange={(e) => setNewRequest({ ...newRequest, units: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Urgency Level</label>
                <select
                  value={newRequest.urgency}
                  onChange={(e) => setNewRequest({ ...newRequest, urgency: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                >
                  <option value="EMERGENCY">EMERGENCY (Critical Need)</option>
                  <option value="HIGH">HIGH (Urgent Surgery)</option>
                  <option value="NORMAL">NORMAL (Elective)</option>
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Patient Name / Ward Details</label>
                <input
                  type="text"
                  value={newRequest.patient}
                  onChange={(e) => setNewRequest({ ...newRequest, patient: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  required
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowReqModal(false)}
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
