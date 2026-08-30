package com.bloodbank.controller;

import com.bloodbank.model.BloodRequest;
import com.bloodbank.repository.BloodRequestRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api/v1/requests")
@CrossOrigin(origins = "*")
public class BloodRequestController {

    @Autowired
    private BloodRequestRepository bloodRequestRepository;

    @GetMapping
    public List<BloodRequest> getAllRequests() {
        return bloodRequestRepository.findAll();
    }

    @PostMapping
    public BloodRequest createRequest(@RequestBody BloodRequest bloodRequest) {
        return bloodRequestRepository.save(bloodRequest);
    }
}
