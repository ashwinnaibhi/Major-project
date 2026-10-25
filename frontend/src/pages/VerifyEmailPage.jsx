import React, { useState, useEffect } from 'react';
import { CheckCircle2, XCircle, Loader2, ArrowRight, RefreshCw, Mail } from 'lucide-react';

import { getApiBaseUrl } from '../api/config';
const API_BASE = getApiBaseUrl();

export default function VerifyEmailPage({ onVerified }) {
  const [status, setStatus] = useState('loading'); // 'loading' | 'success' | 'error' | 'expired'
  const [message, setMessage] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');

    if (!token) {
      setStatus('error');
      setMessage('No verification token provided in the URL. Please click the full link in your verification email.');
      return;
    }

    const verifyToken = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/auth/verify-email?token=${encodeURIComponent(token)}`);
        const data = await res.json().catch(() => ({}));
        if (res.ok && data.success) {
          setStatus('success');
          setMessage(data.message || 'Your email address has been successfully verified!');
          // Immediately update local session so donor portal displays verified status without re-login
          try {
            const saved = JSON.parse(localStorage.getItem('haemopulse_user') || 'null');
            if (saved) {
              saved.is_verified = true;
              localStorage.setItem('haemopulse_user', JSON.stringify(saved));
            }
          } catch (e) {}
          if (typeof onVerified === 'function') {
            try { onVerified(); } catch (e) {}
          }
        } else {
          const detail = data.detail || data.message || 'Verification token is invalid or has expired.';
          if (detail.toLowerCase().includes('expire')) {
            setStatus('expired');
          } else {
            setStatus('error');
          }
          setMessage(detail);
        }
      } catch (err) {
        setStatus('error');
        setMessage('Could not connect to the authentication server. Please ensure the HaemoPulse backend is running.');
      }
    };

    verifyToken();
  }, []);

  const handleGoHome = () => {
    window.location.href = '/';
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md p-8 rounded-2xl glass-panel border border-slate-800 text-center space-y-6 shadow-2xl">
        <div className="w-16 h-16 rounded-2xl mx-auto flex items-center justify-center">
          {status === 'loading' && (
            <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-blood-400">
              <Loader2 className="w-8 h-8 animate-spin" />
            </div>
          )}
          {status === 'success' && (
            <div className="w-16 h-16 rounded-2xl bg-emerald-950/80 border border-emerald-800 flex items-center justify-center text-emerald-400">
              <CheckCircle2 className="w-8 h-8" />
            </div>
          )}
          {status === 'expired' && (
            <div className="w-16 h-16 rounded-2xl bg-amber-950/80 border border-amber-800 flex items-center justify-center text-amber-400">
              <RefreshCw className="w-8 h-8" />
            </div>
          )}
          {status === 'error' && (
            <div className="w-16 h-16 rounded-2xl bg-rose-950/80 border border-rose-800 flex items-center justify-center text-rose-400">
              <XCircle className="w-8 h-8" />
            </div>
          )}
        </div>

        <div className="space-y-2">
          <h2 className="text-2xl font-black text-white">
            {status === 'loading' && 'Verifying Email...'}
            {status === 'success' && 'Email Verified!'}
            {status === 'expired' && 'Token Expired'}
            {status === 'error' && 'Verification Failed'}
          </h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            {message || 'Please wait while we validate your security token...'}
          </p>
        </div>

        {status === 'success' && (
          <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-xs">
            Your account is now activated. Appointment booking and emergency donation features are unlocked.
          </div>
        )}

        {status === 'expired' && (
          <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-800/60 text-amber-300 text-xs">
            Security tokens expire after 30 minutes. Sign in to your Donor Dashboard and click "Resend Verification Link" to receive a fresh token.
          </div>
        )}

        <div>
          <button
            onClick={handleGoHome}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-extrabold text-xs shadow-lg glow-red transition-all flex items-center justify-center space-x-2"
          >
            <span>Proceed to HaemoPulse Portal</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
