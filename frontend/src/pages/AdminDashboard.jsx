import React from 'react';
import StatCard from '../components/StatCard';
import MLPredictionBadge from '../components/MLPredictionBadge';
import { Users, Droplets, AlertOctagon, BrainCircuit, Activity, ArrowUpRight, CheckCircle } from 'lucide-react';

export default function AdminDashboard({ onNavigate, donorsList = [] }) {
  const stockItems = [
    { group: 'O+', units: 45, status: 'AVAILABLE', pct: 90 },
    { group: 'O-', units: 8, status: 'LOW_STOCK', pct: 20 },
    { group: 'A+', units: 32, status: 'AVAILABLE', pct: 64 },
    { group: 'A-', units: 12, status: 'AVAILABLE', pct: 30 },
    { group: 'B+', units: 28, status: 'AVAILABLE', pct: 56 },
    { group: 'B-', units: 5, status: 'LOW_STOCK', pct: 15 },
    { group: 'AB+', units: 18, status: 'AVAILABLE', pct: 40 },
    { group: 'AB-', units: 4, status: 'LOW_STOCK', pct: 10 },
  ];

  const recentRequests = [
    { id: 1, hospital: 'City General Hospital', blood: 'O-', units: 4, urgency: 'EMERGENCY', patient: 'Trauma Patient #402', status: 'PENDING', time: '12 mins ago' },
    { id: 2, hospital: 'St. Jude Emergency Center', blood: 'B-', units: 2, urgency: 'HIGH', patient: 'Surgical Patient #109', status: 'APPROVED', time: '1 hr ago' },
  ];

  const totalDonorsCount = donorsList.length > 0 ? donorsList.length : 1248;
  const highAvailCount = donorsList.length > 0 ? donorsList.filter(d => d.category === 'HIGH' || d.availability_status === 'HIGH').length : 4;

  return (
    <div className="space-y-6">
      
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-6 rounded-2xl glass-panel bg-gradient-to-r from-slate-900 via-slate-900 to-blood-950/40 border border-slate-800">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-blood-400 mb-1">
            <Activity className="w-4 h-4 animate-pulse" />
            <span>Executive Command Center</span>
          </div>
          <h2 className="text-2xl font-black text-white tracking-tight">Blood Bank Analytics & Admin Control</h2>
          <p className="text-xs text-slate-400 mt-1">Real-time registered donor management & Random Forest availability tracking.</p>
        </div>

        <button
          onClick={() => onNavigate('emergency')}
          className="flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-semibold text-xs shadow-lg glow-red transition-all"
        >
          <AlertOctagon className="w-4 h-4" />
          <span>Launch Emergency Donor Search</span>
        </button>
      </div>

      {/* Metric Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Registered Donors"
          value={`${totalDonorsCount} Donors`}
          subtitle={`${highAvailCount} High Availability`}
          icon={Users}
          trend="+ Live Updates"
          color="emerald"
        />
        <StatCard
          title="Total Blood Stock"
          value="151 Units"
          subtitle="Across 8 blood groups"
          icon={Droplets}
          trend="Stock Health: Optimal"
          color="blood"
        />
        <StatCard
          title="Active Requests"
          value="2 Pending"
          subtitle="1 Emergency dispatch"
          icon={AlertOctagon}
          trend="Avg response time: 18m"
          color="amber"
        />
        <StatCard
          title="ML Engine Accuracy"
          value="90.42%"
          subtitle="F1 Score: 93.80%"
          icon={BrainCircuit}
          trend="Random Forest v1.0 Model"
          color="blue"
        />
      </div>

      {/* Registered Donors List Visible to Admin */}
      <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-white">Registered Donors Directory (Admin View)</h3>
            <p className="text-xs text-slate-400">Includes all newly registered donors & their contact profiles</p>
          </div>
          <span className="px-2.5 py-1 rounded-lg text-xs bg-blood-950 text-blood-400 border border-blood-800 font-extrabold">
            {donorsList.length} Donors Registered
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Donor ID</th>
                <th className="py-2.5 px-3">Registered Name</th>
                <th className="py-2.5 px-3">Email Address</th>
                <th className="py-2.5 px-3">Blood Group</th>
                <th className="py-2.5 px-3">Location Zone</th>
                <th className="py-2.5 px-3">Contact Phone</th>
                <th className="py-2.5 px-3">ML Availability</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {donorsList.map((donor) => (
                <tr key={donor.id} className="hover:bg-slate-900/40">
                  <td className="py-2.5 px-3 font-mono text-slate-400">{donor.id}</td>
                  <td className="py-2.5 px-3 font-bold text-white">{donor.name}</td>
                  <td className="py-2.5 px-3 text-slate-300">{donor.email}</td>
                  <td className="py-2.5 px-3 font-black text-blood-400">{donor.blood || donor.blood_group}</td>
                  <td className="py-2.5 px-3 text-slate-400">{donor.location}</td>
                  <td className="py-2.5 px-3 text-slate-300 font-mono">{donor.phone}</td>
                  <td className="py-2.5 px-3">
                    <MLPredictionBadge category={donor.category || 'HIGH'} score={donor.availabilityScore || 91.5} />
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
