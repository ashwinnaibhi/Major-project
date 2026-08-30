-- Seed Data for Blood Bank Management System

-- 1. Users
INSERT INTO users (id, name, email, password, phone, role, status) VALUES
(1, 'System Admin', 'admin@bloodbank.org', '$2a$10$e7aW/Z.1M96jK4/8w401d.R.7sL.F7f8yS0xWkXk6y5n9z8qX8Jeq', '+1-800-555-0199', 'ROLE_ADMIN', 'ACTIVE'),
(2, 'City General Hospital', 'contact@cityhospital.org', '$2a$10$e7aW/Z.1M96jK4/8w401d.R.7sL.F7f8yS0xWkXk6y5n9z8qX8Jeq', '+1-800-555-0101', 'ROLE_HOSPITAL', 'ACTIVE'),
(3, 'St. Jude Emergency Center', 'emergency@stjude.org', '$2a$10$e7aW/Z.1M96jK4/8w401d.R.7sL.F7f8yS0xWkXk6y5n9z8qX8Jeq', '+1-800-555-0102', 'ROLE_HOSPITAL', 'ACTIVE'),
(4, 'John Doe (Donor)', 'john.doe@email.com', '$2a$10$e7aW/Z.1M96jK4/8w401d.R.7sL.F7f8yS0xWkXk6y5n9z8qX8Jeq', '+1-555-0144', 'ROLE_DONOR', 'ACTIVE'),
(5, 'Sarah Jenkins (Donor)', 'sarah.j@email.com', '$2a$10$e7aW/Z.1M96jK4/8w401d.R.7sL.F7f8yS0xWkXk6y5n9z8qX8Jeq', '+1-555-0145', 'ROLE_DONOR', 'ACTIVE'),
(6, 'Michael Brown (Donor)', 'mbrown@email.com', '$2a$10$e7aW/Z.1M96jK4/8w401d.R.7sL.F7f8yS0xWkXk6y5n9z8qX8Jeq', '+1-555-0146', 'ROLE_DONOR', 'ACTIVE'),
(7, 'Emily Davis (Donor)', 'emily.d@email.com', '$2a$10$e7aW/Z.1M96jK4/8w401d.R.7sL.F7f8yS0xWkXk6y5n9z8qX8Jeq', '+1-555-0147', 'ROLE_DONOR', 'ACTIVE'),
(8, 'Dr. Robert Vance (Staff)', 'staff.vance@bloodbank.org', '$2a$10$e7aW/Z.1M96jK4/8w401d.R.7sL.F7f8yS0xWkXk6y5n9z8qX8Jeq', '+1-800-555-0188', 'ROLE_STAFF', 'ACTIVE');

-- 2. Donors
INSERT INTO donors (id, user_id, blood_group, age, gender, location, distance_km, last_donation_date, last_donation_days, total_donations, donation_frequency_per_year, previous_response_rate, preferred_time, health_eligibility_score, availability_status, availability_score) VALUES
(1, 4, 'O+', 29, 'Male', 'Zone A (Central)', 3.5, '2026-03-15', 150, 4, 3, 0.95, 'Morning', 98, 'HIGH', 94.5),
(2, 5, 'A-', 34, 'Female', 'Zone B (North)', 6.2, '2026-04-10', 125, 6, 4, 0.88, 'Afternoon', 95, 'HIGH', 89.0),
(3, 6, 'B+', 42, 'Male', 'Zone A (Central)', 8.0, '2026-07-20', 24, 2, 1, 0.40, 'Evening', 85, 'LOW', 35.0),
(4, 7, 'AB+', 25, 'Female', 'Zone C (South)', 12.5, '2026-01-10', 215, 3, 2, 0.75, 'Morning', 92, 'MEDIUM', 68.5);

-- 3. Hospitals
INSERT INTO hospitals (id, user_id, hospital_name, license_number, address, contact_person, emergency_contact) VALUES
(1, 2, 'City General Hospital', 'HOSP-LIC-2024-8891', '100 Healthcare Blvd, Suite 400', 'Dr. Alice Smith', '+1-800-555-0101'),
(2, 3, 'St. Jude Emergency Center', 'HOSP-LIC-2024-9922', '450 Trauma Way, East Wing', 'Dr. Mark Johnson', '+1-800-555-0102');

-- 4. Blood Inventory
INSERT INTO blood_inventory (id, blood_group, component_type, units_available, expiry_date, status) VALUES
(1, 'O+', 'Whole Blood', 45, '2026-09-15', 'AVAILABLE'),
(2, 'O-', 'Whole Blood', 8, '2026-09-01', 'LOW_STOCK'),
(3, 'A+', 'Whole Blood', 32, '2026-09-20', 'AVAILABLE'),
(4, 'A-', 'Whole Blood', 12, '2026-08-30', 'AVAILABLE'),
(5, 'B+', 'Whole Blood', 28, '2026-09-10', 'AVAILABLE'),
(6, 'B-', 'Whole Blood', 5, '2026-08-25', 'LOW_STOCK'),
(7, 'AB+', 'Whole Blood', 18, '2026-09-25', 'AVAILABLE'),
(8, 'AB-', 'Whole Blood', 4, '2026-08-28', 'LOW_STOCK');

-- 5. Blood Requests
INSERT INTO blood_requests (id, hospital_id, blood_group, units_needed, urgency_level, patient_name, hospital_name, required_by_date, status, request_date) VALUES
(1, 1, 'O-', 4, 'EMERGENCY', 'Trauma Unit Patient #402', 'City General Hospital', '2026-08-14', 'PENDING', '2026-08-13 08:30:00'),
(2, 2, 'B-', 2, 'HIGH', 'Surgical Patient #109', 'St. Jude Emergency Center', '2026-08-15', 'APPROVED', '2026-08-12 14:15:00');

-- 6. Appointments
INSERT INTO appointments (id, donor_id, appointment_date, time_slot, status, created_at) VALUES
(1, 1, '2026-08-16', '10:00 AM', 'SCHEDULED', '2026-08-12 09:00:00'),
(2, 2, '2026-08-18', '02:30 PM', 'SCHEDULED', '2026-08-11 16:20:00');

-- 7. Notifications
INSERT INTO notifications (id, user_id, title, message, is_read, created_at) VALUES
(1, 4, 'Urgent O+ Blood Drive', 'Urgent call for O+ donors in Zone A. Click to schedule an appointment.', FALSE, '2026-08-13 07:00:00'),
(2, 2, 'Blood Request Submitted', 'Your request #1 for O- Whole Blood (4 units) has been logged as EMERGENCY.', TRUE, '2026-08-13 08:30:00');

-- 8. Audit Logs
INSERT INTO audit_logs (id, user_email, action, details, ip_address, timestamp) VALUES
(1, 'admin@bloodbank.org', 'USER_LOGIN', 'Successful login for admin account', '127.0.0.1', '2026-08-13 08:00:00'),
(2, 'contact@cityhospital.org', 'CREATE_BLOOD_REQUEST', 'Emergency blood request created for O- (4 units)', '192.168.1.50', '2026-08-13 08:30:00');
