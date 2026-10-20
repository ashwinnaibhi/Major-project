import React, { useState } from 'react';
import MLPredictionBadge from '../components/MLPredictionBadge';
import LocationFields from '../components/LocationFields';
import { BrainCircuit, Play, Sparkles, Sliders, AlertCircle, CheckCircle2, Loader } from 'lucide-react';

const ML_API_BASE_URL = import.meta.env.VITE_ML_API_BASE_URL || 'http://localhost:8000';
const inputClass = 'w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-white focus:border-blood-500 focus:outline-none focus:ring-2 focus:ring-blood-500/20';
const labelClass = 'mb-1 block text-xs font-semibold text-slate-400';
const BLOOD_GROUPS = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'];

export default function MLPredictorView() {
  const [formData, setFormData] = useState({
    donor_id: 'SIMULATOR_INPUT',
    age: 28,
    gender: 'Male',
    blood_group: 'O+',
    district: '',
    taluk: '',
    location: '',
    distance_km: 4.5,
    last_donation_days: 120,
    donation_frequency: 3,
    previous_response_rate: 0.85,
    preferred_time: 'Morning',
    response_time_hrs: 1.5,
    health_eligibility_score: 95
  });
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (field, value) => {
    setFormData((current) => ({ ...current, [field]: value }));
    setError('');
  };

  const handlePredict = async (event) => {
    event.preventDefault();
    setError('');
    setPrediction(null);

    if (!formData.district || !formData.taluk) {
      setError('Select a district and taluk before running inference.');
      return;
    }

    setLoading(true);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 20000);
    try {
      const payload = {
        donor_id: 'SIMULATOR_INPUT',
        age: Number(formData.age),
        gender: formData.gender,
        blood_group: formData.blood_group,
        // Keep the v1 API feature name and type; this label is unseen by its legacy encoder.
        location: `${formData.taluk}, ${formData.district}`,
        distance_km: Number(formData.distance_km),
        last_donation_days: Number(formData.last_donation_days),
        donation_frequency: Number(formData.donation_frequency),
        previous_response_rate: Number(formData.previous_response_rate),
        preferred_time: formData.preferred_time,
        response_time_hrs: Number(formData.response_time_hrs),
        health_eligibility_score: Number(formData.health_eligibility_score)
      };

      const response = await fetch(`${ML_API_BASE_URL}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(result.detail || `ML inference failed with HTTP ${response.status}.`);
      }
      if (!Number.isFinite(Number(result.availability_score))
          || !Number.isFinite(Number(result.response_probability))
          || !result.availability_category) {
        throw new Error('The ML service returned an incomplete prediction response.');
      }
      setPrediction(result);
    } catch (requestError) {
      if (requestError.name === 'AbortError') {
        setError('The ML service did not respond within 20 seconds. Confirm it is running on the configured ML API URL and retry.');
      } else {
        setError(requestError.message || 'Could not reach the ML prediction service.');
      }
    } finally {
      clearTimeout(timeoutId);
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="space-y-2 rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900 to-blood-950/30 p-5 shadow-xl sm:p-6">
        <div className="flex items-center gap-2 text-xs font-semibold text-blood-300">
          <BrainCircuit className="h-4 w-4" />
          <span>ML Availability Simulator · Live API inference</span>
        </div>
        <h2 className="text-2xl font-black tracking-tight text-white sm:text-3xl">Donor Availability Prediction Engine</h2>
        <p className="max-w-3xl text-sm leading-6 text-slate-400">
          Submit the feature vector to the existing FastAPI ML service. This simulator does not create or look up a donor record.
        </p>
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <form onSubmit={handlePredict} className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6 lg:col-span-7">
          <div className="flex flex-col gap-2 border-b border-slate-800 pb-3 sm:flex-row sm:items-center sm:justify-between">
            <h3 className="flex items-center gap-2 text-sm font-bold text-white">
              <Sliders className="h-4 w-4 text-blood-400" /> Donor feature inputs
            </h3>
            <span className="text-xs text-slate-500">POST {ML_API_BASE_URL}/predict</span>
          </div>

          <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
            <div>
              <label className={labelClass} htmlFor="ml-blood-group">Blood group</label>
              <select id="ml-blood-group" value={formData.blood_group} onChange={(event) => handleChange('blood_group', event.target.value)} className={inputClass}>
                {BLOOD_GROUPS.map((group) => <option key={group} value={group}>{group}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass} htmlFor="ml-age">Age (18–65)</label>
              <input id="ml-age" type="number" min="18" max="65" required value={formData.age} onChange={(event) => handleChange('age', Number(event.target.value))} className={inputClass} />
            </div>
            <div>
              <label className={labelClass} htmlFor="ml-gender">Gender</label>
              <select id="ml-gender" value={formData.gender} onChange={(event) => handleChange('gender', event.target.value)} className={inputClass}>
                <option value="Male">Male</option><option value="Female">Female</option><option value="Other">Other</option>
              </select>
            </div>
            <div>
              <label className={labelClass} htmlFor="ml-preferred-time">Preferred time slot</label>
              <select id="ml-preferred-time" value={formData.preferred_time} onChange={(event) => handleChange('preferred_time', event.target.value)} className={inputClass}>
                <option value="Morning">Morning (8am–12pm)</option><option value="Afternoon">Afternoon (12pm–4pm)</option><option value="Evening">Evening (4pm–8pm)</option>
              </select>
            </div>
          </div>

          <LocationFields
            value={formData}
            onChange={setFormData}
            requiredLocation
            showCoordinates={false}
            showLocality={false}
          />

          <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
            <div>
              <label className={labelClass} htmlFor="ml-distance">Distance feature: <span className="text-white">{Number(formData.distance_km).toFixed(1)} km</span></label>
              <input id="ml-distance" type="range" min="0" max="250" step="0.5" value={formData.distance_km} onChange={(event) => handleChange('distance_km', Number(event.target.value))} className="w-full accent-blood-500" />
              <p className="mt-1 text-[11px] text-slate-500">This is an input feature for the simulator, not a distance calculated from a saved request.</p>
            </div>
            <div>
              <label className={labelClass} htmlFor="ml-last-donation">Days since last donation: <span className="text-white">{formData.last_donation_days} days</span></label>
              <input id="ml-last-donation" type="range" min="0" max="365" value={formData.last_donation_days} onChange={(event) => handleChange('last_donation_days', Number(event.target.value))} className="w-full accent-blood-500" />
            </div>
            <div>
              <label className={labelClass} htmlFor="ml-response-rate">Previous response rate: <span className="text-emerald-300">{Math.round(formData.previous_response_rate * 100)}%</span></label>
              <input id="ml-response-rate" type="range" min="0" max="1" step="0.05" value={formData.previous_response_rate} onChange={(event) => handleChange('previous_response_rate', Number(event.target.value))} className="w-full accent-emerald-500" />
            </div>
            <div>
              <label className={labelClass} htmlFor="ml-donation-frequency">Annual donation frequency: <span className="text-white">{formData.donation_frequency}</span></label>
              <input id="ml-donation-frequency" type="range" min="0" max="15" value={formData.donation_frequency} onChange={(event) => handleChange('donation_frequency', Number(event.target.value))} className="w-full accent-blood-500" />
            </div>
            <div>
              <label className={labelClass} htmlFor="ml-response-time">Expected response time (hours)</label>
              <input id="ml-response-time" type="number" min="0" max="240" step="0.1" required value={formData.response_time_hrs} onChange={(event) => handleChange('response_time_hrs', Number(event.target.value))} className={inputClass} />
            </div>
            <div>
              <label className={labelClass} htmlFor="ml-health-score">Health eligibility score: <span className="text-white">{formData.health_eligibility_score}/100</span></label>
              <input id="ml-health-score" type="range" min="0" max="100" value={formData.health_eligibility_score} onChange={(event) => handleChange('health_eligibility_score', Number(event.target.value))} className="w-full accent-blood-500" />
            </div>
          </div>

          <div className="rounded-xl border border-amber-800/80 bg-amber-950/30 p-3 text-xs leading-5 text-amber-200" role="note">
            <strong>ML location compatibility:</strong> the existing v1 training source uses legacy Zone A–E categories and configures its OneHotEncoder with <code>handle_unknown='ignore'</code>. The selected taluk/district is sent through the unchanged <code>location</code> feature, but an unseen value is ignored by that encoder. The current model therefore has no learned district/taluk-specific effect; retraining requires verified labelled training examples and is not performed here.
          </div>

          {error && (
            <div role="alert" className="flex items-start gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs leading-5 text-rose-200">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> <span>{error}</span>
            </div>
          )}

          <button type="submit" disabled={loading} className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 px-4 py-3 text-xs font-extrabold text-white shadow-lg transition hover:from-blood-500 hover:to-blood-600 disabled:cursor-wait disabled:opacity-60">
            {loading ? <><Loader className="h-4 w-4 animate-spin" /> Sending request to ML service…</> : <><Play className="h-4 w-4 fill-white" /> Run ML service inference</>}
          </button>
        </form>

        <section aria-live="polite" className="flex flex-col justify-between space-y-5 rounded-2xl border border-slate-800 bg-slate-900/60 p-5 sm:p-6 lg:col-span-5">
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <h3 className="flex items-center gap-2 text-sm font-bold text-white"><Sparkles className="h-4 w-4 text-blood-400" /> Prediction output</h3>
              <span className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-[10px] font-mono text-slate-400">API result</span>
            </div>
            {prediction ? (
              <>
                <div className="space-y-3 rounded-2xl border border-slate-800 bg-gradient-to-b from-slate-900 to-slate-950 p-6 text-center">
                  <p className="text-xs font-semibold uppercase text-slate-400">Predicted availability score</p>
                  <div className="text-5xl font-black text-white">{Number(prediction.availability_score).toFixed(1)}<span className="text-xl font-bold text-slate-500"> / 100</span></div>
                  <div className="flex justify-center"><MLPredictionBadge category={prediction.availability_category} score={Number(prediction.availability_score)} /></div>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4">
                  <span className="block text-xs font-semibold text-slate-400">Response probability returned by service</span>
                  <span className="mt-1 block text-2xl font-bold text-emerald-300">{(Number(prediction.response_probability) * 100).toFixed(1)}%</span>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4">
                  <span className="block text-xs font-semibold text-slate-400">Service recommendation</span>
                  <p className="mt-1 text-sm leading-6 text-slate-200">{prediction.recommendation || 'No recommendation was supplied by the service.'}</p>
                  <p className="mt-2 text-[11px] text-slate-500">Model reported by service: {prediction.model_used || 'Not reported'}</p>
                </div>
                <div className="flex items-start gap-2 rounded-xl border border-emerald-900 bg-emerald-950/30 p-3 text-xs leading-5 text-emerald-200">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> Prediction received from the configured ML API. It is an experimental estimate, not a guarantee of donor availability or clinical suitability.
                </div>
              </>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/50 p-8 text-center">
                <BrainCircuit className="mx-auto mb-3 h-9 w-9 text-slate-600" />
                <p className="font-semibold text-white">No prediction run yet</p>
                <p className="mt-2 text-sm leading-6 text-slate-400">Select a Karnataka district and taluk, review the feature inputs, then run inference. Results appear only after the ML service returns a valid response.</p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
