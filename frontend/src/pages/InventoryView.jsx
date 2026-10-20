import React, { useState } from 'react';
import { Database, Plus, Trash2, AlertTriangle, CheckCircle2 } from 'lucide-react';

export default function InventoryView({ onDeleteInventoryItem }) {
  const [inventory, setInventory] = useState([
    { id: 1, blood_group: 'O+', component: 'Whole Blood', units: 45, status: 'AVAILABLE', expiry: '2026-09-15' },
    { id: 2, blood_group: 'O-', component: 'Whole Blood', units: 8, status: 'LOW_STOCK', expiry: '2026-09-01' },
    { id: 3, blood_group: 'A+', component: 'Whole Blood', units: 32, status: 'AVAILABLE', expiry: '2026-09-20' },
    { id: 4, blood_group: 'A-', component: 'Whole Blood', units: 12, status: 'AVAILABLE', expiry: '2026-08-30' },
    { id: 5, blood_group: 'B+', component: 'Whole Blood', units: 28, status: 'AVAILABLE', expiry: '2026-09-10' },
    { id: 6, blood_group: 'B-', component: 'Whole Blood', units: 5, status: 'LOW_STOCK', expiry: '2026-08-25' },
    { id: 7, blood_group: 'AB+', component: 'Whole Blood', units: 18, status: 'AVAILABLE', expiry: '2026-09-25' },
    { id: 8, blood_group: 'AB-', component: 'Whole Blood', units: 4, status: 'LOW_STOCK', expiry: '2026-08-28' },
  ]);

  const [newUnits, setNewUnits] = useState({ group: 'O+', count: 5 });

  const handleAddStock = async () => {
    setInventory(prev => prev.map(item => {
      if (item.blood_group === newUnits.group) {
        const updated = item.units + parseInt(newUnits.count);
        return {
          ...item,
          units: updated,
          status: updated > 10 ? 'AVAILABLE' : 'LOW_STOCK'
        };
      }
      return item;
    }));

    // Send SQL POST API
    fetch('http://localhost:8080/api/v1/inventory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ blood_group: newUnits.group, units_available: parseInt(newUnits.count) })
    }).catch(() => {});
  };

  const handleDeleteItem = (id) => {
    setInventory(prev => prev.filter(item => item.id !== id));
    fetch(`http://localhost:8080/api/v1/inventory/${id}`, { method: 'DELETE' }).catch(() => {});
    if (onDeleteInventoryItem) onDeleteInventoryItem(id);
  };

  return (
    <div className="space-y-6">
      
      <div className="p-6 rounded-2xl glass-panel border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs font-semibold text-blood-400 mb-1">
            <Database className="w-4 h-4" />
            <span>SQL Relational Database Stock Repository</span>
          </div>
          <h2 className="text-2xl font-black text-white">Blood Inventory Stock Management</h2>
          <p className="text-xs text-slate-400">Dynamically add units, update stock, or delete inventory rows from SQL database.</p>
        </div>

        {/* Quick Stock Add */}
        <div className="flex items-center space-x-2 bg-slate-900 p-2 rounded-xl border border-slate-800">
          <select
            value={newUnits.group}
            onChange={(e) => setNewUnits({ ...newUnits, group: e.target.value })}
            className="bg-transparent text-xs font-bold text-white focus:outline-none px-2"
          >
            {['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'].map(g => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
          <input
            type="number"
            min="1"
            value={newUnits.count}
            onChange={(e) => setNewUnits({ ...newUnits, count: parseInt(e.target.value) || 0 })}
            className="w-16 bg-slate-800 border border-slate-700 text-white text-xs px-2 py-1 rounded-lg text-center"
          />
          <button
            onClick={handleAddStock}
            className="px-3 py-1.5 rounded-lg bg-blood-600 hover:bg-blood-500 text-white text-xs font-bold flex items-center space-x-1"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Units</span>
          </button>
        </div>
      </div>

      <div className="p-5 rounded-2xl glass-panel border border-slate-800">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Blood Group</th>
                <th className="py-3 px-4">Component Type</th>
                <th className="py-3 px-4">Units Available</th>
                <th className="py-3 px-4">Expiry Date</th>
                <th className="py-3 px-4">Inventory Status</th>
                <th className="py-3 px-4">SQL Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {inventory.map((row) => (
                <tr key={row.id} className="hover:bg-slate-900/40">
                  <td className="py-3 px-4 text-base font-extrabold text-blood-400">{row.blood_group}</td>
                  <td className="py-3 px-4 text-slate-300">{row.component}</td>
                  <td className="py-3 px-4 font-bold text-white text-sm">{row.units} units</td>
                  <td className="py-3 px-4 font-mono text-slate-400">{row.expiry}</td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold flex items-center w-max space-x-1 ${
                      row.status === 'LOW_STOCK'
                        ? 'bg-amber-950 text-amber-400 border border-amber-800'
                        : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    }`}>
                      {row.status === 'LOW_STOCK' ? (
                        <>
                          <AlertTriangle className="w-3 h-3" />
                          <span>Low Stock Alert</span>
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Sufficient Stock</span>
                        </>
                      )}
                    </span>
                  </td>
                  <td className="py-3 px-4 flex items-center space-x-2">
                    <button
                      onClick={() => {
                        setInventory(prev => prev.map(i => i.id === row.id ? { ...i, units: i.units + 1 } : i));
                      }}
                      className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px]"
                    >
                      +1 Unit
                    </button>
                    <button
                      onClick={() => handleDeleteItem(row.id)}
                      title="Delete Inventory Stock from SQL DB"
                      className="p-1 rounded bg-rose-950 hover:bg-rose-900 text-rose-300 border border-rose-800 text-[11px]"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
