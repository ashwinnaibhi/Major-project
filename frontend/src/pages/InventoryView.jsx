import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Database, Plus, Trash2, AlertTriangle, CheckCircle2, RefreshCw } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';
const BLOOD_GROUPS = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'];
const COMPONENT_TYPES = ['Whole Blood'];

export default function InventoryView({ currentUser }) {
  const [inventory, setInventory] = useState([]);
  const [newUnits, setNewUnits] = useState({ group: 'O+', component: 'Whole Blood', count: '1', expiryDate: '' });
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [rowAction, setRowAction] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const pendingKeysRef = useRef(new Map());

  const authenticated = Boolean(currentUser?.token && currentUser?.isLoggedIn && ['ADMIN', 'STAFF', 'HOSPITAL'].includes(currentUser?.role));
  const apiRole = currentUser?.role;
  const headers = useCallback((extra = {}) => ({ ...extra, ...(currentUser?.token ? { Authorization: `Bearer ${currentUser.token}` } : {}) }), [currentUser?.token]);

  const loadInventory = useCallback(async () => {
    if (!authenticated) {
      setInventory([]);
      setError('Sign in with an authorized admin, hospital, or staff account to view the persisted inventory.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE}/api/v1/inventory`, { headers: headers() });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Unable to load inventory (HTTP ${response.status}).`);
      if (!Array.isArray(data)) throw new Error('Inventory API returned an unexpected response.');
      setInventory(data.map((row) => ({
        ...row,
        component: row.component_type || 'Whole Blood',
        units: Number(row.units_available || 0),
        expiry: row.expiry_date || '—',
        status: row.status || (Number(row.units_available || 0) > 10 ? 'AVAILABLE' : 'LOW_STOCK')
      })));
    } catch (err) {
      setInventory([]);
      setError(err.message || 'Unable to load inventory.');
    } finally {
      setLoading(false);
    }
  }, [authenticated, headers]);

  useEffect(() => { loadInventory(); }, [loadInventory]);

  const addStock = async ({ group, component, count }, actionKey = '') => {
    const quantity = Number(count);
    if (!Number.isInteger(quantity) || quantity <= 0 || quantity > 10000) {
      setError('Quantity must be a whole number between 1 and 10,000.');
      return;
    }
    if (!BLOOD_GROUPS.includes(group) || !COMPONENT_TYPES.includes(component)) {
      setError('Choose a supported blood group and component type.');
      return;
    }
    if (!currentUser?.token || !['ADMIN', 'STAFF'].includes(apiRole)) {
      setError('Stock additions require an authenticated admin or staff account.');
      return;
    }
    setSubmitting(true);
    setError('');
    setNotice('');
    const isExistingGroup = inventory.some((row) => row.blood_group === group);
    const expiryDate = isExistingGroup ? null : (newUnits.expiryDate || null);
    const signature = JSON.stringify({ group, component, quantity, expiryDate, actionKey: actionKey || '' });
    const idempotencyKey = actionKey || pendingKeysRef.current.get(signature) || (globalThis.crypto?.randomUUID ? globalThis.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`);
    if (!actionKey) pendingKeysRef.current.set(signature, idempotencyKey);
    try {
      const response = await fetch(`${API_BASE}/api/v1/inventory`, {
        method: 'POST',
        headers: headers({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ blood_group: group, component_type: component, units_available: quantity, expiry_date: expiryDate, idempotency_key: idempotencyKey })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Stock addition failed (HTTP ${response.status}).`);
      if (!data.persisted || !data.item) throw new Error('The server did not confirm a persisted inventory update.');
      setNotice(`${data.message || 'Stock persisted.'}${data.duplicate ? ' This duplicate submission was not applied twice.' : ''}`);
      if (!actionKey) pendingKeysRef.current.delete(signature);
      await loadInventory();
    } catch (err) {
      setError(err.message || 'Stock addition failed. The displayed quantities were not changed locally.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteItem = async (row) => {
    if (!currentUser?.token || apiRole !== 'ADMIN') {
      setError('Deleting inventory rows requires an authenticated administrator account.');
      return;
    }
    if (!window.confirm(`Delete the ${row.blood_group} inventory record? This cannot be undone.`)) return;
    setRowAction(String(row.id));
    setError('');
    setNotice('');
    try {
      const response = await fetch(`${API_BASE}/api/v1/inventory/${row.id}`, { method: 'DELETE', headers: headers() });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Delete failed (HTTP ${response.status}).`);
      setNotice(data.message || 'Inventory record deleted.');
      await loadInventory();
    } catch (err) {
      setError(err.message || 'Inventory deletion failed.');
    } finally {
      setRowAction('');
    }
  };

  return (
    <div className="space-y-6">
      <section className="p-6 rounded-2xl glass-panel border border-slate-800 space-y-4">
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-blood-400 mb-1"><Database className="w-4 h-4" /><span>Persisted stock repository</span></div>
            <h2 className="text-2xl font-black text-white">Blood Inventory Stock Management</h2>
            <p className="text-xs text-slate-400 mt-1">Quantities update only after the database confirms the transaction. Expiry is required only when creating a missing blood-group row; this schema stores one expiry per group, not separate lots.</p>
          </div>
          <form className="flex flex-wrap items-end gap-2 bg-slate-900 p-3 rounded-xl border border-slate-800" onSubmit={(event) => { event.preventDefault(); addStock(newUnits); }}>
            <div><label htmlFor="stock-group" className="block text-[11px] text-slate-300 mb-1">Blood group</label><select id="stock-group" value={newUnits.group} onChange={(event) => setNewUnits({ ...newUnits, group: event.target.value })} className="bg-slate-950 border border-slate-700 rounded-lg text-xs font-bold text-white focus:outline-none px-2 py-2">{BLOOD_GROUPS.map((group) => <option key={group} value={group} className="bg-slate-950 text-white">{group}</option>)}</select></div>
            <div><label htmlFor="stock-component" className="block text-[11px] text-slate-300 mb-1">Component</label><select id="stock-component" value={newUnits.component} onChange={(event) => setNewUnits({ ...newUnits, component: event.target.value })} className="bg-slate-950 border border-slate-700 rounded-lg text-xs font-bold text-white focus:outline-none px-2 py-2">{COMPONENT_TYPES.map((component) => <option key={component} value={component} className="bg-slate-950 text-white">{component}</option>)}</select></div>
            <div><label htmlFor="stock-quantity" className="block text-[11px] text-slate-300 mb-1">Units to add</label><input id="stock-quantity" type="number" min="1" max="10000" step="1" required value={newUnits.count} onChange={(event) => setNewUnits({ ...newUnits, count: event.target.value })} className="w-24 bg-slate-950 border border-slate-700 text-white text-xs px-2 py-2 rounded-lg" /></div>
            <div><label htmlFor="stock-expiry" className="block text-[11px] text-slate-300 mb-1">Expiry (for new group)</label><input id="stock-expiry" type="date" value={newUnits.expiryDate} onChange={(event) => setNewUnits({ ...newUnits, expiryDate: event.target.value })} className="bg-slate-950 border border-slate-700 text-white text-xs px-2 py-2 rounded-lg" /></div>
            <button type="submit" disabled={submitting || !authenticated || !['ADMIN', 'STAFF'].includes(apiRole)} className="px-3 py-2 rounded-lg bg-blood-600 hover:bg-blood-500 disabled:opacity-50 text-white text-xs font-bold flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" />{submitting ? 'Saving…' : 'Add Units'}</button>
            <button type="button" onClick={loadInventory} disabled={loading} aria-label="Refresh inventory" className="px-2.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200"><RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /></button>
          </form>
        </div>
        {error && <div role="alert" className="p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-200 text-xs">{error}</div>}
        {notice && <div role="status" className="p-3 rounded-xl bg-emerald-950/60 border border-emerald-800 text-emerald-200 text-xs">{notice}</div>}
      </section>

      <section className="p-5 rounded-2xl glass-panel border border-slate-800">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800"><tr><th className="py-3 px-4">Blood Group</th><th className="py-3 px-4">Component Type</th><th className="py-3 px-4">Units Available</th><th className="py-3 px-4">Expiry Date</th><th className="py-3 px-4">Inventory Status</th><th className="py-3 px-4">Actions</th></tr></thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading && inventory.length === 0 && <tr><td colSpan="6" className="py-8 text-center text-slate-400">Loading persisted inventory…</td></tr>}
              {!loading && !error && inventory.length === 0 && <tr><td colSpan="6" className="py-8 text-center text-slate-500">No inventory rows are available in the database.</td></tr>}
              {inventory.map((row) => <tr key={row.id} className="hover:bg-slate-900/40"><td className="py-3 px-4 text-base font-extrabold text-blood-400">{row.blood_group}</td><td className="py-3 px-4 text-slate-300">{row.component}</td><td className="py-3 px-4 font-bold text-white text-sm">{row.units} units</td><td className="py-3 px-4 font-mono text-slate-400">{row.expiry}</td><td className="py-3 px-4"><span className={`px-2 py-0.5 rounded text-[10px] font-bold flex items-center w-max gap-1 ${row.status === 'LOW_STOCK' ? 'bg-amber-950 text-amber-400 border border-amber-800' : 'bg-emerald-950 text-emerald-400 border border-emerald-800'}`}>{row.status === 'LOW_STOCK' ? <><AlertTriangle className="w-3 h-3" />Low Stock Alert</> : <><CheckCircle2 className="w-3 h-3" />Sufficient Stock</>}</span></td><td className="py-3 px-4"><div className="flex items-center gap-2"><button type="button" disabled={submitting || !['ADMIN', 'STAFF'].includes(apiRole)} onClick={() => addStock({ group: row.blood_group, component: row.component, count: '1' })} className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 text-[11px]">+1 Unit</button><button type="button" disabled={rowAction === String(row.id) || apiRole !== 'ADMIN'} onClick={() => handleDeleteItem(row)} title="Delete inventory row (administrator only)" aria-label={`Delete ${row.blood_group} inventory`} className="p-1.5 rounded bg-rose-950 hover:bg-rose-900 disabled:opacity-40 text-rose-300 border border-rose-800"><Trash2 className="w-3.5 h-3.5" /></button></div></td></tr>)}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
