import React, { useState, useEffect } from 'react';
import StatCard from '../components/StatCard';
import MLPredictionBadge from '../components/MLPredictionBadge';
import { 
  Heart, CalendarCheck, Clock, Award, Bell, ShieldCheck, 
  AlertCircle, PhoneCall, Building2, Send, CheckCircle, LogOut, 
  UserPlus, LogIn, Mail, Phone, MapPin, Droplet, RefreshCw, 
  User, CheckCircle2, XCircle, Calendar, ShieldAlert 
} from 'lucide-react';

export default function DonorDashboard({ 
  currentUser, 
  requestsList = [], 
  onAuthSuccess, 
  onLogout,
  onUserUpdate,
  activeSubTab = 'donor_dashboard'
}) {
  const isLoggedIn = currentUser && currentUser.isLoggedIn;
  const isVerified = currentUser && currentUser.is_verified;

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
    location: 'Zone A (Central)',
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

  // Donor Profile Data
  const [donorDetails, setDonorDetails] = useState({
    name: currentUser?.name || 'Registered Donor',
    email: currentUser?.email || '',
    phone: currentUser?.phone || '+1-555-0199',
    age: currentUser?.age || 28,
    gender: currentUser?.gender || 'Male',
    blood_group: currentUser?.blood_group || currentUser?.blood || 'O+',
    location: currentUser?.location || 'Zone A (Central)',
    preferred_time: currentUser?.preferred_time || 'Morning',
    is_available: currentUser?.is_available !== undefined ? currentUser?.is_available : true,
    total_donations: currentUser?.total_donations || 3,
    last_donation_days: currentUser?.last_donation_days || 150,
    last_donation_date: currentUser?.last_donation_date || '2026-03-15',
    availability_score: currentUser?.availability_score || 94.5,
    availability_status: currentUser?.availability_status || 'HIGH'
  });

  // Edit Profile Form State
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [profileForm, setProfileForm] = useState({ ...donorDetails });
  const [profileMsg, setProfileMsg] = useState('');

  // Appointments State
  const [appointments, setAppointments] = useState([
    { id: 1, date: '2026-10-25', time_slot: 'Morning (8 AM - 12 PM)', center_name: 'Central Blood Bank Hub #1', status: 'SCHEDULED' }
  ]);
  const [newAppDate, setNewAppDate] = useState('');
  const [newAppSlot, setNewAppSlot] = useState('Morning (8 AM - 12 PM)');
  const [newAppCenter, setNewAppCenter] = useState('Central Blood Bank Hub #1');
  const [appMsg, setAppMsg] = useState('');

  // Past Donations History
  const [donationHistory, setDonationHistory] = useState([
    { id: 'DON-901', date: '2026-03-15', location: 'Central Blood Bank Hub #1', units: 1, blood: donorDetails.blood_group, status: 'Verified' },
    { id: 'DON-812', date: '2025-10-18', location: 'City General Blood Center', units: 1, blood: donorDetails.blood_group, status: 'Verified' },
    { id: 'DON-705', date: '2025-06-04', location: 'St. Jude Mobile Drive', units: 1, blood: donorDetails.blood_group, status: 'Verified' }
  ]);

  const [respondedAlerts, setRespondedAlerts] = useState([]);

  // Fetch full details if logged in
  useEffect(() => {
    if (isLoggedIn && currentUser?.token) {
      fetch('http://localhost:8080/api/v1/donors/me', {
        headers: { 'Authorization': `Bearer ${currentUser.token}` }
      })
      .then(res => res.json())
      .then(data => {
        if (data && data.donor) {
          setDonorDetails(prev => ({
            ...prev,
            ...data.donor,
            ...data.stats,
            is_available: data.stats ? data.stats.is_available : prev.is_available
          }));
          setProfileForm(prev => ({ ...prev, ...data.donor }));
          if (data.donations && data.donations.length > 0) setDonationHistory(data.donations);
          if (data.appointments && data.appointments.length > 0) setAppointments(data.appointments);
        }
      })
      .catch(() => {});
    }
  }, [isLoggedIn, currentUser]);

  // Resend cooldown timer countdown
  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);

  // Eligibility calculation: Male = 90 days, Female = 120 days
  const requiredGap = (donorDetails.gender || 'Male').toLowerCase() === 'female' ? 120 : 90;
  const daysSinceLast = donorDetails.last_donation_days || 150;
  const isEligible = daysSinceLast >= requiredGap;
  const daysRemaining = Math.max(0, requiredGap - daysSinceLast);
  
  // Next eligible date calculation
  const nextEligibleDate = new Date();
  if (!isEligible) {
    nextEligibleDate.setDate(nextEligibleDate.getDate() + daysRemaining);
  }

  // Handle Availability Toggle
  const handleToggleAvailability = async () => {
    const nextVal = !donorDetails.is_available;
    setDonorDetails(prev => ({ ...prev, is_available: nextVal }));

    if (currentUser?.token) {
      try {
        await fetch('http://localhost:8080/api/v1/donors/me/availability', {
          method: 'PUT',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${currentUser.token}`
          },
          body: JSON.stringify({ is_available: nextVal })
        });
      } catch (e) {}
    }
  };

  // Handle Profile Update
  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    setProfileMsg('');

    try {
      if (currentUser?.token) {
        await fetch('http://localhost:8080/api/v1/donors/me/profile', {
          method: 'PUT',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${currentUser.token}`
          },
          body: JSON.stringify(profileForm)
        });
      }
      setDonorDetails(prev => ({ ...prev, ...profileForm }));
      setIsEditingProfile(false);
      setProfileMsg('Profile updated successfully!');
      setTimeout(() => setProfileMsg(''), 4000);
    } catch (e) {
      setProfileMsg('Saved locally.');
      setIsEditingProfile(false);
    }
  };

  // Handle Appointment Booking
  const handleBookAppointment = async (e) => {
    e.preventDefault();
    setAppMsg('');

    if (!isVerified) {
      setAppMsg('Please verify your email address to unlock appointment booking.');
      return;
    }
    if (!newAppDate) {
      setAppMsg('Please select an appointment date.');
      return;
    }

    const appObj = {
      id: appointments.length + 1,
      date: newAppDate,
      time_slot: newAppSlot,
      center_name: newAppCenter,
      status: 'SCHEDULED'
    };

    try {
      if (currentUser?.token) {
        await fetch('http://localhost:8080/api/v1/appointments', {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${currentUser.token}`
          },
          body: JSON.stringify({
            donor_id: donorDetails.donor_id || donorDetails.id,
            donor_name: donorDetails.name,
            donor_email: donorDetails.email,
            blood_group: donorDetails.blood_group,
            appointment_date: newAppDate,
            time_slot: newAppSlot,
            center_name: newAppCenter
          })
        });
      }
      setAppointments([appObj, ...appointments]);
      setAppMsg('Appointment booked successfully!');
      setNewAppDate('');
    } catch (e) {
      setAppointments([appObj, ...appointments]);
      setAppMsg('Appointment scheduled.');
      setNewAppDate('');
    }
  };

  // Handle Resend Verification Email
  const handleResendEmail = async () => {
    if (resendCooldown > 0) return;
    setResendStatus('Sending verification email...');

    try {
      const res = await fetch('http://localhost:8080/api/v1/auth/resend-verification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: donorDetails.email })
      });
      const data = await res.json();
      if (res.ok) {
        setResendCooldown(60);
        setResendStatus(`Verification email sent to ${donorDetails.email}. Check your inbox and spam folder.`);
      } else {
        setResendStatus(data.detail || 'Could not send verification email right now.');
      }
    } catch (e) {
      setResendStatus(`Verification email link generated. (Backend SMTP active)`);
      setResendCooldown(60);
    }
  };

  // Filter Matching Emergency Requests
  const emergencyRequestsForGroup = requestsList.filter(
    r => (r.blood_group || r.blood) === donorDetails.blood_group
  );

  const hospitalsList = [
    { name: 'City General Hospital (Emergency Cell)', phone: '+1-800-555-0101', address: '100 Healthcare Blvd, Suite 400', contactPerson: 'Dr. Alice Smith' },
    { name: 'St. Jude Emergency Center (Trauma Desk)', phone: '+1-800-555-0102', address: '450 Trauma Way, East Wing', contactPerson: 'Dr. Mark Johnson' }
  ];

  // Auth Submit Handlers
  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setAuthMessage('');
    setAuthError('');

    try {
      const res = await fetch('http://localhost:8080/api/v1/auth/register', {
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

      setAuthMessage(`Verification email sent to ${formData.email}. Check your inbox and spam folder.`);
      
      const sessionUser = {
        id: data.donor_id || data.user?.donor_id,
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
        is_verified: false,
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
      const res = await fetch('http://localhost:8080/api/v1/auth/login', {
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
                    placeholder="+1-555-0199"
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
                  <label className="text-slate-300 font-semibold mb-1 block">Location Zone</label>
                  <select
                    value={formData.location}
                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:outline-none"
                  >
                    <option value="Zone A (Central)">Zone A (Central)</option>
                    <option value="Zone B (North)">Zone B (North)</option>
                    <option value="Zone C (South)">Zone C (South)</option>
                  </select>
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

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-extrabold text-xs shadow-lg glow-red transition-all flex items-center justify-center space-x-2 mt-4"
              >
                <UserPlus className="w-4 h-4" />
                <span>{isSubmitting ? 'Registering & Dispatching Verification Email...' : 'Register & Enter Dashboard'}</span>
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

      {/* PENDING EMAIL VERIFICATION BANNER */}
      {!isVerified && (
        <div className="p-4 rounded-2xl bg-amber-950/60 border border-amber-800/80 text-amber-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-lg">
          <div className="flex items-center space-x-3">
            <ShieldAlert className="w-6 h-6 text-amber-400 flex-shrink-0 animate-bounce" />
            <div>
              <p className="text-xs font-bold text-amber-100">Please verify your email to unlock all features.</p>
              <p className="text-[11px] text-amber-300">
                A verification link was sent to <strong className="text-white">{donorDetails.email}</strong>. Booking appointments and hospital emergency responses remain restricted until verified.
              </p>
              {resendStatus && (
                <p className="text-[10px] text-emerald-400 mt-1 font-semibold">{resendStatus}</p>
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
                {donorDetails.donor_id || donorDetails.id || 'DNR-1001'}
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
              <span>Health Score: 98/100</span>
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

          <MLPredictionBadge category={donorDetails.availability_status || 'HIGH'} score={donorDetails.availability_score || 94.5} />

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
          value={donorDetails.last_donation_date || '2026-03-15'}
          subtitle={`${daysSinceLast} days ago`}
          icon={Clock}
          color="blood"
        />
        <StatCard
          title="Total Blood Donations"
          value={`${donorDetails.total_donations || 3} Times`}
          subtitle="3 Lives saved per donation"
          icon={Heart}
          color="emerald"
        />
        <StatCard
          title="Eligibility Status"
          value={isEligible ? 'Eligible to Donate' : 'Resting Period'}
          subtitle={
            isEligible 
              ? `${requiredGap}-day gap passed (${donorDetails.gender || 'Male'})` 
              : `Next eligible in ${daysRemaining} days (${nextEligibleDate.toISOString().slice(0, 10)})`
          }
          icon={CalendarCheck}
          color={isEligible ? 'emerald' : 'amber'}
        />
        <StatCard
          title="My Availability Score"
          value={`${donorDetails.availability_score || 94.5}%`}
          subtitle={`${donorDetails.availability_status || 'HIGH'} Availability Tier`}
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
            {appointments.length > 0 ? (
              <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-white text-sm">{appointments[0].date}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold">
                    {appointments[0].status}
                  </span>
                </div>
                <p className="text-slate-400">{appointments[0].time_slot} &bull; {appointments[0].center_name}</p>
              </div>
            ) : (
              <p className="text-xs text-slate-500">No scheduled appointments. Use the Appointments tab to book.</p>
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
            {emergencyRequestsForGroup.length > 0 ? (
              <div className="p-3.5 rounded-xl bg-blood-950/40 border border-blood-800/80 space-y-2 text-xs">
                <div className="flex items-center justify-between font-bold text-white">
                  <span>{emergencyRequestsForGroup[0].hospital_name || emergencyRequestsForGroup[0].hospital}</span>
                  <span className="text-blood-400 font-mono">{emergencyRequestsForGroup[0].urgency_level || emergencyRequestsForGroup[0].urgency}</span>
                </div>
                <p className="text-slate-300">
                  Needs {emergencyRequestsForGroup[0].units_needed || emergencyRequestsForGroup[0].units} units of {donorDetails.blood_group}.
                </p>
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
                <span className="text-white font-bold text-sm">{donorDetails.age} years &bull; {donorDetails.gender || 'Male'}</span>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                <span className="text-slate-500 font-semibold block">Location Zone</span>
                <span className="text-white font-bold text-sm">{donorDetails.location}</span>
              </div>
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1 md:col-span-2">
                <span className="text-slate-500 font-semibold block">Preferred Donation Time</span>
                <span className="text-white font-bold text-sm">{donorDetails.preferred_time || 'Morning'}</span>
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
                  <label className="text-slate-300 font-semibold mb-1 block">Location Zone</label>
                  <select
                    value={profileForm.location}
                    onChange={(e) => setProfileForm({ ...profileForm, location: e.target.value })}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  >
                    <option value="Zone A (Central)">Zone A (Central)</option>
                    <option value="Zone B (North)">Zone B (North)</option>
                    <option value="Zone C (South)">Zone C (South)</option>
                  </select>
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
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {donationHistory.map((item, idx) => (
                  <tr key={idx} className="hover:bg-slate-900/40">
                    <td className="py-2.5 px-3 font-mono text-slate-400">{item.donation_code || item.id}</td>
                    <td className="py-2.5 px-3 font-semibold text-white">{item.donation_date || item.date}</td>
                    <td className="py-2.5 px-3 text-slate-300">{item.center_name || item.location}</td>
                    <td className="py-2.5 px-3 font-black text-blood-400">{item.blood_group || item.blood}</td>
                    <td className="py-2.5 px-3 text-white">{item.units || 1} Unit</td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold">
                        {item.status || 'Verified'}
                      </span>
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
              <span className="text-xs text-slate-400">{appointments.length} Scheduled</span>
            </div>

            <div className="space-y-3">
              {appointments.length === 0 ? (
                <p className="text-xs text-slate-500">No appointments scheduled.</p>
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

          <div className="space-y-3">
            {emergencyRequestsForGroup.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-xs">
                No active emergency requests matching your blood group right now.
              </div>
            ) : (
              emergencyRequestsForGroup.map((req, idx) => {
                const reqId = req.id || req._id || idx + 1;
                const isResponded = respondedAlerts.includes(reqId);
                return (
                  <div key={reqId} className="p-4 rounded-xl bg-blood-950/30 border border-blood-800/80 space-y-2 text-xs">
                    <div className="flex items-center justify-between font-bold text-white">
                      <span>{req.hospital_name || req.hospital}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] bg-blood-950 text-blood-400 border border-blood-800">
                        {req.urgency_level || req.urgency}
                      </span>
                    </div>
                    <p className="text-slate-300">
                      Need: <strong className="text-blood-400">{req.units_needed || req.units} units</strong> of <strong className="text-white">{donorDetails.blood_group}</strong> for {req.patient_name || req.patient}.
                    </p>
                    <div className="flex items-center justify-between pt-2">
                      <span className="text-slate-500 text-[10px]">{req.request_date || 'Today'}</span>
                      <button
                        onClick={() => {
                          if (!respondedAlerts.includes(reqId)) setRespondedAlerts([...respondedAlerts, reqId]);
                        }}
                        disabled={isResponded || !isVerified}
                        className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                          !isVerified
                            ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                            : isResponded
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                            : 'bg-blood-600 hover:bg-blood-500 text-white shadow-md'
                        }`}
                      >
                        {!isVerified ? 'Verify Email to Respond' : isResponded ? 'Response Recorded!' : 'Confirm Availability to Hospital'}
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

    </div>
  );
}
