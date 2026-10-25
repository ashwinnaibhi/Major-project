import React, { useState } from 'react';
import { LogIn, UserPlus, X, Droplet, ShieldCheck, Heart, Sparkles } from 'lucide-react';
import LocationFields from './LocationFields';

import { getApiBaseUrl } from '../api/config';
const API_BASE_URL = getApiBaseUrl();

export default function AuthModal({ isOpen, onClose, onAuthSuccess }) {
  const [authMode, setAuthMode] = useState('register'); // 'login' or 'register'
  
  // Login Form State
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Register Form State
  const [regData, setRegData] = useState({
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
    latitude: null,
    longitude: null,
    preferred_time: 'Morning'
  });

  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);

  if (!isOpen) return null;

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMsg(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...regData, role: 'ROLE_DONOR' })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Registration failed. Check the form and backend response.');
      }

      setMsg({ type: 'success', text: data.message || 'Registration successful.' });
      setTimeout(() => {
        onAuthSuccess({
          name: regData.name,
          email: regData.email,
          blood_group: regData.blood_group,
          role: 'DONOR',
          donor_id: data.user?.donor_id || data.donor?.donor_id,
          token: data.token,
          isLoggedIn: true,
          is_verified: data.user?.is_verified ?? false,
          district: data.donor?.district ?? regData.district,
          taluk: data.donor?.taluk ?? regData.taluk
        });
        onClose();
      }, 800);
    } catch (err) {
      setMsg({
        type: 'error',
        text: err.message || 'Registration could not reach the backend. No donor record was confirmed as saved.'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMsg(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Login failed. Please check your credentials.');
      }

      const role = data.user?.role === 'ROLE_ADMIN' ? 'ADMIN' :
                   data.user?.role === 'ROLE_HOSPITAL' ? 'HOSPITAL' :
                   data.user?.role === 'ROLE_STAFF' ? 'STAFF' : 'DONOR';

      setMsg({ type: 'success', text: 'Login successful.' });
      setTimeout(() => {
        onAuthSuccess({
          ...data.user,
          role,
          token: data.token || data.access_token,
          isLoggedIn: true,
          is_verified: Boolean(data.user?.is_verified)
        });
        onClose();
      }, 500);
    } catch (err) {
      setMsg({ type: 'error', text: err.message || 'Login failed. Please verify email and password.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto glass-panel border border-slate-800 rounded-3xl p-6 relative space-y-5 shadow-2xl">
        
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-xl bg-slate-900 text-slate-400 hover:text-white border border-slate-800"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header Logo */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blood-700 to-blood-500 flex items-center justify-center shadow-lg glow-red">
            <Droplet className="w-6 h-6 text-white fill-white animate-pulse" />
          </div>
          <div>
            <h3 className="text-xl font-extrabold text-white">Donor Portal Access</h3>
            <p className="text-xs text-slate-400">Register as a new blood donor or log into your account</p>
          </div>
        </div>

        {/* Mode Switcher Tabs */}
        <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-slate-900 border border-slate-800 text-xs font-bold">
          <button
            onClick={() => setAuthMode('register')}
            className={`py-2 rounded-lg transition-all flex items-center justify-center space-x-1.5 ${
              authMode === 'register' ? 'bg-blood-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <UserPlus className="w-3.5 h-3.5" />
            <span>New Donor Registration</span>
          </button>

          <button
            onClick={() => setAuthMode('login')}
            className={`py-2 rounded-lg transition-all flex items-center justify-center space-x-1.5 ${
              authMode === 'login' ? 'bg-blood-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Donor Login</span>
          </button>
        </div>

        {msg && (
          <div className={`p-3 rounded-xl text-xs font-semibold border ${
            msg.type === 'success' ? 'bg-emerald-950/80 text-emerald-300 border-emerald-800' : 'bg-rose-950/80 text-rose-300 border-rose-800'
          }`}>
            {msg.text}
          </div>
        )}

        {/* 1. NEW DONOR REGISTRATION FORM */}
        {authMode === 'register' ? (
          <form onSubmit={handleRegisterSubmit} className="space-y-3 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Full Name *</label>
                <input
                  type="text" required
                  placeholder="e.g. Alex Johnson"
                  value={regData.name}
                  onChange={(e) => setRegData({ ...regData, name: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:border-blood-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Email Address *</label>
                <input
                  type="email" required
                  placeholder="donor@email.com"
                  value={regData.email}
                  onChange={(e) => setRegData({ ...regData, email: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:border-blood-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Password *</label>
                <input
                  type="password" required
                  placeholder="••••••••"
                  value={regData.password}
                  onChange={(e) => setRegData({ ...regData, password: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:border-blood-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Phone Number *</label>
                <input
                  type="tel" required
                  placeholder="+1-555-0199"
                  value={regData.phone}
                  onChange={(e) => setRegData({ ...regData, phone: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:border-blood-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Blood Group *</label>
                <select
                  value={regData.blood_group}
                  onChange={(e) => setRegData({ ...regData, blood_group: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white font-extrabold focus:border-blood-500 focus:outline-none"
                >
                  {['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'].map(b => (
                    <option key={b} value={b}>{b}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Age (18-65) *</label>
                <input
                  type="number" min="18" max="65" required
                  value={regData.age}
                  onChange={(e) => setRegData({ ...regData, age: parseInt(e.target.value) })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white text-center focus:border-blood-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1 font-semibold">Gender *</label>
                <select
                  value={regData.gender}
                  onChange={(e) => setRegData({ ...regData, gender: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:border-blood-500 focus:outline-none"
                >
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>

            <LocationFields value={regData} onChange={setRegData} requiredLocation showCoordinates />

            <div>
              <label className="text-slate-400 block mb-1 font-semibold">Preferred Time Slot *</label>
              <select
                value={regData.preferred_time}
                onChange={(e) => setRegData({ ...regData, preferred_time: e.target.value })}
                className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white focus:border-blood-500 focus:outline-none"
              >
                <option value="Morning">Morning (8 AM - 12 PM)</option>
                <option value="Afternoon">Afternoon (12 PM - 4 PM)</option>
                <option value="Evening">Evening (4 PM - 8 PM)</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-extrabold text-xs shadow-lg glow-red flex items-center justify-center space-x-2 transition-all mt-4"
            >
              <Heart className="w-4 h-4 fill-white" />
              <span>{loading ? 'Saving Donor Profile...' : 'Complete Donor Registration'}</span>
            </button>
          </form>
        ) : (
          /* 2. DONOR LOGIN FORM */
          <form onSubmit={handleLoginSubmit} className="space-y-4 text-xs">
            <div>
              <label className="text-slate-400 block mb-1 font-semibold">Registered Email Address</label>
              <input
                type="email" required
                placeholder="john.doe@email.com"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:border-blood-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="text-slate-400 block mb-1 font-semibold">Password</label>
              <input
                type="password" required
                placeholder="••••••••"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2.5 text-white focus:border-blood-500 focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-extrabold text-xs shadow-lg glow-red flex items-center justify-center space-x-2 transition-all"
            >
              <LogIn className="w-4 h-4" />
              <span>{loading ? 'Authenticating...' : 'Log In to Donor Dashboard'}</span>
            </button>
          </form>
        )}

      </div>
    </div>
  );
}
