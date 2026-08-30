-- Online Blood Bank Management System with ML Donor Availability Prediction
-- Relational Schema Script (3NF Normalized)

CREATE DATABASE IF NOT EXISTS blood_bank_db;
USE blood_bank_db;

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    role VARCHAR(20) NOT NULL, -- ROLE_ADMIN, ROLE_DONOR, ROLE_HOSPITAL, ROLE_STAFF
    status VARCHAR(20) DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 2. Donors Table
CREATE TABLE IF NOT EXISTS donors (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNIQUE,
    blood_group VARCHAR(5) NOT NULL,
    age INT NOT NULL,
    gender VARCHAR(10) NOT NULL,
    location VARCHAR(100) NOT NULL,
    distance_km DOUBLE DEFAULT 5.0,
    last_donation_date DATE,
    last_donation_days INT DEFAULT 120,
    total_donations INT DEFAULT 0,
    donation_frequency_per_year INT DEFAULT 2,
    previous_response_rate DOUBLE DEFAULT 0.8,
    preferred_time VARCHAR(20) DEFAULT 'Morning',
    health_eligibility_score INT DEFAULT 90,
    availability_status VARCHAR(20) DEFAULT 'HIGH', -- HIGH, MEDIUM, LOW
    availability_score DOUBLE DEFAULT 85.0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 3. Hospitals Table
CREATE TABLE IF NOT EXISTS hospitals (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNIQUE,
    hospital_name VARCHAR(150) NOT NULL,
    license_number VARCHAR(50) NOT NULL UNIQUE,
    address TEXT NOT NULL,
    contact_person VARCHAR(100) NOT NULL,
    emergency_contact VARCHAR(20) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 4. Blood Inventory Table
CREATE TABLE IF NOT EXISTS blood_inventory (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    blood_group VARCHAR(5) NOT NULL,
    component_type VARCHAR(30) DEFAULT 'Whole Blood', -- Whole Blood, Red Cells, Plasma, Platelets
    units_available INT NOT NULL DEFAULT 0,
    expiry_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'AVAILABLE', -- AVAILABLE, LOW_STOCK, EXPIRED
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 5. Blood Requests Table
CREATE TABLE IF NOT EXISTS blood_requests (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    hospital_id BIGINT NOT NULL,
    blood_group VARCHAR(5) NOT NULL,
    units_needed INT NOT NULL,
    urgency_level VARCHAR(20) NOT NULL, -- EMERGENCY, HIGH, NORMAL
    patient_name VARCHAR(100) NOT NULL,
    hospital_name VARCHAR(150) NOT NULL,
    required_by_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, APPROVED, FULFILLED, REJECTED
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE
);

-- 6. Donations Table
CREATE TABLE IF NOT EXISTS donations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    donor_id BIGINT NOT NULL,
    blood_group VARCHAR(5) NOT NULL,
    units_donated INT NOT NULL DEFAULT 1,
    donation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes VARCHAR(255),
    FOREIGN KEY (donor_id) REFERENCES donors(id) ON DELETE CASCADE
);

-- 7. Appointments Table
CREATE TABLE IF NOT EXISTS appointments (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    donor_id BIGINT NOT NULL,
    appointment_date DATE NOT NULL,
    time_slot VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'SCHEDULED', -- SCHEDULED, COMPLETED, CANCELLED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (donor_id) REFERENCES donors(id) ON DELETE CASCADE
);

-- 8. Notifications Table
CREATE TABLE IF NOT EXISTS notifications (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 9. ML Predictions Table
CREATE TABLE IF NOT EXISTS ml_predictions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    donor_id BIGINT NOT NULL,
    response_probability DOUBLE NOT NULL,
    availability_score DOUBLE NOT NULL,
    availability_category VARCHAR(20) NOT NULL, -- High, Medium, Low
    recommendation TEXT,
    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (donor_id) REFERENCES donors(id) ON DELETE CASCADE
);

-- 10. Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_email VARCHAR(100),
    action VARCHAR(255) NOT NULL,
    details TEXT,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Fast Query Optimization
CREATE INDEX idx_donors_bg ON donors(blood_group);
CREATE INDEX idx_donors_location ON donors(location);
CREATE INDEX idx_inventory_bg ON blood_inventory(blood_group);
CREATE INDEX idx_requests_status ON blood_requests(status);
