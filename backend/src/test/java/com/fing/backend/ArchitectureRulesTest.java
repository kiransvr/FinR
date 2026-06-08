package com.fing.backend;

import com.fing.backend.api.controller.BorrowerController;
import com.fing.backend.api.controller.HealthController;
import com.fing.backend.api.exception.ApiExceptionHandler;
import com.fing.backend.application.service.BorrowerService;
import com.fing.backend.domain.model.Borrower;
import com.fing.backend.domain.port.BorrowerRepository;
import com.fing.backend.infrastructure.persistence.PostgresBorrowerRepository;
import org.junit.jupiter.api.Test;
import org.springframework.stereotype.Repository;
import org.springframework.stereotype.Service;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ArchitectureRulesTest {

        @Test
        void baseline_types_reside_in_expected_layers() {
                assertTrue(BorrowerController.class.getPackageName().startsWith("com.fing.backend.api."));
                assertTrue(HealthController.class.getPackageName().startsWith("com.fing.backend.api."));
                assertTrue(ApiExceptionHandler.class.getPackageName().startsWith("com.fing.backend.api."));
                assertTrue(BorrowerService.class.getPackageName().startsWith("com.fing.backend.application."));
                assertTrue(Borrower.class.getPackageName().startsWith("com.fing.backend.domain."));
                assertTrue(BorrowerRepository.class.getPackageName().startsWith("com.fing.backend.domain."));
                assertTrue(PostgresBorrowerRepository.class.getPackageName().startsWith("com.fing.backend.infrastructure."));
        }

        @Test
        void baseline_types_use_expected_stereotypes() {
                assertTrue(BorrowerController.class.isAnnotationPresent(RestController.class));
                assertTrue(HealthController.class.isAnnotationPresent(RestController.class));
                assertTrue(ApiExceptionHandler.class.isAnnotationPresent(RestControllerAdvice.class));
                assertTrue(BorrowerService.class.isAnnotationPresent(Service.class));
                assertTrue(PostgresBorrowerRepository.class.isAnnotationPresent(Repository.class));
        }

        @Test
        void domain_model_stays_framework_agnostic() {
                assertEquals(0, Borrower.class.getAnnotations().length);
                assertEquals(0, BorrowerRepository.class.getAnnotations().length);
        }
}