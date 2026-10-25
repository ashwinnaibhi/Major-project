import React, { useState, useEffect } from 'react';
import { getApiBaseUrl } from '../api/config';
import axios from 'axios';
import { Search, AlertCircle, Send, CheckCircle2, MapPin, Phone, UserCheck } from 'lucide-react';

const EmergencySearch = () => {
  const [bloodGroup, setBloodGroup] = useState('A+');
  const [donors, setDonors] = useState([]);
  const [compatibleGroups, setCompatibleGroups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedDonors, setSelectedDonors] = useState([]);
  const [alertSuccess, setAlertSuccess] = useState('');
  const [alertError, setAlertError] = useState('');
  const [hasSearched, setHasSearched] = useState(false);

  const token = localStorage.getItem('token');
  const API_BASE = getApiBaseUrl();

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setAlertSuccess('');
    setAlertError('');
    setHasSearched(true);
    try {
      const res = await axios.get(`${API_BASE}/api/donors/emergency-search`, {
        params: { blood_group: bloodGroup },
        headers: { Authorization: `Bearer ${token}` }
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

  // Do NOT auto-search on mount — require the user to click Search
  // This prevents confusing results when the blood group changes

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
      setAlertSuccess(res.data.message);
    } catch (err) {
      setAlertError('Failed to dispatch emergency alerts.');
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Emergency Donor Search & Alert</h1>
        <p className="text-gray-500 text-sm">
          Dynamic search based on verified blood compatibility and donor location.
        </p>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex flex-wrap gap-4 items-center justify-between">
        <div className="flex items-center space-x-3">
          <label className="text-sm font-medium text-gray-700">Patient Blood Group Needed:</label>
          <select
            value={bloodGroup}
            onChange={(e) => setBloodGroup(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm font-semibold focus:ring-2 focus:ring-red-500 outline-none"
          >
            {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(bg => (
              <option key={bg} value={bg}>{bg}</option>
            ))}
          </select>
        </div>

        {compatibleGroups.length > 0 && (
          <div className="flex items-center space-x-2 text-xs text-gray-600 bg-gray-50 px-3 py-2 rounded-lg border">
            <span className="font-semibold text-gray-700">Compatible Donors:</span>
            <div className="flex gap-1">
              {compatibleGroups.map(cg => (
                <span key={cg} className="bg-red-50 border border-red-200 text-red-700 px-1.5 py-0.5 rounded font-mono font-bold">
                  {cg}
                </span>
              ))}
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center space-x-2 shadow-sm transition"
        >
          <Search className="w-4 h-4" />
          <span>{loading ? 'Searching...' : hasSearched ? 'Refresh Donors' : 'Search Donors'}</span>
        </button>
      </form>

      {alertSuccess && (
        <div className="p-4 bg-green-50 border border-green-200 text-green-700 rounded-lg flex items-center space-x-2 text-sm">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          <span>{alertSuccess}</span>
        </div>
      )}

      {alertError && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg flex items-center space-x-2 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{alertError}</span>
        </div>
      )}

      {/* Donor Results */}
      {hasSearched && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="p-4 border-b bg-gray-50 flex justify-between items-center">
            <span className="text-sm font-semibold text-gray-700">
              Matching Eligible Donors ({donors.length})
            </span>
            {donors.length > 0 && (
              <button
                onClick={sendAlerts}
                className="bg-orange-600 hover:bg-orange-700 text-white px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 shadow-sm transition"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Broadcast Emergency Alert ({selectedDonors.length})</span>
              </button>
            )}
          </div>

          <div className="divide-y divide-gray-100">
            {donors.length === 0 ? (
              <div className="p-8 text-center text-gray-400">
                No compatible available donors found in the immediate vicinity for {bloodGroup}.
              </div>
            ) : (
              donors.map((d) => (
                <div key={d.id} className="p-4 flex items-center justify-between hover:bg-gray-50 transition">
                  <div className="flex items-center space-x-4">
                    <input
                      type="checkbox"
                      checked={selectedDonors.includes(d.id)}
                      onChange={() => toggleDonorSelect(d.id)}
                      className="h-4 w-4 text-red-600 rounded border-gray-300 focus:ring-red-500 cursor-pointer"
                    />
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-gray-900 text-sm">{d.name || d.full_name}</span>
                        <span className="bg-red-100 text-red-700 font-bold px-2 py-0.5 rounded text-xs">
                          {d.blood_group}
                        </span>
                      </div>
                      <div className="flex items-center space-x-4 text-xs text-gray-500 mt-1">
                        <span className="flex items-center space-x-1">
                          <MapPin className="w-3.5 h-3.5" />
                          <span>{d.taluk || '—'}, {d.district || '—'} (~{d.estimated_distance_km} km)</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <Phone className="w-3.5 h-3.5" />
                          <span>{d.phone || 'Contact on file'}</span>
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <span className="inline-flex items-center text-xs font-medium text-green-700 bg-green-50 px-2 py-1 rounded-full border border-green-200">
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
