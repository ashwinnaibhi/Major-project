import React, { useState } from 'react';
import StatCard from '../components/StatCard';
import MLPredictionBadge from '../components/MLPredictionBadge';
import { Heart, CalendarCheck, Clock, Award, Bell, ShieldCheck, UserCheck, AlertCircle, PhoneCall, Building2, Send, CheckCircle } from 'lucide-react';

export default function DonorDashboard({ currentUser, requestsList = [] }) {
  // Use currently logged-in / registered donor profile dynamically
  const donorProfile = {
    id: currentUser?.id || 'DNR-1001',
    name: currentUser?.name || 'John Doe',
    blood_group: currentUser?.blood_group || currentUser?.blood || 'O+',
    email: currentUser?.email || 'john.doe@email.com',
    total_donations: currentUser?.total_donations || 1,
    last_donation_days: currentUser?.last_donation_days || 180,
    eligibility_status: 'Eligible to Donate Now',
    availability_score: currentUser?.availabilityScore || currentUser?.availability_score || 91.5,
    availability_category: currentUser?.category || currentUser?.availability_category || 'HIGH',
    preferred_time: currentUser?.preferred_time || 'Morning',
    health_score: 95
  };

  const [respondedAlerts, setRespondedAlerts] = useState([]);

  // Filter emergency requests matching donor's blood group
  const emergencyRequestsForGroup = requestsList.filter(
    r => (r.blood_group || r.blood) === donorProfile.blood_group
  );

  const donationHistory = [
    { id: 'DON-901', date: '2026-03-15', location: 'Central Blood Bank Lab', units: 1, blood: donorProfile.blood_group, status: 'Verified' },
  ];

  const hospitalsList = [
    { name: 'City General Hospital (Emergency Cell)', phone: '+1-800-555-0101', address: '100 Healthcare Blvd, Suite 400', contactPerson: 'Dr. Alice Smith' },
    { name: 'St. Jude Emergency Center (Trauma Desk)', phone: '+1-800-555-0102', address: '450 Trauma Way, East Wing', contactPerson: 'Dr. Mark Johnson' }
  ];

  const handleRespondToHospital = (reqId) => {
    if (!respondedAlerts.includes(reqId)) {
      setRespondedAlerts([...respondedAlerts, reqId]);
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Donor Header Banner */}
      <div className="p-6 rounded-2xl glass-panel bg-gradient-to-r from-slate-900 via-slate-900 to-blood-950/50 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blood-700 to-blood-500 flex items-center justify-center text-white font-black text-xl shadow-lg glow-red">
            {donorProfile.blood_group}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-2xl font-black text-white">{donorProfile.name}</h2>
              <span className="px-2 py-0.5 rounded text-xs bg-slate-800 text-blood-400 font-mono font-bold">
                {donorProfile.id}
              </span>
            </div>
            <p className="text-xs text-slate-400 flex items-center space-x-2 mt-1">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>{donorProfile.email} &bull; {donorProfile.eligibility_status} &bull; Health Score: {donorProfile.health_score}/100</span>
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <MLPredictionBadge category={donorProfile.availability_category} score={donorProfile.availability_score} />
        </div>
      </div>

      {/* Stat Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Blood Donations"
          value={`${donorProfile.total_donations} Times`}
          subtitle="Lives Impacted"
          icon={Heart}
          color="blood"
        />
        <StatCard
          title="Days Since Last Donation"
          value={`${donorProfile.last_donation_days} Days`}
          subtitle="90 days minimum threshold passed"
          icon={Clock}
          color="emerald"
        />
        <StatCard
          title="ML Response Score"
          value={`${donorProfile.availability_score}%`}
          subtitle={`${donorProfile.availability_category} Availability Tier`}
          icon={Award}
          color="blue"
        />
        <StatCard
          title="Preferred Time Slot"
          value={donorProfile.preferred_time}
          subtitle="Morning (8 AM - 12 PM)"
          icon={CalendarCheck}
          color="amber"
        />
      </div>

      {/* Main Grid: Hospital Notifications & Hospital Emergency Hotlines */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Hospital Emergency Requisition Notifications Feed */}
        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <Bell className="w-4 h-4 text-blood-400 animate-bounce" />
              <span>Hospital Emergency Requests for {donorProfile.blood_group}</span>
            </h3>
            <span className="px-2 py-0.5 rounded text-[10px] bg-blood-950 text-blood-400 border border-blood-800 font-extrabold">
              {emergencyRequestsForGroup.length} Live Alerts
            </span>
          </div>

          <div className="space-y-3">
            {emergencyRequestsForGroup.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-400 bg-slate-900/50 rounded-xl border border-slate-800">
                No active emergency requests for {donorProfile.blood_group} blood group right now.
              </div>
            ) : (
              emergencyRequestsForGroup.map((req) => {
                const isResponded = respondedAlerts.includes(req.id || req._id);
                return (
                  <div
                    key={req.id || req._id}
                    className="p-4 rounded-xl bg-blood-950/30 border border-blood-800/80 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white flex items-center space-x-1.5">
                        <AlertCircle className="w-4 h-4 text-blood-400 animate-pulse" />
                        <span>{req.hospital_name || req.hospital}</span>
                      </span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-blood-950 text-blood-400 border border-blood-800">
                        {req.urgency_level || req.urgency}
                      </span>
                    </div>

                    <div className="text-xs text-slate-300">
                      Need: <strong className="text-blood-400">{req.units_needed || req.units} units</strong> of <strong className="text-white">{donorProfile.blood_group}</strong> for <span className="text-slate-400">{req.patient_name || req.patient}</span>.
                    </div>

                    <div className="pt-2 flex items-center justify-between">
                      <span className="text-[10px] text-slate-500">Requested: {req.request_date || 'Today'}</span>

                      <button
                        onClick={() => handleRespondToHospital(req.id || req._id)}
                        disabled={isResponded}
                        className={`px-3.5 py-1.5 rounded-lg text-xs font-bold flex items-center space-x-1.5 transition-all ${
                          isResponded
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                            : 'bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white shadow-md glow-red'
                        }`}
                      >
                        {isResponded ? (
                          <>
                            <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                            <span>Response Sent to Hospital!</span>
                          </>
                        ) : (
                          <>
                            <Send className="w-3.5 h-3.5" />
                            <span>Confirm Availability to Hospital</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Hospital Emergency Contact Cell & Hotlines */}
        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <Building2 className="w-4 h-4 text-blood-400" />
              <span>Hospital Emergency Contact Cell</span>
            </h3>
            <span className="text-xs text-slate-400">Direct Hotline Contact</span>
          </div>

          <p className="text-xs text-slate-400">
            Donors can directly contact emergency hospital blood banks during urgent calls:
          </p>

          <div className="space-y-3">
            {hospitalsList.map((hosp, idx) => (
              <div key={idx} className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-white">{hosp.name}</h4>
                  <span className="text-[10px] text-slate-400">{hosp.contactPerson}</span>
                </div>
                <p className="text-[11px] text-slate-400">{hosp.address}</p>

                <div className="pt-1 flex items-center justify-between">
                  <a
                    href={`tel:${hosp.phone}`}
                    className="px-3 py-1.5 rounded-lg bg-emerald-950 hover:bg-emerald-900 text-emerald-300 border border-emerald-800 text-xs font-bold flex items-center space-x-1.5 transition-colors"
                  >
                    <PhoneCall className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Call Emergency Hotline ({hosp.phone})</span>
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

    </div>
  );
}
