import React from 'react';
import StatCard from '../components/StatCard';
import MLPredictionBadge from '../components/MLPredictionBadge';
import { Users, Droplets, AlertOctagon, BrainCircuit, Activity, Trash2, Heart, Clock, Calendar } from 'lucide-react';

export default function AdminDashboard({ onNavigate, donorsList = [], onDeleteDonor }) {
  const totalDonorsCount = donorsList.length;
  const highAvailCount = donorsList.filter(d => d.category === 'HIGH' || d.availability_status === 'HIGH').length;

  return (
    <div className="space-y-6">
      
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-6 rounded-2xl glass-panel bg-gradient-to-r from-slate-900 via-slate-900 to-blood-950/40 border border-slate-800">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-blood-400 mb-1">
            <Activity className="w-4 h-4 animate-pulse" />
            <span>Executive Command Center & Database Manager</span>
          </div>
          <h2 className="text-2xl font-black text-white tracking-tight">Blood Bank Admin Directory & Record Manager</h2>
          <p className="text-xs text-slate-400 mt-1">View comprehensive donor donation history, ML availability scores, health metrics, and manage SQL records.</p>
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
          trend="SQL Relational DB Live"
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

      {/* Registered Donors List Visible to Record Manager / Admin */}
      <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-white">Full Donor Records Directory (Record Manager View)</h3>
            <p className="text-xs text-slate-400">Contains total donation counts, last donation timestamps, ML scores, and contact profiles</p>
          </div>
          <span className="px-2.5 py-1 rounded-lg text-xs bg-blood-950 text-blood-400 border border-blood-800 font-extrabold">
            {donorsList.length} SQL Donor Records
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Donor ID</th>
                <th className="py-2.5 px-3">Registered Name</th>
                <th className="py-2.5 px-3">Blood Group</th>
                <th className="py-2.5 px-3">Total Donations</th>
                <th className="py-2.5 px-3">Last Donated</th>
                <th className="py-2.5 px-3">Location & Phone</th>
                <th className="py-2.5 px-3">Preferred Time</th>
                <th className="py-2.5 px-3">ML Availability Score</th>
                <th className="py-2.5 px-3">SQL Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {donorsList.map((donor) => (
                <tr key={donor.id} className="hover:bg-slate-900/40">
                  <td className="py-2.5 px-3 font-mono text-slate-400">{donor.donor_id || donor.id}</td>
                  <td className="py-2.5 px-3">
                    <div className="font-bold text-white">{donor.name}</div>
                    <div className="text-[10px] text-slate-400">{donor.email}</div>
                  </td>
                  <td className="py-2.5 px-3 font-black text-blood-400 text-sm">{donor.blood || donor.blood_group}</td>
                  <td className="py-2.5 px-3">
                    <span className="px-2 py-0.5 rounded text-[11px] bg-slate-800 text-slate-200 font-bold flex items-center w-max space-x-1">
                      <Heart className="w-3 h-3 text-blood-400 fill-blood-400" />
                      <span>{donor.total_donations !== undefined ? donor.total_donations : 4} Times</span>
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-300 font-semibold">
                    <span className="flex items-center space-x-1">
                      <Clock className="w-3 h-3 text-emerald-400" />
                      <span>{donor.lastDonated || `${donor.last_donation_days || 150} days ago`}</span>
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-400">
                    <div>{donor.location}</div>
                    <div className="font-mono text-slate-300 text-[10px]">{donor.phone}</div>
                  </td>
                  <td className="py-2.5 px-3 text-slate-300 font-medium">
                    <span className="flex items-center space-x-1">
                      <Calendar className="w-3 h-3 text-amber-400" />
                      <span>{donor.preferred_time || 'Morning'}</span>
                    </span>
                  </td>
                  <td className="py-2.5 px-3">
                    <MLPredictionBadge category={donor.category || 'HIGH'} score={donor.availabilityScore || donor.availability_score || 94.5} />
                  </td>
                  <td className="py-2.5 px-3">
                    <button
                      onClick={() => onDeleteDonor && onDeleteDonor(donor.id || donor.donor_id)}
                      title="Delete Donor Record from SQL Database"
                      className="p-1.5 rounded-lg bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800 transition-colors flex items-center space-x-1"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                      <span className="text-[10px]">Delete</span>
                    </button>
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
