import React, { useState } from 'react';
import StatCard from '../components/StatCard';
import { UserCheck, CheckSquare, Plus, RefreshCw, AlertTriangle, FileText, CheckCircle2, Shield } from 'lucide-react';

export default function StaffDashboard({ donorsList = [], requestsList = [], onRequestStatusChange }) {
  const [staffInfo] = useState({
    name: 'Dr. Robert Vance',
    role: 'Senior Blood Bank Technician',
    center: 'Central Blood Bank Hub #1'
  });

  const [pendingAppointments, setPendingAppointments] = useState([
    { id: 'APP-101', donor: 'John Doe', blood: 'O+', date: '2026-08-16', time: '10:00 AM', status: 'SCHEDULED' },
    { id: 'APP-102', donor: 'Sarah Jenkins', blood: 'A-', date: '2026-08-18', time: '02:30 PM', status: 'SCHEDULED' },
  ]);

  const handleVerifyAppointment = (id) => {
    setPendingAppointments(prev => prev.map(a => a.id === id ? { ...a, status: 'COMPLETED' } : a));
  };

  const handleApproveReq = (id) => {
    if (onRequestStatusChange) {
      onRequestStatusChange(id, 'APPROVED');
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Staff Header Banner */}
      <div className="p-6 rounded-2xl glass-panel bg-gradient-to-r from-slate-900 via-slate-900 to-blood-950/40 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="w-14 h-14 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center text-emerald-400">
            <UserCheck className="w-7 h-7" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-2xl font-black text-white">{staffInfo.name}</h2>
              <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold">
                Verified Staff
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">{staffInfo.role} &bull; {staffInfo.center}</p>
          </div>
        </div>
      </div>

      {/* Staff Operational Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Scheduled Check-ins" value={`${pendingAppointments.length} Donors`} subtitle="Today's Appointments" icon={UserCheck} color="blood" />
        <StatCard title="Pending Approvals" value={`${requestsList.filter(r => r.status === 'PENDING').length} Requisitions`} subtitle="Requires staff review" icon={FileText} color="amber" />
        <StatCard title="Stock Verified Today" value="42 Units" subtitle="Passed QA screening" icon={CheckSquare} color="emerald" />
        <StatCard title="Storage Health" value="Optimal" subtitle="Temperature: 4°C" icon={Shield} color="blue" />
      </div>

      {/* Main Grid: Appointment Verification & Requisition Processing */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Donor Check-in Verification Table */}
        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 className="text-sm font-bold text-white">Donor Appointment Verification</h3>
            <span className="text-xs text-slate-400">Scan & Check-in</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Donor Name</th>
                  <th className="py-2.5 px-3">Blood Group</th>
                  <th className="py-2.5 px-3">Slot Time</th>
                  <th className="py-2.5 px-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {pendingAppointments.map((app) => (
                  <tr key={app.id} className="hover:bg-slate-900/40">
                    <td className="py-2.5 px-3 font-bold text-white">{app.donor}</td>
                    <td className="py-2.5 px-3 font-extrabold text-blood-400">{app.blood}</td>
                    <td className="py-2.5 px-3 text-slate-300 font-mono">{app.time}</td>
                    <td className="py-2.5 px-3">
                      {app.status === 'SCHEDULED' ? (
                        <button
                          onClick={() => handleVerifyAppointment(app.id)}
                          className="px-2.5 py-1 rounded bg-emerald-950 hover:bg-emerald-900 text-emerald-300 border border-emerald-800 text-[11px] font-semibold"
                        >
                          Verify & Process
                        </button>
                      ) : (
                        <span className="text-emerald-400 font-semibold text-[11px] flex items-center space-x-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Verified</span>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Hospital Requisition Approval Panel */}
        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 className="text-sm font-bold text-white">Process Hospital Requisitions</h3>
            <span className="text-xs text-slate-400">Inventory Allocation</span>
          </div>

          <div className="space-y-3">
            {requestsList.map((req, idx) => (
              <div key={req.id || req._id || idx} className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">{req.hospital_name || req.hospital}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold ${
                    (req.urgency || req.urgency_level) === 'EMERGENCY' ? 'bg-blood-950 text-blood-400 border border-blood-800' : 'bg-amber-950 text-amber-400'
                  }`}>
                    {req.urgency || req.urgency_level}
                  </span>
                </div>

                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>Group: <strong className="text-blood-400">{req.blood || req.blood_group}</strong> ({req.units || req.units_needed} units)</span>
                  {req.status === 'PENDING' ? (
                    <button
                      onClick={() => handleApproveReq(req.id || req._id)}
                      className="px-3 py-1 rounded bg-blood-600 hover:bg-blood-500 text-white font-bold text-[11px]"
                    >
                      Approve & Allocate
                    </button>
                  ) : (
                    <span className="text-emerald-400 font-semibold">Allocated & Approved</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

    </div>
  );
}
