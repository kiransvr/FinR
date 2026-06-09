package com.fing.backend.application.service;

import com.fing.backend.domain.model.Borrower;
import com.fing.backend.domain.model.BorrowerStatus;
import com.fing.backend.domain.port.BorrowerRepository;
import org.springframework.data.domain.Page;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.Locale;
import java.util.Optional;
import java.util.UUID;

@Service
public class BorrowerService {

    private final BorrowerRepository borrowerRepository;

    public BorrowerService(BorrowerRepository borrowerRepository) {
        this.borrowerRepository = borrowerRepository;
    }

    public Borrower createBorrower(String fullName, String phoneNumber) {
        Instant now = Instant.now();
        Borrower borrower = new Borrower(
                UUID.randomUUID(), fullName, phoneNumber,
                BorrowerStatus.ACTIVE, now, now);
        return borrowerRepository.save(borrower);
    }

    public Borrower getBorrower(UUID borrowerId) {
        return borrowerRepository.findById(borrowerId)
                .orElseThrow(() -> new IllegalArgumentException("Borrower not found: " + borrowerId));
    }

    public Borrower updateBorrower(UUID borrowerId, String fullName, String phoneNumber, String status) {
        Borrower existingBorrower = getBorrower(borrowerId);
        Borrower updatedBorrower = new Borrower(
                existingBorrower.getId(),
                fullName,
                phoneNumber,
                parseStatus(status),
                existingBorrower.getCreatedAt(),
                Instant.now()
        );
        return borrowerRepository.save(updatedBorrower);
    }

    public Page<Borrower> searchBorrowers(Optional<UUID> id, Optional<String> phoneNumber,
                                          Optional<String> fullName, int page, int size) {
        return borrowerRepository.search(id, phoneNumber, fullName, page, size);
    }

    private BorrowerStatus parseStatus(String status) {
        return BorrowerStatus.valueOf(status.trim().toUpperCase(Locale.ROOT));
    }
}
