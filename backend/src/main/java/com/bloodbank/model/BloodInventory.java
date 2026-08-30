package com.bloodbank.model;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Entity
@Table(name = "blood_inventory")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class BloodInventory {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String bloodGroup;

    private String componentType = "Whole Blood";
    private int unitsAvailable;
    private LocalDate expiryDate;
    private String status = "AVAILABLE"; // AVAILABLE, LOW_STOCK, EXPIRED
}
