package com.fing.backend.api.controller;

import com.fing.backend.api.dto.BorrowerResponse;
import com.fing.backend.api.dto.BorrowerSearchResponse;
import com.fing.backend.api.dto.CreateBorrowerRequest;
import com.fing.backend.api.dto.UpdateBorrowerRequest;
import com.fing.backend.api.exception.BadRequestException;
import com.fing.backend.api.exception.CorrelationIdFilter;
import com.fing.backend.application.service.BorrowerService;
import com.fing.backend.domain.model.Borrower;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.http.HttpStatus;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.Optional;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/borrowers")
public class BorrowerController {

    private static final Logger LOGGER = LoggerFactory.getLogger(BorrowerController.class);
    private static final String ACTOR_HEADER = "X-Actor-Id";
    private static final String SOURCE_HEADER = "X-Source-System";

    private final BorrowerService borrowerService;

    public BorrowerController(BorrowerService borrowerService) {
        this.borrowerService = borrowerService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public BorrowerResponse create(@Valid @RequestBody CreateBorrowerRequest request, HttpServletRequest httpRequest) {
        String correlationId = getCorrelationId(httpRequest);
        long startedAt = System.currentTimeMillis();

        Borrower borrower = borrowerService.createBorrower(request.getFullName(), request.getPhoneNumber());

        LOGGER.info(
                "event=borrower_mutation operation=create outcome=success correlationId={} actor={} source={} borrowerId={} elapsedMs={}",
                correlationId,
                getActor(httpRequest),
                getSource(httpRequest),
                borrower.getId(),
                System.currentTimeMillis() - startedAt
        );
        return BorrowerResponse.fromDomain(borrower);
    }

    @PutMapping("/{borrowerId}")
    public BorrowerResponse update(
            @PathVariable UUID borrowerId,
            @Valid @RequestBody UpdateBorrowerRequest request,
            HttpServletRequest httpRequest
    ) {
        String correlationId = getCorrelationId(httpRequest);
        long startedAt = System.currentTimeMillis();

        Borrower borrower = borrowerService.updateBorrower(
                borrowerId,
                request.getFullName(),
                request.getPhoneNumber(),
                request.getStatus()
        );

        LOGGER.info(
                "event=borrower_mutation operation=update outcome=success correlationId={} actor={} source={} borrowerId={} elapsedMs={}",
                correlationId,
                getActor(httpRequest),
                getSource(httpRequest),
                borrower.getId(),
                System.currentTimeMillis() - startedAt
        );
        return BorrowerResponse.fromDomain(borrower);
    }

    @GetMapping("/{borrowerId}")
    public BorrowerResponse getById(@PathVariable UUID borrowerId) {
        Borrower borrower = borrowerService.getBorrower(borrowerId);
        return BorrowerResponse.fromDomain(borrower);
    }

    @GetMapping
    public BorrowerSearchResponse search(
            @RequestParam(required = false) UUID id,
            @RequestParam(required = false) String phoneNumber,
            @RequestParam(required = false) String fullName,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            HttpServletRequest httpRequest
    ) {
        String correlationId = getCorrelationId(httpRequest);
        long startedAt = System.currentTimeMillis();

        validateSearchInputs(phoneNumber, fullName, page, size);

        Page<BorrowerResponse> borrowers = borrowerService.searchBorrowers(
                        Optional.ofNullable(id),
                        optionalText(phoneNumber),
                        optionalText(fullName),
                        page,
                        size
                )
                .map(BorrowerResponse::fromDomain);

        LOGGER.info(
                "event=borrower_query operation=search outcome=success correlationId={} page={} size={} totalElements={} filters.id={} filters.phoneNumber={} filters.fullName={} elapsedMs={}",
                correlationId,
                borrowers.getNumber(),
                borrowers.getSize(),
                borrowers.getTotalElements(),
                id,
                maskPhone(phoneNumber),
                fullName,
                System.currentTimeMillis() - startedAt
        );

        return BorrowerSearchResponse.fromPage(borrowers);
    }

    private String getCorrelationId(HttpServletRequest request) {
        Object correlationId = request.getAttribute(CorrelationIdFilter.CORRELATION_ID_ATTRIBUTE);
        return correlationId == null ? "unavailable" : correlationId.toString();
    }

    private String getActor(HttpServletRequest request) {
        String actor = request.getHeader(ACTOR_HEADER);
        return StringUtils.hasText(actor) ? actor.trim() : "anonymous-placeholder";
    }

    private String getSource(HttpServletRequest request) {
        String source = request.getHeader(SOURCE_HEADER);
        return StringUtils.hasText(source) ? source.trim() : "api";
    }

    private String maskPhone(String phoneNumber) {
        if (!StringUtils.hasText(phoneNumber)) {
            return "<none>";
        }
        String trimmed = phoneNumber.trim();
        if (trimmed.length() <= 4) {
            return "****";
        }
        return "****" + trimmed.substring(trimmed.length() - 4);
    }

    private Optional<String> optionalText(String value) {
        return StringUtils.hasText(value) ? Optional.of(value.trim()) : Optional.empty();
    }

    private void validateSearchInputs(String phoneNumber, String fullName, int page, int size) {
        if (page < 0) {
            throw new BadRequestException("page must be greater than or equal to 0");
        }
        if (size < 1 || size > 100) {
            throw new BadRequestException("size must be between 1 and 100");
        }
        if (StringUtils.hasText(phoneNumber) && !phoneNumber.trim().matches("^[0-9]{10,15}$")) {
            throw new BadRequestException("phoneNumber must be 10 to 15 digits");
        }
        if (StringUtils.hasText(fullName)) {
            String trimmed = fullName.trim();
            if (trimmed.length() < 2 || trimmed.length() > 150) {
                throw new BadRequestException("fullName must be between 2 and 150 characters");
            }
        }
    }
}
