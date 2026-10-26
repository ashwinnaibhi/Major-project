import React from 'react';
import { Droplet, Building2, ShieldAlert, ArrowRight, HeartPulse, Sparkles, CheckCircle2 } from 'lucide-react';

export default function RoleSelection({ onSelectRole }) {
  const roles = [
    {
      id: 'DONOR',
      title: 'Voluntary Donor Portal',
      subtitle: 'For individual donors and volunteers',
      description: 'Book blood donation appointments, earn verified donation certificates, and respond to urgent hospital requisitions in your taluk.',
      icon: Droplet,
      badge: 'Public & Donors',
      badgeColor: 'bg-blood-950 text-blood-400 border-blood-800',
      iconColor: 'bg-blood-700 text-white',
      accentColor: 'hover:border-blood-600',
      buttonText: 'Enter Donor Portal',
      features: ['Appointment booking', 'Emergency request alerts', 'Personal donation certificates']
    },
    {
      id: 'HOSPITAL',
      title: 'Hospital & Blood Bank Portal',
      subtitle: 'For authorized hospitals and clinics',
      description: 'Submit urgent blood requisitions, record verified donations, manage hospital blood reserves, and search nearby hospital stock.',
      icon: Building2,
      badge: 'Healthcare Providers',
      badgeColor: 'bg-sky-950 text-sky-400 border-sky-800',
      iconColor: 'bg-sky-700 text-white',
      accentColor: 'hover:border-sky-600',
      buttonText: 'Access Hospital Desk',
      features: ['Emergency requisitions', 'Hospital inventory tracking', 'Transfusion verification']
    },
    {
      id: 'ADMIN',
      title: 'System Administrator Desk',
      subtitle: 'For blood bank coordinators & staff',
      description: 'Supervise donor registries, inspect machine learning predictions, manage inventory stock, and oversee system requisitions.',
      icon: ShieldAlert,
      badge: 'Authorized Staff',
      badgeColor: 'bg-amber-950 text-amber-400 border-amber-800',
      iconColor: 'bg-amber-700 text-white',
      accentColor: 'hover:border-amber-600',
      buttonText: 'Access Admin Desk',
      features: ['Full donor registry', 'ML predictive simulation', 'System-wide analytics']
    }
  ];

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-8">
      <div className="text-center space-y-3 max-w-2xl mx-auto">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blood-950/80 border border-blood-800 text-blood-400 text-xs font-bold">
          <HeartPulse className="w-4 h-4 animate-pulse" />
          <span>HaemoPulse Access Portal</span>
        </div>
        <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          Select Your Access Role
        </h2>
        <p className="text-sm text-slate-400 leading-relaxed">
          HaemoPulse provides dedicated interfaces tailored for voluntary blood donors, healthcare facilities, and blood bank administrators.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {roles.map((r) => {
          const Icon = r.icon;
          return (
            <div
              key={r.id}
              className={`p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col justify-between transition-all duration-300 ${r.accentColor} space-y-6 hover:-translate-y-1`}
            >
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shadow-lg ${r.iconColor}`}>
                    <Icon className="w-6 h-6" />
                  </div>
                  <span className={`px-2.5 py-1 rounded-lg text-[10px] font-bold border ${r.badgeColor}`}>
                    {r.badge}
                  </span>
                </div>

                <div>
                  <h3 className="text-lg font-bold text-white">{r.title}</h3>
                  <p className="text-xs text-slate-400 font-medium">{r.subtitle}</p>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed">
                  {r.description}
                </p>

                <div className="space-y-2 pt-2 border-t border-slate-800/80">
                  {r.features.map((feat, idx) => (
                    <div key={idx} className="flex items-center space-x-2 text-[11px] text-slate-400">
                      <CheckCircle2 className="w-3.5 h-3.5 text-blood-400 flex-shrink-0" />
                      <span>{feat}</span>
                    </div>
                  ))}
                </div>
              </div>

              <button
                type="button"
                onClick={() => onSelectRole(r.id)}
                className="w-full py-3 px-4 rounded-xl bg-slate-900 hover:bg-blood-700 text-white font-bold text-xs flex items-center justify-center space-x-2 border border-slate-700 hover:border-blood-600 transition-all shadow-md group"
              >
                <span>{r.buttonText}</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
