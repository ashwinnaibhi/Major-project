import React, { useEffect, useState } from 'react';
import MLPredictionBadge from '../components/MLPredictionBadge';
import { BrainCircuit, Play, Sparkles, Sliders, CheckCircle2, AlertCircle, MapPin, Database } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';
const ML_API_BASE = import.meta.env.VITE_ML_API_BASE_URL || 'http://localhost:8000';
const BLOOD_GROUPS = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'];
const MODEL_ZONES = ['Zone A (Central)', 'Zone B (North)', 'Zone C (South)', 'Zone D (East)', 'Zone E (West)'];

export default function MLPredictorView() {
  const [formData, setFormData] = useState({
    donor_id: 'MODEL-SCENARIO', age: 28, gender: 'Male', blood_group: 'O+', location: 'Zone A (Central)',
    distance_km: 4.5, last_donation_days: 120, donation_frequency: 3, previous_response_rate: 0.85,
    preferred_time: 'Morning', response_time_hrs: 1.5, health_eligibility_score: 95
  });
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [predictionError, setPredictionError] = useState('');
  const [locations, setLocations] = useState({ districts: [], taluks_by_district: {} });
  const [district, setDistrict] = useState('');
  const [taluk, setTaluk] = useState('');
  const [locationError, setLocationError] = useState('');
  const [summaryError, setSummaryError] = useState('');
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  const handleChange = (field, value) => setFormData((previous) => ({ ...previous, [field]: value }));
  const talukOptions = district ? (locations.taluks_by_district?.[district] || []) : [];

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/locations`)
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || `Location catalogue failed (HTTP ${response.status}).`);
        return data;
      })
      .then((data) => { if (!cancelled) setLocations(data); })
      .catch((error) => { if (!cancelled) setLocationError(error.message || 'Location catalogue unavailable.'); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setSummary(null);
    setSummaryLoading(true);
    setSummaryError('');
    const params = new URLSearchParams({ blood_group: formData.blood_group });
    if (district) params.set('district', district);
    if (taluk) params.set('taluk', taluk);
    fetch(`${API_BASE}/api/v1/availability/summary?${params.toString()}`)
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || `Availability summary failed (HTTP ${response.status}).`);
        return data;
      })
      .then((data) => { if (!cancelled) setSummary(data); })
      .catch((error) => { if (!cancelled) { setSummary(null); setSummaryError(error.message || 'Unable to retrieve location statistics.'); } })
      .finally(() => { if (!cancelled) setSummaryLoading(false); });
    return () => { cancelled = true; };
  }, [district, taluk, formData.blood_group]);

  const handlePredict = async (event) => {
    event.preventDefault();
    setLoading(true);
    setPrediction(null);
    setPredictionError('');
    try {
      const payload = {
        donor_id: String(formData.donor_id || 'MODEL-SCENARIO'),
        age: Number(formData.age), gender: formData.gender, blood_group: formData.blood_group,
        location: formData.location, distance_km: Number(formData.distance_km),
        last_donation_days: Number(formData.last_donation_days), donation_frequency: Number(formData.donation_frequency),
        previous_response_rate: Number(formData.previous_response_rate), preferred_time: formData.preferred_time,
        response_time_hrs: Number(formData.response_time_hrs), health_eligibility_score: Number(formData.health_eligibility_score)
      };
      const response = await fetch(`${ML_API_BASE}/predict`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `ML service returned HTTP ${response.status}.`);
      if (typeof data.availability_score !== 'number' || typeof data.response_probability !== 'number') throw new Error('ML service response is missing the expected prediction fields.');
      setPrediction(data);
    } catch (error) {
      setPredictionError(`${error.message || 'Prediction failed.'} Confirm the ML service is running and that its model artifact is available.`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-2">
        <div className="flex items-center gap-2 text-xs font-semibold text-blood-400"><BrainCircuit className="w-4 h-4" /><span>Connected Scikit-learn prediction service</span></div>
        <h2 className="text-2xl font-black text-white">Donor Availability Prediction Engine</h2>
        <p className="text-xs text-slate-400">Model output is returned by the actual ML service. District/taluk statistics below are separately calculated from the backend database; the current model uses synthetic zone categories, not district or taluk as model features.</p>
      </section>

      <section className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
        <div className="flex items-center gap-2"><MapPin className="w-4 h-4 text-blood-400" /><h3 className="text-sm font-bold text-white">Actual database availability by location</h3></div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div><label htmlFor="predict-district" className="block text-slate-300 font-semibold mb-1">District</label><select id="predict-district" value={district} onChange={(event) => { setDistrict(event.target.value); setTaluk(''); }} className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white"><option value="">All districts</option>{locations.districts.map((item) => <option key={item} value={item}>{item}</option>)}</select></div>
          <div><label htmlFor="predict-taluk" className="block text-slate-300 font-semibold mb-1">Taluk</label><select id="predict-taluk" value={taluk} disabled={!district} onChange={(event) => setTaluk(event.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white disabled:opacity-50"><option value="">All taluks</option>{talukOptions.map((item) => <option key={item} value={item}>{item}</option>)}</select></div>
          <div><label className="block text-slate-300 font-semibold mb-1">Blood group for counts</label><div className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white">{formData.blood_group}</div></div>
        </div>
        {locationError && <p role="alert" className="text-xs text-amber-300">{locationError}</p>}
        {summaryError && <p role="alert" className="text-xs text-amber-300">{summaryError}</p>}
        {summaryLoading && <p className="text-xs text-slate-400">Loading database counts…</p>}
        {summary && <div className="grid grid-cols-1 sm:grid-cols-3 gap-3"><div className="p-4 rounded-xl bg-slate-900 border border-slate-800"><span className="text-xs text-slate-400 block">Donor records in selection</span><strong className="text-2xl text-white">{summary.total_records}</strong></div><div className="p-4 rounded-xl bg-slate-900 border border-slate-800"><span className="text-xs text-slate-400 block">Available and basic-eligible</span><strong className="text-2xl text-white">{summary.eligible_available_donors}</strong></div><div className="p-4 rounded-xl bg-slate-900 border border-slate-800"><span className="text-xs text-slate-400 block">Eligible with explicit alert consent</span><strong className="text-2xl text-white">{summary.eligible_contactable_donors}</strong></div></div>}
        <p className="text-[11px] text-slate-500 flex items-start gap-2"><Database className="w-3.5 h-3.5 shrink-0 mt-0.5" />These are database aggregates, not ML probabilities. Donor contact consent is counted independently from availability.</p>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <form onSubmit={handlePredict} className="lg:col-span-7 p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800"><h3 className="text-sm font-bold text-white flex items-center gap-2"><Sliders className="w-4 h-4 text-blood-400" />Model input features</h3><span className="text-xs text-slate-500">Sent to POST /predict</span></div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div><label htmlFor="model-blood" className="text-slate-400 block font-semibold mb-1">Blood group</label><select id="model-blood" value={formData.blood_group} onChange={(e) => handleChange('blood_group', e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-white">{BLOOD_GROUPS.map((group) => <option key={group} value={group}>{group}</option>)}</select></div>
            <div><label htmlFor="model-zone" className="text-slate-400 block font-semibold mb-1">Model zone feature</label><select id="model-zone" value={formData.location} onChange={(e) => handleChange('location', e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-white">{MODEL_ZONES.map((zone) => <option key={zone} value={zone}>{zone}</option>)}</select></div>
            <div><label htmlFor="model-age" className="text-slate-400 block font-semibold mb-1">Age</label><input id="model-age" type="number" min="18" max="65" required value={formData.age} onChange={(e) => handleChange('age', Number(e.target.value))} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-white" /></div>
            <div><label htmlFor="model-gender" className="text-slate-400 block font-semibold mb-1">Gender</label><select id="model-gender" value={formData.gender} onChange={(e) => handleChange('gender', e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-white"><option>Male</option><option>Female</option><option>Other</option></select></div>
            <div><label htmlFor="model-days" className="text-slate-400 block font-semibold mb-1">Days since donation: <strong className="text-white">{formData.last_donation_days}</strong></label><input id="model-days" type="range" min="0" max="365" value={formData.last_donation_days} onChange={(e) => handleChange('last_donation_days', Number(e.target.value))} className="w-full accent-blood-500" /></div>
            <div><label htmlFor="model-distance" className="text-slate-400 block font-semibold mb-1">Distance to hospital: <strong className="text-white">{formData.distance_km} km</strong></label><input id="model-distance" type="range" min="0" max="100" step="0.5" value={formData.distance_km} onChange={(e) => handleChange('distance_km', Number(e.target.value))} className="w-full accent-blood-500" /></div>
            <div><label htmlFor="model-response-rate" className="text-slate-400 block font-semibold mb-1">Previous response rate: <strong className="text-emerald-400">{Math.round(formData.previous_response_rate * 100)}%</strong></label><input id="model-response-rate" type="range" min="0" max="1" step="0.05" value={formData.previous_response_rate} onChange={(e) => handleChange('previous_response_rate', Number(e.target.value))} className="w-full accent-emerald-500" /></div>
            <div><label htmlFor="model-frequency" className="text-slate-400 block font-semibold mb-1">Donation frequency/year: <strong className="text-white">{formData.donation_frequency}</strong></label><input id="model-frequency" type="range" min="0" max="8" step="1" value={formData.donation_frequency} onChange={(e) => handleChange('donation_frequency', Number(e.target.value))} className="w-full accent-blood-500" /></div>
            <div><label htmlFor="model-health" className="text-slate-400 block font-semibold mb-1">Health eligibility score: <strong className="text-white">{formData.health_eligibility_score}/100</strong></label><input id="model-health" type="range" min="0" max="100" value={formData.health_eligibility_score} onChange={(e) => handleChange('health_eligibility_score', Number(e.target.value))} className="w-full accent-blood-500" /></div>
            <div><label htmlFor="model-time" className="text-slate-400 block font-semibold mb-1">Preferred time</label><select id="model-time" value={formData.preferred_time} onChange={(e) => handleChange('preferred_time', e.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-white"><option>Morning</option><option>Afternoon</option><option>Evening</option></select></div>
            <div><label htmlFor="model-response-hours" className="text-slate-400 block font-semibold mb-1">Expected response time (hours)</label><input id="model-response-hours" type="number" min="0" step="0.1" value={formData.response_time_hrs} onChange={(e) => handleChange('response_time_hrs', Number(e.target.value))} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-white" /></div>
          </div>
          {predictionError && <div role="alert" className="p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-200 text-xs flex gap-2"><AlertCircle className="w-4 h-4 shrink-0" />{predictionError}</div>}
          <button type="submit" disabled={loading} className="w-full py-3 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 disabled:opacity-50 text-white font-extrabold text-xs flex items-center justify-center gap-2 mt-4">{loading ? 'Calling ML service…' : <><Play className="w-4 h-4 fill-white" />Run model inference</>}</button>
        </form>

        <section className="lg:col-span-5 p-6 rounded-2xl glass-panel border border-slate-800 space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800"><h3 className="text-sm font-bold text-white flex items-center gap-2"><Sparkles className="w-4 h-4 text-blood-400" />Prediction response</h3><span className="px-2 py-0.5 rounded text-[9px] bg-slate-900 text-slate-300 border border-slate-700 font-mono">API output</span></div>
          {!prediction && <div className="p-8 rounded-xl bg-slate-900 border border-slate-800 text-center"><BrainCircuit className="w-8 h-8 text-slate-500 mx-auto mb-2" /><p className="text-sm font-bold text-slate-300">No prediction run yet</p><p className="text-xs text-slate-500 mt-1">Submit the feature values to display the service's actual response.</p></div>}
          {prediction && <div className="space-y-4"><div className="p-6 rounded-2xl bg-gradient-to-b from-slate-900 via-slate-950 to-slate-900 border border-slate-800 text-center space-y-3"><p className="text-xs text-slate-400 uppercase font-semibold">Model availability score</p><div className="text-5xl font-black text-white">{Number(prediction.availability_score).toFixed(1)}<span className="text-xl font-bold text-slate-500"> / 100</span></div><div className="flex justify-center"><MLPredictionBadge category={String(prediction.availability_category || '').toUpperCase()} score={prediction.availability_score} /></div></div><div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800"><span className="text-xs text-slate-400 font-semibold block">Model response probability</span><span className="text-xl font-bold text-emerald-400">{(Number(prediction.response_probability) * 100).toFixed(1)}%</span></div><div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800"><span className="text-xs text-slate-400 font-semibold block">Recommendation returned by model</span><p className="text-xs text-slate-300 mt-1 leading-relaxed">{prediction.recommendation}</p></div><p className="text-[11px] text-slate-500">Model: {prediction.model_used || 'Not specified by the service'}. Prediction applies to the submitted feature scenario only; it is not a district/taluk prediction and is not a confirmed donor availability result.</p></div>}
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-[10px] text-slate-500 flex items-start gap-2"><CheckCircle2 className="w-4 h-4 text-slate-500 shrink-0" /><span>The service's pre-existing training dataset uses synthetic zone labels. Do not infer geographic precision or clinical eligibility from this score alone.</span></div>
        </section>
      </div>
    </div>
  );
}
