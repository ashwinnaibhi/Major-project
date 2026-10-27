import React, { useState, useEffect, useCallback } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import AdminDashboard from './pages/AdminDashboard';
import DonorDashboard from './pages/DonorDashboard';
import HospitalDashboard from './pages/HospitalDashboard';
import StaffDashboard from './pages/StaffDashboard';
import EmergencySearch from './pages/EmergencySearch';
import MLPredictorView from './pages/MLPredictorView';
import InventoryView from './pages/InventoryView';
import RequestsView from './pages/RequestsView';
import AppointmentsView from './pages/AppointmentsView';
import VerifyEmailPage from './pages/VerifyEmailPage';
import HospitalAuth from './pages/HospitalAuth';
import RoleSelection from './components/RoleSelection';
import { ShieldAlert } from 'lucide-react';

import { getApiBaseUrl } from './api/config';
const API_BASE = getApiBaseUrl();

function normalizeRole(role) {
  if (!role) return 'DONOR';
  const value = String(role).toUpperCase();
  const trimmed = value.startsWith('ROLE_') ? value.slice(5) : value;
  return ['ADMIN', 'HOSPITAL', 'DONOR', 'STAFF'].includes(trimmed) ? trimmed : 'DONOR';
}

function readPersistedUser() {
  try {
    const saved = JSON.parse(localStorage.getItem('haemopulse_user') || 'null');
    return saved && saved.token && saved.isLoggedIn ? { ...saved, role: normalizeRole(saved.role) } : null;
  } catch {
    return null;
  }
}

function roleFromSession(user) {
  return normalizeRole(user?.role);
}

