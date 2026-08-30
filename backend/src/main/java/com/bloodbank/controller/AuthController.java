package com.bloodbank.controller;

import com.bloodbank.model.User;
import com.bloodbank.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/auth")
@CrossOrigin(origins = "*")
public class AuthController {

    @Autowired
    private UserRepository userRepository;

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody Map<String, String> credentials) {
        String email = credentials.get("email");
        String password = credentials.get("password");

        Optional<User> userOpt = userRepository.findByEmail(email);
        if (userOpt.isPresent()) {
            User user = userOpt.get();
            Map<String, Object> response = new HashMap<>();
            response.put("token", "jwt-token-for-" + user.getId() + "-" + user.getRole());
            response.put("user", user);
            return ResponseEntity.ok(response);
        }

        Map<String, String> err = new HashMap<>();
        err.put("message", "Invalid credentials");
        return ResponseEntity.status(401).body(err);
    }
}
