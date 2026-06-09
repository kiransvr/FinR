package com.fing.backend.api.exception;

import com.fing.backend.api.dto.ApiErrorResponse;
import com.fing.backend.api.dto.ApiValidationError;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.time.Instant;
import java.util.List;

@RestControllerAdvice
public class ApiExceptionHandler {

    private static final Logger LOGGER = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ApiErrorResponse> handleIllegalArgument(IllegalArgumentException ex, HttpServletRequest request) {
        return buildErrorResponse(HttpStatus.NOT_FOUND, ex.getMessage(), request, List.of());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiErrorResponse> handleValidation(MethodArgumentNotValidException ex, HttpServletRequest request) {
        List<ApiValidationError> validationErrors = ex.getBindingResult().getFieldErrors().stream()
                .map(error -> new ApiValidationError(error.getField(), error.getDefaultMessage()))
                .toList();

        return buildErrorResponse(HttpStatus.BAD_REQUEST, "Validation failed", request, validationErrors);
    }

    @ExceptionHandler(BadRequestException.class)
    public ResponseEntity<ApiErrorResponse> handleBadRequest(BadRequestException ex, HttpServletRequest request) {
        return buildErrorResponse(HttpStatus.BAD_REQUEST, ex.getMessage(), request, List.of());
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ApiErrorResponse> handleTypeMismatch(
            MethodArgumentTypeMismatchException ex,
            HttpServletRequest request
    ) {
        String message = "Invalid value for parameter '" + ex.getName() + "'";
        return buildErrorResponse(HttpStatus.BAD_REQUEST, message, request, List.of());
    }

    private ResponseEntity<ApiErrorResponse> buildErrorResponse(
            HttpStatus status,
            String message,
            HttpServletRequest request,
            List<ApiValidationError> validationErrors
    ) {
        ApiErrorResponse response = new ApiErrorResponse(
                Instant.now(),
                status.value(),
                status.getReasonPhrase(),
                message,
                request.getRequestURI(),
                getCorrelationId(request),
                validationErrors
        );

        LOGGER.warn(
            "event=api_error outcome=failure correlationId={} status={} path={} message={} validationErrorCount={}",
            response.correlationId(),
            response.status(),
            response.path(),
            response.message(),
            response.validationErrors().size()
        );

        return ResponseEntity.status(status).body(response);
    }

    private String getCorrelationId(HttpServletRequest request) {
        Object correlationId = request.getAttribute(CorrelationIdFilter.CORRELATION_ID_ATTRIBUTE);
        return correlationId == null ? "unavailable" : correlationId.toString();
    }
}
