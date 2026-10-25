import React, { useState, useEffect } from 'react';

import { getApiBaseUrl } from '../api/config';
const API_BASE = getApiBaseUrl();
import StatCard from '../components/StatCard';
import MLPredictionBadge from '../components/MLPredictionBadge';
import { getNextUpcomingAppointment } from '../utils/appointments';
import {
  Heart, CalendarCheck, Clock, Award, Bell, ShieldCheck,
  AlertCircle, PhoneCall, Building2, Send, CheckCircle, LogOut,
  UserPlus, LogIn, Mail, Phone, MapPin, Droplet, RefreshCw,
  User, CheckCircle2, XCircle, Calendar, ShieldAlert, X, Printer, FileCheck
} from 'lucide-react';

export default function DonorDashboard({
  currentUser,
  requestsList = [],
  onAuthSuccess,
  onLogout,
  onUserUpdate,
  onRefreshRequests,
  activeSubTab = 'donor_dashboard'
}) {
  const isLoggedIn = currentUser && currentUser.isLoggedIn;

  // Tabs for Auth: 'register' | 'login'
  const [authTab, setAuthTab] = useState('register');
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    phone: '',
    blood_group: 'O+',
    age: 25,
    gender: 'Male',
    location: '',
    district: '',
    taluk: '',
    consent_to_emergency_alerts: false,
    preferred_time: 'Morning'
  });

  const [loginData, setLoginData] = useState({
    email: '',
    password: ''
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [authMessage, setAuthMessage] = useState('');
  const [authError, setAuthError] = useState('');

  // Resend Verification State
  const [resendCooldown, setResendCooldown] = useState(0);
  const [resendStatus, setResendStatus] = useState('');
  const [resendStatusError, setResendStatusError] = useState(false);

  // Profile values start empty and are replaced only with a real backend response.
  const [donorDetails, setDonorDetails] = useState({
    name: currentUser?.name || '',
    email: currentUser?.email || '',
    phone: currentUser?.phone || '',
    age: currentUser?.age ?? null,
    gender: currentUser?.gender || '',
    blood_group: currentUser?.blood_group || currentUser?.blood || '',
    location: currentUser?.location || '',
    district: currentUser?.district || '',
    taluk: currentUser?.taluk || '',
    preferred_time: currentUser?.preferred_time || '',
    is_available: currentUser?.is_available ?? false,
    total_donations: null,
    last_donation_days: null,
    last_donation_date: null,
    availability_score: null,
    availability_status: null
  });
  const isVerified = Boolean(currentUser?.is_verified || donorDetails?.is_verified);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileLoadError, setProfileLoadError] = useState('');
  const [locations, setLocations] = useState({ districts: [], taluks_by_district: {} });

  // Edit Profile Form State
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [profileForm, setProfileForm] = useState({ ...donorDetails });
  const [profileMsg, setProfileMsg] = useState('');

  // Lists come from persisted API responses; no example appointment/donation is injected.
  const [appointments, setAppointments] = useState([]);
  const [newAppDate, setNewAppDate] = useState('');
  const [newAppSlot, setNewAppSlot] = useState('Morning (8 AM - 12 PM)');
  const [newAppCenter, setNewAppCenter] = useState('');
  const [appMsg, setAppMsg] = useState('');
  const [donationHistory, setDonationHistory] = useState([]);
  const [selectedCertificate, setSelectedCertificate] = useState(null);
  const [showCertModal, setShowCertModal] = useState(false);

  const [respondedAlerts, setRespondedAlerts] = useState({});
  const [availabilityPrediction, setAvailabilityPrediction] = useState({ status: 'idle', data: null, message: '' });
  const [appointmentError, setAppointmentError] = useState('');
  const [requestActionBusy, setRequestActionBusy] = useState({});
  const [requestActionMessages, setRequestActionMessages] = useState({});
  const [requestActionNotice, setRequestActionNotice] = useState('');

  // Shared district/taluk catalog used by registration.
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/locations`)
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Location catalogue is unavailable.');
        return data;
      })
      .then((data) => { if (!cancelled) setLocations(data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  // Fetch the authenticated donor's own profile. Failure is surfaced instead of displaying defaults.
  useEffect(() => {
    let cancelled = false;
    if (!(isLoggedIn && currentUser?.token)) {
      setDonorDetails({ name: '', email: '', phone: '', age: null, gender: '', blood_group: '', location: '', district: '', taluk: '', preferred_time: '', is_available: false, total_donations: null, last_donation_days: null, last_donation_date: null, availability_score: null, availability_status: null });
      setAppointments([]);
      setDonationHistory([]);
      setAvailabilityPrediction({ status: 'idle', data: null, message: '' });
      setAppointmentError('');
      setProfileLoadError('');
      return () => { cancelled = true; };
    }
    setProfileLoading(true);
    setProfileLoadError('');
    setAppointments([]);
    setDonationHistory([]);
    setAppointmentError('');
    fetch(`${API_BASE}/api/v1/donors/me`, { headers: { Authorization: `Bearer ${currentUser.token}` } })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || `Profile request failed (HTTP ${response.status}).`);
        if (!data?.donor) throw new Error('The API did not return a donor profile for this account.');
        return data;
      })
      .then((data) => {
        if (cancelled) return;
        const details = { ...data.donor, ...(data.stats || {}), ...(data.user || {}), is_available: data.stats?.is_available ?? Boolean(data.donor.is_available) };
        setDonorDetails(details);
        if (data.user?.is_verified && !currentUser?.is_verified && onUserUpdate) {
          onUserUpdate({ ...currentUser, is_verified: true });
        }
        setProfileForm(details);
        setDonationHistory(Array.isArray(data.donations) ? data.donations : []);
        // Fetch verified donation records from dedicated history endpoint
        fetch(`${API_BASE}/api/v1/donations/my-history`, { headers: { Authorization: `Bearer ${currentUser.token}` } })
          .then(res => res.ok ? res.json() : null)
          .then(hist => {
            if (hist && Array.isArray(hist.records) && hist.records.length > 0) {
              setDonationHistory(hist.records);
            }
          })
          .catch(() => {});
        setAppointments((Array.isArray(data.appointments) ? data.appointments : []).slice().sort((a, b) => { const active = (v) => ['SCHEDULED', 'PENDING'].includes(String(v.status || '').toUpperCase()) ? 0 : 1; return active(a) - active(b) || String(a.appointment_date || a.date || '').localeCompare(String(b.appointment_date || b.date || '')); }));
        setAppointmentError('');
        setAvailabilityPrediction({ status: 'loading', data: null, message: '' });
        fetch(`${API_BASE}/api/v1/donors/me/availability-score`, { headers: { Authorization: `Bearer ${currentUser.token}` } })
          .then(async (response) => { const result = await response.json().catch(() => ({})); if (!response.ok) throw new Error(result.detail || 'Availability prediction is unavailable.'); return result; })
          .then((result) => { if (cancelled) return; setAvailabilityPrediction(result.eligible ? { status: 'success', data: result, message: '' } : { status: 'ineligible', data: result, message: result.completed_donations == null ? (result.message || 'Verified donation history is not recorded yet.') : `${result.message || 'Your personalized availability score is not available yet.'} (${result.completed_donations} verified completed donations recorded.)` }); })
          .catch((error) => { if (!cancelled) setAvailabilityPrediction({ status: 'error', data: null, message: error.message || 'Availability prediction is currently unavailable.' }); });
      })
      .catch((error) => { if (!cancelled) { setProfileLoadError(error.message || 'Unable to retrieve your profile.'); setAppointmentError(error.message || 'Unable to retrieve appointments.'); setAvailabilityPrediction({ status: 'error', data: null, message: 'Donor information could not be verified for an availability prediction.' }); } })
      .finally(() => { if (!cancelled) setProfileLoading(false); });
    return () => { cancelled = true; };
  }, [isLoggedIn, currentUser?.token, currentUser?.id]);

  // Resend cooldown timer countdown
  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);

  // Eligibility calculation: Male = 90 days, Female = 120 days
  const requiredGap = (donorDetails.gender || 'Male').toLowerCase() === 'female' ? 120 : 90;
  const daysSinceLast = donorDetails.last_donation_days == null ? null : Number(donorDetails.last_donation_days);
  const hasDonationInterval = Number.isFinite(daysSinceLast);
  const isEligible = hasDonationInterval && daysSinceLast >= requiredGap;
  const daysRemaining = hasDonationInterval ? Math.max(0, requiredGap - daysSinceLast) : null;

  const nextAppointment = getNextUpcomingAppointment(appointments);

  // Next eligible date calculation
  const nextEligibleDate = new Date();
  if (!isEligible && daysRemaining !== null) nextEligibleDate.setDate(nextEligibleDate.getDate() + daysRemaining);

  // Toggle availability only after the backend confirms persistence.
  const handleToggleAvailability = async () => {
    if (!currentUser?.token) return;
    const nextVal = !donorDetails.is_available;
    setProfileMsg('');
    try {
      const response = await fetch(`${API_BASE}/api/v1/donors/me/availability`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${currentUser.token}` },
        body: JSON.stringify({ is_available: nextVal })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Availability update failed (HTTP ${response.status}).`);
      setDonorDetails((previous) => ({ ...previous, is_available: Boolean(data.is_available) }));
      setProfileMsg(data.message || 'Availability setting was saved.');
    } catch (error) {
      setProfileMsg(error.message || 'Availability could not be saved.');
    }
  };

  // Profile edits are accepted only after a successful backend response.
  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    setProfileMsg('');
    if (!currentUser?.token) { setProfileMsg('Sign in again before editing your profile.'); return; }
    try {
      const response = await fetch(`${API_BASE}/api/v1/donors/me/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${currentUser.token}` },
        body: JSON.stringify(profileForm)
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Profile update failed (HTTP ${response.status}).`);
      const refreshed = { ...donorDetails, ...(data.donor || profileForm) };
      setDonorDetails(refreshed);
      setProfileForm(refreshed);
      setIsEditingProfile(false);
      setProfileMsg(data.message || 'Profile updated successfully.');
      if (onUserUpdate) onUserUpdate({ ...currentUser, ...refreshed });
    } catch (error) {
      setProfileMsg(error.message || 'Profile update failed.');
    }
  };

  // Appointment booking uses the authenticated donor identity on the backend.
  const handleBookAppointment = async (e) => {
    e.preventDefault();
    setAppMsg('');
    if (!isVerified) { setAppMsg('Please verify your email address to unlock appointment booking.'); return; }
    if (!newAppDate) { setAppMsg('Please select an appointment date.'); return; }
    if (!currentUser?.token) { setAppMsg('Please sign in before booking an appointment.'); return; }
    try {
      const response = await fetch(`${API_BASE}/api/v1/appointments`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${currentUser.token}` },
        body: JSON.stringify({ appointment_date: newAppDate, time_slot: newAppSlot, center_name: newAppCenter || 'Central Blood Bank Hub #1' })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Appointment booking failed (HTTP ${response.status}).`);
      setAppMsg(data.message || 'Appointment saved successfully.');
      setNewAppDate('');
      setAppointmentError('');
      try {
        const profileResponse = await fetch(`${API_BASE}/api/v1/donors/me`, { headers: { Authorization: `Bearer ${currentUser.token}` } });
        const profileData = await profileResponse.json().catch(() => ({}));
        if (!profileResponse.ok) throw new Error(profileData.detail || 'Appointment list refresh failed.');
        setAppointments((Array.isArray(profileData.appointments) ? profileData.appointments : []).slice().sort((a, b) => { const active = (v) => ['SCHEDULED', 'PENDING'].includes(String(v.status || '').toUpperCase()) ? 0 : 1; return active(a) - active(b) || String(a.appointment_date || a.date || '').localeCompare(String(b.appointment_date || b.date || '')); }));
        setAppointmentError('');
      } catch {
        setAppointmentError('Your appointment was saved, but the list could not be refreshed. Reload the dashboard to view it.');
      }
    } catch (error) { setAppMsg(error.message || 'Appointment could not be saved.'); }
  };

  // Handle Resend Verification Email
  const handleResendEmail = async () => {
    if (resendCooldown > 0) return;
    setResendStatus('Requesting verification email...');
    setResendStatusError(false);

    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/resend-verification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: donorDetails.email })
      });
      const data = await res.json();
      if (res.ok) {
        if (data.success && data.delivery?.sent) {
          setResendCooldown(60);
          setResendStatus(data.message || `Verification email delivered to ${donorDetails.email}. Please check your inbox or spam folder.`);
          setResendStatusError(false);
        } else {
          setResendCooldown(30);
          const errMsg = data.delivery?.error || data.message || 'Verification email delivery failed. Please check backend SMTP configuration.';
          setResendStatus(errMsg);
          setResendStatusError(true);
        }
      } else if (res.status === 429) {
        setResendStatus(data.detail || 'Rate limit: Please wait for the cooldown timer before requesting another email.');
        setResendStatusError(true);
      } else {
        setResendStatus(data.detail || data.message || 'Could not send verification email right now.');
        setResendStatusError(true);
      }
    } catch (e) {
      setResendStatus('Could not reach the backend. Verification email delivery was not confirmed.');
      setResendStatusError(true);
    }
  };

  // Filter Matching Emergency Requests
  const emergencyRequestsForGroup = requestsList.filter(
    r => (r.blood_group || r.blood) === donorDetails.blood_group
  );
  const quickEmergencyRequest = emergencyRequestsForGroup[0] || null;
  const quickEmergencyRequestId = quickEmergencyRequest?.id ?? quickEmergencyRequest?._id;
  const quickHasRequestId = quickEmergencyRequestId !== undefined
    && quickEmergencyRequestId !== null && String(quickEmergencyRequestId).trim() !== '';
  const quickEmergencyResponse = quickEmergencyRequest?.donor_response || respondedAlerts[quickEmergencyRequestId];

  const hospitalsList = [
    { name: 'City General Hospital (Emergency Cell)', phone: '+1-800-555-0101', address: '100 Healthcare Blvd, Suite 400', contactPerson: 'Dr. Alice Smith' },
    { name: 'St. Jude Emergency Center (Trauma Desk)', phone: '+1-800-555-0102', address: '450 Trauma Way, East Wing', contactPerson: 'Dr. Mark Johnson' }
  ];

  const handleEmergencyResponse = async (requestId, action) => {
    if (!requestId || !currentUser?.token || !isVerified || requestActionBusy[requestId]
      || respondedAlerts[requestId]) return;
    setRequestActionBusy((previous) => ({ ...previous, [requestId]: true }));
    setRequestActionMessages((previous) => ({ ...previous, [requestId]: '' }));
    setRequestActionNotice('');
    try {
      const response = await fetch(`${API_BASE}/api/v1/requests/${requestId}/response`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${currentUser.token}` },
        body: JSON.stringify({ action })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = new Error(data.detail || `Could not ${action.toLowerCase()} this request.`);
        error.status = response.status;
        throw error;
      }
      const confirmedResponse = String(data.response || '').trim().toUpperCase();
      if (data.success !== true || !['ACCEPTED', 'REJECTED'].includes(confirmedResponse)) {
        throw new Error('The backend did not confirm the emergency response. Refresh the request list and try again.');
      }
      setRespondedAlerts((previous) => ({ ...previous, [requestId]: confirmedResponse }));
      setRequestActionMessages((previous) => ({ ...previous, [requestId]: data.message || `Your ${action.toLowerCase()} response was recorded.` }));
      // The API response is authoritative; refresh so persisted per-donor state is reloaded.
      if (onRefreshRequests) {
        try {
          await onRefreshRequests();
        } catch {
          setRequestActionNotice('Your response was saved, but the request list could not be refreshed. Reload the Donor Page to confirm the latest state.');
        }
      }
    } catch (error) {
      setRequestActionMessages((previous) => ({ ...previous, [requestId]: error.message || 'Your response could not be saved. Refresh the request list and try again.' }));
      // A 409 can mean the request changed or a response already exists. Reload server state.
      let requestsRefreshed = false;
      if (onRefreshRequests) {
        try { await onRefreshRequests(); requestsRefreshed = true; } catch { /* Keep the original action error visible. */ }
      }
      if (error.status === 409) {
        setRequestActionNotice(requestsRefreshed
          ? 'This request changed or a response was already recorded. The emergency request list has been refreshed.'
          : 'This request changed or a response was already recorded, but the request list could not be refreshed. Reload the Donor Page.');
      }
    } finally {
      setRequestActionBusy((previous) => ({ ...previous, [requestId]: false }));
    }
  };

  // Auth Submit Handlers
  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setAuthMessage('');
    setAuthError('');

    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      const data = await res.json();

      if (!res.ok) {
        setAuthError(data.detail || 'Registration failed. Please try again.');
        setIsSubmitting(false);
        return;
      }

      const mailStatus = data.email_delivery?.delivery_status || 'UNKNOWN';
      setAuthMessage(mailStatus === 'DELIVERED' ? `Verification email was delivered to ${formData.email}.` : `Registration saved. Verification email status: ${mailStatus}. Configure SMTP to deliver verification emails.`);

      const sessionUser = {
        id: data.user?.id || data.donor?.user_id || data.user?.donor_id,
        name: formData.name,
        email: formData.email,
        phone: formData.phone,
        blood: formData.blood_group,
        blood_group: formData.blood_group,
        location: formData.location,
        preferred_time: formData.preferred_time,
        age: formData.age,
        gender: formData.gender,
        role: 'DONOR',
        is_verified: Boolean(data.user?.is_verified),
        isLoggedIn: true,
        token: data.token
      };

      setTimeout(() => {
        if (onAuthSuccess) onAuthSuccess(sessionUser);
      }, 800);
    } catch (err) {
      setAuthError('Could not reach backend service. Ensure server.py is running.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setAuthMessage('');
    setAuthError('');

    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginData)
      });
      const data = await res.json();

      if (!res.ok) {
        setAuthError(data.detail || 'Invalid email or password.');
        setIsSubmitting(false);
        return;
      }

      const role = data.user?.role === 'ROLE_ADMIN' ? 'ADMIN' :
                   data.user?.role === 'ROLE_HOSPITAL' ? 'HOSPITAL' :
                   data.user?.role === 'ROLE_STAFF' ? 'STAFF' : 'DONOR';

      const sessionUser = {
        ...data.user,
        role,
        isLoggedIn: true,
        token: data.token,
        is_verified: Boolean(data.user.is_verified)
      };

      setAuthMessage('Login verified! Redirecting to dashboard...');
      setTimeout(() => {
        if (onAuthSuccess) onAuthSuccess(sessionUser);
      }, 500);
    } catch (err) {
      setAuthError('Connection error. Please ensure the backend is running.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ==========================================
  // VIEW 1: UNLOGGED-IN DONOR AUTH FORM
  // ==========================================
  if (!isLoggedIn) {
    return (
      <div className="max-w-2xl mx-auto py-6 space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blood-950/80 border border-blood-800 text-blood-400 text-xs font-bold">
            <Droplet className="w-4 h-4 text-blood-500 fill-blood-500 animate-pulse" />
            <span>Donor Authentication Portal</span>
          </div>
          <h2 className="text-3xl font-black text-white tracking-tight">Access Your Donor Dashboard</h2>
          <p className="text-xs text-slate-400">Log in or register to access donation metrics, manage appointments, and respond to hospital emergencies.</p>
        </div>

        <div className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-6 shadow-2xl">
          <div className="flex rounded-xl bg-slate-900 p-1 border border-slate-800">
            <button
              onClick={() => { setAuthTab('register'); setAuthError(''); setAuthMessage(''); }}
              className={`flex-1 py-2.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center space-x-2 ${
                authTab === 'register'
                  ? 'bg-gradient-to-r from-blood-600 to-blood-700 text-white shadow-md'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <UserPlus className="w-4 h-4" />
              <span>New Donor Registration</span>
            </button>
            <button
              onClick={() => { setAuthTab('login'); setAuthError(''); setAuthMessage(''); }}
              className={`flex-1 py-2.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center space-x-2 ${
                authTab === 'login'
                  ? 'bg-gradient-to-r from-blood-600 to-blood-700 text-white shadow-md'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <LogIn className="w-4 h-4" />
              <span>Donor Account Login</span>
            </button>
          </div>

          {authMessage && (
            <div className="p-3 rounded-xl bg-emerald-950/80 border border-emerald-800 text-emerald-300 text-xs font-semibold text-center flex items-center justify-center space-x-2 animate-pulse">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>{authMessage}</span>
            </div>
          )}

          {authError && (
            <div className="p-3 rounded-xl bg-rose-950/80 border border-rose-800 text-rose-300 text-xs font-semibold text-center flex items-center justify-center space-x-2">
              <XCircle className="w-4 h-4 text-rose-400" />
              <span>{authError}</span>
            </div>
          )}

          {/* Registration Form */}
          {authTab === 'register' && (
            <form onSubmit={handleRegisterSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Full Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Alex Johnson"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-blood-500"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Email Address (for Verification) *</label>
                  <input
                    type="email"
                    required
                    placeholder="alex@email.com"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-blood-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Account Password *</label>
                  <input
                    type="password"
                    required
                    placeholder="••••••••"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-blood-500"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Contact Phone Number *</label>
                  <input
                    type="tel"
                    required
                    placeholder="+91 98765 43210"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-blood-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Blood Group</label>
                  <select
                    value={formData.blood_group}
                    onChange={(e) => setFormData({ ...formData, blood_group: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-blood-400 font-bold focus:outline-none"
                  >
                    {['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'].map(b => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Age (18-65)</label>
                  <input
                    type="number"
                    min="18" max="65"
                    value={formData.age}
                    onChange={(e) => setFormData({ ...formData, age: parseInt(e.target.value) || 18 })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-white focus:outline-none text-center"
                  />
                </div>

                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Gender</label>
                  <select
                    value={formData.gender}
                    onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-white focus:outline-none"
                  >
                    <option value="Male">Male (90d gap)</option>
                    <option value="Female">Female (120d gap)</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Locality / Nearby Area *</label>
                  <input
                    type="text"
                    required
                    minLength={2}
                    maxLength={160}
                    placeholder="e.g. Anekal town — not a precise home address"
                    value={formData.location}
                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Preferred Donation Time</label>
                  <select
                    value={formData.preferred_time}
                    onChange={(e) => setFormData({ ...formData, preferred_time: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:outline-none"
                  >
                    <option value="Morning">Morning (8 AM - 12 PM)</option>
                    <option value="Afternoon">Afternoon (12 PM - 4 PM)</option>
                    <option value="Evening">Evening (4 PM - 8 PM)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block" htmlFor="donor-register-district">District</label>
                  <select id="donor-register-district" value={formData.district} onChange={(event) => setFormData({ ...formData, district: event.target.value, taluk: '' })} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white" required>
                    <option value="">Select district</option>{locations.districts.map((district) => <option key={district} value={district}>{district}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block" htmlFor="donor-register-taluk">Taluk</label>
                  <select id="donor-register-taluk" value={formData.taluk} disabled={!formData.district} onChange={(event) => setFormData({ ...formData, taluk: event.target.value })} className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white disabled:opacity-50" required>
                    <option value="">Select taluk</option>{(locations.taluks_by_district?.[formData.district] || []).map((taluk) => <option key={taluk} value={taluk}>{taluk}</option>)}
                  </select>
                </div>
              </div>
              <label className="flex items-start gap-2 text-xs text-slate-300">
                <input type="checkbox" checked={formData.consent_to_emergency_alerts} onChange={(event) => setFormData({ ...formData, consent_to_emergency_alerts: event.target.checked })} className="mt-0.5 accent-red-600" />
                <span>I consent to receiving emergency blood donation email alerts. This is optional and can be withheld.</span>
              </label>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-extrabold text-xs shadow-lg glow-red transition-all flex items-center justify-center space-x-2 mt-4"
              >
                <UserPlus className="w-4 h-4" />
                <span>{isSubmitting ? 'Creating donor account…' : 'Register & Enter Dashboard'}</span>
              </button>
            </form>
          )}

          {/* Login Form */}
          {authTab === 'login' && (
            <form onSubmit={handleLoginSubmit} className="space-y-4 text-xs">
              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Email Address</label>
                <input
                  type="email"
                  required
                  placeholder="your.email@example.com"
                  value={loginData.email}
                  onChange={(e) => setLoginData({ ...loginData, email: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-blood-500"
                />
              </div>

              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Password</label>
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={loginData.password}
                  onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-blood-500"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-extrabold text-xs shadow-lg glow-red transition-all flex items-center justify-center space-x-2 mt-4"
              >
                <LogIn className="w-4 h-4" />
                <span>{isSubmitting ? 'Authenticating...' : 'Sign In to Donor Portal'}</span>
              </button>
            </form>
          )}

        </div>
      </div>
    );
  }

  // ==========================================
  // VIEW 2: LOGGED-IN DONOR DASHBOARD
  // ==========================================
  return (
    <div className="space-y-6">
      {profileLoading && <div role="status" className="p-3 rounded-xl bg-slate-900 border border-slate-700 text-slate-300 text-xs">Loading your persisted donor profile…</div>}
      {profileLoadError && <div role="alert" className="p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-200 text-xs">{profileLoadError}</div>}

      {/* PENDING EMAIL VERIFICATION BANNER */}
      {!isVerified && (
        <div className="p-4 rounded-2xl bg-amber-950/60 border border-amber-800/80 text-amber-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg">
          <div className="flex items-center space-x-3">
            <ShieldAlert className="w-6 h-6 text-amber-400 flex-shrink-0 animate-bounce" />
            <div>
              <p className="text-xs font-bold text-amber-100">Please verify your email to unlock all features.</p>
              <p className="text-[11px] text-amber-300">
                Verification status for <strong className="text-white">{donorDetails.email}</strong> is pending. Appointment booking remains restricted until verified.
              </p>
              {resendStatus && (
                <p role="status" className={`text-[10px] mt-1 font-semibold ${resendStatusError ? 'text-amber-300' : 'text-emerald-400'}`}>{resendStatus}</p>
              )}
            </div>
          </div>

          <button
            onClick={handleResendEmail}
            disabled={resendCooldown > 0}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all whitespace-nowrap flex items-center space-x-1.5 ${
              resendCooldown > 0
                ? 'bg-slate-800 text-slate-400 cursor-not-allowed border border-slate-700'
                : 'bg-amber-600 hover:bg-amber-500 text-white shadow-md'
            }`}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${resendCooldown > 0 ? 'animate-spin' : ''}`} />
            <span>{resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend Verification Email'}</span>
          </button>
        </div>
      )}

      {/* WELCOME HEADER WITH BADGES & LOGOUT */}
      <div className="p-6 rounded-2xl glass-panel bg-gradient-to-r from-slate-900 via-slate-900 to-blood-950/50 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blood-700 to-blood-500 flex items-center justify-center text-white font-black text-xl shadow-lg glow-red">
            {donorDetails.blood_group}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-2xl font-black text-white">{donorDetails.name}</h2>
              <span className="px-2 py-0.5 rounded text-xs bg-slate-800 text-blood-400 font-mono font-bold">
                {donorDetails.donor_id || donorDetails.id || 'Donor ID unavailable'}
              </span>

              {/* VERIFICATION BADGE */}
              {isVerified ? (
                <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-950 text-emerald-400 border border-emerald-800">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>Verified</span>
                </span>
              ) : (
                <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-950 text-amber-400 border border-amber-800 animate-pulse">
                  <AlertCircle className="w-3 h-3" />
                  <span>Pending Verification</span>
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 flex items-center space-x-2 mt-1">
              <span>{donorDetails.email}</span>
              <span>&bull;</span>
              <span>{donorDetails.location}</span>
              <span>&bull;</span>
              {donorDetails.health_score != null && <span>Health Score: {donorDetails.health_score}/100</span>}
            </p>
          </div>
        </div>

        {/* AVAILABILITY TOGGLE & LOGOUT */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 bg-slate-900/90 p-1.5 px-3 rounded-xl border border-slate-800 text-xs">
            <span className="text-slate-400 font-semibold text-[11px]">Availability:</span>
            <button
              onClick={handleToggleAvailability}
              className={`px-3 py-1 rounded-lg font-bold text-xs transition-all flex items-center space-x-1.5 ${
                donorDetails.is_available
                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                  : 'bg-rose-950 text-rose-300 border border-rose-800'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${donorDetails.is_available ? 'bg-emerald-400' : 'bg-rose-400'}`} />
              <span>{donorDetails.is_available ? 'Available' : 'Not Available'}</span>
            </button>
          </div>

          {availabilityPrediction.status === 'success' ? <MLPredictionBadge category={availabilityPrediction.data.availability_status} score={availabilityPrediction.data.availability_score} /> : <span className="text-xs text-slate-400">{availabilityPrediction.status === 'loading' ? 'Calculating availability…' : availabilityPrediction.status === 'error' ? 'Availability score unavailable' : availabilityPrediction.status === 'ineligible' ? 'Personalized score not available yet' : 'Availability score not calculated'}</span>}

          {onLogout && (
            <button
              onClick={onLogout}
              className="px-3.5 py-2 rounded-xl bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800 font-bold text-xs shadow-md flex items-center space-x-1.5 transition-all"
            >
              <LogOut className="w-3.5 h-3.5 text-rose-400" />
              <span>Log Out</span>
            </button>
          )}
        </div>
      </div>

      {/* STAT CARDS: Last Donation, Total Donations, Eligibility, Availability Score */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Last Donation Date"
          value={donorDetails.last_donation_date || 'Not recorded'}
          subtitle={daysSinceLast == null ? 'Donation interval not available' : `${daysSinceLast} days ago`}
          icon={Clock}
          color="blood"
        />
        <StatCard
          title="Total Blood Donations"
          value={`${donorDetails.total_donations ?? donationHistory.length} Times`}
          subtitle={donorDetails.total_donations == null ? "No verified donation total is recorded" : "Recorded donation total"}
          icon={Heart}
          color="emerald"
        />
        <StatCard
          title="Donation Interval Status"
          value={daysSinceLast == null ? 'Interval Unrecorded' : isEligible ? 'Interval Satisfied' : 'Recovery Period'}
          subtitle={
            isEligible
              ? `${requiredGap}-day gap met; subject to on-site clinical & Hb screening`
              : daysRemaining == null ? 'Donation history not recorded' : `Interval active: ${daysRemaining} days remaining (${nextEligibleDate.toISOString().slice(0, 10)})`
          }
          icon={CalendarCheck}
          color={isEligible ? 'emerald' : 'amber'}
        />
        <StatCard
          title="My Availability Score"
          value={availabilityPrediction.status === 'success' ? `${availabilityPrediction.data.availability_score}%` : '—'}
          subtitle={availabilityPrediction.status === 'success' ? `${availabilityPrediction.data.availability_status} Availability Tier` : availabilityPrediction.message || (availabilityPrediction.status === 'loading' ? 'Requesting the ML service…' : 'Personalized score requires 3 verified completed donations')}
          icon={Award}
          color="blue"
        />
      </div>

      {/* SUBTAB 1 / MAIN DASHBOARD VIEW */}
      {(activeSubTab === 'donor_dashboard' || activeSubTab === 'dashboard') && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Quick Appointments Overview */}
          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Calendar className="w-4 h-4 text-blood-400" />
                <span>My Next Scheduled Appointment</span>
              </h3>
            </div>
            {profileLoading ? (
              <p className="text-xs text-slate-500">Loading your appointments…</p>
            ) : appointmentError ? (
              <p className="text-xs text-rose-300" role="alert">{appointmentError}</p>
            ) : nextAppointment ? (
              <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-white text-sm">{nextAppointment.appointment_date || nextAppointment.date}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold">
                    {nextAppointment.status}
                  </span>
                </div>
                <p className="text-slate-400">{nextAppointment.time_slot || 'Time not recorded'} &bull; {nextAppointment.center_name || 'Donation center not recorded'}</p>
              </div>
            ) : (
              <p className="text-xs text-slate-500">You have no upcoming scheduled appointments.</p>
            )}
          </div>

          {/* Quick Hospital Requisitions Feed */}
          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Bell className="w-4 h-4 text-blood-400 animate-bounce" />
                <span>Emergency Requests for {donorDetails.blood_group}</span>
              </h3>
              <span className="px-2 py-0.5 rounded text-[10px] bg-blood-950 text-blood-400 border border-blood-800 font-bold">
                {emergencyRequestsForGroup.length} Live
              </span>
            </div>
            {quickEmergencyRequest ? (
              <div className="p-3.5 rounded-xl bg-blood-950/40 border border-blood-800/80 space-y-2 text-xs">
                <div className="flex items-center justify-between font-bold text-white">
                  <span>{quickEmergencyRequest.hospital_name || quickEmergencyRequest.hospital}</span>
                  <span className="text-blood-400 font-mono">{quickEmergencyRequest.urgency_level || quickEmergencyRequest.urgency}</span>
                </div>
                <p className="text-slate-300">
                  Needs {quickEmergencyRequest.units_needed || quickEmergencyRequest.units} units of {donorDetails.blood_group}.
                </p>
                {requestActionNotice && <p className="text-xs text-amber-300" role="status">{requestActionNotice}</p>}
                {requestActionMessages[quickEmergencyRequestId] && <p className="text-xs text-slate-300" role="status">{requestActionMessages[quickEmergencyRequestId]}</p>}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  {quickEmergencyResponse ? (
                    <span className={`px-2 py-1 rounded-lg text-[10px] font-bold border ${quickEmergencyResponse === 'ACCEPTED' ? 'bg-emerald-950 text-emerald-300 border-emerald-800' : 'bg-slate-900 text-slate-300 border-slate-700'}`}>Response: {quickEmergencyResponse}</span>
                  ) : (
                    <>
                      <button onClick={() => handleEmergencyResponse(quickEmergencyRequestId, 'ACCEPT')} disabled={!quickHasRequestId || !isVerified || Boolean(requestActionBusy[quickEmergencyRequestId])} className="px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-700 hover:bg-emerald-600 text-white disabled:opacity-50">{requestActionBusy[quickEmergencyRequestId] ? 'Saving…' : 'Accept'}</button>
                      <button onClick={() => handleEmergencyResponse(quickEmergencyRequestId, 'REJECT')} disabled={!quickHasRequestId || !isVerified || Boolean(requestActionBusy[quickEmergencyRequestId])} className="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-600 disabled:opacity-50">Reject</button>
                      {!isVerified && <span className="text-xs text-amber-300">Verify email to respond</span>}
                      {!quickHasRequestId && <span className="text-xs text-amber-300">Request ID unavailable; actions disabled</span>}
                    </>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500">No emergency blood requests matching your group right now.</p>
            )}
          </div>
        </div>
      )}

      {/* SUBTAB 2: MY PROFILE (VIEW & EDIT) */}
      {(activeSubTab === 'donor_profile') && (
        <div className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <div>
              <h3 className="text-base font-bold text-white flex items-center space-x-2">
                <User className="w-4 h-4 text-blood-400" />
                <span>My Donor Profile</span>
              </h3>
              <p className="text-xs text-slate-400">View and update your personal information and donation preferences.</p>
            </div>
            <button
              onClick={() => setIsEditingProfile(!isEditingProfile)}
              className="px-4 py-2 rounded-xl bg-blood-600 hover:bg-blood-500 text-white text-xs font-bold"
            >
              {isEditingProfile ? 'Cancel' : 'Edit Profile'}
            </button>
          </div>

          {profileMsg && (
            <div className="p-3 rounded-xl bg-emerald-950/80 border border-emerald-800 text-emerald-300 text-xs font-bold text-center">
              {profileMsg}
            </div>
          )}

          {!isEditingProfile ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                <span className="text-slate-500 font-semibold block">Full Name</span>
                <span className="text-white font-bold text-sm">{donorDetails.name}</span>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                <span className="text-slate-500 font-semibold block">Email Address</span>
                <span className="text-white font-bold text-sm">{donorDetails.email}</span>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                <span className="text-slate-500 font-semibold block">Phone Number</span>
                <span className="text-white font-bold text-sm">{donorDetails.phone}</span>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                <span className="text-slate-500 font-semibold block">Blood Group</span>
                <span className="text-blood-400 font-black text-sm">{donorDetails.blood_group}</span>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                <span className="text-slate-500 font-semibold block">Age & Gender</span>
                <span className="text-white font-bold text-sm">{donorDetails.age ?? 'Age not recorded'}{donorDetails.age == null ? '' : ' years'} &bull; {donorDetails.gender || 'Gender not recorded'}</span>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                <span className="text-slate-500 font-semibold block">Locality / Nearby Area</span>
                <span className="text-white font-bold text-sm">{donorDetails.location || 'Not recorded'}</span>
                <span className="text-slate-400 block">{[donorDetails.district, donorDetails.taluk].filter(Boolean).join(', ')}</span>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1 md:col-span-2">
                <span className="text-slate-500 font-semibold block">Preferred Donation Time</span>
                <span className="text-white font-bold text-sm">{donorDetails.preferred_time || 'Not recorded'}</span>
              </div>
            </div>
          ) : (
            <form onSubmit={handleProfileSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Full Name</label>
                  <input
                    type="text"
                    value={profileForm.name}
                    onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Phone Number</label>
                  <input
                    type="tel"
                    value={profileForm.phone}
                    onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Blood Group</label>
                  <select
                    value={profileForm.blood_group}
                    onChange={(e) => setProfileForm({ ...profileForm, blood_group: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-blood-400 font-bold"
                  >
                    {['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'].map(b => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Age</label>
                  <input
                    type="number"
                    min="18" max="65"
                    value={profileForm.age}
                    onChange={(e) => setProfileForm({ ...profileForm, age: parseInt(e.target.value) || 18 })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white text-center"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Gender</label>
                  <select
                    value={profileForm.gender}
                    onChange={(e) => setProfileForm({ ...profileForm, gender: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Locality / Nearby Area</label>
                  <input
                    type="text"
                    maxLength={160}
                    value={profileForm.location || ''}
                    onChange={(e) => setProfileForm({ ...profileForm, location: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                    placeholder="Town or nearby area; avoid a precise home address"
                  />
                </div>
                <div>
                  <label className="text-slate-300 font-semibold mb-1 block">Preferred Donation Time</label>
                  <select
                    value={profileForm.preferred_time}
                    onChange={(e) => setProfileForm({ ...profileForm, preferred_time: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  >
                    <option value="Morning">Morning (8 AM - 12 PM)</option>
                    <option value="Afternoon">Afternoon (12 PM - 4 PM)</option>
                    <option value="Evening">Evening (4 PM - 8 PM)</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                className="px-5 py-2.5 rounded-xl bg-blood-600 hover:bg-blood-500 text-white font-bold"
              >
                Save Profile Changes
              </button>
            </form>
          )}
        </div>
      )}

      {/* SUBTAB 3: DONATION HISTORY */}
      {(activeSubTab === 'donor_history') && (
        <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div>
              <h3 className="text-sm font-bold text-white">Verified Donation History</h3>
              <p className="text-xs text-slate-400">Past blood donations recorded and verified in the database.</p>
            </div>
            <span className="px-2.5 py-1 rounded-lg text-xs bg-blood-950 text-blood-400 border border-blood-800 font-extrabold">
              {donationHistory.length} Recorded Donations
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Donation Code</th>
                  <th className="py-2.5 px-3">Date</th>
                  <th className="py-2.5 px-3">Blood Bank / Center</th>
                  <th className="py-2.5 px-3">Blood Group</th>
                  <th className="py-2.5 px-3">Units</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Certificate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {donationHistory.map((item, idx) => (
                  <tr key={idx} className="hover:bg-slate-900/40">
                    <td className="py-2.5 px-3 font-mono text-slate-400">{item.certificate_code || item.donation_code || item.id}</td>
                    <td className="py-2.5 px-3 font-semibold text-white">{item.donation_date || item.date}</td>
                    <td className="py-2.5 px-3 text-slate-300">{item.hospital_name || item.center_name || item.location}</td>
                    <td className="py-2.5 px-3 font-black text-blood-400">{item.blood_group || item.blood}</td>
                    <td className="py-2.5 px-3 text-white">{item.units || 1} Unit</td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold">
                        {item.status || 'Verified'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={() => { setSelectedCertificate(item); setShowCertModal(true); }}
                        className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-blood-400 border border-slate-700 text-[11px] font-bold inline-flex items-center space-x-1 transition-all"
                      >
                        <Award className="w-3.5 h-3.5" />
                        <span>View</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SUBTAB 4: APPOINTMENTS */}
      {(activeSubTab === 'donor_appointments') && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Book Appointment Form */}
          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
            <div className="pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Calendar className="w-4 h-4 text-blood-400" />
                <span>Book Blood Donation Appointment</span>
              </h3>
              <p className="text-xs text-slate-400">Schedule your next life-saving donation drive visit.</p>
            </div>

            {appMsg && (
              <div className={`p-3 rounded-xl text-xs font-bold text-center ${
                appMsg.includes('verify')
                  ? 'bg-rose-950/80 border border-rose-800 text-rose-300'
                  : 'bg-emerald-950/80 border border-emerald-800 text-emerald-300'
              }`}>
                {appMsg}
              </div>
            )}

            <form onSubmit={handleBookAppointment} className="space-y-3 text-xs">
              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Appointment Date</label>
                <input
                  type="date"
                  required
                  min={new Date().toISOString().slice(0, 10)}
                  value={newAppDate}
                  onChange={(e) => setNewAppDate(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                />
              </div>

              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Preferred Time Slot</label>
                <select
                  value={newAppSlot}
                  onChange={(e) => setNewAppSlot(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                >
                  <option value="Morning (8 AM - 12 PM)">Morning (8 AM - 12 PM)</option>
                  <option value="Afternoon (12 PM - 4 PM)">Afternoon (12 PM - 4 PM)</option>
                  <option value="Evening (4 PM - 8 PM)">Evening (4 PM - 8 PM)</option>
                </select>
              </div>

              <div>
                <label className="text-slate-300 font-semibold mb-1 block">Blood Bank Center</label>
                <select
                  value={newAppCenter}
                  onChange={(e) => setNewAppCenter(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                >
                  <option value="Central Blood Bank Hub #1">Central Blood Bank Hub #1</option>
                  <option value="City General Blood Center">City General Blood Center</option>
                  <option value="St. Jude Emergency Center Desk">St. Jude Emergency Center Desk</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={!isVerified}
                className={`w-full py-2.5 rounded-xl text-xs font-bold transition-all ${
                  isVerified
                    ? 'bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white shadow-md'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
                }`}
              >
                {isVerified ? 'Confirm Appointment Booking' : 'Verify Email to Book Appointment'}
              </button>
            </form>
          </div>

          {/* Scheduled Appointments List */}
          <div className="p-5 rounded-2xl glass-panel border border-slate-800 space-y-4">
            <div className="pb-3 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-sm font-bold text-white">My Appointments List</h3>
              <span className="text-xs text-slate-400">{appointments.length} Appointments</span>
            </div>

            <div className="space-y-3">
              {profileLoading ? (
                <p className="text-xs text-slate-500">Loading your appointments…</p>
              ) : appointmentError ? (
                <p className="text-xs text-rose-300" role="alert">{appointmentError}</p>
              ) : appointments.length === 0 ? (
                <p className="text-xs text-slate-500">No appointments recorded.</p>
              ) : (
                appointments.map((app, idx) => (
                  <div key={idx} className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-white text-sm">{app.appointment_date || app.date}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold">
                        {app.status || 'SCHEDULED'}
                      </span>
                    </div>
                    <p className="text-slate-400">{app.time_slot}</p>
                    <p className="text-slate-500 text-[11px]">{app.center_name}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* SUBTAB 5: NOTIFICATIONS */}
      {(activeSubTab === 'donor_notifications') && (
        <div className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Bell className="w-4 h-4 text-blood-400" />
                <span>Hospital Emergency Blood Requisition Notifications</span>
              </h3>
              <p className="text-xs text-slate-400">Real-time alerts for urgent blood group {donorDetails.blood_group} requirements.</p>
            </div>
            <span className="px-2.5 py-1 rounded-lg text-xs bg-blood-950 text-blood-400 border border-blood-800 font-extrabold">
              {emergencyRequestsForGroup.length} Live Alerts
            </span>
          </div>

          {requestActionNotice && <p className="text-xs text-amber-300" role="status">{requestActionNotice}</p>}

          <div className="space-y-3">
            {emergencyRequestsForGroup.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-xs">
                No active emergency requests matching your blood group right now.
              </div>
            ) : (
              emergencyRequestsForGroup.map((req, idx) => {
                const reqId = req.id ?? req._id;
                const hasRequestId = reqId !== undefined && reqId !== null && String(reqId).trim() !== '';
                const savedResponse = req.donor_response || respondedAlerts[reqId];
                const actionMessage = requestActionMessages[reqId];
                return (
                  <div key={reqId ?? `${req.hospital_name || req.hospital || 'request'}-${idx}`} className="p-4 rounded-xl bg-blood-950/30 border border-blood-800/80 space-y-2 text-xs">
                    <div className="flex items-center justify-between font-bold text-white">
                      <span>{req.hospital_name || req.hospital}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] bg-blood-950 text-blood-400 border border-blood-800">
                        {req.urgency_level || req.urgency}
                      </span>
                    </div>
                    <p className="text-slate-300">
                      Need: <strong className="text-blood-400">{req.units_needed || req.units} units</strong> of <strong className="text-white">{donorDetails.blood_group}</strong> for {req.patient_name || req.patient}.
                    </p>
                    <p className="text-slate-400">{req.hospital_address || 'Hospital location not provided'}</p>
                    {actionMessage && <p className={`text-xs ${savedResponse ? 'text-emerald-300' : 'text-rose-300'}`} role={savedResponse ? 'status' : 'alert'}>{actionMessage}</p>}
                    <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
                      <span className="text-slate-500 text-[10px]">{req.request_date || 'Date not provided'}{savedResponse ? ` · ${savedResponse}` : ''}</span>
                      {savedResponse ? (
                        <span className={`px-3 py-1.5 rounded-lg text-xs font-bold border ${savedResponse === 'ACCEPTED' ? 'bg-emerald-950 text-emerald-300 border-emerald-800' : 'bg-slate-900 text-slate-300 border-slate-700'}`}>Response: {savedResponse}</span>
                      ) : (
                        <div className="flex gap-2">
                          <button onClick={() => handleEmergencyResponse(reqId, 'ACCEPT')} disabled={!hasRequestId || !isVerified || Boolean(requestActionBusy[reqId]) || Boolean(respondedAlerts[reqId])} className="px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-700 hover:bg-emerald-600 text-white disabled:opacity-50">{requestActionBusy[reqId] ? 'Saving…' : 'Accept'}</button>
                          <button onClick={() => handleEmergencyResponse(reqId, 'REJECT')} disabled={!hasRequestId || !isVerified || Boolean(requestActionBusy[reqId]) || Boolean(respondedAlerts[reqId])} className="px-3 py-1.5 rounded-lg text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-600 disabled:opacity-50">Reject</button>
                          {!isVerified && <span className="text-xs text-amber-300 self-center">Verify email to respond</span>}
                          {!hasRequestId && <span className="text-xs text-amber-300 self-center">Request ID unavailable; actions disabled</span>}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* CERTIFICATE VIEWER MODAL */}
      {showCertModal && selectedCertificate && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div role="dialog" aria-modal="true" className="w-full max-w-lg p-6 rounded-2xl glass-panel border border-slate-700 bg-slate-950/95 space-y-6 shadow-2xl relative">
            <button
              onClick={() => { setShowCertModal(false); setSelectedCertificate(null); }}
              className="absolute top-4 right-4 p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-all"
              aria-label="Close certificate modal"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Certificate Header Banner */}
            <div className="text-center space-y-2 border-b border-slate-800 pb-4">
              <div className="inline-flex p-3 rounded-2xl bg-blood-950/80 border border-blood-800 text-blood-400 mx-auto">
                <Award className="w-8 h-8" />
              </div>
              <h3 className="text-xl font-black text-white tracking-wide">Certificate of Blood Donation</h3>
              <p className="text-xs text-slate-400 font-mono">
                Official Certification #{selectedCertificate.certificate_code || selectedCertificate.donation_code || selectedCertificate.id}
              </p>
            </div>

            {/* Certificate Body */}
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-3 text-xs">
              <p className="text-slate-300 text-center leading-relaxed">
                This certifies that <strong className="text-white text-sm">{selectedCertificate.donor_name || donorDetails.name || 'Honored Donor'}</strong> has generously contributed to saving human lives through voluntary blood donation.
              </p>

              <div className="grid grid-cols-2 gap-3 pt-2">
                <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase block font-semibold">Blood Group</span>
                  <span className="text-sm font-black text-blood-400">{selectedCertificate.blood_group}</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase block font-semibold">Units Donated</span>
                  <span className="text-sm font-bold text-white">{selectedCertificate.units || 1} Unit(s)</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase block font-semibold">Date of Donation</span>
                  <span className="text-xs font-semibold text-white">{selectedCertificate.donation_date}</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase block font-semibold">Donation Type</span>
                  <span className="text-xs font-semibold text-white">{selectedCertificate.donation_type || 'Whole Blood'}</span>
                </div>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                <span className="text-[10px] text-slate-500 uppercase block font-semibold">Medical Facility / Center</span>
                <span className="text-xs font-bold text-slate-200">{selectedCertificate.hospital_name || selectedCertificate.center_name || 'Central Blood Bank Hub #1'}</span>
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="inline-flex items-center space-x-1.5 text-emerald-400 font-bold text-[11px]">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Status: {selectedCertificate.status || 'CONFIRMED'}</span>
                </span>
                <span className="text-[10px] font-mono text-slate-500">HaemoPulse Verified</span>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end space-x-3 pt-2">
              <button
                type="button"
                onClick={() => window.print()}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold flex items-center space-x-1.5 border border-slate-700 transition-all"
              >
                <Printer className="w-4 h-4" />
                <span>Print Certificate</span>
              </button>
              <button
                type="button"
                onClick={() => { setShowCertModal(false); setSelectedCertificate(null); }}
                className="px-4 py-2 rounded-xl bg-blood-600 hover:bg-blood-500 text-white text-xs font-bold transition-all"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
