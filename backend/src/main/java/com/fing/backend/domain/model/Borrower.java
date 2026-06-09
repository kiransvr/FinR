package com.fing.backend.domain.model;

import java.time.Instant;
import java.util.UUID;

public class Borrower {

    private UUID id;
    private String fullName;
    private String phoneNumber;
    private BorrowerStatus status;
    private Instant createdAt;
    private Instant updatedAt;

    public Borrower(UUID id, String fullName, String phoneNumber, BorrowerStatus status,
                    Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.fullName = fullName;
        this.phoneNumber = phoneNumber;
        this.status = status;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    public UUID getId() {
        return id;
    }

    public String getFullName() {
        return fullName;
    }

    public String getPhoneNumber() {
        return phoneNumber;
    }

    public BorrowerStatus getStatus() {
        return status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
