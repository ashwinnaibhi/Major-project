import React, { useEffect, useMemo, useRef, useState } from 'react';
import MLPredictionBadge from '../components/MLPredictionBadge';
import { AlertTriangle, CheckCircle2, MapPin, Mail, Search, SlidersHorizontal, Send } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';
const BLOOD_GROUPS = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'];

export default function EmergencySearch({ requestsList = [], currentUser, activeRole }) {
  const [selectedGroup, setSelectedGroup] = useState('O+');
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [selectedTaluk, setSelectedTaluk] = useState('');
  const [availabilityLevel, setAvailabilityLevel] = useState('');
  const [useRadius, setUseRadius] = useState(false);
  const [radiusKm, setRadiusKm] = useState('25');
  const [locations, setLocations] = useState({ districts: [], taluks_by_district: {} });
  const [selectedRequestId, setSelectedRequestId] = useState('');
  const [donors, setDonors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sendingDonor, setSendingDonor] = useState('');
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState('');
  const [refreshIndex, setRefreshIndex] = useState(0);
  const alertKeysRef = useRef(new Map());

  const isAuthorizedView = Boolean(currentUser?.token && currentUser?.role === activeRole && ['ADMIN', 'HOSPITAL'].includes(currentUser.role));
  const emergencyRequests = useMemo(
    () => requestsList.filter((request) => String(request.status || 'PENDING').toUpperCase() === 'PENDING' && String(request.urgency_level || request.urgency || '').toUpperCase() === 'EMERGENCY'),
    [requestsList]
  );
  const selectedRequest = emergencyRequests.find((request) => String(request.id) === selectedRequestId) || null;
  const talukOptions = selectedDistrict ? (locations.taluks_by_district?.[selectedDistrict] || []) : [];
  const destinationValid = selectedRequest && Number.isFinite(Number(selectedRequest.destination_latitude)) && Number.isFinite(Number(selectedRequest.destination_longitude)) && selectedRequest.destination_latitude !== null && selectedRequest.destination_longitude !== null;

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/locations`)
      .then(async (response) => {
        if (!response.ok) throw new Error('Location catalogue is unavailable.');
        return response.json();
      })
      .then((data) => { if (!cancelled) setLocations(data); })
      .catch((err) => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!selectedRequestId && emergencyRequests.length) {
      const firstRequest = emergencyRequests[0];
      setSelectedRequestId(String(firstRequest.id));
      setSelectedGroup(String(firstRequest.blood_group || firstRequest.blood || 'O+').toUpperCase());
    }
    if (selectedRequestId && !emergencyRequests.some((request) => String(request.id) === selectedRequestId)) {
      const nextRequest = emergencyRequests[0];
      setSelectedRequestId(nextRequest ? String(nextRequest.id) : '');
      if (nextRequest) setSelectedGroup(String(nextRequest.blood_group || nextRequest.blood || 'O+').toUpperCase());
    }
  }, [emergencyRequests, selectedRequestId]);

  useEffect(() => {
    let cancelled = false;
    if (!isAuthorizedView) {
      setDonors([]);
      setError('Sign in with an authorized administrator or hospital account to search eligible donors. Changing the role view does not grant access.');
      return () => { cancelled = true; };
    }
    if (useRadius && (!destinationValid || !Number.isFinite(Number(radiusKm)) || Number(radiusKm) <= 0 || Number(radiusKm) > 500)) {
      setDonors([]);
      setError(!destinationValid ? 'The selected emergency request has no valid destination coordinates. Add coordinates to that request before enabling radius filtering.' : 'Radius must be greater than 0 and no more than 500 km.');
      return () => { cancelled = true; };
    }

    const params = new URLSearchParams({ blood_group: selectedGroup, eligible_only: 'true' });
    if (selectedDistrict) params.set('district', selectedDistrict);
    if (selectedTaluk) params.set('taluk', selectedTaluk);
    if (availabilityLevel) params.set('availability_level', availabilityLevel);
    // Send destination coordinates whenever available so distances and nearest-first ordering
    // work even when the optional radius cutoff is disabled.
    if (destinationValid) {
      params.set('destination_latitude', String(selectedRequest.destination_latitude));
      params.set('destination_longitude', String(selectedRequest.destination_longitude));
    }
    if (useRadius) params.set('radius_km', String(Number(radiusKm)));
    setLoading(true);
    setError('');
    fetch(`${API_BASE}/api/v1/donors?${params.toString()}`, { headers: { Authorization: `Bearer ${currentUser.token}` } })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || `Donor search failed (HTTP ${response.status}).`);
        if (!Array.isArray(data)) throw new Error('Donor search returned an unexpected response.');
        if (!cancelled) setDonors(data);
      })
      .catch((err) => { if (!cancelled) { setDonors([]); setError(err.message); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [isAuthorizedView, currentUser?.token, selectedGroup, selectedDistrict, selectedTaluk, availabilityLevel, useRadius, radiusKm, selectedRequest, destinationValid, refreshIndex]);

  const sendAlert = async (donor) => {
    if (!isAuthorizedView) return;
    if (!selectedRequest) {
      setNotice({ type: 'error', text: 'Select a pending emergency requisition before creating a donor alert.' });
      return;
    }
    if (String(donor.blood_group || '').toUpperCase() !== String(selectedRequest.blood_group || selectedRequest.blood || '').toUpperCase()) {
      setNotice({ type: 'error', text: 'The donor blood group does not match the selected request.' });
      return;
    }
    const donorKey = String(donor.id ?? donor.donor_id);
    setSendingDonor(donorKey);
    setNotice(null);
    try {
      // Reuse a stable key for the same donor/request pair so an uncertain network retry
      // cannot persist or send the same alert twice. A distinct request gets a new key.
      const alertIdentity = `${selectedRequest.id}:${donorKey}:${selectedGroup}`;
      let key = alertKeysRef.current.get(alertIdentity);
      if (!key) {
        key = globalThis.crypto?.randomUUID ? globalThis.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        alertKeysRef.current.set(alertIdentity, key);
      }
      const response = await fetch(`${API_BASE}/api/v1/donors/send-email-alert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${currentUser.token}` },
        body: JSON.stringify({ donor_id: donorKey, blood_group: selectedGroup, request_id: selectedRequest.id, idempotency_key: key })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Alert request failed (HTTP ${response.status}).`);
      const delivery = data.delivery_status || data.status || 'UNKNOWN';
      const statusText = delivery === 'DELIVERED'
        ? 'External notification delivered.'
        : delivery === 'QUEUED'
          ? 'Alert was queued, but delivery is not yet confirmed.'
          : delivery === 'DISABLED'
            ? 'Alert was persisted, but external messaging is disabled.'
            : delivery === 'NOT_CONFIGURED'
              ? 'Alert was persisted, but the email provider is not configured.'
              : delivery === 'FAILED'
                ? 'Alert was persisted, but external delivery failed.'
                : `Alert accepted; provider status: ${delivery}.`;
      setNotice({ type: delivery === 'DELIVERED' ? 'success' : 'warning', text: `${data.persisted ? 'Alert persisted. ' : ''}${statusText}` });
      setRefreshIndex((value) => value + 1);
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Unable to create the alert.' });
    } finally {
      setSendingDonor('');
    }
  };

  return (
    <div className="space-y-6">
      <section className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-blood-400 mb-1"><Search className="w-4 h-4" /><span>Authorized emergency donor search</span></div>
            <h2 className="text-2xl font-black text-white">Emergency Donor Search &amp; Alert</h2>
            <p className="text-xs text-slate-400 mt-1">Filters run on the backend. Only opted-in, eligible donors are returned when recipient filtering is enabled.</p>
          </div>
          <div className="text-xs text-slate-400">{loading ? 'Searching…' : `${donors.length} eligible result${donors.length === 1 ? '' : 's'}`}</div>
        </div>

        {error && <div role="alert" className="p-3 rounded-xl bg-amber-950/60 border border-amber-800 text-amber-200 text-xs">{error}</div>}
        {notice && <div role="status" className={`p-3 rounded-xl border text-xs ${notice.type === 'success' ? 'bg-emerald-950/50 border-emerald-800 text-emerald-200' : notice.type === 'error' ? 'bg-rose-950/50 border-rose-800 text-rose-200' : 'bg-amber-950/50 border-amber-800 text-amber-200'}`}>{notice.text}</div>}

        <div>
          <label className="text-xs font-bold text-slate-300 uppercase tracking-wide block mb-2">Required blood group</label>
          <div className="flex flex-wrap gap-2">{BLOOD_GROUPS.map((group) => <button type="button" key={group} onClick={() => setSelectedGroup(group)} aria-pressed={selectedGroup === group} className={`px-4 py-2 rounded-xl text-sm font-extrabold ${selectedGroup === group ? 'bg-blood-600 text-white border border-blood-400' : 'bg-slate-900 text-slate-300 border border-slate-800 hover:bg-slate-800'}`}>{group}</button>)}</div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 text-xs">
          <div><label htmlFor="emergency-district" className="block text-slate-300 font-semibold mb-1">District</label><select id="emergency-district" value={selectedDistrict} onChange={(event) => { setSelectedDistrict(event.target.value); setSelectedTaluk(''); }} className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white"><option value="">All districts</option>{locations.districts.map((district) => <option key={district} value={district}>{district}</option>)}</select></div>
          <div><label htmlFor="emergency-taluk" className="block text-slate-300 font-semibold mb-1">Taluk</label><select id="emergency-taluk" value={selectedTaluk} onChange={(event) => setSelectedTaluk(event.target.value)} disabled={!selectedDistrict} className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white disabled:opacity-50"><option value="">All taluks</option>{talukOptions.map((taluk) => <option key={taluk} value={taluk}>{taluk}</option>)}</select></div>
          <div><label htmlFor="availability-level" className="block text-slate-300 font-semibold mb-1">Availability score</label><select id="availability-level" value={availabilityLevel} onChange={(event) => setAvailabilityLevel(event.target.value)} className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white"><option value="">All score levels</option><option value="HIGH">High (≥ 75)</option><option value="MEDIUM">Medium (40–74.9)</option><option value="LOW">Low (&lt; 40)</option></select></div>
          <div><label htmlFor="emergency-request" className="block text-slate-300 font-semibold mb-1">Pending emergency request</label><select id="emergency-request" value={selectedRequestId} onChange={(event) => { const nextId = event.target.value; const nextRequest = emergencyRequests.find((request) => String(request.id) === nextId); setSelectedRequestId(nextId); if (nextRequest) setSelectedGroup(String(nextRequest.blood_group || nextRequest.blood || '').toUpperCase()); setNotice(null); }} className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white"><option value="">Select a request</option>{emergencyRequests.map((request) => <option key={request.id} value={String(request.id)}>#{request.id} · {request.blood_group || request.blood} · {request.hospital_name || request.hospital}</option>)}</select></div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 flex flex-col md:flex-row md:items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-semibold text-slate-200"><input type="checkbox" checked={useRadius} onChange={(event) => setUseRadius(event.target.checked)} className="accent-red-600" />Filter by distance from selected request</label>
          <div className="flex items-center gap-2"><label htmlFor="radius-km" className="text-xs text-slate-400">Radius (km)</label><input id="radius-km" type="number" min="0.1" max="500" step="0.1" value={radiusKm} onChange={(event) => setRadiusKm(event.target.value)} disabled={!useRadius} className="w-24 bg-slate-950 border border-slate-700 rounded-lg px-2 py-1.5 text-white disabled:opacity-40" /></div>
          <p className="text-[11px] text-slate-500">Distance uses the selected request's stored coordinates. Missing distances are excluded when a radius is active.</p>
        </div>
        {!emergencyRequests.length && <p className="text-xs text-amber-300">There are no pending emergency requests available to select. Create a request from an authorized hospital account first.</p>}
      </section>

      <section className="space-y-3">
        <h3 className="text-base font-bold text-white flex items-center gap-2"><SlidersHorizontal className="w-4 h-4 text-blood-400" /> Eligible donor results <span className="text-xs text-slate-400 font-normal">Availability score is an application/database field, not a delivery guarantee.</span></h3>
        {!loading && !error && donors.length === 0 && <div className="p-8 text-center glass-panel rounded-2xl border border-slate-800"><AlertTriangle className="w-8 h-8 text-amber-400 mx-auto mb-2" /><p className="text-sm font-bold text-slate-300">No donors satisfy these filters.</p><p className="text-xs text-slate-500 mt-1">Eligibility and explicit emergency-contact consent are checked by the server.</p></div>}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">{donors.map((donor, index) => {
          const score = donor.availability_score == null ? null : Number(donor.availability_score);
          const category = score == null ? null : score >= 75 ? 'HIGH' : score >= 40 ? 'MEDIUM' : 'LOW';
          const donorKey = String(donor.id ?? donor.donor_id);
          const distance = donor.distance_km === null || donor.distance_km === undefined ? 'Distance unavailable' : `${Number(donor.distance_km).toFixed(1)} km`;
          return <article key={donorKey} className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
            <div className="flex items-start justify-between gap-3"><div><h4 className="text-sm font-bold text-white">{donor.name}</h4><p className="text-xs text-slate-400 mt-1">{donor.blood_group} · {donor.district || 'District unavailable'}{donor.taluk ? `, ${donor.taluk}` : ''}</p><p className="text-xs text-slate-500 mt-1 flex items-center gap-1"><MapPin className="w-3 h-3" />{distance}</p></div>{score == null ? <span className="px-2 py-1 rounded-lg border border-slate-700 text-slate-400 text-[11px]">No stored score</span> : <MLPredictionBadge category={category} score={score} />}</div>
            <div className="grid grid-cols-3 gap-2 p-3 rounded-xl bg-slate-900 border border-slate-800 text-[11px]"><div><span className="text-slate-500 block">Last donation</span><span className="text-slate-200">{donor.last_donation_days == null ? 'Unknown' : `${donor.last_donation_days} days ago`}</span></div><div><span className="text-slate-500 block">Frequency</span><span className="text-slate-200">{donor.donation_frequency ?? 'Unknown'}</span></div><div><span className="text-slate-500 block">Rank</span><span className="text-slate-200">#{index + 1}</span></div></div>
            <button type="button" disabled={!selectedRequest || sendingDonor === donorKey || !isAuthorizedView || String(donor.blood_group).toUpperCase() !== String(selectedRequest?.blood_group || selectedRequest?.blood || '').toUpperCase()} onClick={() => sendAlert(donor)} className="w-full px-4 py-2.5 rounded-xl bg-blood-700 hover:bg-blood-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-bold flex items-center justify-center gap-2"><Send className="w-4 h-4" />{sendingDonor === donorKey ? 'Creating alert…' : 'Create emergency alert'}</button>
          </article>;
        })}</div>
      </section>
    </div>
  );
}
