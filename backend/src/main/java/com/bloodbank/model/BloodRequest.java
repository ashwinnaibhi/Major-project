package com.bloodbank.model;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Entity
@Table(name = "blood_requests")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class BloodRequest {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Long hospitalId;
    private String bloodGroup;
    private int unitsNeeded;
    private String urgencyLevel; // EMERGENCY, HIGH, NORMAL
    private String patientName;
    private String hospitalName;
    private LocalDate requiredByDate;
    private String status = "PENDING"; // PENDING, APPROVED, FULFILLED, REJECTED
    private LocalDateTime requestDate = LocalDateTime.now();
}
