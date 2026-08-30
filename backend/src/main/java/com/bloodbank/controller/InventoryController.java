package com.bloodbank.controller;

import com.bloodbank.model.BloodInventory;
import com.bloodbank.repository.BloodInventoryRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api/v1/inventory")
@CrossOrigin(origins = "*")
public class InventoryController {

    @Autowired
    private BloodInventoryRepository inventoryRepository;

    @GetMapping
    public List<BloodInventory> getInventory() {
        return inventoryRepository.findAll();
    }
}
