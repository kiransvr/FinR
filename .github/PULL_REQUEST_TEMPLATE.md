## Summary

- Describe the change and business purpose.

## Validation

- [ ] Tests added or updated
- [ ] Local validation completed
- [ ] Documentation updated where needed

## Backend Architecture Checklist

- [ ] Controllers stay under `api.controller`
- [ ] Request/response models stay under `api.dto`
- [ ] Business orchestration stays under `application.service`
- [ ] Domain code remains free of Spring stereotypes/framework leakage
- [ ] Infrastructure adapters are kept under `infrastructure.*`
- [ ] API layer does not call persistence adapters directly
- [ ] Any schema change includes a Flyway migration

## Risks

- List technical, data, or rollout risks introduced by this PR.