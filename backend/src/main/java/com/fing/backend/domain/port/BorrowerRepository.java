package com.fing.backend.domain.port;

import com.fing.backend.domain.model.Borrower;
import org.springframework.data.domain.Page;

import java.util.Optional;
import java.util.UUID;

public interface BorrowerRepository {

    Borrower save(Borrower borrower);

    Optional<Borrower> findById(UUID id);

    Page<Borrower> search(Optional<UUID> id, Optional<String> phoneNumber,
                          Optional<String> fullName, int page, int size);
}
