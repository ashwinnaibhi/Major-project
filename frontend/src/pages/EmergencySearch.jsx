import React, { useEffect, useMemo, useState } from 'react';
import MLPredictionBadge from '../components/MLPredictionBadge';
import useLocationOptions from '../hooks/useLocationOptions';
import {
  Search, RotateCcw, Phone, Send, Sparkles, AlertTriangle, CheckCircle,
  MapPin, Mail, Loader, Navigation, Clock3
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';
const BLOOD_GROUPS = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'];
const inputClass = 'w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-white focus:border-blood-500 focus:outline-none focus:ring-2 focus:ring-blood-500/20 disabled:cursor-not-allowed disabled:opacity-50';
const labelClass = 'mb-1.5 block text-xs font-semibold text-slate-300';

function hasCoordinates(place) {
  if (!place || place.latitude === null || place.latitude === undefined || place.longitude === null || place.longitude === undefined) return false;
  const latitude = Number(place.latitude);
  const longitude = Number(place.longitude);
  return Number.isFinite(latitude) && Number.isFinite(longitude)
    && latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180;
}

export default function EmergencySearch() {
  const { districts, taluksByDistrict, loading: locationsLoading, error: locationsError } = useLocationOptions();
  const [selectedGroup, setSelectedGroup] = useState('O+');
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [selectedTaluk, setSelectedTaluk] = useState('');
  const [selectedRequestId, setSelectedRequestId] = useState('');
  const [availableOnly, setAvailableOnly] = useState(true);
  const [sortBy, setSortBy] = useState('availability');
  const [radiusKm, setRadiusKm] = useState('');
  const [requests, setRequests] = useState([]);
  const [requestsLoading, setRequestsLoading] = useState(true);
  const [requestError, setRequestError] = useState('');
  const [donors, setDonors] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [notifiedDonors, setNotifiedDonors] = useState([]);
  const [emailStatusMessage, setEmailStatusMessage] = useState('');
  const [retryToken, setRetryToken] = useState(0);

  const selectedRequest = useMemo(
    () => requests.find((request) => String(request.id) === String(selectedRequestId)) || null,
    [requests, selectedRequestId]
  );
  const requestHasCoordinates = hasCoordinates(selectedRequest);
  const availableTaluks = selectedDistrict ? (taluksByDistrict[selectedDistrict] || []) : [];
  const displayedDonors = useMemo(() => donors.slice(0, 50), [donors]);

  useEffect(() => {
    const controller = new AbortController();
    async function fetchRequests() {
      setRequestsLoading(true);
      setRequestError('');
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/requests`, { signal: controller.signal });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Could not load blood requests.');
        setRequests(Array.isArray(data) ? data : []);
      } catch (error) {
        if (error.name !== 'AbortError') setRequestError(error.message || 'Could not load blood requests.');
      } finally {
        if (!controller.signal.aborted) setRequestsLoading(false);
      }
    }
    fetchRequests();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function searchDonors() {
      setSearchLoading(true);
      setSearchError('');
      try {
        const params = new URLSearchParams({ blood_group: selectedGroup, available_only: String(availableOnly) });
        if (selectedDistrict) params.set('district', selectedDistrict);
        if (selectedTaluk) params.set('taluk', selectedTaluk);
        if (selectedRequestId) params.set('request_id', selectedRequestId);
        if (requestHasCoordinates && radiusKm !== '') params.set('radius_km', radiusKm);
        if (sortBy === 'distance' && requestHasCoordinates) params.set('sort_by', 'distance');
        const response = await fetch(`${API_BASE_URL}/api/v1/donors?${params.toString()}`, { signal: controller.signal });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Donor search failed.');
        setDonors(Array.isArray(data) ? data : []);
      } catch (error) {
        if (error.name !== 'AbortError') {
          setSearchError(error.message || 'Donor search failed.');
          setDonors([]);
        }
      } finally {
        if (!controller.signal.aborted) setSearchLoading(false);
      }
    }
    searchDonors();
    return () => controller.abort();
  }, [selectedGroup, selectedDistrict, selectedTaluk, selectedRequestId, availableOnly, radiusKm, sortBy, requestHasCoordinates, retryToken]);

  const handleRequestChange = (event) => {
    const nextId = event.target.value;
    setSelectedRequestId(nextId);
    setRadiusKm('');
    setSortBy('availability');
    const request = requests.find((item) => String(item.id) === nextId);
    if (request?.blood_group) setSelectedGroup(request.blood_group);
  };

  const resetFilters = () => {
    setSelectedGroup('O+');
    setSelectedDistrict('');
    setSelectedTaluk('');
    setSelectedRequestId('');
    setAvailableOnly(true);
    setSortBy('availability');
    setRadiusKm('');
    setEmailStatusMessage('');
  };

  const handleNotify = async (donor) => {
    if (!selectedRequest) {
      setEmailStatusMessage('Select the actual blood request before dispatching an emergency alert.');
      return;
    }
    const donorKey = donor.id || donor.donor_id;
    if (notifiedDonors.includes(donorKey)) return;
    setEmailStatusMessage(`Sending emergency alert for ${selectedRequest.hospital_name}…`);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/donors/send-email-alert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          donor_email: donor.email,
          donor_name: donor.name,
          blood_group: donor.blood_group,
          hospital_name: selectedRequest.hospital_name,
          urgency: selectedRequest.urgency_level,
          patient: selectedRequest.patient_name
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'The emergency alert request failed.');
      if (data.sent) {
        setNotifiedDonors((current) => [...current, donorKey]);
        setEmailStatusMessage(`Emergency email successfully sent to ${donor.name}.`);
      } else {
        setEmailStatusMessage(`The backend did not send an email to ${donor.name}. Check the SMTP configuration before retrying.`);
      }
    } catch (error) {
      setEmailStatusMessage(error.message || `Could not send an emergency alert to ${donor.name}.`);
    }
  };

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900 to-blood-950/30 shadow-xl">
        <div className="flex flex-col gap-4 border-b border-slate-800 p-5 sm:p-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-blood-300">
              <Sparkles className="h-4 w-4" />
              <span>Emergency response workspace</span>
            </div>
            <h2 className="text-2xl font-black tracking-tight text-white sm:text-3xl">Emergency Donor Search</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
              Search donors using backend-enforced blood group, availability, district and taluk filters. Select a saved blood request to calculate distance from its recorded coordinates.
            </p>
          </div>
          <button type="button" onClick={resetFilters} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-950 px-4 py-2.5 text-sm font-semibold text-slate-200 transition hover:border-slate-500 hover:bg-slate-800">
            <RotateCcw className="h-4 w-4" /> Reset filters
          </button>
        </div>

        <div className="space-y-5 p-5 sm:p-6">
          <div>
            <label className={labelClass} htmlFor="emergency-request">Blood request / hospital location</label>
            <select id="emergency-request" value={selectedRequestId} onChange={handleRequestChange} className={inputClass} disabled={requestsLoading}>
              <option value="">Select a saved request to calculate distance (optional)</option>
              {requests.map((request) => (
                <option key={request.id} value={request.id}>
                  #{request.id} · {request.hospital_name} · {request.blood_group} · {request.urgency_level}
                </option>
              ))}
            </select>
            {requestsLoading && <p className="mt-1 text-xs text-slate-500">Loading saved blood requests…</p>}
            {requestError && <p role="alert" className="mt-1 text-xs text-rose-300">{requestError}</p>}
            {selectedRequest && (
              <div className="mt-2 flex flex-col gap-1 rounded-xl border border-slate-700 bg-slate-950/70 p-3 text-xs sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-2 text-slate-300">
                  <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-blood-400" />
                  <div>
                    <p className="font-semibold text-white">{selectedRequest.hospital_name}</p>
                    <p className="mt-0.5 text-slate-400">{[selectedRequest.taluk, selectedRequest.district, selectedRequest.hospital_address].filter(Boolean).join(' · ') || 'Location details not recorded'}</p>
                  </div>
                </div>
                <span className={`mt-1 inline-flex w-fit items-center gap-1 rounded-full px-2.5 py-1 font-semibold sm:mt-0 ${requestHasCoordinates ? 'bg-emerald-950 text-emerald-300' : 'bg-amber-950 text-amber-200'}`}>
                  {requestHasCoordinates ? <Navigation className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
                  {requestHasCoordinates ? 'Coordinates available' : 'Distance unavailable without coordinates'}
                </span>
              </div>
            )}
          </div>

          <div>
            <label className={labelClass}>Required blood group</label>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Required blood group">
              {BLOOD_GROUPS.map((group) => (
                <button
                  key={group}
                  type="button"
                  aria-pressed={selectedGroup === group}
                  onClick={() => setSelectedGroup(group)}
                  className={`min-w-14 rounded-xl border px-4 py-2.5 text-sm font-extrabold transition focus:outline-none focus:ring-2 focus:ring-blood-400/50 ${selectedGroup === group ? 'border-blood-400 bg-blood-600 text-white shadow-lg' : 'border-slate-700 bg-slate-950 text-slate-300 hover:border-slate-500 hover:bg-slate-800'}`}
                >{group}</button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div>
              <label className={labelClass} htmlFor="emergency-district">District</label>
              <select id="emergency-district" value={selectedDistrict} onChange={(event) => { setSelectedDistrict(event.target.value); setSelectedTaluk(''); }} className={inputClass} disabled={locationsLoading}>
                <option value="">All districts</option>
                {districts.map((district) => <option key={district} value={district}>{district}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass} htmlFor="emergency-taluk">Taluk</label>
              <select id="emergency-taluk" value={selectedTaluk} onChange={(event) => setSelectedTaluk(event.target.value)} className={inputClass} disabled={!selectedDistrict || locationsLoading}>
                <option value="">All taluks in selected district</option>
                {availableTaluks.map((taluk) => <option key={taluk} value={taluk}>{taluk}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass} htmlFor="emergency-sort">Sort results</label>
              <select id="emergency-sort" value={sortBy} onChange={(event) => setSortBy(event.target.value)} className={inputClass}>
                <option value="availability">Availability score</option>
                <option value="distance" disabled={!requestHasCoordinates}>Nearest to request</option>
              </select>
            </div>
            <div>
              <label className={labelClass} htmlFor="emergency-radius">Distance radius (km)</label>
              <input id="emergency-radius" type="number" min="0.1" max="5000" step="0.1" value={radiusKm} onChange={(event) => setRadiusKm(event.target.value)} className={inputClass} placeholder="No radius limit" disabled={!requestHasCoordinates} />
            </div>
          </div>

          <div className="flex flex-col gap-3 border-t border-slate-800 pt-4 sm:flex-row sm:items-center sm:justify-between">
            <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={availableOnly} onChange={(event) => setAvailableOnly(event.target.checked)} className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-blood-500 focus:ring-blood-500" />
              Show only donors marked available
            </label>
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
              {selectedDistrict && <span className="rounded-full border border-slate-700 bg-slate-950 px-2.5 py-1">District: {selectedDistrict}</span>}
              {selectedTaluk && <span className="rounded-full border border-slate-700 bg-slate-950 px-2.5 py-1">Taluk: {selectedTaluk}</span>}
              {selectedRequest && <span className="rounded-full border border-slate-700 bg-slate-950 px-2.5 py-1">Request #{selectedRequest.id}</span>}
            </div>
          </div>

          {(locationsError || searchError || emailStatusMessage) && (
            <div role="status" className={`flex items-start gap-2 rounded-xl border p-3 text-sm ${searchError || locationsError ? 'border-rose-800 bg-rose-950/40 text-rose-200' : 'border-slate-700 bg-slate-950 text-slate-300'}`}>
              <Mail className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{searchError || locationsError || emailStatusMessage}</span>
            </div>
          )}
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="text-lg font-bold text-white">Matching donors</h3>
            <p className="mt-1 text-sm text-slate-400">
              {searchLoading ? 'Applying filters on the backend…' : `${donors.length} donor${donors.length === 1 ? '' : 's'} matched for ${selectedGroup}${selectedDistrict ? ` · ${selectedDistrict}` : ''}${selectedTaluk ? ` · ${selectedTaluk}` : ''}.`}
              {donors.length > 50 ? ' Showing the first 50 results.' : ''}
            </p>
          </div>
          {requestHasCoordinates && <span className="inline-flex items-center gap-1.5 text-xs text-slate-400"><Navigation className="h-3.5 w-3.5" /> Straight-line distance from request coordinates, not driving distance</span>}
        </div>

        {searchLoading ? (
          <div className="flex min-h-40 items-center justify-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/50 text-sm text-slate-300">
            <Loader className="h-5 w-5 animate-spin text-blood-400" /> Searching eligible donors…
          </div>
        ) : searchError ? (
          <div className="rounded-2xl border border-rose-800 bg-rose-950/30 p-6 text-center">
            <AlertTriangle className="mx-auto mb-2 h-8 w-8 text-rose-300" />
            <p className="font-semibold text-white">Donor search could not be completed</p>
            <p className="mt-1 text-sm text-rose-200">{searchError}</p>
            <button type="button" onClick={() => setRetryToken((current) => current + 1)} className="mt-3 rounded-lg border border-rose-700 px-3 py-2 text-xs font-semibold text-rose-100 hover:bg-rose-950">Retry search</button>
          </div>
        ) : donors.length === 0 ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-8 text-center">
            <Search className="mx-auto mb-2 h-8 w-8 text-slate-500" />
            <p className="font-semibold text-white">No donors match the current filters</p>
            <p className="mt-1 text-sm text-slate-400">Try another blood group or location, or reset the filters.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {displayedDonors.map((donor, index) => {
              const donorKey = donor.id || donor.donor_id;
              const isNotified = notifiedDonors.includes(donorKey);
              const score = donor.availability_score ?? 0;
              const category = donor.availability_status || 'UNKNOWN';
              const distance = donor.distance_from_request_km;
              const lastDonation = donor.last_donation_date || (donor.last_donation_days != null ? `${donor.last_donation_days} days ago` : 'Not recorded');
              const phone = donor.phone || '';
              return (
                <article key={donorKey} className="flex flex-col justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-lg transition hover:border-slate-700">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-blood-800 bg-blood-950 text-sm font-black text-blood-300">#{index + 1}</div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="font-bold text-white">{donor.name || 'Registered donor'}</h4>
                          <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">{donor.donor_id || donor.id}</span>
                        </div>
                        <p className="mt-1 text-xs text-slate-400">{[donor.taluk, donor.district, donor.location].filter(Boolean).filter((item, itemIndex, all) => all.indexOf(item) === itemIndex).join(' · ') || 'Location not recorded'}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                          <span className="rounded-lg border border-blood-800 bg-blood-950/50 px-2 py-1 font-black text-blood-300">{donor.blood_group}</span>
                          <span className={`inline-flex items-center gap-1 rounded-lg px-2 py-1 font-semibold ${donor.is_available ? 'bg-emerald-950 text-emerald-300' : 'bg-slate-800 text-slate-400'}`}>
                            {donor.is_available ? <CheckCircle className="h-3.5 w-3.5" /> : <Clock3 className="h-3.5 w-3.5" />}
                            {donor.is_available ? 'Available' : 'Not marked available'}
                          </span>
                        </div>
                      </div>
                    </div>
                    <MLPredictionBadge category={category} score={score} />
                  </div>

                  <div className="grid grid-cols-2 gap-3 rounded-xl border border-slate-800 bg-slate-950/80 p-3 sm:grid-cols-3">
                    <div>
                      <span className="block text-[11px] text-slate-500">Distance from request</span>
                      <span className={`mt-1 block text-sm font-bold ${distance == null ? 'text-slate-400' : 'text-sky-300'}`}>
                        {distance == null ? 'Distance unavailable' : `${Number(distance).toFixed(1)} km away`}
                      </span>
                    </div>
                    <div>
                      <span className="block text-[11px] text-slate-500">Last donation</span>
                      <span className="mt-1 block text-sm font-semibold text-slate-200">{lastDonation}</span>
                    </div>
                    <div>
                      <span className="block text-[11px] text-slate-500">Response rate</span>
                      <span className="mt-1 block text-sm font-semibold text-emerald-300">{donor.previous_response_rate == null ? 'Not recorded' : `${Math.round(Number(donor.previous_response_rate) * 100)}%`}</span>
                    </div>
                  </div>

                  <div className="flex flex-col gap-2 border-t border-slate-800 pt-3 sm:flex-row sm:items-center sm:justify-between">
                    {phone ? (
                      <a href={`tel:${phone}`} className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2.5 text-xs font-semibold text-slate-200 transition hover:bg-slate-700">
                        <Phone className="h-3.5 w-3.5 text-slate-400" /> Call donor
                      </a>
                    ) : (
                      <span className="text-xs text-slate-500">Phone number not recorded</span>
                    )}
                    <button
                      type="button"
                      onClick={() => handleNotify(donor)}
                      disabled={isNotified || !selectedRequest}
                      title={!selectedRequest ? 'Select a saved blood request first' : ''}
                      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition disabled:cursor-not-allowed disabled:opacity-50 ${isNotified ? 'border border-emerald-800 bg-emerald-950 text-emerald-300' : 'bg-gradient-to-r from-blood-600 to-blood-700 text-white hover:from-blood-500 hover:to-blood-600'}`}
                    >
                      {isNotified ? <CheckCircle className="h-4 w-4" /> : <Send className="h-4 w-4" />}
                      {isNotified ? 'Email sent' : 'Dispatch alert for selected request'}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
