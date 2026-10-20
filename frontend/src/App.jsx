import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import AuthModal from './components/AuthModal';
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

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [activeRole, setActiveRole] = useState('ADMIN');
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  // Check if current route is /verify-email
  const isVerifyEmailRoute = window.location.pathname.startsWith('/verify-email');

  // Load persisted session from localStorage
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const savedUser = localStorage.getItem('haemopulse_user');
      if (savedUser) {
        return JSON.parse(savedUser);
      }
    } catch (e) {}
    return { name: 'System Admin', email: 'admin@bloodbank.org', role: 'ADMIN', isLoggedIn: true };
  });

  // Master Donors List
  const [donorsList, setDonorsList] = useState([]);

  // Master Requisitions List
  const [requestsList, setRequestsList] = useState([]);

  // Fetch initial data from backend SQL
  const fetchAllData = () => {
    fetch('http://localhost:8080/api/v1/donors')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setDonorsList(data);
      })
      .catch(() => {});

    fetch('http://localhost:8080/api/v1/requests')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setRequestsList(data);
      })
      .catch(() => {});
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  // Update localStorage when currentUser changes
  useEffect(() => {
    if (currentUser) {
      localStorage.setItem('haemopulse_user', JSON.stringify(currentUser));
    } else {
      localStorage.removeItem('haemopulse_user');
    }
  }, [currentUser]);

  // Handle Role Change
  const handleRoleChange = (newRole) => {
    setActiveRole(newRole);
    if (newRole === 'DONOR') {
      setActiveTab('donor_dashboard');
      if (!currentUser || currentUser.role !== 'DONOR') {
        const defaultDonor = donorsList.find(d => d.email === 'john.doe@email.com') || donorsList[0] || {
          id: 'DNR-1001', name: 'John Doe', email: 'john.doe@email.com', blood_group: 'O+', role: 'DONOR', is_verified: true, isLoggedIn: true
        };
        setCurrentUser({ ...defaultDonor, role: 'DONOR', isLoggedIn: true, is_verified: defaultDonor.is_verified ?? true });
      }
    } else {
      setActiveTab('dashboard');
    }
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

    // Refresh lists from DB
    fetchAllData();
  };

  // Handle Logout
  const handleLogout = () => {
    localStorage.removeItem('haemopulse_user');
    setCurrentUser({ name: 'System Admin', email: 'admin@bloodbank.org', role: 'ADMIN', isLoggedIn: true });
    setActiveRole('ADMIN');
    setActiveTab('dashboard');
  };

  // Hospital Request Creation with Immediate DB Sync
  const handleRequestCreated = async (newReq) => {
    const res = await fetch('http://localhost:8080/api/v1/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        hospital_name: newReq.hospital_name || newReq.hospital,
        hospital_address: newReq.hospital_address,
        contact_phone: newReq.contact_phone || '',
        blood_group: newReq.blood_group || newReq.blood,
        units_needed: parseInt(newReq.units_needed || newReq.units, 10),
        urgency_level: newReq.urgency_level || newReq.urgency,
        patient_name: newReq.patient_name || newReq.patient,
        district: newReq.district || null,
        taluk: newReq.taluk || null,
        latitude: newReq.latitude === '' || newReq.latitude === undefined ? null : newReq.latitude,
        longitude: newReq.longitude === '' || newReq.longitude === undefined ? null : newReq.longitude
      })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'The blood request could not be saved.');
    }
    setRequestsList(prev => [data, ...prev]);
    return data;
  };

  // Request Status Change with Immediate DB Sync
  const handleRequestStatusChange = async (id, newStatus) => {
    setRequestsList(prev => prev.map(r => ((r.id === id || r._id === id) ? { ...r, status: newStatus } : r)));

    try {
      await fetch(`http://localhost:8080/api/v1/requests/${id}/status?status=${encodeURIComponent(newStatus)}`, {
        method: 'PUT'
      });
    } catch (e) {}
  };

  // Delete Donor
  const handleDeleteDonor = (donorId) => {
    setDonorsList(prev => prev.filter(d => d.id !== donorId && d.donor_id !== donorId));
    fetch(`http://localhost:8080/api/v1/donors/${donorId}`, { method: 'DELETE' }).catch(() => {});
  };

  // Delete Request
  const handleRequestDeleted = (reqId) => {
    setRequestsList(prev => prev.filter(r => r.id !== reqId && r._id !== reqId));
    fetch(`http://localhost:8080/api/v1/requests/${reqId}`, { method: 'DELETE' }).catch(() => {});
  };

  // Render Page Content
  const renderContent = () => {
    // If donor tab selected
    if (activeRole === 'DONOR' || activeTab.startsWith('donor_')) {
      return (
        <DonorDashboard 
          currentUser={currentUser} 
          requestsList={requestsList} 
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
            donorsList={donorsList} 
            onDeleteDonor={handleDeleteDonor} 
          />
        );

      case 'emergency':
        return <EmergencySearch />;
      case 'ml_predictor':
        return <MLPredictorView />;
      case 'inventory':
        return <InventoryView />;
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
        return <AppointmentsView />;
      default:
        return <AdminDashboard onNavigate={(tab) => setActiveTab(tab)} donorsList={donorsList} onDeleteDonor={handleDeleteDonor} />;
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

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onAuthSuccess={handleAuthSuccess}
      />
    </div>
  );
}
