import React, { useState, useEffect } from 'react';
import { getApiBaseUrl } from '../api/config';
import axios from 'axios';
import { PlusCircle, Clock, AlertTriangle, CheckCircle, FileText } from 'lucide-react';

const RequestsView = () => {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({
    blood_group: 'A+',
    units_requested: 1,
    urgency: 'Medium',
    notes: ''
  });
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const token = localStorage.getItem('token');
  const API_BASE = getApiBaseUrl();

  const fetchRequests = async () => {
    try {
      setLoading(true);
      const res = await axios.get(`${API_BASE}/api/requisitions`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRequests(res.data);
    } catch (err) {
      console.error("Failed to load requisitions", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');
    try {
      await axios.post(`${API_BASE}/api/requisitions`, {
        blood_group: formData.blood_group,
        units_requested: parseInt(formData.units_requested, 10),
        urgency: formData.urgency,
        notes: formData.notes
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSuccessMsg('Requisition submitted successfully.');
      setShowModal(false);
      setFormData({ blood_group: 'A+', units_requested: 1, urgency: 'Medium', notes: '' });
      fetchRequests();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Failed to submit requisition.');
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Hospital Blood Requisitions</h1>
          <p className="text-gray-500 text-sm">Create and track hospital blood supply requisitions</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg flex items-center space-x-2 font-medium transition shadow-sm"
        >
          <PlusCircle className="w-5 h-5" />
          <span>New Requisition</span>
        </button>
      </div>

      {successMsg && (
        <div className="p-4 bg-green-50 border border-green-200 text-green-700 rounded-lg flex items-center space-x-2">
          <CheckCircle className="w-5 h-5 flex-shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Requisitions Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-600">
            <thead className="bg-gray-50 text-gray-700 font-semibold border-b">
              <tr>
                <th className="py-3 px-4">Req ID</th>
                <th className="py-3 px-4">Blood Group</th>
                <th className="py-3 px-4">Units</th>
                <th className="py-3 px-4">Urgency</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Submitted At</th>
                <th className="py-3 px-4">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                <tr>
                  <td colSpan="7" className="text-center py-8 text-gray-400">Loading requisitions...</td>
                </tr>
              ) : requests.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center py-8 text-gray-400">No requisitions found.</td>
                </tr>
              ) : (
                requests.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50 transition">
                    <td className="py-3 px-4 font-mono font-medium text-gray-900">REQ-{r.id}</td>
                    <td className="py-3 px-4">
                      <span className="inline-block bg-red-100 text-red-700 font-bold px-2 py-0.5 rounded text-xs">
                        {r.blood_group}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-semibold">{r.units_requested}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                        r.urgency === 'Critical' ? 'bg-red-600 text-white' :
                        r.urgency === 'High' ? 'bg-orange-100 text-orange-700' :
                        'bg-blue-100 text-blue-700'
                      }`}>
                        {r.urgency}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="flex items-center space-x-1 text-xs font-medium text-gray-600">
                        <Clock className="w-3.5 h-3.5 text-gray-400" />
                        <span>{r.status || 'Pending'}</span>
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-gray-500">{r.created_at || 'Recently'}</td>
                    <td className="py-3 px-4 text-xs max-w-xs truncate">{r.notes || '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Creation Modal - ISSUE 1: Assigned Admin Dropdown Removed */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-40 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h2 className="text-xl font-bold text-gray-800">Submit Blood Requisition</h2>
            {errorMsg && (
              <div className="p-3 bg-red-50 text-red-600 text-xs rounded border border-red-200">
                {errorMsg}
              </div>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Blood Group Required</label>
                <select
                  className="w-full border border-gray-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-red-500 outline-none"
                  value={formData.blood_group}
                  onChange={(e) => setFormData({ ...formData, blood_group: e.target.value })}
                >
                  {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(bg => (
                    <option key={bg} value={bg}>{bg}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Quantity (Units)</label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  required
                  className="w-full border border-gray-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-red-500 outline-none"
                  value={formData.units_requested}
                  onChange={(e) => setFormData({ ...formData, units_requested: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Urgency Level</label>
                <select
                  className="w-full border border-gray-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-red-500 outline-none"
                  value={formData.urgency}
                  onChange={(e) => setFormData({ ...formData, urgency: e.target.value })}
                >
                  <option value="Low">Low - Elective Procedure</option>
                  <option value="Medium">Medium - Standard Request</option>
                  <option value="High">High - Urgent Case</option>
                  <option value="Critical">Critical - Emergency Trauma</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Clinical Notes</label>
                <textarea
                  rows="3"
                  className="w-full border border-gray-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-red-500 outline-none"
                  placeholder="Patient info, department, diagnosis..."
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                ></textarea>
              </div>

              <div className="flex justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border rounded-lg text-gray-600 hover:bg-gray-100 text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium shadow-sm transition"
                >
                  Submit Request
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default RequestsView;