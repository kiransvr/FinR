# FinG Mobile (Sprint 1 Shell)

This module contains the Flutter mobile shell baseline for Sprint 1.

## Included in Sprint 1

- Basic app startup and route flow.
- Auth placeholder service with token storage abstraction.
- API client abstraction with environment base URL support.
- Basic smoke tests for widget render and auth service behavior.

## Run locally

1. Install Flutter SDK.
2. From this folder run:

```bash
flutter pub get
flutter test
flutter run
```

## Environment base URL

Set compile-time API base URL using:

```bash
flutter run --dart-define=API_BASE_URL=http://localhost:8080/api/v1
```

Default value:

- `http://localhost:8080/api/v1`
