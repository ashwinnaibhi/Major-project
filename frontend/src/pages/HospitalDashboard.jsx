import React, { useState, useEffect, useCallback } from 'react';
import { getApiBaseUrl } from '../api/config';
const API_BASE = getApiBaseUrl();
import StatCard from '../components/StatCard';
import MLPredictionBadge from '../components/MLPredictionBadge';
import { Plus, FileText, CheckCircle2, Clock, MapPin, AlertCircle, Building2, X, Award } from 'lucide-react';

export default function HospitalDashboard({ donorsList = [], requestsList = [], onRequestCreated, currentUser, onRefreshRequests }) {
  const [showReqModal, setShowReqModal] = useState(false);
  const [showDonationModal, setShowDonationModal] = useState(false);
  const [hospitalDonations, setHospitalDonations] = useState([]);
  const [isSubmittingDonation, setIsSubmittingDonation] = useState(false);
  const [donationFormError, setDonationFormError] = useState('');
  const [requisitionTab, setRequisitionTab] = useState('pending');
  const [donationForm, setDonationForm] = useState({
    donor_email: '',
    donor_name: '',
    blood_group: 'O+',
    units: 1,
    donation_date: new Date().toISOString().split('T')[0],
    donation_type: 'Whole Blood',
    appointment_id: '',
    requisition_id: '',
    notes: ''
  });
  const [newRequest, setNewRequest] = useState({
    hospital_name: currentUser?.name || '',
    hospital_address: '',
    contact_phone: currentUser?.phone || '',
    blood_group: 'O-',
    units: 2,
    urgency: 'EMERGENCY',
    patient: '',
    destination_latitude: '',
    destination_longitude: ''
  });
  const [formError, setFormError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [successNotice, setSuccessNotice] = useState('');
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [profileForm, setProfileForm] = useState({ contact_email: '', contact_phone: '' });
  const [profileStatus, setProfileStatus] = useState(null);
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setProfileStatus(null);
    setIsSavingProfile(true);
    try {
      const resp = await fetch(`${API_BASE}/api/v1/hospitals/me/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${currentUser?.token}`
        },
        body: JSON.stringify({
          hospital_name: currentUser?.hospital_profile?.hospital_name || currentUser?.name || 'Hospital',
          address: currentUser?.hospital_profile?.address || 'Hospital Address',
          district: currentUser?.hospital_profile?.district || 'General',
          taluk: currentUser?.hospital_profile?.taluk || null,
          latitude: currentUser?.hospital_profile?.latitude,
          longitude: currentUser?.hospital_profile?.longitude,
          contact_email: profileForm.contact_email.trim() || null,
          contact_phone: profileForm.contact_phone.trim() || null,
        })
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.detail || 'Could not save profile.');
      if (currentUser?.hospital_profile) {
        currentUser.hospital_profile.contact_email = data.hospital_profile.contact_email;
        currentUser.hospital_profile.contact_phone = data.hospital_profile.contact_phone;
      }
      setProfileStatus({ type: 'success', text: 'Hospital contact details saved. Emergency notifications will route to this email.' });
      setTimeout(() => setShowProfileModal(false), 1200);
    } catch (err) {
      setProfileStatus({ type: 'error', text: err.message });
    } finally {
      setIsSavingProfile(false);
    }
  };

  const updateField = (field, value) => {
    setNewRequest((previous) => ({ ...previous, [field]: value }));
    setIsDirty(true);
  };

  const resetRequestForm = () => {
    setNewRequest({
      hospital_name: currentUser?.name || '',
      hospital_address: '',
      contact_phone: currentUser?.phone || '',
      blood_group: 'O-',
      units: 2,
      urgency: 'EMERGENCY',
      patient: '',
      destination_latitude: '',
      destination_longitude: ''
    });
    setIsDirty(false);
  };

  const closeRequestModal = useCallback(() => {
    if (isSubmitting) return;
    if (isDirty && !window.confirm('Discard the unsaved blood request?')) return;
    setShowReqModal(false);
    setFormError('');
    setIsDirty(false);
  }, [isDirty, isSubmitting]);

  useEffect(() => {
    if (!showReqModal) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') closeRequestModal();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showReqModal, closeRequestModal]);

  const pendingRequests = requestsList.filter(r => (r.status || 'PENDING') === 'PENDING');
  const fulfilledRequests = requestsList.filter(r => r.status === 'FULFILLED' || r.status === 'APPROVED' || r.status === 'ALLOCATED');
  const pendingCount = pendingRequests.length;
  const fulfilledCount = fulfilledRequests.length;
  const emergencyCount = pendingRequests.filter(r => (r.urgency || r.urgency_level) === 'EMERGENCY').length;

  const openFulfillModal = (req) => {
    const remainingUnits = Math.max(1, (Number(req.units_needed || req.units) - Number(req.units_fulfilled || 0)));
    setDonationForm({
      donor_email: '',
      donor_name: '',
      blood_group: req.blood_group || req.blood || 'O+',
      units: remainingUnits,
      donation_date: new Date().toISOString().split('T')[0],
      donation_type: 'Whole Blood',
      appointment_id: '',
      requisition_id: String(req.id || ''),
      notes: `Fulfillment donation for Requisition #${req.id} (${req.patient_name || req.patient || 'Patient'})`
    });
    setDonationFormError('');
    setShowDonationModal(true);
  };

  const isHospitalAuthorized = Boolean(
    currentUser?.token &&
    ['HOSPITAL', 'ROLE_HOSPITAL', 'ADMIN', 'ROLE_ADMIN'].includes(
      String(currentUser?.role || '').toUpperCase()
    )
  );

  const loadHospitalDonations = useCallback(async () => {
    if (!currentUser?.token || !isHospitalAuthorized) {
      setHospitalDonations([]);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/v1/hospitals/donations`, {
        headers: { Authorization: `Bearer ${currentUser.token}` }
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) setHospitalDonations(data);
      } else if (res.status === 403 || res.status === 401) {
        setHospitalDonations([]);
      }
    } catch (_) {
      setHospitalDonations([]);
    }
  }, [currentUser?.token, isHospitalAuthorized]);

  useEffect(() => {
    loadHospitalDonations();
  }, [loadHospitalDonations]);

  const handleRecordDonation = async (e) => {
    e.preventDefault();
    setDonationFormError('');
    if (!isHospitalAuthorized || !currentUser?.token) {
      setDonationFormError('Sign in with an authorized hospital or administrator account to record donations.');
      return;
    }
    setIsSubmittingDonation(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/hospitals/donations/record`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(currentUser?.token ? { Authorization: `Bearer ${currentUser.token}` } : {})
        },
        body: JSON.stringify({
          donor_email: donationForm.donor_email.trim(),
          donor_name: donationForm.donor_name.trim() || undefined,
          blood_group: donationForm.blood_group,
          units: Number(donationForm.units),
          donation_date: donationForm.donation_date,
          donation_type: donationForm.donation_type,
          appointment_id: donationForm.appointment_id ? Number(donationForm.appointment_id) : undefined,
          requisition_id: donationForm.requisition_id ? Number(donationForm.requisition_id) : undefined,
          notes: donationForm.notes.trim() || undefined
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to record donation.');
      const noticeSuffix = data.requisition_id
        ? ` Requisition #${data.requisition_id} updated (${data.requisition_status}).`
        : '';
      setSuccessNotice(`Donation confirmed! Certificate #${data.certificate_code} issued for ${data.donor_name} (${data.units} unit(s) of ${data.blood_group}).${noticeSuffix}`);
      setShowDonationModal(false);
      setDonationForm({
        donor_email: '',
        donor_name: '',
        blood_group: 'O+',
        units: 1,
        donation_date: new Date().toISOString().split('T')[0],
        donation_type: 'Whole Blood',
        appointment_id: '',
        requisition_id: '',
        notes: ''
      });
      await loadHospitalDonations();
      if (typeof onRefreshRequests === 'function') {
        await onRefreshRequests();
      }
    } catch (err) {
      setDonationFormError(err.message || 'Could not record donation.');
    } finally {
      setIsSubmittingDonation(false);
    }
  };

  const handleCreateRequest = async (e) => {
    e.preventDefault();
    setFormError('');
    if (!isHospitalAuthorized || !currentUser?.token) {
      setFormError('Sign in with an authorized hospital account to create a requisition.');
      return;
    }
    if (!newRequest.hospital_name.trim()) { setFormError('Hospital name is required.'); return; }
    if (!newRequest.hospital_address.trim()) { setFormError('Hospital address is required.'); return; }
    if (!Number.isInteger(Number(newRequest.units)) || Number(newRequest.units) <= 0 || Number(newRequest.units) > 1000) {
      setFormError('Units must be a whole number between 1 and 1,000.');
      return;
    }
    if (!newRequest.patient.trim()) { setFormError('Patient or ward reference is required.'); return; }
    const hasLat = String(newRequest.destination_latitude).trim() !== '';
    const hasLon = String(newRequest.destination_longitude).trim() !== '';
    if (hasLat !== hasLon) {
      setFormError('Enter both destination latitude and longitude, or leave both blank.');
      return;
    }
    const latitude = hasLat ? Number(newRequest.destination_latitude) : null;
    const longitude = hasLon ? Number(newRequest.destination_longitude) : null;
    if (hasLat && (!Number.isFinite(latitude) || latitude < -90 || latitude > 90 || !Number.isFinite(longitude) || longitude < -180 || longitude > 180)) {
      setFormError('Enter valid coordinates (latitude −90 to 90, longitude −180 to 180).');
      return;
    }

    setIsSubmitting(true);
    try {
      let saved = null;
      if (typeof onRequestCreated === 'function') {
        saved = await onRequestCreated({
          hospital_name: newRequest.hospital_name.trim(),
          hospital_address: newRequest.hospital_address.trim(),
          contact_phone: newRequest.contact_phone.trim(),
          blood_group: newRequest.blood_group,
          units_needed: Number(newRequest.units),
          urgency_level: newRequest.urgency,
          patient_name: newRequest.patient.trim(),
          destination_latitude: latitude,
          destination_longitude: longitude,
          assigned_admin_user_id: null
        });
      } else {
        const response = await fetch(`${API_BASE}/api/v1/requests`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(currentUser?.token ? { Authorization: `Bearer ${currentUser.token}` } : {})
          },
          body: JSON.stringify({
            hospital_name: newRequest.hospital_name.trim(),
            hospital_address: newRequest.hospital_address.trim(),
            contact_phone: newRequest.contact_phone.trim(),
            blood_group: newRequest.blood_group,
            units_needed: Number(newRequest.units),
            urgency_level: newRequest.urgency,
            patient_name: newRequest.patient.trim(),
            destination_latitude: latitude,
            destination_longitude: longitude,
            assigned_admin_user_id: null
          })
        });
        saved = await response.json();
      }

      if (!saved || saved.id == null) throw new Error('The backend did not confirm a persisted request ID.');
      setIsDirty(false);
      setSuccessNotice(saved.notification_summary?.message || `Request #${saved.id} was saved. The notification queue status should be checked in the request monitor.`);
      setShowReqModal(false);
      resetRequestForm();
    } catch (error) {
      setFormError(error.message || 'The request could not be saved. No success has been assumed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {successNotice && (
        <div role="status" className="rounded-xl border border-emerald-800 bg-emerald-950/50 p-3 text-xs text-emerald-200">
          {successNotice}
        </div>
      )}

      {/* Dedicated Hospital Identity & Notification Routing Banner */}
      <div className="p-4 rounded-2xl glass-panel border border-slate-800 bg-slate-950/70 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blood-800/80 border border-blood-700/60 text-white shadow-md">
            <Building2 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-extrabold text-white">
                {currentUser?.hospital_profile?.hospital_name || currentUser?.name || 'Hospital Facility'}
              </h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                Taluk: {currentUser?.hospital_profile?.taluk || 'General'}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400 mt-1">
              <span>
                Dedicated Login ID: <strong className="font-mono text-blood-300">{currentUser?.email || 'N/A'}</strong>
              </span>
              <span>•</span>
              <span>
                Verified Notification Email: <strong className={currentUser?.hospital_profile?.contact_email ? "text-emerald-400 font-mono" : "text-amber-400 font-mono"}>
                  {currentUser?.hospital_profile?.contact_email || 'Not configured'}
                </strong>
              </span>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(!currentUser?.hospital_profile?.contact_email || currentUser?.hospital_profile?.contact_email.endsWith('@haemopulse.in')) && (
            <span className="text-[11px] text-amber-400 bg-amber-950/60 border border-amber-800/80 px-2.5 py-1 rounded-lg">
              ⚠️ Email notifications require a verified contact email
            </span>
          )}
          <button
            type="button"
            onClick={() => {
              setProfileForm({
                contact_email: currentUser?.hospital_profile?.contact_email || '',
                contact_phone: currentUser?.hospital_profile?.contact_phone || currentUser?.phone || '',
              });
              setShowProfileModal(true);
            }}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-bold transition shadow-sm"
          >
            Configure Notification Email
          </button>
        </div>
      </div>

      {/* Hospital Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Active Requisitions"
          value={`${requestsList.length} Total`}
          subtitle={`${pendingCount} Pending Verification`}
          icon={FileText}
          color="blood"
        />
        <StatCard
          title="Fulfilled Requests"
          value={`${fulfilledCount} Allocated`}
          subtitle="Processed by staff"
          icon={CheckCircle2}
          color="emerald"
        />
        <StatCard
          title="Emergency Priority"
          value={`${emergencyCount} Calls`}
          subtitle="Critical priority"
          icon={AlertCircle}
          color="amber"
        />
        <StatCard
          title="Nearby Matched Donors"
          value={`${donorsList.length} Registered`}
          subtitle="Ready for emergency dispatch"
          icon={MapPin}
          color="blue"
        />
      </div>

      {/* Main Focus: Hospital Blood Requisitions Section */}
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div>
            <div className="flex items-center space-x-2 text-xs font-semibold text-blood-400 mb-1">
              <Building2 className="w-4 h-4" />
              <span>Hospital Operations Center</span>
            </div>
            <h2 className="text-2xl font-black text-white">Hospital Blood Requisitions</h2>
            <p className="text-xs text-slate-400">Submit urgent and routine blood requests; updates sync in real-time with Blood Bank staff.</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => { setDonationFormError(''); setShowDonationModal(true); }}
              className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-blood-400 border border-slate-700 font-bold text-xs shadow-md flex items-center space-x-2 transition-all"
            >
              <Award className="w-4 h-4" />
              <span>Record Completed Donation</span>
            </button>

            <button
              onClick={() => { setFormError(''); setIsDirty(false); setShowReqModal(true); }}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-bold text-xs shadow-lg glow-red flex items-center space-x-2 transition-all"
            >
              <Plus className="w-4 h-4" />
              <span>New Emergency Requisition</span>
            </button>
          </div>
        </div>

        {/* Tab Controls for Active Pending vs Fulfilled History */}
        <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
          <button
            type="button"
            onClick={() => setRequisitionTab('pending')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center space-x-1.5 ${
              requisitionTab === 'pending'
                ? 'bg-amber-950/80 text-amber-300 border border-amber-700/80'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Active Pending Requisitions ({pendingRequests.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setRequisitionTab('fulfilled')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center space-x-1.5 ${
              requisitionTab === 'fulfilled'
                ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700/80'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Fulfilled & Completed Archive ({fulfilledRequests.length})</span>
          </button>
        </div>

        {/* Requisitions Tables */}
        <div className="overflow-x-auto">
          {requisitionTab === 'pending' ? (
            pendingRequests.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-xs">
                No active pending requisitions. All facility requests have been fulfilled or click "New Emergency Requisition" to request blood units.
              </div>
            ) : (
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Req ID</th>
                    <th className="py-2.5 px-3">Hospital Name</th>
                    <th className="py-2.5 px-3">Hospital Address</th>
                    <th className="py-2.5 px-3">Blood Group</th>
                    <th className="py-2.5 px-3">Units Needed</th>
                    <th className="py-2.5 px-3">Urgency</th>
                    <th className="py-2.5 px-3">Patient / Ward</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {pendingRequests.map((req, idx) => {
                    const reqId = req.id || req._id || `REQ-${idx + 1}`;
                    const needed = Number(req.units_needed || req.units || 1);
                    const fulfilled = Number(req.units_fulfilled || 0);

                    return (
                      <tr key={reqId} className="hover:bg-slate-900/40">
                        <td className="py-2.5 px-3 font-mono text-slate-400">#{reqId}</td>
                        <td className="py-2.5 px-3 font-bold text-white">
                          {req.hospital_name || req.hospital}
                          {req.contact_phone && (
                            <span className="block text-[10px] text-slate-400 font-mono">{req.contact_phone}</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400 max-w-xs truncate" title={req.hospital_address || ''}>
                          {req.hospital_address || 'Address on file'}
                        </td>
                        <td className="py-2.5 px-3 font-extrabold text-blood-400 text-sm">
                          {req.blood || req.blood_group}
                        </td>
                        <td className="py-2.5 px-3 font-semibold text-white">
                          <div>{fulfilled > 0 ? `${fulfilled} / ${needed} units` : `${needed} units`}</div>
                          {fulfilled > 0 && (
                            <span className="inline-block text-[10px] text-amber-400 font-medium">
                              Partially satisfied ({needed - fulfilled} remaining)
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold ${
                            (req.urgency || req.urgency_level) === 'EMERGENCY'
                              ? 'bg-blood-950 text-blood-400 border border-blood-800 animate-pulse'
                              : 'bg-amber-950 text-amber-400 border border-amber-800'
                          }`}>
                            {req.urgency || req.urgency_level}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">{req.patient || req.patient_name}</td>
                        <td className="py-2.5 px-3 font-bold">
                          <span className="text-amber-400">
                            {req.status || 'PENDING'}
                          </span>
                        </td>
                        <td className="py-2.5 px-3">
                          <button
                            type="button"
                            onClick={() => openFulfillModal(req)}
                            className="px-2.5 py-1 rounded-lg bg-emerald-950/80 hover:bg-emerald-900 text-emerald-300 border border-emerald-800 text-[11px] font-bold transition flex items-center space-x-1 shadow-sm"
                            title="Record donation fulfilling this requisition"
                          >
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Fulfill</span>
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )
          ) : (
            fulfilledRequests.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-xs">
                No fulfilled requisitions archived yet. Completed requisitions will appear here.
              </div>
            ) : (
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Req ID</th>
                    <th className="py-2.5 px-3">Hospital Name</th>
                    <th className="py-2.5 px-3">Blood Group</th>
                    <th className="py-2.5 px-3">Units Satisfied</th>
                    <th className="py-2.5 px-3">Urgency</th>
                    <th className="py-2.5 px-3">Patient / Ward</th>
                    <th className="py-2.5 px-3">Fulfilled Date</th>
                    <th className="py-2.5 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {fulfilledRequests.map((req, idx) => {
                    const reqId = req.id || req._id || `REQ-${idx + 1}`;
                    return (
                      <tr key={reqId} className="hover:bg-slate-900/40">
                        <td className="py-2.5 px-3 font-mono text-slate-400">#{reqId}</td>
                        <td className="py-2.5 px-3 font-bold text-white">{req.hospital_name || req.hospital}</td>
                        <td className="py-2.5 px-3 font-extrabold text-blood-400 text-sm">{req.blood || req.blood_group}</td>
                        <td className="py-2.5 px-3 font-semibold text-emerald-400">{req.units_fulfilled || req.units_needed || req.units} units</td>
                        <td className="py-2.5 px-3">
                          <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-slate-800 text-slate-300">
                            {req.urgency || req.urgency_level}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">{req.patient || req.patient_name}</td>
                        <td className="py-2.5 px-3 font-mono text-slate-400">{req.fulfilled_at || 'Archived'}</td>
                        <td className="py-2.5 px-3 font-bold">
                          <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-bold">
                            {req.status || 'FULFILLED'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )
          )}
        </div>
      </div>

      {/* Facility Recorded Donations Section */}
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div>
            <div className="flex items-center space-x-2 text-xs font-semibold text-emerald-400 mb-1">
              <Award className="w-4 h-4" />
              <span>Verified Clinical Collections</span>
            </div>
            <h2 className="text-2xl font-black text-white">Facility Recorded Donations</h2>
            <p className="text-xs text-slate-400">Verified donations collected at this facility, backed by official digital certificates.</p>
          </div>

          <span className="px-3 py-1 rounded-xl text-xs bg-emerald-950 text-emerald-400 border border-emerald-800 font-bold">
            {hospitalDonations.length} Verified Donations
          </span>
        </div>

        <div className="overflow-x-auto">
          {hospitalDonations.length === 0 ? (
            <div className="p-8 text-center text-slate-500 text-xs">
              {!isHospitalAuthorized ? (
                <span>Hospital sign-in required to view facility donation records.</span>
              ) : (
                <span>No completed donations recorded yet. Click "Record Completed Donation" after collecting blood from a donor.</span>
              )}
            </div>
          ) : (
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Certificate Code</th>
                  <th className="py-2.5 px-3">Donor Name / Email</th>
                  <th className="py-2.5 px-3">Blood Group</th>
                  <th className="py-2.5 px-3">Units</th>
                  <th className="py-2.5 px-3">Date</th>
                  <th className="py-2.5 px-3">Type</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {hospitalDonations.map((d, idx) => (
                  <tr key={d.id || idx} className="hover:bg-slate-900/40">
                    <td className="py-2.5 px-3 font-mono font-bold text-blood-400">
                      {d.certificate_code}
                      {d.requisition_id && (
                        <span className="block text-[10px] text-emerald-400 font-sans font-semibold">
                          Fulfills Req #{d.requisition_id}
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 font-bold text-white">
                      {d.donor_name}
                      <span className="block text-[10px] text-slate-500 font-normal">{d.donor_email}</span>
                    </td>
                    <td className="py-2.5 px-3 font-black text-blood-400 text-sm">{d.blood_group}</td>
                    <td className="py-2.5 px-3 font-semibold text-white">{d.units} Unit(s)</td>
                    <td className="py-2.5 px-3 font-mono text-slate-300">{d.donation_date}</td>
                    <td className="py-2.5 px-3 text-slate-400">{d.donation_type || 'Whole Blood'}</td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-bold">
                        {d.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Modal for Creating Extended Blood Requisition */}
      {showReqModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-start md:items-center justify-center overflow-y-auto p-3 sm:p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) closeRequestModal(); }}>
          <div role="dialog" aria-modal="true" aria-labelledby="hospital-request-title" className="my-2 w-full max-w-lg max-h-[calc(100dvh-1rem)] overflow-y-auto overscroll-contain p-5 sm:p-6 rounded-2xl glass-panel border border-slate-800 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <h3 id="hospital-request-title" className="text-lg font-extrabold text-white">Create Hospital Blood Request</h3>
              <button type="button" onClick={closeRequestModal} disabled={isSubmitting} aria-label="Back to hospital dashboard" className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 disabled:opacity-50"><X className="w-4 h-4" /></button>
            </div>

            {formError && (
              <div className="p-3 rounded-xl bg-rose-950/80 border border-rose-800 text-rose-300 text-xs font-semibold">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreateRequest} className="space-y-3 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Hospital Name *</label>
                  <input
                    type="text"
                    required
                    value={newRequest.hospital_name}
                    onChange={(e) => updateField('hospital_name', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-blood-500"
                  />
                </div>

                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Contact Phone Number</label>
                  <input
                    type="tel"
                    value={newRequest.contact_phone}
                    onChange={(e) => updateField('contact_phone', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-blood-500"
                    placeholder="+1-800-555-0101"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-300 block mb-1 font-semibold">Hospital Address (Delivery / Trauma Desk) *</label>
                <textarea
                  required
                  rows={2}
                  value={newRequest.hospital_address}
                  onChange={(e) => updateField('hospital_address', e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-blood-500"
                  placeholder="e.g. 100 Healthcare Blvd, Suite 400, Trauma Wing Desk"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div><label htmlFor="destination-latitude" className="text-slate-300 block mb-1 font-semibold">Destination latitude (optional)</label><input id="destination-latitude" type="number" min="-90" max="90" step="any" value={newRequest.destination_latitude} onChange={(event) => updateField('destination_latitude', event.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white" placeholder="12.9716" /></div>
                <div><label htmlFor="destination-longitude" className="text-slate-300 block mb-1 font-semibold">Destination longitude (optional)</label><input id="destination-longitude" type="number" min="-180" max="180" step="any" value={newRequest.destination_longitude} onChange={(event) => updateField('destination_longitude', event.target.value)} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white" placeholder="77.5946" /></div>
              </div>
              <p className="text-[10px] text-slate-500">Only enter coordinates confirmed for this hospital destination; they are used by the radius filter.</p>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Blood Group Required *</label>
                  <select
                    value={newRequest.blood_group}
                    onChange={(e) => updateField('blood_group', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-blood-400 font-bold focus:outline-none"
                  >
                    {['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'].map(b => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Units Required (Min 1) *</label>
                  <input
                    type="number"
                    min="1"
                    max="50"
                    required
                    value={newRequest.units}
                    onChange={(e) => updateField('units', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Urgency Level *</label>
                  <select
                    value={newRequest.urgency}
                    onChange={(e) => updateField('urgency', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none"
                  >
                    <option value="EMERGENCY">EMERGENCY (Immediate Dispatch)</option>
                    <option value="HIGH">HIGH (Urgent Surgery)</option>
                    <option value="NORMAL">NORMAL (Elective Requisition)</option>
                  </select>
                </div>

                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Patient Name / Ward Details *</label>
                  <input
                    type="text"
                    required
                    value={newRequest.patient}
                    onChange={(e) => updateField('patient', e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none"
                    placeholder="e.g. ICU Ward Bed #4"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={closeRequestModal}
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 font-semibold disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-extrabold shadow-md glow-red disabled:opacity-50"
                >
                  {isSubmitting ? 'Saving request…' : 'Submit & Sync with Staff'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal - Hospital Profile & Contact Email Configuration */}
      {showProfileModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-950 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl relative">
            <button
              onClick={() => setShowProfileModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center space-x-2 text-blood-400 mb-2">
              <Building2 className="w-5 h-5" />
              <h3 className="text-xl font-black text-white">Hospital Notification Settings</h3>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              Configure the real contact email address that receives transactional Brevo alerts when donors accept emergency blood requests.
            </p>

            {profileStatus && (
              <div role="status" className={`rounded-xl border p-3 text-xs mb-4 ${
                profileStatus.type === 'error'
                  ? 'border-rose-800 bg-rose-950/50 text-rose-200'
                  : 'border-emerald-800 bg-emerald-950/50 text-emerald-200'
              }`}>
                {profileStatus.text}
              </div>
            )}

            <form onSubmit={handleSaveProfile} className="space-y-4 text-xs">
              <div>
                <label className="text-slate-400 block mb-1">Facility Login Identity (Immutable)</label>
                <input
                  type="text"
                  disabled
                  value={currentUser?.email || ''}
                  className="w-full bg-slate-900/60 border border-slate-800 rounded-xl px-3 py-2 text-slate-400 font-mono"
                />
                <span className="text-[10px] text-slate-500 mt-1 block">Dedicated system username format: taluk_hospital@haemopulse.in</span>
              </div>

              <div>
                <label className="text-slate-300 block mb-1 font-semibold">Official Notification Email (Real Inbox) *</label>
                <input
                  type="email"
                  required
                  value={profileForm.contact_email}
                  onChange={(e) => setProfileForm({ ...profileForm, contact_email: e.target.value })}
                  placeholder="e.g. staff_contact@hospital.org"
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-blood-500"
                />
                <span className="text-[10px] text-slate-400 mt-1 block">Brevo transactional alerts will only be delivered to this verified inbox, never to dummy @haemopulse.in identities.</span>
              </div>

              <div>
                <label className="text-slate-300 block mb-1 font-semibold">Hospital Emergency Contact Phone</label>
                <input
                  type="tel"
                  value={profileForm.contact_phone}
                  onChange={(e) => setProfileForm({ ...profileForm, contact_phone: e.target.value })}
                  placeholder="e.g. 08265-221234"
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-blood-500"
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowProfileModal(false)}
                  disabled={isSavingProfile}
                  className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 font-semibold disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSavingProfile}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-extrabold shadow-md glow-red disabled:opacity-50"
                >
                  {isSavingProfile ? 'Saving…' : 'Save Notification Settings'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal for Recording Completed Donation */}
      {showDonationModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4">
          <div role="dialog" aria-modal="true" className="w-full max-w-lg p-5 sm:p-6 rounded-2xl glass-panel border border-slate-800 space-y-4 shadow-2xl bg-slate-950">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <h3 className="text-lg font-extrabold text-white flex items-center space-x-2">
                <Award className="w-5 h-5 text-blood-400" />
                <span>Record Completed Blood Donation</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowDonationModal(false)}
                className="p-2 rounded-lg text-slate-300 hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {donationFormError && (
              <div className="p-3 rounded-xl bg-rose-950/80 border border-rose-800 text-rose-300 text-xs font-semibold">
                {donationFormError}
              </div>
            )}

            <form onSubmit={handleRecordDonation} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-300 block mb-1 font-semibold">Link to Requisition (Auto-Fulfill)</label>
                <select
                  value={donationForm.requisition_id}
                  onChange={(e) => {
                    const selectedId = e.target.value;
                    const matchingReq = pendingRequests.find(r => String(r.id) === String(selectedId));
                    if (matchingReq) {
                      const remaining = Math.max(1, (Number(matchingReq.units_needed || matchingReq.units) - Number(matchingReq.units_fulfilled || 0)));
                      setDonationForm(prev => ({
                        ...prev,
                        requisition_id: selectedId,
                        blood_group: matchingReq.blood_group || matchingReq.blood || prev.blood_group,
                        units: remaining,
                        notes: `Fulfillment donation for Requisition #${selectedId} (${matchingReq.patient_name || matchingReq.patient || 'Patient'})`
                      }));
                    } else {
                      setDonationForm(prev => ({ ...prev, requisition_id: selectedId }));
                    }
                  }}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none"
                >
                  <option value="">None (Standard Voluntary Facility Donation)</option>
                  {pendingRequests.map(r => (
                    <option key={r.id} value={r.id}>
                      Req #{r.id} — {r.patient_name || r.patient || 'Patient'} ({r.blood_group || r.blood}, {Math.max(1, (Number(r.units_needed || r.units) - Number(r.units_fulfilled || 0)))} unit(s) remaining)
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Donor Email *</label>
                  <input
                    type="email"
                    required
                    value={donationForm.donor_email}
                    onChange={(e) => setDonationForm({ ...donationForm, donor_email: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-blood-500"
                    placeholder="donor@example.com"
                  />
                </div>
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Donor Name (Optional)</label>
                  <input
                    type="text"
                    value={donationForm.donor_name}
                    onChange={(e) => setDonationForm({ ...donationForm, donor_name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-blood-500"
                    placeholder="Full Name"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Blood Group *</label>
                  <select
                    value={donationForm.blood_group}
                    onChange={(e) => setDonationForm({ ...donationForm, blood_group: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-blood-400 font-bold focus:outline-none"
                  >
                    {['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'].map(b => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Units (Min 1) *</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    required
                    value={donationForm.units}
                    onChange={(e) => setDonationForm({ ...donationForm, units: Number(e.target.value) })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Date of Donation *</label>
                  <input
                    type="date"
                    required
                    value={donationForm.donation_date}
                    onChange={(e) => setDonationForm({ ...donationForm, donation_date: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Donation Type</label>
                  <select
                    value={donationForm.donation_type}
                    onChange={(e) => setDonationForm({ ...donationForm, donation_type: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none"
                  >
                    <option value="Whole Blood">Whole Blood</option>
                    <option value="Platelets">Platelets</option>
                    <option value="Plasma">Plasma</option>
                    <option value="Red Blood Cells">Red Blood Cells</option>
                  </select>
                </div>
                <div>
                  <label className="text-slate-300 block mb-1 font-semibold">Appointment ID (Optional)</label>
                  <input
                    type="number"
                    value={donationForm.appointment_id}
                    onChange={(e) => setDonationForm({ ...donationForm, appointment_id: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none"
                    placeholder="e.g. 1"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-300 block mb-1 font-semibold">Clinical Screening Notes</label>
                <textarea
                  rows={2}
                  value={donationForm.notes}
                  onChange={(e) => setDonationForm({ ...donationForm, notes: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none"
                  placeholder="Hemoglobin check, vitals passed, no adverse reactions."
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowDonationModal(false)}
                  disabled={isSubmittingDonation}
                  className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 font-semibold disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingDonation}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-extrabold shadow-md glow-red disabled:opacity-50"
                >
                  {isSubmittingDonation ? 'Recording…' : 'Confirm & Generate Certificate'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
