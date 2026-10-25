import React, { useState, useMemo, useEffect } from 'react';
import StatCard from '../components/StatCard';
import MLPredictionBadge from '../components/MLPredictionBadge';
import { Users, Droplets, AlertOctagon, BrainCircuit, Activity, Trash2, Heart, Clock, Calendar, Search, ChevronLeft, ChevronRight } from 'lucide-react';

import { getApiBaseUrl, getMlServiceUrl } from '../api/config';
const API_BASE = getApiBaseUrl();
const ML_API_BASE = getMlServiceUrl();

export default function AdminDashboard({ onNavigate, donorsList = [], requestsList = [], currentUser, onDeleteDonor }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 25;
  const [inventoryRows, setInventoryRows] = useState(null);
  const [modelMetrics, setModelMetrics] = useState(null);
  const [operationNotice, setOperationNotice] = useState('');
  const [operationError, setOperationError] = useState(false);
  const isAdmin = Boolean(currentUser?.token && currentUser?.isLoggedIn && currentUser?.role === 'ADMIN');

  useEffect(() => {
    let cancelled = false;
    if (!isAdmin) { setInventoryRows(null); return () => { cancelled = true; }; }
    fetch(`${API_BASE}/api/v1/inventory`, { headers: { Authorization: `Bearer ${currentUser.token}` } })
      .then(async (response) => { const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.detail || 'Inventory summary unavailable.'); return data; })
      .then((data) => { if (!cancelled && Array.isArray(data)) setInventoryRows(data); })
      .catch(() => { if (!cancelled) setInventoryRows(null); });
    return () => { cancelled = true; };
  }, [isAdmin, currentUser?.token]);

  useEffect(() => {
    let cancelled = false;
    fetch(`${ML_API_BASE}/metrics`)
      .then(async (response) => { const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error('Model evaluation metrics unavailable.'); return data; })
      .then((data) => { if (!cancelled && data?.['Random Forest']) setModelMetrics(data['Random Forest']); })
      .catch(() => { if (!cancelled) setModelMetrics(null); });
    return () => { cancelled = true; };
  }, []);

  const handleDelete = async (donor) => {
    if (!isAdmin || typeof onDeleteDonor !== 'function') {
      setOperationNotice('Deleting donor records requires an authenticated administrator.'); setOperationError(true); return;
    }
    if (!window.confirm(`Delete donor record ${donor.donor_id || donor.id}? This cannot be undone.`)) return;
    setOperationNotice(''); setOperationError(false);
    try { await onDeleteDonor(donor.id || donor.donor_id); setOperationNotice('Donor record deleted.'); }
    catch (error) { setOperationNotice(error.message || 'Donor deletion failed.'); setOperationError(true); }
  };

  const totalStock = Array.isArray(inventoryRows) ? inventoryRows.reduce((sum, row) => sum + Number(row.units_available || 0), 0) : null;
  const pendingCount = requestsList.filter((request) => String(request.status || 'PENDING').toUpperCase() === 'PENDING').length;
  const emergencyCount = requestsList.filter((request) => String(request.status || 'PENDING').toUpperCase() === 'PENDING' && String(request.urgency_level || '').toUpperCase() === 'EMERGENCY').length;

  const visibleDonors = isAdmin ? donorsList : [];
  const totalDonorsCount = visibleDonors.length;
  const highAvailCount = visibleDonors.filter(d => d.category === 'HIGH' || d.availability_status === 'HIGH' || (d.availability_score != null && Number(d.availability_score) >= 75)).length;

  const filteredDonors = useMemo(() => {
    if (!searchTerm.trim()) return visibleDonors;
    const term = searchTerm.toLowerCase();
    return visibleDonors.filter(d => 
      (d.name && d.name.toLowerCase().includes(term)) ||
      (d.donor_id && d.donor_id.toLowerCase().includes(term)) ||
      (d.blood_group && d.blood_group.toLowerCase().includes(term)) ||
      (d.blood && d.blood.toLowerCase().includes(term)) ||
      (d.district && d.district.toLowerCase().includes(term)) ||
      (d.taluk && d.taluk.toLowerCase().includes(term)) ||
      (d.location && d.location.toLowerCase().includes(term))
    );
  }, [visibleDonors, searchTerm]);

  const totalPages = Math.max(1, Math.ceil(filteredDonors.length / pageSize));
  const currentSafePage = Math.min(currentPage, totalPages);
  const paginatedDonors = useMemo(() => {
    const start = (currentSafePage - 1) * pageSize;
    return filteredDonors.slice(start, start + pageSize);
  }, [filteredDonors, currentSafePage, pageSize]);

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
          value={totalStock == null ? 'Unavailable' : `${totalStock} Units`}
          subtitle={Array.isArray(inventoryRows) ? `Across ${inventoryRows.length} inventory records` : 'Inventory data could not be retrieved'}
          icon={Droplets}
          trend={Array.isArray(inventoryRows) ? 'Persisted inventory records' : 'Requires an authenticated administrator'}
          color="blood"
        />
        <StatCard
          title="Active Requests"
          value={`${pendingCount} Pending`}
          subtitle={`${emergencyCount} pending emergency requests`}
          icon={AlertOctagon}
          trend="Live request records"
          color="amber"
        />
        <StatCard
          title="ML Engine Accuracy"
          value={modelMetrics?.Accuracy == null ? 'Unavailable' : `${Number(modelMetrics.Accuracy).toFixed(2)}%`}
          subtitle={modelMetrics?.F1_Score == null ? 'Evaluation metrics unavailable' : `F1 Score: ${Number(modelMetrics.F1_Score).toFixed(2)}%`}
          icon={BrainCircuit}
          trend="Stored model evaluation snapshot; synthetic dataset"
          color="blue"
        />
      </div>

      {operationNotice && <div role="status" className={`rounded-xl border p-3 text-xs ${operationError ? 'border-rose-800 bg-rose-950/60 text-rose-200' : 'border-emerald-800 bg-emerald-950/50 text-emerald-200'}`}>{operationNotice}</div>}
      {!isAdmin && <div role="alert" className="rounded-xl border border-amber-800 bg-amber-950/40 p-3 text-xs text-amber-200">Sign in with an administrator account to view protected donor records and inventory metrics. Choosing the Admin view does not grant access.</div>}

      {/* Registered Donors List Visible to Record Manager / Admin */}
      <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-3 border-b border-slate-800 gap-2">
          <div>
            <h3 className="text-sm font-bold text-white">Full Donor Records Directory (Record Manager View)</h3>
            <p className="text-xs text-slate-400">Contains total donation counts, last donation timestamps, ML scores, and contact profiles</p>
          </div>
          <span className="px-2.5 py-1 rounded-lg text-xs bg-blood-950 text-blood-400 border border-blood-800 font-extrabold whitespace-nowrap">
            {visibleDonors.length} SQL Donor Records
          </span>
        </div>

        {/* Search Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by name, donor ID, blood group, district, or taluk..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blood-500"
            />
          </div>
          {searchTerm && (
            <span className="text-xs text-slate-400 self-center">
              Found <strong className="text-white">{filteredDonors.length}</strong> matching donors
            </span>
          )}
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
              {paginatedDonors.map((donor) => (
                <tr key={donor.id || donor.donor_id} className="hover:bg-slate-900/40">
                  <td className="py-2.5 px-3 font-mono text-slate-400">{donor.donor_id || donor.id}</td>
                  <td className="py-2.5 px-3">
                    <div className="font-bold text-white">{donor.name}</div>
                    <div className="text-[10px] text-slate-400">{donor.email}</div>
                  </td>
                  <td className="py-2.5 px-3 font-black text-blood-400 text-sm">{donor.blood || donor.blood_group}</td>
                  <td className="py-2.5 px-3">
                    <span className="px-2 py-0.5 rounded text-[11px] bg-slate-800 text-slate-200 font-bold flex items-center w-max space-x-1">
                      <Heart className="w-3 h-3 text-blood-400 fill-blood-400" />
                      <span>{donor.total_donations == null ? 'Not recorded' : `${donor.total_donations} Times`}</span>
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-300 font-semibold">
                    <span className="flex items-center space-x-1">
                      <Clock className="w-3 h-3 text-emerald-400" />
                      <span>{donor.last_donation_date || (donor.last_donation_days != null ? `${donor.last_donation_days} days ago` : 'Not recorded')}</span>
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-400">
                    <div>{donor.location || [donor.district, donor.taluk].filter(Boolean).join(', ') || 'Location not recorded'}</div>
                    <div className="font-mono text-slate-300 text-[10px]">{donor.phone || 'Phone unavailable'}</div>
                  </td>
                  <td className="py-2.5 px-3 text-slate-300 font-medium">
                    <span className="flex items-center space-x-1">
                      <Calendar className="w-3 h-3 text-amber-400" />
                      <span>{donor.preferred_time || 'Not recorded'}</span>
                    </span>
                  </td>
                  <td className="py-2.5 px-3">
                    {donor.availability_score == null ? <span className="text-slate-500">Not scored</span> : <MLPredictionBadge category={donor.availability_status || donor.category || (Number(donor.availability_score) >= 75 ? 'HIGH' : Number(donor.availability_score) >= 40 ? 'MEDIUM' : 'LOW')} score={Number(donor.availability_score)} />}
                  </td>
                  <td className="py-2.5 px-3">
                    <button
                      onClick={() => handleDelete(donor)}
                      title="Delete Donor Record from SQL Database"
                      disabled={!isAdmin}
                      className="p-1.5 rounded-lg bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800 transition-colors flex items-center space-x-1 disabled:opacity-40"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                      <span className="text-[10px]">Delete</span>
                    </button>
                  </td>
                </tr>
              ))}
              {paginatedDonors.length === 0 && (
                <tr>
                  <td colSpan={9} className="text-center py-8 text-slate-500">
                    No donor records found matching &ldquo;{searchTerm}&rdquo;.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-slate-800 text-xs text-slate-400">
          <div>
            Showing {filteredDonors.length === 0 ? 0 : (currentSafePage - 1) * pageSize + 1} to {Math.min(currentSafePage * pageSize, filteredDonors.length)} of {filteredDonors.length} donors
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentSafePage <= 1}
              className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800 flex items-center space-x-1"
            >
              <ChevronLeft className="w-4 h-4" />
              <span>Previous</span>
            </button>
            <span className="font-semibold text-white px-2">
              Page {currentSafePage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentSafePage >= totalPages}
              className="px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800 flex items-center space-x-1"
            >
              <span>Next</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

    </div>
  );
}
