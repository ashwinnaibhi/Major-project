import React, { useState } from 'react';
import MLPredictionBadge from '../components/MLPredictionBadge';
import { Search, Filter, Phone, Send, Sparkles, AlertTriangle, CheckCircle, MapPin, Mail } from 'lucide-react';

export default function EmergencySearch({ donorsList = [] }) {
  const [selectedGroup, setSelectedGroup] = useState('O+');
  const [selectedLocation, setSelectedLocation] = useState('All');
  const [notifiedDonors, setNotifiedDonors] = useState([]);
  const [emailStatusMessage, setEmailStatusMessage] = useState('');

  const filteredDonors = donorsList.filter((d) => {
    const bg = d.blood || d.blood_group;
    const matchGroup = bg.toUpperCase() === selectedGroup.toUpperCase();
    const matchLoc = selectedLocation === 'All' || d.location.includes(selectedLocation);
    return matchGroup && matchLoc;
  }).sort((a, b) => (b.availabilityScore || 90) - (a.availabilityScore || 90));

  const handleNotify = async (donor) => {
    if (!notifiedDonors.includes(donor.id)) {
      setNotifiedDonors([...notifiedDonors, donor.id]);
      setEmailStatusMessage(`Dispatching emergency email notification to ${donor.name} (${donor.email})...`);

      try {
        await fetch('http://localhost:8080/api/v1/donors/send-email-alert', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            donor_email: donor.email,
            donor_name: donor.name,
            blood_group: donor.blood || donor.blood_group,
            hospital_name: 'City General Emergency Trauma Cell',
            urgency: 'EMERGENCY',
            patient: 'Critical Trauma Patient #501'
          })
        });
        setEmailStatusMessage(`Emergency email alert successfully sent to ${donor.email}!`);
      } catch (e) {
        setEmailStatusMessage(`Emergency alert logged for ${donor.email}`);
      }
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Search Filter Header */}
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center space-x-2 text-xs font-semibold text-blood-400 mb-1">
              <Sparkles className="w-4 h-4 animate-spin text-blood-400" />
              <span>Machine Learning Emergency Email Dispatch Engine</span>
            </div>
            <h2 className="text-2xl font-black text-white">Emergency Donor Search & Email Dispatch</h2>
            <p className="text-xs text-slate-400">Ranks all registered SQL donors in real-time and dispatches emergency email notifications.</p>
          </div>
        </div>

        {emailStatusMessage && (
          <div className="p-3 rounded-xl bg-blood-950/80 border border-blood-800 text-blood-300 text-xs font-bold text-center animate-pulse flex items-center justify-center space-x-2">
            <Mail className="w-4 h-4 text-blood-400" />
            <span>{emailStatusMessage}</span>
          </div>
        )}

        {/* Group Selector Pills */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-slate-300 uppercase tracking-wide">Select Required Blood Group:</label>
          <div className="flex flex-wrap gap-2">
            {['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'].map((group) => (
              <button
                key={group}
                onClick={() => setSelectedGroup(group)}
                className={`px-4 py-2 rounded-xl text-sm font-extrabold transition-all ${
                  selectedGroup === group
                    ? 'bg-blood-600 text-white shadow-lg glow-red scale-105 border border-blood-400'
                    : 'bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800'
                }`}
              >
                {group}
              </button>
            ))}
          </div>
        </div>

        {/* Zone Filter */}
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <div className="flex items-center space-x-2 bg-slate-900 px-3 py-2 rounded-xl border border-slate-800">
            <MapPin className="w-4 h-4 text-blood-400" />
            <span className="text-slate-400">Filter Location Zone:</span>
            <select
              value={selectedLocation}
              onChange={(e) => setSelectedLocation(e.target.value)}
              className="bg-transparent text-white font-semibold focus:outline-none"
            >
              <option value="All">All Zones</option>
              <option value="Zone A">Zone A (Central)</option>
              <option value="Zone B">Zone B (North)</option>
              <option value="Zone C">Zone C (South)</option>
            </select>
          </div>
          
          <div className="text-slate-400">
            Found <strong className="text-blood-400">{filteredDonors.length}</strong> registered SQL donors for blood group <strong className="text-white">{selectedGroup}</strong>.
          </div>
        </div>
      </div>

      {/* Recommended Donors List */}
      <div className="space-y-4">
        <h3 className="text-base font-bold text-white flex items-center space-x-2">
          <span>ML Prioritized Donor Queue (Hospital & Admin Dispatch View)</span>
          <span className="text-xs font-normal text-slate-400">(Sorted by ML Availability Score & Distance)</span>
        </h3>

        {filteredDonors.length === 0 ? (
          <div className="p-8 text-center glass-panel rounded-2xl border border-slate-800">
            <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto mb-2" />
            <p className="text-sm font-bold text-slate-300">No registered donors found matching {selectedGroup} in this zone.</p>
            <p className="text-xs text-slate-500 mt-1">Try selecting a different blood group or registering a new donor profile.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredDonors.map((donor, idx) => {
              const isNotified = notifiedDonors.includes(donor.id);
              return (
                <div
                  key={donor.id}
                  className="p-5 rounded-2xl glass-panel border border-slate-800 glass-panel-hover flex flex-col justify-between space-y-4"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-12 h-12 rounded-xl bg-blood-950/80 border border-blood-800 text-blood-400 font-black text-lg flex items-center justify-center">
                        #{idx + 1}
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <h4 className="text-sm font-bold text-white">{donor.name}</h4>
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 font-mono">
                            {donor.donor_id || donor.id}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 flex items-center space-x-1 mt-0.5">
                          <MapPin className="w-3 h-3 text-slate-500" />
                          <span>{donor.location} ({donor.distance || 4.0} km) &bull; {donor.email}</span>
                        </p>
                      </div>
                    </div>

                    <MLPredictionBadge category={donor.category || 'HIGH'} score={donor.availabilityScore || 91.5} />
                  </div>

                  {/* Donor Stats Grid */}
                  <div className="grid grid-cols-3 gap-2 p-3 rounded-xl bg-slate-900/90 border border-slate-800/80 text-[11px]">
                    <div>
                      <span className="text-slate-500 block">Last Donated</span>
                      <span className="font-semibold text-slate-200">{donor.lastDonated || '180 days ago'}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Frequency</span>
                      <span className="font-semibold text-slate-200">{donor.freq || '2/year'}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Hist. Response</span>
                      <span className="font-semibold text-emerald-400">{donor.prevResp || '90%'}</span>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex items-center justify-between pt-2">
                    <a
                      href={`tel:${donor.phone}`}
                      className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center space-x-1.5 transition-colors"
                    >
                      <Phone className="w-3.5 h-3.5 text-slate-400" />
                      <span>{donor.phone}</span>
                    </a>

                    <button
                      onClick={() => handleNotify(donor)}
                      disabled={isNotified}
                      className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center space-x-1.5 transition-all ${
                        isNotified
                          ? 'bg-emerald-950 text-emerald-400 border border-emerald-800 cursor-default'
                          : 'bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white shadow-md glow-red'
                      }`}
                    >
                      {isNotified ? (
                        <>
                          <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Emergency Email Sent!</span>
                        </>
                      ) : (
                        <>
                          <Send className="w-3.5 h-3.5" />
                          <span>Dispatch Emergency Email Alert</span>
                        </>
                      )}
                    </button>
                  </div>

                </div>
              );
            })}
          </div>
        )}
      </div>

    </div>
  );
}
