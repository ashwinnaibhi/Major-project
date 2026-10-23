import React, { useState, useEffect } from 'react';
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

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

function normalizeRole(role) {
  const value = String(role || 'ADMIN').toUpperCase();
  if (value.startsWith('ROLE_')) return value.slice(5);
  return ['ADMIN', 'HOSPITAL', 'DONOR', 'STAFF'].includes(value) ? value : 'ADMIN';
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
    setActiveRole(newRole);
    setActiveTab(newRole === 'DONOR' ? 'donor_dashboard' : 'dashboard');
  };

  // Handle Login/Register Success
  const handleAuthSuccess = (authenticatedUser) => {
    setCurrentUser(authenticatedUser);
    const targetRole = authenticatedUser.role || 'DONOR';
    setActiveRole(targetRole);

    if (targetRole === 'DONOR') {
      setActiveTab('donor_dashboard');
    } else {
      setActiveTab('dashboard');
    }

  };

  // Handle Logout
  const handleLogout = () => {
    localStorage.removeItem('haemopulse_user');
    setCurrentUser(null);
    setActiveRole('DONOR');
    setActiveTab('donor_dashboard');
  };

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
        destination_longitude: newReq.destination_longitude ?? null
      })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Request was not saved (HTTP ${res.status}).`);
    setRequestsList(prev => [data, ...prev]);
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
    // If donor tab selected
    if (activeRole === 'DONOR' || activeTab.startsWith('donor_')) {
      return (
        <DonorDashboard 
          currentUser={currentUser?.role === 'DONOR' ? currentUser : null}
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
          return (
            <HospitalDashboard 
              donorsList={donorsList} 
              requestsList={requestsList} 
              onRequestCreated={handleRequestCreated} 
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
          />
        );

      case 'emergency':
        return <EmergencySearch donorsList={donorsList} requestsList={requestsList} currentUser={currentUser} activeRole={activeRole} />;
      case 'ml_predictor':
        return <MLPredictorView />;
      case 'inventory':
        return <InventoryView currentUser={currentUser} />;
      case 'requests':
        return (
          <RequestsView 
            requestsList={requestsList} 
            onRequestCreated={handleRequestCreated} 
            onRequestStatusChange={handleRequestStatusChange} 
            onRequestDeleted={handleRequestDeleted} 
          />
        );
      case 'appointments':
        return <AppointmentsView currentUser={currentUser} activeRole={activeRole} />;
      default:
        return <AdminDashboard onNavigate={(tab) => setActiveTab(tab)} currentUser={currentUser} donorsList={donorsList} requestsList={requestsList} onDeleteDonor={handleDeleteDonor} />;
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
        />
        
        <main className="flex-1 p-6 overflow-y-auto max-w-7xl mx-auto w-full">
          {renderContent()}
        </main>
      </div>

    </div>
  );
}
