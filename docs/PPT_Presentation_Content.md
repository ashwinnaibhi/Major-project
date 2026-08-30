# Major Project Presentation Content (15 Slides)

**Project Title**: Online Blood Bank Management System with Donor Availability Prediction using Machine Learning  
**Presented by**: B.E. / B.Tech Final Year Team  
**Department**: Computer Science & Engineering / AI & ML  

---

## SLIDE 1: Title Slide
* **Title**: Online Blood Bank Management System with Donor Availability Prediction using Machine Learning
* **Subtitle**: An AI-Driven Emergency Response Platform
* **Team Members**: [Student Name 1], [Student Name 2], [Student Name 3]
* **Guide**: [Guide Name], Associate Professor, Dept. of CSE
* **Institution**: [College Name & Logo]

---

## SLIDE 2: Project Overview & Motivation
* **Context**: Emergency blood transfusion is vital in trauma, surgeries, and critical care.
* **The Core Problem**: Conventional blood portals act as static inventory databases and rely on untargeted mass messaging during shortages, leading to low response rates, donor fatigue, and critical delays.
* **Our Solution**: An intelligent system integrating **Random Forest Machine Learning** to predict donor availability probabilities in real-time, sorting donors by response probability before dispatching emergency alerts.

---

## SLIDE 3: Objectives
1. Develop a supervised ML model to predict donor availability scores (0–100) during emergency shortages.
2. Analyze 11 multidimensional donor parameters (recency, frequency, distance, historical response rate, health score).
3. Classify donors into 3 operational tiers: **High (>75%)**, **Medium (40-75%)**, and **Low (<40%)**.
4. Reduce emergency response dispatch time by over 65%.
5. Implement an enterprise-grade full-stack web application with role-based access control (Admin, Donor, Hospital, Staff).

---

## SLIDE 4: Literature Survey & Research Gaps
* **Static Portals (2022)**: Managed inventory stock but lacked predictive intelligence.
* **Rule-Based KNN Classification (2023)**: Considered age and blood group but omitted temporal donation intervals.
* **Offline RFTM Models (2024)**: Evaluated Decision Trees in isolation without REST API integration or web UI.
* **Our Research Contribution**: Real-time integration of a trained Random Forest model into a Spring Boot REST API microservice and React single-page frontend.

---

## SLIDE 5: Technology Stack
* **Machine Learning**: Python 3.11, Scikit-Learn, Pandas, NumPy, Joblib, FastAPI
* **Backend API**: Java 17, Spring Boot 3.x, Spring Security, JWT Authentication, Spring Data JPA
* **Frontend UI**: React.js, Tailwind CSS, Lucide Icons, Recharts Analytics
* **Database**: MySQL 8.0 (3NF Normalized, 10 Relational Tables) / Embedded H2

---

## SLIDE 6: System Architecture Diagram
*(Features standard 4-tier decoupled diagram: Presentation Tier -> Spring Boot REST API -> MySQL Database & Python FastAPI ML Microservice)*

---

## SLIDE 7: Machine Learning Methodology & Features
* **Dataset**: 1,200 realistic donor profile records.
* **Input Features**:
  - `age`, `gender`, `blood_group`, `location`, `distance_km`
  - `last_donation_days` (Recency)
  - `donation_frequency` (Frequency)
  - `previous_response_rate` (Historical Reliability)
  - `preferred_time_slot`, `response_time_hrs`, `health_eligibility_score`
* **Target Output**: `availability_status` (Binary: 1 = Responded, 0 = Declined)

---

## SLIDE 8: ML Model Performance & Evaluation Matrix
* Benchmarked 3 algorithms on 20% test data split:

| Model Algorithm | Accuracy | Precision | Recall | F1 Score |
| :--- | :--- | :--- | :--- | :--- |
| **Random Forest** | **90.42%** | **89.69%** | **98.31%** | **93.80%** |
| **Decision Tree** | 87.92% | 91.11% | 92.66% | 91.88% |
| **Logistic Regression** | 82.92% | 87.78% | 89.27% | 88.52% |

* **Key Takeaway**: Random Forest achieved **98.31% Recall**, minimizing False Negatives in emergency scenarios.

---

## SLIDE 9: Relational Database Design (3NF)
* Designed 10 3NF normalized tables:
  1. `Users` (Authentication & Roles)
  2. `Donors` (Donor profile & ML score metrics)
  3. `Hospitals` (Hospital licenses & addresses)
  4. `BloodInventory` (Stock levels per ABO group)
  5. `BloodRequests` (Requisitions & urgency levels)
  6. `Donations` (Donation log history)
  7. `Appointments` (Booking slots)
  8. `Notifications` (Emergency alerts log)
  9. `MLPredictions` (Model predictions log)
  10. `AuditLogs` (Security audit trails)

---

## SLIDE 10: User Roles & Core Modules
* **Admin**: Executive analytics, user management, audit logs.
* **Donor**: Profile update, donation history, eligibility status, booking calendar.
* **Hospital**: Search blood stock, submit emergency requisitions, view prioritized donors.
* **Blood Bank Staff**: Verify stock, process requests, confirm appointment check-ins.

---

## SLIDE 11: Application Demonstration Screenshots
*(Include screenshots of Admin Dashboard, Emergency Search Queue, ML Simulator, and Inventory Table)*

---

## SLIDE 12: Emergency Donor Search Workflow
1. Hospital logs an emergency requisition for O-negative blood.
2. System triggers ML API microservice.
3. Random Forest pipeline computes availability probability for candidate donors.
4. Donors are ranked by score; **High Availability (>75%)** donors appear at top.
5. Operator clicks **1-Click Emergency Dispatch** to send immediate alert.

---

## SLIDE 13: Project Verification & Testing
* **ML Model Verification**: Cross-validated with confusion matrices & F1 score calculation.
* **Backend Verification**: Spring Security JWT unit tests & JPA endpoint validation.
* **Frontend Verification**: Build bundle optimization with zero linting/compilation errors.

---

## SLIDE 14: Future Enhancements
* Mobile Push Notifications (Firebase FCM / Twilio SMS).
* AI Chatbot for instant donor eligibility screening.
* Cloud deployment on Vercel, Render, and Railway.

---

## SLIDE 15: Conclusion & Q&A
* Successfully built an AI-powered Online Blood Bank Management System.
* Combined Random Forest ML (90.42% accuracy) with enterprise Spring Boot + React full-stack architecture.
* **Thank You! We invite your questions.**
