package com.fing.backend.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public class CreateBorrowerRequest {

    @NotBlank
    @Size(min = 2, max = 150, message = "fullName must be between 2 and 150 characters")
    private String fullName;

    @NotBlank
    @Pattern(regexp = "^[0-9]{10,15}$", message = "phoneNumber must be 10 to 15 digits")
    private String phoneNumber;

    public String getFullName() {
        return fullName;
    }

    public void setFullName(String fullName) {
        this.fullName = fullName;
    }

    public String getPhoneNumber() {
        return phoneNumber;
    }

    public void setPhoneNumber(String phoneNumber) {
        this.phoneNumber = phoneNumber;
    }
}
