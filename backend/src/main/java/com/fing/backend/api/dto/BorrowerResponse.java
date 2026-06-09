package com.fing.backend.api.dto;

import com.fing.backend.domain.model.Borrower;

import java.time.Instant;
import java.util.UUID;

public class BorrowerResponse {

    private UUID id;
    private String fullName;
    private String phoneNumber;
    private String status;
    private Instant createdAt;
    private Instant updatedAt;

    public static BorrowerResponse fromDomain(Borrower borrower) {
        BorrowerResponse response = new BorrowerResponse();
        response.id = borrower.getId();
        response.fullName = borrower.getFullName();
        response.phoneNumber = borrower.getPhoneNumber();
        response.status = borrower.getStatus().name();
        response.createdAt = borrower.getCreatedAt();
        response.updatedAt = borrower.getUpdatedAt();
        return response;
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

    public String getStatus() {
        return status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
