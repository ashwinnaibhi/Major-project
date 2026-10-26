import React, { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '../api/config';
import axios from 'axios';
import { Package, PlusCircle, CheckCircle, AlertCircle, RefreshCw, Database, ShieldAlert } from 'lucide-react';

const InventoryView = ({ currentUser }) => {
  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({
    blood_group: 'A+',
    units: 5,
    expiry_date: ''
  });
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });

  const token = currentUser?.token || (() => {
    try {
      return JSON.parse(localStorage.getItem('haemopulse_user') || '{}')?.token;
    } catch {
      return null;
    }
  })();

  const isAuthorized = Boolean(
    token && ['HOSPITAL', 'ROLE_HOSPITAL', 'ADMIN', 'ROLE_ADMIN', 'STAFF', 'ROLE_STAFF'].includes(
      String(currentUser?.role || '').toUpperCase()
    )
  );

  const API_BASE = getApiBaseUrl();

  const fetchInventory = useCallback(async () => {
    if (!token || !isAuthorized) {
      setLoading(false);
      setInventory([]);
      return;
    }
    try {
      setLoading(true);
      const res = await axios.get(`${API_BASE}/api/v1/inventory`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setInventory(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error("Failed to load inventory", err);
      setInventory([]);
    } finally {
      setLoading(false);
    }
  }, [token, API_BASE]);

  useEffect(() => {
    fetchInventory();
  }, [fetchInventory]);

  const handleAddStock = async (e) => {
    e.preventDefault();
    setMsg({ type: '', text: '' });

    if (!token || !isAuthorized) {
      setMsg({ type: 'error', text: 'Sign in with an authorized hospital or administrator account to update inventory.' });
      return;
    }

    if (parseInt(formData.units, 10) <= 0) {
      setMsg({ type: 'error', text: 'Stock quantity must be greater than zero.' });
      return;
    }

    try {
      setSubmitting(true);
      const res = await axios.post(`${API_BASE}/api/inventory/add-stock`, {
        blood_group: formData.blood_group,
        units: parseInt(formData.units, 10),
        expiry_date: formData.expiry_date || null
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setMsg({ type: 'success', text: res.data.message || 'Inventory updated successfully.' });
      setFormData({ blood_group: 'A+', units: 5, expiry_date: '' });
      fetchInventory();
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Failed to update stock.' });
    } finally {
      setSubmitting(false);
    }
  };

  if (!token || !isAuthorized) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] p-6">
        <div className="w-full max-w-md p-6 rounded-2xl glass-panel border border-slate-800 text-center space-y-4 bg-slate-950/80 shadow-2xl">
          <div className="w-12 h-12 rounded-2xl bg-amber-950/80 border border-amber-800 flex items-center justify-center text-amber-400 mx-auto">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white">Access Restricted</h3>
            <p className="text-xs text-slate-400 mt-1">
              Detailed blood inventory stock management is restricted to authorized Hospital and Administrator accounts.
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
            <Database className="w-4 h-4" />
            <span>Real-time Blood Bank Stock</span>
          </div>
          <h2 className="text-2xl font-black text-white">Blood Inventory Stock Management</h2>
          <p className="text-xs text-slate-400">
            Monitor verified blood reserves, expiry windows, and update unit quantities.
          </p>
        </div>
        <button
          onClick={fetchInventory}
          disabled={loading || !token}
          className="shrink-0 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3.5 py-2 text-slate-200 text-xs font-bold flex items-center space-x-1.5 transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Stock</span>
        </button>
      </div>

      {msg.text && (
        <div className={`p-4 rounded-xl text-xs font-bold flex items-center space-x-2 border ${
          msg.type === 'success' ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300' : 'bg-rose-950/60 border-rose-800 text-rose-300'
        }`}>
          {msg.type === 'success' ? <CheckCircle className="w-4 h-4 flex-shrink-0" /> : <AlertCircle className="w-4 h-4 flex-shrink-0" />}
          <span>{msg.text}</span>
        </div>
      )}

      {/* Add Stock Form */}
      <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center space-x-2">
          <PlusCircle className="w-4 h-4 text-blood-400" />
          <span>Add Units to Blood Stock</span>
        </h3>
        <form onSubmit={handleAddStock} className="grid grid-cols-1 sm:grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Blood Group</label>
            <select
              value={formData.blood_group}
              onChange={(e) => setFormData({ ...formData, blood_group: e.target.value })}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-xs font-bold focus:border-blood-500 outline-none"
            >
              {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(bg => (
                <option key={bg} value={bg} className="bg-slate-900 text-white">{bg}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Units to Add</label>
            <input
              type="number"
              min="1"
              required
              value={formData.units}
              onChange={(e) => setFormData({ ...formData, units: e.target.value })}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-xs font-bold focus:border-blood-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Expiry Date (Optional)</label>
            <input
              type="date"
              value={formData.expiry_date}
              onChange={(e) => setFormData({ ...formData, expiry_date: e.target.value })}
              className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2 text-xs font-bold focus:border-blood-500 outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={submitting || !token}
            className="w-full bg-blood-700 hover:bg-blood-600 text-white text-xs font-bold py-2.5 rounded-xl shadow-sm transition flex items-center justify-center space-x-1.5 disabled:opacity-50"
          >
            <Package className="w-3.5 h-3.5" />
            <span>{submitting ? 'Saving...' : 'Add Stock'}</span>
          </button>
        </form>
      </div>

      {/* Current Inventory Display */}
      <div className="rounded-2xl glass-panel border border-slate-800 overflow-hidden">
        <div className="p-4 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider">Persisted Blood Stock</h3>
          <span className="text-[10px] text-slate-400 font-mono">
            {inventory.reduce((sum, item) => sum + Number(item.units || 0), 0)} Total Units
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-5">
          {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(bg => {
            const item = inventory.find(i => i.blood_group === bg);
            const units = item ? item.units : 0;
            return (
              <div key={bg} className="bg-slate-900/60 border border-slate-800/90 rounded-xl p-4 flex flex-col justify-between hover:border-slate-700 transition">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xl font-black text-blood-400">{bg}</span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                    units > 10 ? 'bg-emerald-950 text-emerald-300 border-emerald-800' :
                    units > 0 ? 'bg-amber-950 text-amber-300 border-amber-800' :
                    'bg-slate-950 text-slate-400 border-slate-800'
                  }`}>
                    {units > 10 ? 'Available' : units > 0 ? 'Low Stock' : 'Out of Stock'}
                  </span>
                </div>
                <div>
                  <div className="text-3xl font-extrabold text-white">{units}</div>
                  <div className="text-[11px] text-slate-400 mt-1 truncate">
                    {item?.expiry_date ? `Expires: ${item.expiry_date}` : 'No expiry set'}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default InventoryView;
