import React, { useState } from 'react';
import { getMlServiceUrl } from '../api/config';
import axios from 'axios';
import { Cpu, CheckCircle, AlertTriangle, Info } from 'lucide-react';

const MLPredictorView = () => {
  const [formData, setFormData] = useState({
    taluk: 'Koppa',
    district: 'Chikmagalur',
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
    setLoading(true);
    setError('');
    setPrediction(null);

    try {
      const res = await axios.post(`${ML_SERVICE_URL}/predict-availability`, {
        taluk: formData.taluk,
        district: formData.district,
        blood_group: formData.blood_group,
        units_requested: parseInt(formData.units_requested, 10),
        urgency_level: formData.urgency_level
      });
      setPrediction(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Prediction service temporarily unavailable.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Hospital ML Availability Simulator</h1>
        <p className="text-gray-500 text-sm">
          Estimate regional blood stock availability at the taluk level based on historical supply and demand.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Form Column */}
        <div className="md:col-span-2 bg-white p-6 rounded-xl border border-gray-200 shadow-sm space-y-4">
          <form onSubmit={handlePredict} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">Taluk</label>
                <input
                  type="text"
                  required
                  value={formData.taluk}
                  onChange={(e) => setFormData({ ...formData, taluk: e.target.value })}
                  className="w-full border rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-red-500 outline-none"
                  placeholder="e.g. Koppa"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">District</label>
                <input
                  type="text"
                  required
                  value={formData.district}
                  onChange={(e) => setFormData({ ...formData, district: e.target.value })}
                  className="w-full border rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-red-500 outline-none"
                  placeholder="e.g. Chikmagalur"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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
                <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">Units Needed</label>
                <input
                  type="number"
                  min="1"
                  max="50"
                  required
                  value={formData.units_requested}
                  onChange={(e) => setFormData({ ...formData, units_requested: e.target.value })}
                  className="w-full border rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-red-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-600 uppercase mb-1">Urgency</label>
                <select
                  value={formData.urgency_level}
                  onChange={(e) => setFormData({ ...formData, urgency_level: e.target.value })}
                  className="w-full border rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-red-500 outline-none"
                >
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                  <option value="Critical">Critical</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-red-600 hover:bg-red-700 text-white font-medium p-3 rounded-lg shadow-sm transition flex items-center justify-center space-x-2 text-sm"
            >
              <Cpu className="w-4 h-4" />
              <span>{loading ? 'Evaluating Model...' : 'Simulate Availability'}</span>
            </button>
          </form>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-600 text-xs rounded-lg flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Prediction Results Card */}
        <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm flex flex-col justify-between">
          <div>
            <h3 className="font-semibold text-gray-800 text-sm mb-3">Simulation Verdict</h3>
            {prediction ? (
              <div className="space-y-4">
                <div className={`p-4 rounded-xl border text-center ${
                  prediction.is_available
                    ? 'bg-green-50 border-green-200 text-green-800'
                    : 'bg-red-50 border-red-200 text-red-800'
                }`}>
                  <div className="text-2xl font-black">
                    {prediction.is_available ? 'LIKELY AVAILABLE' : 'SHORTAGE PREDICTED'}
                  </div>
                  <div className="text-xs mt-1 font-medium">
                    Confidence: {(prediction.confidence * 100).toFixed(1)}%
                  </div>
                </div>

                <div className="text-xs text-gray-600 space-y-1 bg-gray-50 p-3 rounded-lg border">
                  <div><strong>Taluk Analyzed:</strong> {formData.taluk}</div>
                  <div><strong>Group:</strong> {formData.blood_group} ({formData.units_requested} units)</div>
                  <div><strong>Fulfillment Probability:</strong> {prediction.fulfillment_score}/100</div>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-gray-400 text-xs">
                Fill the form and trigger simulation to evaluate regional availability.
              </div>
            )}
          </div>

          <div className="mt-4 pt-4 border-t flex items-start space-x-2 text-xs text-gray-400">
            <Info className="w-4 h-4 flex-shrink-0 text-gray-500" />
            <span>Predictions are advisory estimates based on regional inventory and requisition frequency.</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MLPredictorView;