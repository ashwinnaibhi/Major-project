import React from 'react';
import { Droplet, Bell, ShieldAlert, User, Cpu, UserPlus, LogIn } from 'lucide-react';

export default function Navbar({ activeRole, handleRoleChange, onOpenAuth, currentUser }) {
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
        return {
          name: currentUser?.name || 'Registered Donor',
          email: currentUser?.email || 'donor@email.com',
          title: `Donor (${currentUser?.blood || currentUser?.blood_group || 'O+'})`
        };
      default:
        return { name: 'System User', email: 'user@bloodbank.org', title: 'User' };
    }
  };

  const userInfo = getUserDisplayInfo();

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

        {/* Right Section: Role Switcher & Auth */}
        <div className="flex items-center space-x-4">
          
          {/* Register / Login CTA Button */}
          <button
            onClick={onOpenAuth}
            className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-blood-600 to-blood-700 hover:from-blood-500 hover:to-blood-600 text-white font-extrabold text-xs shadow-md glow-red flex items-center space-x-1.5 transition-all"
          >
            <UserPlus className="w-3.5 h-3.5" />
            <span>Donor Register / Login</span>
          </button>

          {/* Role Selector dropdown */}
          <div className="flex items-center space-x-2 bg-slate-900/90 p-1 rounded-xl border border-slate-800">
            <span className="text-xs text-slate-400 px-2 font-medium">Role:</span>
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
          </div>

        </div>

      </div>
    </header>
  );
}
