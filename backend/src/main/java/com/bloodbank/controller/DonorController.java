package com.bloodbank.controller;

import com.bloodbank.model.Donor;
import com.bloodbank.repository.DonorRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/donors")
@CrossOrigin(origins = "*")
public class DonorController {

    @Autowired
    private DonorRepository donorRepository;

    @GetMapping
    public List<Donor> getAllDonors(@RequestParam(required = false) String bloodGroup) {
        if (bloodGroup != null && !bloodGroup.isEmpty()) {
            return donorRepository.findByBloodGroup(bloodGroup);
        }
        return donorRepository.findAll();
    }

    @GetMapping("/emergency-search")
    public ResponseEntity<?> emergencySearch(@RequestParam String bloodGroup) {
        List<Donor> rankedDonors = donorRepository.findByBloodGroupOrderByAvailabilityScoreDesc(bloodGroup);
        Map<String, Object> response = new HashMap<>();
        response.put("requested_blood_group", bloodGroup);
        response.put("total_matched", rankedDonors.size());
        response.put("donors", rankedDonors);
        return ResponseEntity.ok(response);
    }
}
