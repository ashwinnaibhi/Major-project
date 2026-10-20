import React from 'react';
import { Droplet, ShieldAlert, User, Cpu, LogOut } from 'lucide-react';

export default function Navbar({ activeRole, handleRoleChange, currentUser, onLogout }) {
  // Compute display user info based on activeRole
  const getUserDisplayInfo = () => {
    switch (activeRole) {
      case 'ADMIN':
        return { name: 'System Admin', email: 'admin@bloodbank.org', title: 'System Administrator' };
      case 'HOSPITAL':
        return { name: 'City General Hospital', email: 'contact@cityhospital.org', title: 'Registered Hospital' };
      case 'STAFF':
        return { name: 'Dr. Robert Vance', email: 'staff.vance@bloodbank.org', title: 'Blood Bank Staff' };
      case 'DONOR':
        const isCustomUser = currentUser && currentUser.isLoggedIn && currentUser.name !== 'System Admin';
        const dName = isCustomUser ? currentUser.name : 'Donor Portal (Log In Required)';
        const dEmail = isCustomUser ? currentUser.email : 'Please login/register below';
        const dBlood = isCustomUser ? (currentUser.blood || currentUser.blood_group || 'O+') : 'N/A';
        return {
          name: dName,
          email: dEmail,
          title: isCustomUser ? `Registered Donor (${dBlood})` : 'Guest Visitor'
        };
      default:
        return { name: 'System User', email: 'user@bloodbank.org', title: 'User' };
    }
  };

  const userInfo = getUserDisplayInfo();
  const isDonorLoggedIn = activeRole === 'DONOR' && currentUser && currentUser.isLoggedIn;

  return (
    <header className="sticky top-0 z-40 glass-panel border-b border-slate-800 px-6 py-3">
      <div className="flex items-center justify-between">
        
        {/* Brand Logo */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blood-700 to-blood-500 flex items-center justify-center shadow-lg glow-red">
            <Droplet className="w-6 h-6 text-white fill-white animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-extrabold tracking-tight text-white">Haemo<span className="text-blood-500">Pulse</span></h1>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blood-950 text-blood-400 border border-blood-800">
                <Cpu className="w-3 h-3 mr-1" /> ML v1.0
              </span>
            </div>
            <p className="text-xs text-slate-400">Donor Availability & Emergency Response Engine</p>
          </div>
        </div>

        {/* Center Banner */}
        <div className="hidden lg:flex items-center space-x-2 px-4 py-1.5 rounded-full bg-blood-950/60 border border-blood-900/50 text-blood-300 text-xs font-medium">
          <ShieldAlert className="w-4 h-4 text-blood-400 animate-bounce" />
          <span>Emergency Blood Request Mode Active &bull; ML Optimization Enabled</span>
        </div>

        {/* Right Section: Role Switcher & User Status */}
        <div className="flex items-center space-x-4">
          
          {/* Role Selector dropdown */}
          <div className="flex items-center space-x-2 bg-slate-900/90 p-1 rounded-xl border border-slate-800">
            <span className="text-xs text-slate-400 px-2 font-medium">Role View:</span>
            {[
              { id: 'ADMIN', label: 'Admin' },
              { id: 'HOSPITAL', label: 'Hospital' },
              { id: 'DONOR', label: 'Donor' },
              { id: 'STAFF', label: 'Staff' }
            ].map(r => (
              <button
                key={r.id}
                onClick={() => handleRoleChange(r.id)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                  activeRole === r.id
                    ? 'bg-blood-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>

          <div className="flex items-center space-x-3 pl-2 border-l border-slate-800">
            <div className="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center">
              <User className="w-5 h-5 text-blood-400" />
            </div>
            <div className="hidden sm:block text-left">
              <p className="text-xs font-semibold text-slate-200">{userInfo.name}</p>
              <p className="text-[10px] text-slate-400">{userInfo.title}</p>
            </div>

            {/* Donor Log Out Button (Only shown when donor is logged in) */}
            {isDonorLoggedIn && (
              <button
                onClick={onLogout}
                title="Log Out of Account"
                className="px-2.5 py-1.5 rounded-xl bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800 text-xs font-bold flex items-center space-x-1 transition-all"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden md:inline">Log Out</span>
              </button>
            )}
          </div>

        </div>

      </div>
    </header>
  );
}
