import React, { useEffect, useMemo, useState } from 'react';
import { Building2, LogIn, UserPlus, MapPin, ShieldCheck, HeartPulse, KeyRound } from 'lucide-react';

import { getApiBaseUrl } from '../api/config';
const API_BASE = getApiBaseUrl();

function toHospitalSession(data) {
  const rawUser = data?.user || {};
  const role = String(rawUser.role || '').toUpperCase().replace(/^ROLE_/, '');
  if (!data?.token || !rawUser.id) {
    throw new Error('The server did not return a valid account session. Please try again.');
  }
  if (role !== 'HOSPITAL') {
    throw new Error('This account is not registered as a hospital. Please use the matching portal.');
  }
  // Legacy hospital accounts may not yet have a separate profile row. Allow them to
  // sign in, then require them to complete the profile before using hospital tools.
  const profile = data?.hospital_profile || rawUser.hospital_profile || {
    hospital_user_id: Number(rawUser.id),
    hospital_name: rawUser.name || '',
    address: '',
    district: '',
    taluk: '',
    latitude: null,
    longitude: null,
    contact_email: '',
    contact_phone: '',
    needs_setup: true,
  };
  return {
    ...rawUser,
    id: Number(rawUser.id),
    role: 'HOSPITAL',
    token: data.token,
    isLoggedIn: true,
    is_verified: rawUser.is_verified ?? true,
    must_change_password: Boolean(data?.must_change_password ?? rawUser.must_change_password),
    hospital_profile: profile,
    name: profile.hospital_name || rawUser.name,
  };
}

