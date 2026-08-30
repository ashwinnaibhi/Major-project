import React from 'react';
import { Sparkles, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';

export default function MLPredictionBadge({ category = 'HIGH', score = 85.0 }) {
  const getTierDetails = (status) => {
    switch (status.toUpperCase()) {
      case 'HIGH':
        return {
          bg: 'bg-emerald-950/80 text-emerald-300 border-emerald-800',
          bar: 'bg-emerald-500',
          icon: CheckCircle2,
          label: 'High Availability'
        };
      case 'MEDIUM':
        return {
          bg: 'bg-amber-950/80 text-amber-300 border-amber-800',
          bar: 'bg-amber-500',
          icon: AlertTriangle,
          label: 'Medium Availability'
        };
      default:
        return {
          bg: 'bg-rose-950/80 text-rose-300 border-rose-800',
          bar: 'bg-rose-500',
          icon: XCircle,
          label: 'Low Availability'
        };
    }
  };

  const tier = getTierDetails(category);
  const Icon = tier.icon;

  return (
    <div className="space-y-1.5 min-w-[130px]">
      <div className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs font-semibold ${tier.bg}`}>
        <Sparkles className="w-3 h-3 animate-spin text-blood-400" />
        <Icon className="w-3.5 h-3.5" />
        <span>{tier.label}</span>
      </div>

      <div className="flex items-center space-x-2 text-[10px] font-semibold text-slate-400">
        <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${tier.bar}`}
            style={{ width: `${Math.min(score, 100)}%` }}
          />
        </div>
        <span className="text-white">{score}%</span>
      </div>
    </div>
  );
}
