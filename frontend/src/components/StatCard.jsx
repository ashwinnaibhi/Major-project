import React from 'react';

export default function StatCard({ title, value, subtitle, icon: Icon, trend, color = 'blood' }) {
  const colorMap = {
    blood: 'from-blood-600/20 to-blood-950/40 border-blood-900/50 text-blood-400',
    emerald: 'from-emerald-600/20 to-emerald-950/40 border-emerald-900/50 text-emerald-400',
    amber: 'from-amber-600/20 to-amber-950/40 border-amber-900/50 text-amber-400',
    blue: 'from-sky-600/20 to-sky-950/40 border-sky-900/50 text-sky-400',
  };

  return (
    <div className={`p-4 rounded-2xl glass-panel bg-gradient-to-br ${colorMap[color]} border glass-panel-hover flex flex-col justify-between`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">{title}</span>
        {Icon && (
          <div className="w-8 h-8 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-center">
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className="my-3">
        <h3 className="text-2xl font-extrabold text-white tracking-tight">{value}</h3>
        {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
      </div>

      {trend && (
        <div className="flex items-center space-x-1 text-[11px] font-medium text-emerald-400">
          <span>{trend}</span>
        </div>
      )}
    </div>
  );
}