export default function App() {
  const [currentUser, setCurrentUser] = useState(readPersistedUser);
  const [activeTab, setActiveTab] = useState(() => readPersistedUser()?.role === 'DONOR' ? 'donor_dashboard' : 'dashboard');
  const [activeRole, setActiveRole] = useState(() => roleFromSession(readPersistedUser()));
  const [roleSwitchPrompt, setRoleSwitchPrompt] = useState(null);

  // Check if current route is /verify-email
  const isVerifyEmailRoute = window.location.pathname.startsWith('/verify-email');

  // Master Donors List
  const [donorsList, setDonorsList] = useState([]);

  // Master Requisitions List
  const [requestsList, setRequestsList] = useState([]);

  // Fetch protected data only with the current verified backend session.
  const fetchAllData = async (user = currentUser) => {
    if (!user?.token) {
      setDonorsList([]);
      setRequestsList([]);
      return;
    }
    const headers = { Authorization: `Bearer ${user.token}` };
    const userRole = String(user.role || '').toUpperCase().replace(/^ROLE_/, '');

    // Full donors directory is strictly restricted to administrator sessions
    if (userRole === 'ADMIN') {
      try {
        const response = await fetch(`${API_BASE}/api/v1/donors`, { headers });
        if (response.ok) {
          const data = await response.json();
          if (Array.isArray(data)) setDonorsList(data);
        } else {
          setDonorsList([]);
        }
      } catch {
        setDonorsList([]);
      }
    } else {
      setDonorsList([]);
    }

    try {
      const response = await fetch(`${API_BASE}/api/v1/requests`, { headers });
      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data)) setRequestsList(data);
      } else {
        setRequestsList([]);
      }
    } catch {
      setRequestsList([]);
    }
  };

  // Refresh only the authenticated request feed after a donor response; do not reload unrelated lists.
  const refreshRequests = async (user = currentUser) => {
    if (!user?.token) {
      setRequestsList([]);
      return [];
    }
    const response = await fetch(`${API_BASE}/api/v1/requests`, {
      headers: { Authorization: `Bearer ${user.token}` }
    });
    const data = await response.json().catch(() => null);
    if (!response.ok || !Array.isArray(data)) {
      throw new Error(data?.detail || `Emergency requests could not be refreshed (HTTP ${response.status}).`);
    }
    setRequestsList(data);
    return data;
  };

  useEffect(() => {
    fetchAllData(currentUser);
  }, [currentUser]);

  // Update localStorage when currentUser changes
  useEffect(() => {
    if (currentUser?.token && currentUser?.isLoggedIn) {
      localStorage.setItem('haemopulse_user', JSON.stringify(currentUser));
    } else {
      localStorage.removeItem('haemopulse_user');
    }
  }, [currentUser]);

  // The role selector changes the view only; it never manufactures a logged-in identity.
  const handleRoleChange = (newRole) => {
    if (newRole === 'ROLE_SELECT' || newRole === 'ROLE_SELECTION') {
      setActiveRole('ROLE_SELECTION');
      setActiveTab('role_select');
      return;
    }

    const currentRole = currentUser?.role;
    const isLoggedIn = Boolean(currentUser?.token && currentUser?.isLoggedIn);

    // If currently logged in under a different role, require explicit confirmation before switching
    if (isLoggedIn && currentRole && currentRole !== newRole) {
      setRoleSwitchPrompt({ fromRole: currentRole, toRole: newRole });
      return;
    }

    setActiveRole(newRole);
    setActiveTab(newRole === 'DONOR' ? 'donor_dashboard' : 'dashboard');
  };

  // Handle Login/Register Success
  const handleAuthSuccess = useCallback((authenticatedUser) => {
    const rawRole = authenticatedUser?.role || 'DONOR';
    const normalized = normalizeRole(rawRole);
    const sessionUser = {
      ...authenticatedUser,
      role: normalized,
      isLoggedIn: true
    };
    setCurrentUser(sessionUser);
    setActiveRole(normalized);

    if (normalized === 'DONOR') {
      setActiveTab('donor_dashboard');
    } else {
      setActiveTab('dashboard');
    }
  }, []);

  // Handle Logout safely with redirection to role-selection portal
  const handleLogout = useCallback((goToRoleSelect = true) => {
    localStorage.removeItem('haemopulse_user');
    localStorage.removeItem('token');
    setCurrentUser(null);
    if (goToRoleSelect) {
      setActiveRole('DONOR');
      setActiveTab('role_select');
    }
  }, []);

  // Persist requisitions before changing the UI. No optimistic/fake request rows.
  const handleRequestCreated = async (newReq) => {
    if (!currentUser?.token) throw new Error('Sign in with an authorized hospital account to create a blood request.');
    const res = await fetch(`${API_BASE}/api/v1/requests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${currentUser.token}` },
      body: JSON.stringify({
        hospital_name: newReq.hospital_name || newReq.hospital,
        hospital_address: newReq.hospital_address,
        contact_phone: newReq.contact_phone || '',
        blood_group: newReq.blood_group || newReq.blood,
        units_needed: Number.parseInt(newReq.units_needed ?? newReq.units, 10),
        urgency_level: newReq.urgency_level || newReq.urgency,
        patient_name: newReq.patient_name || newReq.patient,
        destination_latitude: newReq.destination_latitude ?? null,
        destination_longitude: newReq.destination_longitude ?? null,
        hospital_user_id: newReq.hospital_user_id ?? null,
        assigned_admin_user_id: newReq.assigned_admin_user_id ?? null
      })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Request was not saved (HTTP ${res.status}).`);
    setRequestsList(prev => [data, ...prev]);
    return data;
  };

  // Request notification routing is persisted by the backend; no optimistic recipient assignments.
  const handleRequestAssignmentsChange = async (id, assignments) => {
    if (!currentUser?.token) throw new Error('Sign in with an authorized admin account first.');
    const res = await fetch(`${API_BASE}/api/v1/requests/${id}/notification-assignments`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${currentUser.token}` },
      body: JSON.stringify({
        hospital_user_id: assignments.hospital_user_id ? Number(assignments.hospital_user_id) : null,
        assigned_admin_user_id: assignments.assigned_admin_user_id ? Number(assignments.assigned_admin_user_id) : null
      })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Notification routing update failed (HTTP ${res.status}).`);
    setRequestsList(prev => prev.map(r => (r.id === id ? { ...r, hospital_user_id: data.hospital_user_id, assigned_admin_user_id: data.assigned_admin_user_id } : r)));
    return data;
  };

  // Request status/deletion controls update the view only after the backend confirms success.
  const handleRequestStatusChange = async (id, newStatus) => {
    if (!currentUser?.token) throw new Error('Sign in with an authorized account first.');
    const res = await fetch(`${API_BASE}/api/v1/requests/${id}/status?status=${encodeURIComponent(newStatus)}`, {
      method: 'PUT', headers: { Authorization: `Bearer ${currentUser.token}` }
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Status update failed (HTTP ${res.status}).`);
    setRequestsList(prev => prev.map(r => ((r.id === id || r._id === id) ? { ...r, status: newStatus } : r)));
    return data;
  };

  const handleDeleteDonor = async (donorId) => {
    if (!currentUser?.token) throw new Error('Sign in with an administrator account first.');
    const res = await fetch(`${API_BASE}/api/v1/donors/${encodeURIComponent(donorId)}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${currentUser.token}` }
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Donor deletion failed (HTTP ${res.status}).`);
    setDonorsList(prev => prev.filter(d => d.id !== donorId && d.donor_id !== donorId));
    return data;
  };

  const handleRequestDeleted = async (reqId) => {
    if (!currentUser?.token) throw new Error('Sign in with an administrator account first.');
    const res = await fetch(`${API_BASE}/api/v1/requests/${reqId}`, {
      method: 'DELETE', headers: { Authorization: `Bearer ${currentUser.token}` }
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Request deletion failed (HTTP ${res.status}).`);
    setRequestsList(prev => prev.filter(r => r.id !== reqId && r._id !== reqId));
    return data;
  };

  // Render Page Content
  const renderContent = () => {
    const isHospital = Boolean(
      currentUser?.token &&
      currentUser?.isLoggedIn &&
      ['HOSPITAL', 'ROLE_HOSPITAL'].includes(String(currentUser?.role || '').toUpperCase())
    );

    // Role selection screen after logout or portal navigation
    if (activeTab === 'role_select') {
      return (
        <RoleSelection
          onSelectRole={(selectedRole) => {
            setActiveRole(selectedRole);
            setActiveTab(selectedRole === 'DONOR' ? 'donor_dashboard' : 'dashboard');
          }}
        />
      );
    }

    // If donor tab selected
    if (activeRole === 'DONOR' || activeTab.startsWith('donor_')) {
      return (
        <DonorDashboard 
          currentUser={['DONOR', 'ROLE_DONOR'].includes(String(currentUser?.role || '').toUpperCase()) ? currentUser : null}
          requestsList={requestsList} 
          onRefreshRequests={() => refreshRequests(currentUser)}
          onAuthSuccess={handleAuthSuccess}
          onLogout={handleLogout}
          activeSubTab={activeTab}
        />
      );
    }

    switch (activeTab) {
      case 'dashboard':
        if (activeRole === 'HOSPITAL') {
          if (!isHospital) {
            return (
              <HospitalAuth
                onAuthSuccess={handleAuthSuccess}
                onSwitchToDonor={() => handleRoleChange('DONOR')}
              />
            );
          }
          return (
            <HospitalDashboard 
              donorsList={donorsList} 
              requestsList={requestsList} 
              onRequestCreated={handleRequestCreated}
              currentUser={currentUser}
              onRefreshRequests={() => refreshRequests(currentUser)}
            />
          );
        }
        if (activeRole === 'STAFF') {
          return (
            <StaffDashboard 
              requestsList={requestsList} 
              onRequestStatusChange={handleRequestStatusChange} 
            />
          );
        }
        return (
          <AdminDashboard
            onNavigate={(tab) => setActiveTab(tab)}
            currentUser={currentUser}
            donorsList={donorsList}
            requestsList={requestsList}
            onDeleteDonor={handleDeleteDonor}
            onAuthSuccess={handleAuthSuccess}
            onLogout={handleLogout}
          />
        );

      case 'emergency':
        if (!isHospital) {
          return (
            <div className="flex flex-col items-center justify-center min-h-[50vh] p-6">
              <div className="w-full max-w-md p-6 rounded-2xl glass-panel border border-slate-800 text-center space-y-4 bg-slate-950/80 shadow-2xl">
                <div className="w-12 h-12 rounded-2xl bg-amber-950/80 border border-amber-800 flex items-center justify-center text-amber-400 mx-auto">
                  <ShieldAlert className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Access Restricted</h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Emergency Donor Search &amp; Alert is restricted to authenticated Hospital accounts only.
                  </p>
                </div>
              </div>
            </div>
          );
        }
        return <EmergencySearch donorsList={donorsList} requestsList={requestsList} currentUser={currentUser} activeRole={activeRole} />;
      case 'ml_predictor':
        if (!isHospital) {
          return (
            <div className="flex flex-col items-center justify-center min-h-[50vh] p-6">
              <div className="w-full max-w-md p-6 rounded-2xl glass-panel border border-slate-800 text-center space-y-4 bg-slate-950/80 shadow-2xl">
                <div className="w-12 h-12 rounded-2xl bg-amber-950/80 border border-amber-800 flex items-center justify-center text-amber-400 mx-auto">
                  <ShieldAlert className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Access Restricted</h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Hospital ML Availability Simulator is restricted to authenticated Hospital accounts only.
                  </p>
                </div>
              </div>
            </div>
          );
        }
        return <MLPredictorView currentUser={currentUser} />;
      case 'inventory':
        return <InventoryView currentUser={currentUser} />;
      case 'requests':
        return (
          <RequestsView 
            requestsList={requestsList} 
            onRequestCreated={handleRequestCreated} 
            onRequestStatusChange={handleRequestStatusChange} 
            onRequestDeleted={handleRequestDeleted}
            onRequestAssignmentsChange={handleRequestAssignmentsChange}
            currentUser={currentUser}
          />
        );
      case 'appointments':
        return <AppointmentsView currentUser={currentUser} activeRole={activeRole} />;
      default:
        return (
          <AdminDashboard
            onNavigate={(tab) => setActiveTab(tab)}
            currentUser={currentUser}
            donorsList={donorsList}
            requestsList={requestsList}
            onDeleteDonor={handleDeleteDonor}
            onAuthSuccess={handleAuthSuccess}
            onLogout={handleLogout}
          />
        );
    }
  };

  // If visiting /verify-email URL route
  if (isVerifyEmailRoute) {
    return <VerifyEmailPage onVerified={() => { window.location.href = '/'; }} />;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar
        activeRole={activeRole}
        handleRoleChange={handleRoleChange}
        currentUser={currentUser}
        onLogout={handleLogout}
        onOpenDonorPortal={() => handleRoleChange('DONOR')}
      />

      <div className="flex-1 flex">
        <Sidebar 
          activeTab={activeTab} 
          setActiveTab={setActiveTab} 
          activeRole={activeRole}
          currentUser={currentUser}
        />
        
        <main className="flex-1 p-6 overflow-y-auto max-w-7xl mx-auto w-full">
          {renderContent()}
        </main>
      </div>

      {/* Role Switch Confirmation Modal */}
      {roleSwitchPrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center space-x-3 pb-3 border-b border-slate-800">
              <div className="w-10 h-10 rounded-xl bg-blood-950 border border-blood-800 flex items-center justify-center text-blood-400">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Role Switch Confirmation</h3>
                <p className="text-xs text-slate-400">Separate authentication is required for each portal.</p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              You are currently signed in as a <strong className="text-white">{roleSwitchPrompt.fromRole}</strong>.
              To access the <strong className="text-white">{roleSwitchPrompt.toRole}</strong> interface, an authorized {roleSwitchPrompt.toRole.toLowerCase()} account is required.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setRoleSwitchPrompt(null)}
                className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition"
              >
                Cancel / Stay Signed In
              </button>
              <button
                type="button"
                onClick={() => {
                  const targetRole = roleSwitchPrompt.toRole;
                  setRoleSwitchPrompt(null);
                  handleLogout(false);
                  setActiveRole(targetRole);
                  setActiveTab(targetRole === 'DONOR' ? 'donor_dashboard' : 'dashboard');
                }}
                className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-blood-700 hover:bg-blood-600 text-white text-xs font-bold transition"
              >
                Log Out &amp; Continue
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
