import React from 'react';
import { Droplet, ShieldAlert, User, Cpu, LogOut, LogIn } from 'lucide-react';

export default function Navbar({ activeRole = 'DONOR', handleRoleChange, currentUser, onLogout, onOpenDonorPortal }) {
  const safeRole = activeRole || 'DONOR';
  const isAuthenticated = Boolean(currentUser?.token && currentUser?.isLoggedIn);
  const authenticatedRole = currentUser?.role;
  const isViewingOwnRole = isAuthenticated && authenticatedRole === safeRole;
  const name = isViewingOwnRole ? (currentUser.name || currentUser.email || 'Signed-in user') : (isAuthenticated ? `${currentUser.name || currentUser.email} (${authenticatedRole})` : 'Sign-in required');
  const title = isViewingOwnRole
    ? `${authenticatedRole} account`
    : (safeRole === 'ROLE_SELECTION' ? 'Choose account role' : `Viewing ${String(safeRole).toLowerCase()} interface`);

  return (
    <header className="sticky top-0 z-40 glass-panel border-b border-slate-800 px-4 md:px-6 py-3">
      <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blood-700 to-blood-500 flex items-center justify-center shadow-lg glow-red">
            <Droplet className="w-6 h-6 text-white fill-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-extrabold tracking-tight text-white">Haemo<span className="text-blood-500">Pulse</span></h1>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blood-950 text-blood-400 border border-blood-800">
                <Cpu className="w-3 h-3 mr-1" /> ML v1.0
              </span>
            </div>
            <p className="text-xs text-slate-400">Donor Availability &amp; Emergency Response Engine</p>
          </div>
        </div>

        <div className="hidden 2xl:flex items-center space-x-2 px-4 py-1.5 rounded-full bg-blood-950/60 border border-blood-900/50 text-blood-300 text-xs font-medium">
          <ShieldAlert className="w-4 h-4 text-blood-400" />
          <span>Emergency Blood Request Operations</span>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1 bg-slate-900/90 p-1 rounded-xl border border-slate-800">
            <span className="text-xs text-slate-400 px-2 font-medium">View:</span>
            {!isAuthenticated && (
              <button
                type="button"
                onClick={() => handleRoleChange('ROLE_SELECTION')}
                aria-pressed={activeRole === 'ROLE_SELECTION'}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${activeRole === 'ROLE_SELECTION' ? 'bg-blood-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'}`}
              >
                Roles Portal
              </button>
            )}
            {[
              { id: 'ADMIN', label: 'Admin' },
              { id: 'HOSPITAL', label: 'Hospital' },
              { id: 'DONOR', label: 'Donor' },
            ].map((role) => (
              <button
                key={role.id}
                type="button"
                onClick={() => handleRoleChange(role.id)}
                aria-pressed={activeRole === role.id}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${activeRole === role.id ? 'bg-blood-600 text-white shadow-md' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'}`}
              >
                {role.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 pl-2 xl:border-l border-slate-800">
            <div className="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center">
              <User className="w-5 h-5 text-blood-400" />
            </div>
            <div className="hidden sm:block text-left max-w-[220px]">
              <p className="text-xs font-semibold text-slate-200 truncate">{name}</p>
              <p className="text-[10px] text-slate-400">{title}</p>
            </div>
            {!isAuthenticated && activeRole === 'DONOR' && (
              <button type="button" onClick={onOpenDonorPortal} className="px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-bold flex items-center gap-1">
                <LogIn className="w-3.5 h-3.5" /><span>Donor sign in</span>
              </button>
            )}
            {!isAuthenticated && activeRole === 'HOSPITAL' && (
              <span className="rounded-xl border border-sky-900 bg-sky-950/50 px-2.5 py-1.5 text-xs font-semibold text-sky-200">Hospital sign-in required</span>
            )}
            {!isAuthenticated && activeRole === 'ADMIN' && (
              <span className="rounded-xl border border-amber-900 bg-amber-950/50 px-2.5 py-1.5 text-xs font-semibold text-amber-200">Admin auth required</span>
            )}
            {isAuthenticated && (
              <button type="button" onClick={onLogout} title="Log out" className="px-2.5 py-1.5 rounded-xl bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800 text-xs font-bold flex items-center gap-1">
                <LogOut className="w-3.5 h-3.5" /><span>Log out</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
