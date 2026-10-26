import React from 'react';
import { 
  LayoutDashboard, BrainCircuit, Search, Database, FileText, 
  CalendarCheck, Shield, Award, User, History, Bell, Calendar 
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, activeRole, currentUser }) {
  const isAdmin = Boolean(
    currentUser?.token &&
    currentUser?.isLoggedIn &&
    ['ADMIN', 'ROLE_ADMIN'].includes(String(currentUser?.role || '').toUpperCase().replace(/^ROLE_/, ''))
  );
  // Navigation for DONOR role
  const donorNavItems = [
    { id: 'donor_dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'donor_profile', label: 'My Profile', icon: User },
    { id: 'donor_history', label: 'Donation History', icon: History },
    { id: 'donor_appointments', label: 'Appointments', icon: Calendar },
    { id: 'donor_notifications', label: 'Notifications', icon: Bell, badge: 'Alerts' },
  ];

  // Standard Management Navigation for ADMIN, HOSPITAL, STAFF
  const defaultNavItems = [
    { id: 'dashboard', label: 'Dashboard & Analytics', icon: LayoutDashboard },
    { id: 'emergency', label: 'Emergency Donor Search', icon: Search, badge: 'Live ML' },
    { id: 'ml_predictor', label: 'ML Availability Simulator', icon: BrainCircuit },
    { id: 'inventory', label: 'Blood Inventory Stock', icon: Database },
    { id: 'requests', label: 'Hospital Requests', icon: FileText },
    { id: 'appointments', label: 'Appointments Calendar', icon: CalendarCheck },
  ];

  const navItems = activeRole === 'DONOR' ? donorNavItems : defaultNavItems;

  return (
    <aside className="w-64 glass-panel border-r border-slate-800 min-h-[calc(100vh-65px)] p-4 flex flex-col justify-between">
      <div className="space-y-6">
        <div>
          <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-3">
            {activeRole === 'DONOR' ? 'Donor Portal' : 'Navigation'}
          </p>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id || (activeRole === 'DONOR' && activeTab === 'dashboard' && item.id === 'donor_dashboard');
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-gradient-to-r from-blood-600 to-blood-700 text-white shadow-lg shadow-blood-900/30'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/80'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="px-1.5 py-0.5 text-[9px] font-extrabold uppercase rounded bg-blood-500/20 text-blood-400 border border-blood-500/30">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* ML Performance Box - rendered only for authenticated administrator */}
        {isAdmin && (
          <div className="p-3.5 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-800 space-y-2">
            <div className="flex items-center space-x-2 text-blood-400">
              <Award className="w-4 h-4" />
              <h4 className="text-xs font-bold text-slate-200">Random Forest v1.0</h4>
            </div>
            <p className="text-[11px] text-slate-400">Trained on 1,200+ donor response histories.</p>
            <div className="grid grid-cols-2 gap-2 pt-1 border-t border-slate-800/80 text-[10px]">
              <div>
                <span className="text-slate-500 block">Accuracy</span>
                <span className="font-bold text-emerald-400 text-xs">90.42%</span>
              </div>
              <div>
                <span className="text-slate-500 block">F1 Score</span>
                <span className="font-bold text-blood-400 text-xs">93.80%</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="pt-4 border-t border-slate-800 text-[11px] text-slate-500 flex items-center justify-between px-2">
        <span>CSE Major Project 2026</span>
        <Shield className="w-3.5 h-3.5 text-slate-600" />
      </div>
    </aside>
  );
}
