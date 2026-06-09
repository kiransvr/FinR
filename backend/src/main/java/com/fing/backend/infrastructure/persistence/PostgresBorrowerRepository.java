package com.fing.backend.infrastructure.persistence;

import com.fing.backend.domain.model.Borrower;
import com.fing.backend.domain.port.BorrowerRepository;
import com.fing.backend.infrastructure.persistence.entity.BorrowerEntity;
import com.fing.backend.infrastructure.persistence.jpa.SpringDataBorrowerJpaRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public class PostgresBorrowerRepository implements BorrowerRepository {

    private final SpringDataBorrowerJpaRepository jpaRepository;

    public PostgresBorrowerRepository(SpringDataBorrowerJpaRepository jpaRepository) {
        this.jpaRepository = jpaRepository;
    }

    @Override
    public Borrower save(Borrower borrower) {
        BorrowerEntity entity = toEntity(borrower);
        BorrowerEntity saved = jpaRepository.save(entity);
        return toDomain(saved);
    }

    @Override
    public Optional<Borrower> findById(UUID id) {
        return jpaRepository.findById(id).map(this::toDomain);
    }

    @Override
    public Page<Borrower> search(Optional<UUID> id, Optional<String> phoneNumber,
                                 Optional<String> fullName, int page, int size) {
        Specification<BorrowerEntity> spec = Specification.where(null);
        if (id.isPresent()) {
            spec = spec.and((root, query, cb) -> cb.equal(root.get("id"), id.get()));
        }
        if (phoneNumber.isPresent()) {
            spec = spec.and((root, query, cb) -> cb.equal(root.get("phoneNumber"), phoneNumber.get()));
        }
        if (fullName.isPresent()) {
            String pattern = fullName.get().trim().toLowerCase() + "%";
            spec = spec.and((root, query, cb) -> cb.like(cb.lower(root.get("fullName")), pattern));
        }
        return jpaRepository.findAll(spec, PageRequest.of(page, size)).map(this::toDomain);
    }

    private BorrowerEntity toEntity(Borrower borrower) {
        return new BorrowerEntity(
                borrower.getId(),
                borrower.getFullName(),
                borrower.getPhoneNumber(),
                borrower.getStatus(),
                borrower.getCreatedAt(),
                borrower.getUpdatedAt()
        );
    }

    private Borrower toDomain(BorrowerEntity entity) {
        return new Borrower(
                entity.getId(),
                entity.getFullName(),
                entity.getPhoneNumber(),
                entity.getStatus(),
                entity.getCreatedAt(),
                entity.getUpdatedAt()
        );
    }
}

