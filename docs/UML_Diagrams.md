# UML System Architecture Diagrams

This document contains standard UML diagrams for the **Online Blood Bank Management System with Donor Availability Prediction using Machine Learning**.

---

## 1. USE CASE DIAGRAM

```mermaid
graph TD
    subgraph Users ["System Actors & Roles"]
        Admin(("System Admin"))
        Donor(("Donor"))
        Hospital(("Hospital / Doctor"))
        Staff(("Blood Bank Staff"))
    end

    subgraph System ["Blood Bank Management System"]
        UC1["Register & Authenticate (JWT)"]
        UC2["Manage Users & System Roles"]
        UC3["View Analytics Dashboard"]
        UC4["Search Blood Stock Inventory"]
        UC5["Create Emergency Blood Request"]
        UC6["Run ML Availability Prediction"]
        UC7["Schedule Donation Appointment"]
        UC8["Verify & Update Blood Stock"]
        UC9["Dispatch Emergency Donor Alert"]
        UC10["Generate PDF Reports"]
    end

    Admin --> UC1
    Admin --> UC2
    Admin --> UC3
    Admin --> UC6
    Admin --> UC10

    Hospital --> UC1
    Hospital --> UC4
    Hospital --> UC5
    Hospital --> UC9

    Donor --> UC1
    Donor --> UC6
    Donor --> UC7

    Staff --> UC1
    Staff --> UC4
    Staff --> UC8
    Staff --> UC7

    UC5 ..> UC6 : "<<include>>"
    UC6 ..> UC9 : "<<extend>>"
```

---

## 2. CLASS DIAGRAM

```mermaid
classDiagram
    class User {
        +Long id
        +String name
        +String email
        +String password
        +String role
        +String status
        +login()
        +register()
    }

    class Donor {
        +Long id
        +String bloodGroup
        +int age
        +String gender
        +String location
        +Double distanceKm
        +LocalDate lastDonationDate
        +int totalDonations
        +Double previousResponseRate
        +Double availabilityScore
        +String availabilityStatus
        +updateAvailability()
    }

    class Hospital {
        +Long id
        +String hospitalName
        +String licenseNumber
        +String address
        +String emergencyContact
        +requestBlood()
    }

    class BloodInventory {
        +Long id
        +String bloodGroup
        +String componentType
        +int unitsAvailable
        +LocalDate expiryDate
        +String status
        +updateStock()
    }

    class BloodRequest {
        +Long id
        +Long hospitalId
        +String bloodGroup
        +int unitsNeeded
        +String urgencyLevel
        +String status
        +approveRequest()
    }

    class MLPrediction {
        +Long id
        +Long donorId
        +Double responseProbability
        +Double availabilityScore
        +String category
        +String recommendation
        +predictAvailability()
    }

    User "1" <|-- "1" Donor
    User "1" <|-- "1" Hospital
    Hospital "1" -- "0..*" BloodRequest : creates
    Donor "1" -- "0..*" MLPrediction : evaluated_by
    BloodInventory "0..*" -- "1" BloodRequest : fulfills
```

---

## 3. SEQUENCE DIAGRAM (Emergency Blood Request & ML Donor Dispatch Workflow)

```mermaid
sequenceDiagram
    autonumber
    actor Hospital as Hospital User
    participant Frontend as React Frontend
    participant Backend as Spring Boot API
    participant ML as Python ML Service
    participant DB as MySQL Database
    actor Donor as High-Availability Donor

    Hospital->>Frontend: Select Blood Group & Create Emergency Request
    Frontend->>Backend: POST /api/v1/requests (urgency="EMERGENCY")
    Backend->>DB: Save BloodRequest (Status="PENDING")
    Backend->>DB: Query Donors by Blood Group
    DB-->>Backend: Return Candidate Donors List
    
    loop For Each Candidate Donor
        Backend->>ML: POST /predict (Donor Features)
        ML-->>Backend: Response {availability_score: 94.5, category: "HIGH"}
    end
    
    Backend->>Backend: Sort Donors by ML Availability Score (Desc)
    Backend-->>Frontend: Return ML Prioritized Donor Queue
    Frontend-->>Hospital: Display High-Availability Donor List
    
    Hospital->>Frontend: Click "Dispatch Emergency Alert"
    Frontend->>Backend: POST /api/v1/notifications/dispatch
    Backend->>Donor: Send SMS / Mobile Alert
    Backend->>DB: Log Audit Action & Notification
```

---

## 4. ACTIVITY DIAGRAM (Donor Availability Prediction & Classification)

```mermaid
stateDiagram-v2
    [*] --> ReceiveDonorRequest : Hospital Triggers Search
    
    state ReceiveDonorRequest {
        [*] --> FetchDonorProfile
        FetchDonorProfile --> ExtractFeatures : Load Age, Distance, Days, Response Rate
    }
    
    ReceiveDonorRequest --> MLInference : Feed to Random Forest Model
    
    state MLInference {
        [*] --> StandardizeNumericalFeatures
        StandardizeNumericalFeatures --> OneHotEncodeCategoricals
        OneHotEncodeCategoricals --> ComputeTreeProbabilities
        ComputeTreeProbabilities --> ReturnScore : Score (0 - 100)
    }

    MLInference --> CategorizationChoice
    
    state CategorizationChoice <<choice>>
    CategorizationChoice --> HighTier : Score >= 75
    CategorizationChoice --> MediumTier : 40 <= Score < 75
    CategorizationChoice --> LowTier : Score < 40
    
    HighTier --> PriorityDispatchQueue : Top Rank Priority Alert
    MediumTier --> BackupQueue : Secondary Reserve
    LowTier --> FilterOutQueue : Exclude from Alert
    
    PriorityDispatchQueue --> [*] : Alert Sent
```