export default function HospitalAuth({ onAuthSuccess, onSwitchToDonor }) {
  const [mode, setMode] = useState('login');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [locations, setLocations] = useState({ districts: [], taluks_by_district: {} });
  const [form, setForm] = useState({
    hospital_name: '', email: '', phone: '', password: '', confirm_password: '', address: '',
    district: '', taluk: '', latitude: '', longitude: '',
  });

  // Mandatory password change state when account has must_change_password = true
  const [pendingSession, setPendingSession] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [changePwLoading, setChangePwLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/v1/locations`)
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || 'Hospital location options could not be loaded.');
        return data;
      })
      .then((data) => { if (!cancelled) setLocations(data); })
      .catch((error) => { if (!cancelled) setMessage({ type: 'error', text: error.message }); });
    return () => { cancelled = true; };
  }, []);

  const taluks = useMemo(() => locations.taluks_by_district?.[form.district] || [], [locations, form.district]);
  const update = (field, value) => setForm((previous) => ({ ...previous, [field]: value }));
  const switchMode = (nextMode) => { setMode(nextMode); setMessage(null); setPendingSession(null); };

  const submit = async (event) => {
    event.preventDefault();
    if (loading) return;
    setMessage(null);
    if (mode === 'register') {
      if (form.password.length < 8) { setMessage({ type: 'error', text: 'Password must contain at least 8 characters.' }); return; }
      if (form.password !== form.confirm_password) { setMessage({ type: 'error', text: 'Password and confirmation do not match.' }); return; }
      const hasLatitude = String(form.latitude).trim() !== '';
      const hasLongitude = String(form.longitude).trim() !== '';
      if (hasLatitude !== hasLongitude) { setMessage({ type: 'error', text: 'Enter both map coordinates, or leave both blank.' }); return; }
    }

    setLoading(true);
    try {
      const endpoint = mode === 'register' ? '/api/v1/auth/hospital/register' : '/api/v1/auth/login';
      const payload = mode === 'register'
        ? {
            hospital_name: form.hospital_name.trim(), email: form.email.trim(), phone: form.phone.trim(),
            password: form.password, address: form.address.trim(), district: form.district,
            taluk: form.taluk || null,
            latitude: String(form.latitude).trim() === '' ? null : Number(form.latitude),
            longitude: String(form.longitude).trim() === '' ? null : Number(form.longitude),
          }
        : { email: form.email.trim(), password: form.password };
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || data.message || `Hospital ${mode} failed (HTTP ${response.status}).`);
      const session = toHospitalSession(data);
      if (data?.must_change_password || session.must_change_password) {
        setPendingSession(session);
        setMessage({ type: 'info', text: 'Initial security requirement: You must update your password before accessing hospital operations.' });
        return;
      }
      onAuthSuccess(session);
    } catch (error) {
      setMessage({ type: 'error', text: error.message || 'Hospital account could not be authenticated.' });
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async (event) => {
    event.preventDefault();
    if (!pendingSession) return;
    if (newPassword.length < 8) {
      setMessage({ type: 'error', text: 'New password must contain at least 8 characters.' });
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setMessage({ type: 'error', text: 'New password and confirmation do not match.' });
      return;
    }

    setChangePwLoading(true);
    setMessage(null);
    try {
      const resp = await fetch(`${API_BASE}/api/v1/auth/change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${pendingSession.token}`,
        },
        body: JSON.stringify({
          current_password: form.password,
          new_password: newPassword,
        }),
      });
      const resData = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(resData.detail || resData.message || 'Password update failed.');
      }
      const updatedSession = {
        ...pendingSession,
        must_change_password: false,
      };
      setPendingSession(null);
      onAuthSuccess(updatedSession);
    } catch (err) {
      setMessage({ type: 'error', text: err.message || 'Password could not be updated.' });
    } finally {
      setChangePwLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl py-4">
      <div className="overflow-hidden rounded-3xl border border-slate-800 bg-slate-950/70 shadow-2xl">
        <div className="bg-gradient-to-r from-blood-950 via-slate-900 to-slate-950 p-6 sm:p-8 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blood-700 shadow-lg"><Building2 className="h-6 w-6 text-white" /></div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-blood-300">HaemoPulse Hospital Portal</p>
              <h2 className="mt-1 text-2xl font-black text-white">{mode === 'login' ? 'Hospital sign in' : 'Register your hospital'}</h2>
              <p className="mt-1 text-sm text-slate-400">Manage your hospital's requisitions, donor alerts and blood-stock availability.</p>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-4 text-xs text-slate-300">
            <span className="flex items-center gap-1.5"><ShieldCheck className="h-4 w-4 text-emerald-400" /> Dedicated login identity</span>
            <span className="flex items-center gap-1.5"><HeartPulse className="h-4 w-4 text-blood-400" /> Emergency requisitions</span>
            <span className="flex items-center gap-1.5"><MapPin className="h-4 w-4 text-sky-400" /> Verified notification routing</span>
          </div>
        </div>

        <div className="p-5 sm:p-8 space-y-5">
          {!pendingSession && (
            <div className="grid grid-cols-2 gap-2 rounded-xl border border-slate-800 bg-slate-900 p-1">
              <button type="button" onClick={() => switchMode('login')} className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-bold ${mode === 'login' ? 'bg-blood-600 text-white' : 'text-slate-400 hover:bg-slate-800 hover:text-white'}`}>
                <LogIn className="h-4 w-4" /> Sign in
              </button>
              <button type="button" onClick={() => switchMode('register')} className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-bold ${mode === 'register' ? 'bg-blood-600 text-white' : 'text-slate-400 hover:bg-slate-800 hover:text-white'}`}>
                <UserPlus className="h-4 w-4" /> Register hospital
              </button>
            </div>
          )}

          {message && (
            <div role="status" className={`rounded-xl border p-3 text-sm ${
              message.type === 'error'
                ? 'border-rose-800 bg-rose-950/50 text-rose-200'
                : message.type === 'info'
                ? 'border-amber-800 bg-amber-950/50 text-amber-200'
                : 'border-emerald-800 bg-emerald-950/50 text-emerald-200'
            }`}>
              {message.text}
            </div>
          )}

          {pendingSession ? (
            <form onSubmit={handlePasswordChange} className="space-y-4">
              <div className="rounded-xl border border-amber-800/80 bg-amber-950/40 p-4 space-y-1">
                <div className="flex items-center gap-2 text-amber-300 font-bold text-sm">
                  <KeyRound className="h-4 w-4" />
                  <span>Update Temporary Initial Password</span>
                </div>
                <p className="text-xs text-amber-200/80">
                  Logged in as <span className="font-mono font-bold text-white">{pendingSession.email}</span>. Please choose a strong, personalized password with at least 8 characters to secure your hospital facility account.
                </p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="New Password" required>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={8}
                    maxLength={256}
                    autoComplete="new-password"
                    className={inputClass}
                    placeholder="Enter new password"
                  />
                </Field>
                <Field label="Confirm New Password" required>
                  <input
                    type="password"
                    value={confirmNewPassword}
                    onChange={(e) => setConfirmNewPassword(e.target.value)}
                    required
                    minLength={8}
                    maxLength={256}
                    autoComplete="new-password"
                    className={inputClass}
                    placeholder="Re-enter new password"
                  />
                </Field>
              </div>

              <button
                type="submit"
                disabled={changePwLoading}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blood-700 to-blood-600 px-4 py-3.5 text-sm font-extrabold text-white shadow-lg transition hover:from-blood-600 hover:to-blood-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <KeyRound className="h-4 w-4" />
                {changePwLoading ? 'Updating password…' : 'Save Password & Enter Portal'}
              </button>
            </form>
          ) : (
            <form onSubmit={submit} className="space-y-4">
              {mode === 'register' && (
                <>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="Hospital / Blood Bank Name" required>
                      <input value={form.hospital_name} onChange={(e) => update('hospital_name', e.target.value)} required minLength={2} maxLength={160} autoComplete="organization" className={inputClass} placeholder="e.g. General Hospital Koppa" />
                    </Field>
                    <Field label="Contact Phone" required>
                      <input type="tel" value={form.phone} onChange={(e) => update('phone', e.target.value)} required minLength={6} maxLength={32} autoComplete="tel" className={inputClass} placeholder="Hospital contact phone" />
                    </Field>
                  </div>
                  <Field label="Hospital Address" required>
                    <textarea value={form.address} onChange={(e) => update('address', e.target.value)} required minLength={4} maxLength={300} rows={2} autoComplete="street-address" className={inputClass} placeholder="Street, area and locality" />
                  </Field>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="District" required>
                      <select value={form.district} onChange={(e) => setForm((previous) => ({ ...previous, district: e.target.value, taluk: '' }))} required className={inputClass}>
                        <option value="">Select district</option>
                        {(locations.districts || []).map((district) => <option key={district} value={district}>{district}</option>)}
                      </select>
                    </Field>
                    <Field label="Taluk (optional)">
                      <select value={form.taluk} onChange={(e) => update('taluk', e.target.value)} disabled={!form.district} className={`${inputClass} disabled:opacity-50`}>
                        <option value="">Select taluk</option>
                        {taluks.map((taluk) => <option key={taluk} value={taluk}>{taluk}</option>)}
                      </select>
                    </Field>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
                    <p className="text-sm font-bold text-slate-200">Map coordinates <span className="font-normal text-slate-500">(recommended)</span></p>
                    <p className="text-xs leading-relaxed text-slate-400">Coordinates let HaemoPulse calculate nearest hospitals by distance. Without them, stock search is limited to the registered district.</p>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <Field label="Latitude">
                        <input type="number" min="-90" max="90" step="any" value={form.latitude} onChange={(e) => update('latitude', e.target.value)} className={inputClass} placeholder="13.5333" />
                      </Field>
                      <Field label="Longitude">
                        <input type="number" min="-180" max="180" step="any" value={form.longitude} onChange={(e) => update('longitude', e.target.value)} className={inputClass} placeholder="75.3667" />
                      </Field>
                    </div>
                  </div>
                </>
              )}

              <Field label={mode === 'login' ? 'Hospital Login Identity' : 'Official Contact Email'} required>
                <input
                  type={mode === 'login' ? 'text' : 'email'}
                  value={form.email}
                  onChange={(e) => update('email', e.target.value)}
                  required
                  autoComplete={mode === 'login' ? 'username' : 'email'}
                  maxLength={254}
                  className={inputClass}
                  placeholder={mode === 'login' ? 'koppa_ghpc@haemopulse.in' : 'hospital_admin@example.org'}
                />
                <span className="block text-[11px] text-slate-400 mt-1">
                  {mode === 'login'
                    ? 'Enter your dedicated hospital identity (e.g. koppa_ghpc@haemopulse.in) or registered contact email.'
                    : 'A real external email address to receive emergency donor alerts and official notices (not @haemopulse.in).'}
                </span>
              </Field>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Password" required>
                  <input type="password" value={form.password} onChange={(e) => update('password', e.target.value)} required minLength={8} maxLength={256} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} className={inputClass} placeholder={mode === 'login' ? 'Your password' : 'At least 8 characters'} />
                </Field>
                {mode === 'register' && <Field label="Confirm Password" required>
                  <input type="password" value={form.confirm_password} onChange={(e) => update('confirm_password', e.target.value)} required minLength={8} maxLength={256} autoComplete="new-password" className={inputClass} placeholder="Re-enter password" />
                </Field>}
              </div>

              <button type="submit" disabled={loading || (mode === 'register' && (locations.districts || []).length === 0)} className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blood-700 to-blood-600 px-4 py-3.5 text-sm font-extrabold text-white shadow-lg transition hover:from-blood-600 hover:to-blood-500 disabled:cursor-not-allowed disabled:opacity-60">
                {mode === 'login' ? <LogIn className="h-4 w-4" /> : <UserPlus className="h-4 w-4" />}
                {loading ? 'Please wait…' : mode === 'login' ? 'Sign in to Hospital Portal' : 'Create Hospital Account'}
              </button>
            </form>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 pt-4 text-xs text-slate-500">
            <span>{mode === 'login' ? "Don't have a hospital account?" : 'Already registered?'}</span>
            <button type="button" onClick={() => switchMode(mode === 'login' ? 'register' : 'login')} className="font-bold text-blood-300 hover:text-blood-200">
              {mode === 'login' ? 'Register hospital' : 'Go to sign in'}
            </button>
            {onSwitchToDonor && <button type="button" onClick={onSwitchToDonor} className="basis-full text-left font-semibold text-slate-400 hover:text-white sm:basis-auto">Switch to donor portal</button>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, required, children }) {
  return <label className="block space-y-1.5"><span className="block text-xs font-semibold text-slate-300">{label}{required ? ' *' : ''}</span>{children}</label>;
}

const inputClass = 'w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-blood-500 focus:ring-1 focus:ring-blood-500';
