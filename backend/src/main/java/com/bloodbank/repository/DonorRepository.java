package com.bloodbank.repository;

import com.bloodbank.model.Donor;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.Optional;

@Repository
public interface DonorRepository extends MongoRepository<Donor, String> {
    List<Donor> findByBloodGroup(String bloodGroup);
    List<Donor> findByBloodGroupOrderByAvailabilityScoreDesc(String bloodGroup);
    Optional<Donor> findByUserId(String userId);
}
