import React, { useId } from 'react';
import useLocationOptions from '../hooks/useLocationOptions';

const inputClass = 'w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:border-blood-500 focus:outline-none focus:ring-2 focus:ring-blood-500/20 disabled:cursor-not-allowed disabled:opacity-50';
const labelClass = 'mb-1.5 block text-xs font-semibold text-slate-300';

/** Shared dependent district/taluk, locality and optional coordinate fields. */
export default function LocationFields({
  value,
  onChange,
  requiredLocation = false,
  showCoordinates = true,
  showLocality = true,
  localityLabel = 'Locality / Village / Area (optional)',
}) {
  const { districts, taluksByDistrict, loading, error, notice } = useLocationOptions();
  const fieldId = useId().replace(/:/g, '');
  const district = value?.district || '';
  const taluk = value?.taluk || '';
  const taluks = district ? (taluksByDistrict[district] || []) : [];

  const update = (changes) => onChange({ ...value, ...changes });
  const districtExists = district && !districts.some((item) => item.toLowerCase() === district.toLowerCase());

  return (
    <div className="space-y-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
      <div>
        <h4 className="text-sm font-bold text-white">Location details</h4>
        <p className="mt-1 text-xs leading-5 text-slate-400">
          Choose a district first. Taluk choices depend on that district. Legacy zone labels are not converted automatically.
        </p>
        {notice && <p className="mt-1 text-xs leading-5 text-amber-300" role="note">{notice}</p>}
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-amber-800 bg-amber-950/40 px-3 py-2 text-xs text-amber-200">
          {error} Check that the Python backend is running.
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor={`${fieldId}-district`}>District{requiredLocation ? ' *' : ''}</label>
          <select
            id={`${fieldId}-district`}
            value={district}
            required={requiredLocation}
            onChange={(event) => update({ district: event.target.value, taluk: '' })}
            className={inputClass}
            disabled={loading}
          >
            <option value="">{loading ? 'Loading districts…' : 'Select district'}</option>
            {districtExists && <option value={district}>{district} (existing value)</option>}
            {districts.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>
        <div>
          <label className={labelClass} htmlFor={`${fieldId}-taluk`}>Taluk{requiredLocation ? ' *' : ''}</label>
          <select
            id={`${fieldId}-taluk`}
            value={taluk}
            required={requiredLocation || Boolean(district)}
            onChange={(event) => update({ taluk: event.target.value })}
            className={inputClass}
            disabled={!district || loading}
          >
            <option value="">{district ? 'Select taluk' : 'Select a district first'}</option>
            {taluks.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>
        {showLocality && (
          <div className="sm:col-span-2">
            <label className={labelClass} htmlFor={`${fieldId}-locality`}>{localityLabel}</label>
            <input
              id={`${fieldId}-locality`}
              type="text"
              value={value?.location || ''}
              onChange={(event) => update({ location: event.target.value })}
              className={inputClass}
              placeholder="Local area, village, landmark or location text"
              autoComplete="address-level3"
            />
          </div>
        )}
      </div>

      {showCoordinates && (
        <div>
          <div className="mb-2">
            <p className="text-xs font-semibold text-slate-300">Coordinates (optional)</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">Enter verified latitude and longitude together to enable straight-line distance calculations. Leave both blank if unknown; do not estimate or fabricate them.</p>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className={labelClass} htmlFor={`${fieldId}-latitude`}>Latitude (-90 to 90)</label>
              <input
                id={`${fieldId}-latitude`}
                type="number"
                step="any"
                min="-90"
                max="90"
                value={value?.latitude ?? ''}
                onChange={(event) => update({ latitude: event.target.value === '' ? null : event.target.value })}
                className={inputClass}
                placeholder="e.g. 12.9716"
              />
            </div>
            <div>
              <label className={labelClass} htmlFor={`${fieldId}-longitude`}>Longitude (-180 to 180)</label>
              <input
                id={`${fieldId}-longitude`}
                type="number"
                step="any"
                min="-180"
                max="180"
                value={value?.longitude ?? ''}
                onChange={(event) => update({ longitude: event.target.value === '' ? null : event.target.value })}
                className={inputClass}
                placeholder="e.g. 77.5946"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
