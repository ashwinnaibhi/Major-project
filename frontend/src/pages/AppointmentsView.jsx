import React, { useState } from 'react';
import { CalendarCheck, Plus, Check, Clock, UserCheck } from 'lucide-react';

export default function AppointmentsView() {
  const [appointments, setAppointments] = useState([
    { id: 1, donor: 'John Doe', blood: 'O+', date: '2026-08-16', time: '10:00 AM', status: 'SCHEDULED' },
    { id: 2, donor: 'Sarah Jenkins', blood: 'A-', date: '2026-08-18', time: '02:30 PM', status: 'SCHEDULED' },
    { id: 3, donor: 'Emily Davis', blood: 'AB+', date: '2026-08-10', time: '11:15 AM', status: 'COMPLETED' },
  ]);

  const handleComplete = (id) => {
    setAppointments(prev => prev.map(a => a.id === id ? { ...a, status: 'COMPLETED' } : a));
  };

  return (
    <div className="space-y-6">
      
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-blood-400 mb-1">
            <CalendarCheck className="w-4 h-4" />
            <span>Donation Drive Scheduling</span>
          </div>
          <h2 className="text-2xl font-black text-white">Donor Appointment Calendar</h2>
          <p className="text-xs text-slate-400">Schedule, verify eligibility, and complete blood donation appointments.</p>
        </div>
      </div>

      <div className="p-5 rounded-2xl glass-panel border border-slate-800">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Donor Name</th>
                <th className="py-3 px-4">Blood Group</th>
                <th className="py-3 px-4">Appointment Date</th>
                <th className="py-3 px-4">Time Slot</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {appointments.map((app) => (
                <tr key={app.id} className="hover:bg-slate-900/40">
                  <td className="py-3 px-4 font-bold text-white flex items-center space-x-2">
                    <UserCheck className="w-4 h-4 text-blood-400" />
                    <span>{app.donor}</span>
                  </td>
                  <td className="py-3 px-4 font-extrabold text-blood-400 text-sm">{app.blood}</td>
                  <td className="py-3 px-4 text-slate-300 font-mono">{app.date}</td>
                  <td className="py-3 px-4 text-slate-300">{app.time}</td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      app.status === 'COMPLETED'
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                        : 'bg-amber-950 text-amber-400 border border-amber-800'
                    }`}>
                      {app.status}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    {app.status === 'SCHEDULED' ? (
                      <button
                        onClick={() => handleComplete(app.id)}
                        className="px-2.5 py-1 rounded bg-emerald-950 hover:bg-emerald-900 text-emerald-300 border border-emerald-800 text-[11px] font-semibold flex items-center space-x-1"
                      >
                        <Check className="w-3 h-3" />
                        <span>Verify & Complete</span>
                      </button>
                    ) : (
                      <span className="text-slate-500 text-[11px]">Donation Verified</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
