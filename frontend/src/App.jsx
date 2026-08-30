import React, { useState } from 'react';
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

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [activeRole, setActiveRole] = useState('ADMIN');
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  // 1. Master Donors List (Shared globally)
  const [donorsList, setDonorsList] = useState([
    {
      id: 'DNR-1001', name: 'John Doe', email: 'john.doe@email.com', blood: 'O+', location: 'Zone A (Central)',
      distance: 3.5, lastDonated: '150 days ago', freq: '3/year', prevResp: '95%', phone: '+1-555-0144',
      availabilityScore: 94.5, category: 'HIGH', total_donations: 4, last_donation_days: 150, preferred_time: 'Morning'
    },
    {
      id: 'DNR-1002', name: 'Sarah Jenkins', email: 'sarah.j@email.com', blood: 'A-', location: 'Zone B (North)',
      distance: 6.2, lastDonated: '125 days ago', freq: '4/year', prevResp: '88%', phone: '+1-555-0145',
      availabilityScore: 89.0, category: 'HIGH', total_donations: 6, last_donation_days: 125, preferred_time: 'Afternoon'
    },
    {
      id: 'DNR-1003', name: 'Michael Brown', email: 'mbrown@email.com', blood: 'B+', location: 'Zone A (Central)',
      distance: 8.0, lastDonated: '24 days ago', freq: '1/year', prevResp: '40%', phone: '+1-555-0146',
      availabilityScore: 35.0, category: 'LOW', total_donations: 2, last_donation_days: 24, preferred_time: 'Evening'
    },
    {
      id: 'DNR-1004', name: 'Emily Davis', email: 'emily.d@email.com', blood: 'AB+', location: 'Zone C (South)',
      distance: 12.5, lastDonated: '215 days ago', freq: '2/year', prevResp: '75%', phone: '+1-555-0147',
      availabilityScore: 68.5, category: 'MEDIUM', total_donations: 3, last_donation_days: 215, preferred_time: 'Morning'
    }
  ]);

  // 2. Master Requisitions List (Shared globally)
  const [requestsList, setRequestsList] = useState([
    {
      id: 'REQ-402', hospital_name: 'City General Hospital', hospital: 'City General Hospital',
      blood_group: 'O-', blood: 'O-', units_needed: 4, units: 4, urgency_level: 'EMERGENCY', urgency: 'EMERGENCY',
      patient_name: 'Trauma Unit Patient #402', patient: 'Trauma Unit Patient #402', status: 'PENDING', request_date: '2026-08-13 08:30'
    },
    {
      id: 'REQ-109', hospital_name: 'St. Jude Emergency Center', hospital: 'St. Jude Emergency Center',
      blood_group: 'B-', blood: 'B-', units_needed: 2, units: 2, urgency_level: 'HIGH', urgency: 'HIGH',
      patient_name: 'Surgical Patient #109', patient: 'Surgical Patient #109', status: 'APPROVED', request_date: '2026-08-12 14:15'
    }
  ]);

  const [currentUser, setCurrentUser] = useState({ name: 'System Admin', email: 'admin@bloodbank.org', role: 'ADMIN' });

  // Handle Role Selection (Resets activeTab to dashboard so user returns to selected role page)
  const handleRoleChange = (newRole) => {
    setActiveRole(newRole);
    setActiveTab('dashboard');
  };

  const handleAuthSuccess = (newDonor) => {
    const formattedDonor = {
      id: newDonor.donor_id || `DNR-${Math.floor(1000 + Math.random() * 9000)}`,
      name: newDonor.name,
      email: newDonor.email,
      blood: newDonor.blood_group || 'O+',
      blood_group: newDonor.blood_group || 'O+',
      location: newDonor.location || 'Zone A (Central)',
      distance: 4.0,
      lastDonated: '180 days ago',
      freq: '2/year',
      prevResp: '90%',
      phone: newDonor.phone || '+1-555-0199',
      availabilityScore: 91.5,
      category: 'HIGH',
      total_donations: 0,
      last_donation_days: 180,
      preferred_time: newDonor.preferred_time || 'Morning'
    };

    setDonorsList(prev => [formattedDonor, ...prev]);
    setCurrentUser(formattedDonor);
    setActiveRole('DONOR');
    setActiveTab('dashboard');
  };

  const handleRequestCreated = (newReq) => {
    setRequestsList(prev => [newReq, ...prev]);
    // POST to backend API
    fetch('http://localhost:8080/api/v1/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newReq)
    }).catch(() => {});
  };

  const handleRequestStatusChange = (id, newStatus) => {
    setRequestsList(prev => prev.map(r => (r.id === id || r._id === id) ? { ...r, status: newStatus } : r));
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        if (activeRole === 'DONOR') return <DonorDashboard currentUser={currentUser} requestsList={requestsList} />;
        if (activeRole === 'HOSPITAL') return <HospitalDashboard donorsList={donorsList} requestsList={requestsList} onRequestCreated={handleRequestCreated} />;
        if (activeRole === 'STAFF') return <StaffDashboard donorsList={donorsList} requestsList={requestsList} onRequestStatusChange={handleRequestStatusChange} />;
        return <AdminDashboard onNavigate={(tab) => setActiveTab(tab)} donorsList={donorsList} />;
      case 'emergency':
        return <EmergencySearch donorsList={donorsList} />;
      case 'ml_predictor':
        return <MLPredictorView />;
      case 'inventory':
        return <InventoryView />;
      case 'requests':
        return <RequestsView requestsList={requestsList} onRequestCreated={handleRequestCreated} onRequestStatusChange={handleRequestStatusChange} />;
      case 'appointments':
        return <AppointmentsView />;
      default:
        return <AdminDashboard onNavigate={(tab) => setActiveTab(tab)} donorsList={donorsList} />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar
        activeRole={activeRole}
        handleRoleChange={handleRoleChange}
        onOpenAuth={() => setIsAuthOpen(true)}
        currentUser={currentUser}
      />

      <div className="flex-1 flex">
        <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
        
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
