import React, { useState } from 'react';
import { getMlServiceUrl } from '../api/config';
import axios from 'axios';
import { Cpu, CheckCircle, AlertTriangle, Info, BrainCircuit, ShieldAlert } from 'lucide-react';

const MLPredictorView = ({ currentUser }) => {
  const isHospital = Boolean(
    currentUser?.token &&
    currentUser?.isLoggedIn &&
    ['HOSPITAL', 'ROLE_HOSPITAL'].includes(String(currentUser?.role || '').toUpperCase())
  );

  const token = currentUser?.token || localStorage.getItem('token');
  const [formData, setFormData] = useState({
    taluk: 'Koppa',
    district: 'Chikkamagaluru',
    blood_group: 'B+',
    units_requested: 2,
    urgency_level: 'High'
  });
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const ML_SERVICE_URL = getMlServiceUrl();

  const handlePredict = async (e) => {
    e.preventDefault();
    if (!token || !isHospital) {
      setError('Authenticated hospital account required.');
      return;
    }
    setLoading(true);
    setError('');
    setPrediction(null);

    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await axios.post(`${ML_SERVICE_URL}/predict-availability`, {
        taluk: formData.taluk,
        district: formData.district,
        blood_group: formData.blood_group,
        units_requested: parseInt(formData.units_requested, 10),
        urgency_level: formData.urgency_level
      }, { headers });
      setPrediction(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Prediction service temporarily unavailable.');
    } finally {
      setLoading(false);
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
              Hospital ML Availability Simulator is restricted to authenticated Hospital accounts only.
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
            <BrainCircuit className="w-4 h-4" />
            <span>Machine Learning Intelligence</span>
          </div>
          <h2 className="text-2xl font-black text-white">Hospital ML Availability Simulator</h2>
          <p className="text-xs text-slate-400">
            Estimate regional blood stock availability at the taluk level based on historical supply and demand.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Form Column */}
        <div className="md:col-span-2 p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <form onSubmit={handlePredict} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Taluk</label>
                <input
                  type="text"
                  required
                  value={formData.taluk}
                  onChange={(e) => setFormData({ ...formData, taluk: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3.5 py-2.5 text-xs font-bold focus:border-blood-500 outline-none"
                  placeholder="e.g. Koppa"
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">District</label>
                <input
                  type="text"
                  required
                  value={formData.district}
                  onChange={(e) => setFormData({ ...formData, district: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3.5 py-2.5 text-xs font-bold focus:border-blood-500 outline-none"
                  placeholder="e.g. Chikkamagaluru"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Blood Group</label>
                <select
                  value={formData.blood_group}
                  onChange={(e) => setFormData({ ...formData, blood_group: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2.5 text-xs font-bold focus:border-blood-500 outline-none"
                >
                  {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(bg => (
                    <option key={bg} value={bg} className="bg-slate-900 text-white">{bg}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Units Needed</label>
                <input
                  type="number"
                  min="1"
                  max="50"
                  required
                  value={formData.units_requested}
                  onChange={(e) => setFormData({ ...formData, units_requested: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3.5 py-2.5 text-xs font-bold focus:border-blood-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Urgency</label>
                <select
                  value={formData.urgency_level}
                  onChange={(e) => setFormData({ ...formData, urgency_level: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 text-white rounded-xl px-3 py-2.5 text-xs font-bold focus:border-blood-500 outline-none"
                >
                  <option value="Low" className="bg-slate-900 text-white">Low</option>
                  <option value="Medium" className="bg-slate-900 text-white">Medium</option>
                  <option value="High" className="bg-slate-900 text-white">High</option>
                  <option value="Critical" className="bg-slate-900 text-white">Critical</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blood-700 hover:bg-blood-600 text-white font-bold p-3 rounded-xl shadow-sm transition flex items-center justify-center space-x-2 text-xs disabled:opacity-50"
            >
              <Cpu className="w-4 h-4" />
              <span>{loading ? 'Evaluating Model...' : 'Simulate Availability'}</span>
            </button>
          </form>

          {error && (
            <div className="p-3 bg-rose-950/60 border border-rose-800 text-rose-300 text-xs rounded-xl flex items-center space-x-2 font-bold" role="alert">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Prediction Results Card */}
        <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col justify-between space-y-4">
          <div>
            <h3 className="font-bold text-white text-xs uppercase tracking-wider mb-3">Simulation Verdict</h3>
            {prediction ? (
              <div className="space-y-4">
                <div className={`p-4 rounded-xl border text-center ${
                  prediction.is_available
                    ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300'
                    : 'bg-rose-950/60 border-rose-800 text-rose-300'
                }`}>
                  <div className="text-xl font-black">
                    {prediction.is_available ? 'LIKELY AVAILABLE' : 'SHORTAGE PREDICTED'}
                  </div>
                  <div className="text-xs mt-1 font-bold">
                    Confidence: {(prediction.confidence * 100).toFixed(1)}%
                  </div>
                </div>

                <div className="text-xs text-slate-300 space-y-1.5 bg-slate-900/80 p-3 rounded-xl border border-slate-800">
                  <div><strong className="text-white">Taluk Analyzed:</strong> {formData.taluk}</div>
                  <div><strong className="text-white">Group:</strong> {formData.blood_group} ({formData.units_requested} units)</div>
                  <div><strong className="text-white">Fulfillment Score:</strong> {prediction.fulfillment_score}/100</div>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-slate-500 text-xs">
                Fill the form and trigger simulation to evaluate regional availability.
              </div>
            )}
          </div>

          <div className="pt-3 border-t border-slate-800 flex items-start space-x-2 text-[11px] text-slate-400">
            <Info className="w-4 h-4 flex-shrink-0 text-slate-500" />
            <span>Predictions are advisory estimates based on regional inventory and requisition frequency.</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MLPredictorView;
