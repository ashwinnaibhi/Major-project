import React, { useState } from 'react';
import StatCard from '../components/StatCard';
import { CheckSquare, AlertTriangle, FileText, CheckCircle2, Shield, XCircle, Clock } from 'lucide-react';

export default function StaffDashboard({ requestsList = [], onRequestStatusChange }) {
  const [staffInfo] = useState({
    name: 'Dr. Robert Vance',
    role: 'Senior Blood Bank Technician',
    center: 'Central Blood Bank Hub #1'
  });

  const pendingRequests = requestsList.filter(r => (r.status || 'PENDING') === 'PENDING');
  const approvedRequests = requestsList.filter(r => r.status === 'APPROVED' || r.status === 'ALLOCATED');

  const handleStatusChange = (id, newStatus) => {
    if (onRequestStatusChange) {
      onRequestStatusChange(id, newStatus);
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Staff Header Banner */}
      <div className="p-6 rounded-2xl glass-panel bg-gradient-to-r from-slate-900 via-slate-900 to-blood-950/40 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="w-14 h-14 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center text-emerald-400">
            <Shield className="w-7 h-7" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-2xl font-black text-white">{staffInfo.name}</h2>
              <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold">
                Verified Blood Bank Staff
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">{staffInfo.role} &bull; {staffInfo.center}</p>
          </div>
        </div>
      </div>

      {/* Staff Operational Metrics (Removed scheduled check-ins) */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard 
          title="Pending Approvals" 
          value={`${pendingRequests.length} Requisitions`} 
          subtitle="Requires staff verification" 
          icon={FileText} 
          color="blood" 
        />
        <StatCard 
          title="Approved / Allocated" 
          value={`${approvedRequests.length} Requests`} 
          subtitle="Ready for dispatch" 
          icon={CheckSquare} 
          color="emerald" 
        />
        <StatCard 
          title="Storage Health" 
          value="Optimal" 
          subtitle="Temperature: 4°C" 
          icon={Shield} 
          color="blue" 
        />
      </div>

      {/* Process Hospital Requisitions (FULL WIDTH) */}
      <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4 w-full">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-white">Process Hospital Requisitions</h3>
            <p className="text-xs text-slate-400">Review, allocate inventory, and approve hospital blood requests</p>
          </div>
          <span className="px-2.5 py-1 rounded-lg text-xs bg-blood-950 text-blood-400 border border-blood-800 font-extrabold">
            {pendingRequests.length} Pending
          </span>
        </div>

        {requestsList.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-xs">
            No hospital requisitions recorded in the system.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Req ID</th>
                  <th className="py-2.5 px-3">Hospital Details</th>
                  <th className="py-2.5 px-3">Blood Group</th>
                  <th className="py-2.5 px-3">Units</th>
                  <th className="py-2.5 px-3">Urgency</th>
                  <th className="py-2.5 px-3">Patient / Ward</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Staff Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {requestsList.map((req, idx) => {
                  const reqId = req.id || req._id || idx + 1;
                  const isPending = (req.status || 'PENDING') === 'PENDING';
                  const isApproved = req.status === 'APPROVED';
                  const isAllocated = req.status === 'ALLOCATED';
                  const isRejected = req.status === 'REJECTED';

                  return (
                    <tr key={reqId} className="hover:bg-slate-900/40 transition-colors">
                      <td className="py-2.5 px-3 font-mono text-slate-400">#{reqId}</td>
                      <td className="py-2.5 px-3">
                        <div className="font-bold text-white">{req.hospital_name || req.hospital}</div>
                        <div className="text-[10px] text-slate-400">{req.hospital_address || 'Address on file'}</div>
                        {req.contact_phone && (
                          <div className="text-[10px] text-slate-500 font-mono">{req.contact_phone}</div>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="font-black text-blood-400 text-sm">{req.blood || req.blood_group}</span>
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-white">
                        {req.units || req.units_needed} units
                      </td>
                      <td className="py-2.5 px-3">
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
                      <td className="py-2.5 px-3 text-right">
                        <div className="flex items-center justify-end space-x-1.5">
                          {isPending && (
                            <>
                              <button
                                onClick={() => handleStatusChange(reqId, 'APPROVED')}
                                className="px-2.5 py-1 rounded bg-emerald-950 hover:bg-emerald-900 text-emerald-300 border border-emerald-800 text-[11px] font-bold"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => handleStatusChange(reqId, 'REJECTED')}
                                className="px-2.5 py-1 rounded bg-rose-950 hover:bg-rose-900 text-rose-300 border border-rose-800 text-[11px] font-bold"
                              >
                                Reject
                              </button>
                            </>
                          )}
                          {isApproved && (
                            <button
                              onClick={() => handleStatusChange(reqId, 'ALLOCATED')}
                              className="px-2.5 py-1 rounded bg-sky-950 hover:bg-sky-900 text-sky-300 border border-sky-800 text-[11px] font-bold"
                            >
                              Allocate Stock
                            </button>
                          )}
                          {(isAllocated || isRejected) && (
                            <span className="text-[10px] text-slate-500">Processed</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}
