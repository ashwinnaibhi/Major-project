package com.bloodbank.model;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "ml_predictions")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class MLPrediction {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne
    @JoinColumn(name = "donor_id", nullable = false)
    private Donor donor;

    private Double responseProbability;
    private Double availabilityScore;
    private String availabilityCategory; // HIGH, MEDIUM, LOW

    @Column(columnDefinition = "TEXT")
    private String recommendation;

    private LocalDateTime predictedAt = LocalDateTime.now();
}
