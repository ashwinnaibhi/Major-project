package com.bloodbank.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import lombok.*;
import java.time.LocalDate;

@Document(collection = "donors")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Donor {
    @Id
    private String id;

    private String userId;
    private String donorId;
    private String name;
    private String email;
    private String bloodGroup;

    private int age;
    private String gender;
    private String location;
    private Double distanceKm;

    private LocalDate lastDonationDate;
    private int lastDonationDays;
    private int totalDonations;
    private int donationFrequencyPerYear;

    private Double previousResponseRate;
    private String preferredTime;
    private int healthEligibilityScore;

    private String availabilityStatus; // HIGH, MEDIUM, LOW
    private Double availabilityScore;  // 0 - 100
}
