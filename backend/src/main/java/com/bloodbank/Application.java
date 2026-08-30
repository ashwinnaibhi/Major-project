package com.bloodbank;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
        System.out.println("=================================================");
        System.out.println(" Blood Bank Backend Service Running on Port 8080 ");
        System.out.println(" H2 Console Available at: http://localhost:8080/h2-console ");
        System.out.println("=================================================");
    }
}
