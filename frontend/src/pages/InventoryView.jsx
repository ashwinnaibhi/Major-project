import React, { useState, useEffect } from 'react';
import { getApiBaseUrl } from '../api/config';
import axios from 'axios';
import { Package, PlusCircle, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';

const InventoryView = () => {
  const [inventory, setInventory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({
    blood_group: 'A+',
    units: 5,
    expiry_date: ''
  });
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });

  const token = localStorage.getItem('token');
  const API_BASE = getApiBaseUrl();

  const fetchInventory = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API_BASE}/api/inventory`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setInventory(res.data);
    } catch (err) {
      console.error("Failed to load inventory", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInventory();
  }, []);

  const handleAddStock = async (e) => {
    e.preventDefault();
    setMsg({ type: '', text: '' });
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

      setMsg({ type: 'success', text: res.data.message });
      setFormData({ blood_group: 'A+', units: 5, expiry_date: '' });
      fetchInventory();
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Failed to update stock.' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Blood Inventory Stock Management</h1>
          <p className="text-gray-500 text-sm">Monitor and update real-time hospital blood reserves</p>
        </div>
        <button
          onClick={fetchInventory}
          className="text-gray-600 hover:text-gray-900 border px-3 py-1.5 rounded-lg flex items-center space-x-1 text-sm bg-white shadow-sm"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Refresh Stock</span>
        </button>
      </div>

      {msg.text && (
        <div className={`p-4 rounded-lg text-sm flex items-center space-x-2 border ${
          msg.type === 'success' ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700'
        }`}>
          {msg.type === 'success' ? <CheckCircle className="w-5 h-5 flex-shrink-0" /> : <AlertCircle className="w-5 h-5 flex-shrink-0" />}
          <span>{msg.text}</span>
        </div>
      )}

      {/* Add Stock Form */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center space-x-2">
          <PlusCircle className="w-5 h-5 text-red-600" />
          <span>Add Units to Repository</span>
        </h2>
        <form onSubmit={handleAddStock} className="grid grid-cols-1 sm:grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">Blood Group</label>
            <select
              value={formData.blood_group}
              onChange={(e) => setFormData({ ...formData, blood_group: e.target.value })}
              className="w-full border rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-red-500 outline-none"
            >
              {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(bg => (
                <option key={bg} value={bg}>{bg}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">Units to Add</label>
            <input
              type="number"
              min="1"
              required
              value={formData.units}
              onChange={(e) => setFormData({ ...formData, units: e.target.value })}
              className="w-full border rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-red-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">Expiry Date (Optional)</label>
            <input
              type="date"
              value={formData.expiry_date}
              onChange={(e) => setFormData({ ...formData, expiry_date: e.target.value })}
              className="w-full border rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-red-500 outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-red-600 hover:bg-red-700 text-white font-medium p-2.5 rounded-lg shadow-sm transition text-sm flex items-center justify-center space-x-1"
          >
            <Package className="w-4 h-4" />
            <span>{submitting ? 'Saving...' : 'Add Stock'}</span>
          </button>
        </form>
      </div>

      {/* Current Inventory Display */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b bg-gray-50">
          <h3 className="font-semibold text-gray-800 text-sm">Persisted Blood Stock</h3>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-6">
          {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(bg => {
            const item = inventory.find(i => i.blood_group === bg);
            const units = item ? item.units : 0;
            return (
              <div key={bg} className="border rounded-xl p-4 flex flex-col justify-between hover:shadow-sm transition">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xl font-black text-red-600">{bg}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                    units > 10 ? 'bg-green-100 text-green-700' :
                    units > 0 ? 'bg-yellow-100 text-yellow-700' :
                    'bg-red-100 text-red-700'
                  }`}>
                    {units > 10 ? 'Available' : units > 0 ? 'Low Stock' : 'Out of Stock'}
                  </span>
                </div>
                <div>
                  <div className="text-3xl font-bold text-gray-800">{units}</div>
                  <div className="text-xs text-gray-400 mt-1">
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