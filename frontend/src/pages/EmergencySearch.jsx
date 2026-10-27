import React, { useState } from 'react';
import { getApiBaseUrl } from '../api/config';
import axios from 'axios';
import { Search, AlertCircle, Send, CheckCircle2, MapPin, Phone, UserCheck, ShieldAlert } from 'lucide-react';

const EmergencySearch = ({ currentUser }) => {
  const [bloodGroup, setBloodGroup] = useState('A+');
  const [donors, setDonors] = useState([]);
  const [compatibleGroups, setCompatibleGroups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedDonors, setSelectedDonors] = useState([]);
  const [alertSuccess, setAlertSuccess] = useState('');
  const [alertError, setAlertError] = useState('');
  const [hasSearched, setHasSearched] = useState(false);

  const isHospital = Boolean(
    currentUser?.token &&
    currentUser?.isLoggedIn &&
    ['HOSPITAL', 'ROLE_HOSPITAL'].includes(String(currentUser?.role || '').toUpperCase())
  );

  const token = currentUser?.token || localStorage.getItem('token');
  const API_BASE = getApiBaseUrl();

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!token || !isHospital) {
      setAlertError('Authenticated hospital account required.');
      return;
    }
    setLoading(true);
    setAlertSuccess('');
    setAlertError('');
    setHasSearched(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await axios.get(`${API_BASE}/api/donors/emergency-search`, {
        params: { blood_group: bloodGroup },
        headers
      });
      setDonors(res.data.donors || []);
      setCompatibleGroups(res.data.compatible_groups || []);
      setSelectedDonors((res.data.donors || []).map(d => d.id));
    } catch (err) {
      setAlertError(err.response?.data?.detail || 'Emergency search failed. Ensure the backend is running.');
      setDonors([]);
      setCompatibleGroups([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleDonorSelect = (id) => {
    if (selectedDonors.includes(id)) {
      setSelectedDonors(selectedDonors.filter(x => x !== id));
    } else {
      setSelectedDonors([...selectedDonors, id]);
    }
  };

  const sendAlerts = async () => {
    if (selectedDonors.length === 0) {
      setAlertError('Please select at least one donor to alert.');
      return;
    }
    if (!token || !isHospital) {
      setAlertError('Sign in with an authorized hospital account to broadcast emergency alerts.');
      return;
    }
    setAlertError('');
    try {
      const res = await axios.post(`${API_BASE}/api/donors/emergency-alert`, {
        blood_group: bloodGroup,
        urgency: 'Critical',
        units_needed: 2,
        donor_ids: selectedDonors
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setAlertSuccess(res.data.message || 'Emergency alerts dispatched successfully.');
    } catch (err) {
      setAlertError(err.response?.data?.detail || 'Failed to dispatch emergency alerts.');
    }
  };

  if (!isHospital) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] p-6">
        <div className="w-full max-w-md p-6 rounded-2xl glass-panel border border-slate-800 text-center space-y-4 bg-slate-950/80 shadow-2xl">
          <div className="w-12 h-12 rounded-2xl bg-amber-950/80 border border-amber-800 flex items-center justify-center text-amber-400 mx-auto">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">Access Restricted</h3>
            <p className="text-xs text-slate-400 mt-1">
              Emergency Donor Search &amp; Alert is restricted to authenticated Hospital accounts only.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-blood-400 mb-1">
            <ShieldAlert className="w-4 h-4" />
            <span>Geo-Targeted Emergency Dispatch</span>
          </div>
          <h2 className="text-2xl font-black text-white">Emergency Donor Search &amp; Alert</h2>
          <p className="text-xs text-slate-400">
            Dynamic donor search based on verified blood compatibility and location coordinates.
          </p>
        </div>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="p-5 rounded-2xl glass-panel border border-slate-800 flex flex-wrap gap-4 items-center justify-between">
        <div className="flex items-center space-x-3">
          <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">Patient Blood Group Needed:</label>
          <select
            value={bloodGroup}
            onChange={(e) => setBloodGroup(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-xs font-bold focus:border-blood-500 outline-none"
          >
            {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(bg => (
              <option key={bg} value={bg} className="bg-slate-900 text-white">{bg}</option>
            ))}
          </select>
        </div>

        {compatibleGroups.length > 0 && (
          <div className="flex items-center space-x-2 text-xs text-slate-400 bg-slate-900/90 px-3 py-2 rounded-xl border border-slate-800">
            <span className="font-semibold text-slate-300">Compatible Groups:</span>
            <div className="flex gap-1">
              {compatibleGroups.map(cg => (
                <span key={cg} className="bg-blood-950/80 border border-blood-800 text-blood-400 px-2 py-0.5 rounded text-xs font-mono font-bold">
                  {cg}
                </span>
              ))}
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="bg-blood-700 hover:bg-blood-600 text-white px-4 py-2 rounded-xl text-xs font-bold flex items-center space-x-2 shadow-sm transition disabled:opacity-50"
        >
          <Search className="w-4 h-4" />
          <span>{loading ? 'Searching...' : hasSearched ? 'Refresh Donors' : 'Search Donors'}</span>
        </button>
      </form>

      {alertSuccess && (
        <div className="p-4 bg-emerald-950/60 border border-emerald-800 text-emerald-300 rounded-xl flex items-center space-x-2 text-xs font-bold">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span>{alertSuccess}</span>
        </div>
      )}

      {alertError && (
        <div className="p-4 bg-rose-950/60 border border-rose-800 text-rose-300 rounded-xl flex items-center space-x-2 text-xs font-bold" role="alert">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{alertError}</span>
        </div>
      )}

      {/* Donor Results */}
      {hasSearched && (
        <div className="rounded-2xl glass-panel border border-slate-800 overflow-hidden space-y-0">
          <div className="p-4 border-b border-slate-800 bg-slate-900/80 flex justify-between items-center">
            <span className="text-xs font-bold text-white uppercase tracking-wider">
              Matching Eligible Donors ({donors.length})
            </span>
            {donors.length > 0 && (
              <button
                onClick={sendAlerts}
                className="bg-amber-700 hover:bg-amber-600 text-white px-3 py-1.5 rounded-xl text-xs font-bold flex items-center space-x-1.5 shadow-sm transition"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Broadcast Emergency Alert ({selectedDonors.length})</span>
              </button>
            )}
          </div>

          <div className="divide-y divide-slate-800">
            {donors.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs">
                No compatible available donors found in the immediate vicinity for {bloodGroup}.
              </div>
            ) : (
              donors.map((d) => (
                <div key={d.id} className="p-4 flex items-center justify-between hover:bg-slate-900/40 transition">
                  <div className="flex items-center space-x-4">
                    <input
                      type="checkbox"
                      checked={selectedDonors.includes(d.id)}
                      onChange={() => toggleDonorSelect(d.id)}
                      className="h-4 w-4 text-blood-600 rounded bg-slate-900 border-slate-700 focus:ring-blood-500 cursor-pointer"
                    />
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-white text-xs">{d.name || d.full_name}</span>
                        <span className="bg-blood-950 text-blood-400 border border-blood-800 font-bold px-2 py-0.5 rounded text-[10px]">
                          {d.blood_group}
                        </span>
                      </div>
                      <div className="flex items-center space-x-4 text-[11px] text-slate-400 mt-1">
                        <span className="flex items-center space-x-1">
                          <MapPin className="w-3.5 h-3.5 text-blood-400" />
                          <span>{d.taluk || '—'}, {d.district || '—'} (~{d.estimated_distance_km} km)</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <Phone className="w-3.5 h-3.5 text-emerald-400" />
                          <span>{d.phone || 'Contact on file'}</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <span className="inline-flex items-center text-[11px] font-bold text-emerald-400 bg-emerald-950/80 px-2.5 py-1 rounded-full border border-emerald-800">
                      <UserCheck className="w-3 h-3 mr-1" />
                      Available
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default EmergencySearch;
