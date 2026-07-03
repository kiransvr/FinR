from __future__ import annotations

import logging
import time
import uuid
from threading import Lock

from fastapi import FastAPI, Request


REQUEST_ID_HEADER = "X-Request-ID"
logger = logging.getLogger("api.observability")


class ObservabilityStore:
    """In-memory request metrics store with Prometheus text exposition."""

    def __init__(self):
        self._lock = Lock()
        self._requests_total = 0
        self._requests_by_route_status: dict[tuple[str, str], int] = {}
        self._latency_buckets_ms = [50.0, 100.0, 250.0, 500.0, 1000.0, float("inf")]
        self._latency_bucket_counts = [0] * len(self._latency_buckets_ms)
        self._errors_total = 0

    def record(self, route: str, status_code: int, duration_ms: float) -> None:
        status_group = f"{status_code // 100}xx"
        with self._lock:
            self._requests_total += 1
            key = (route, status_group)
            self._requests_by_route_status[key] = self._requests_by_route_status.get(key, 0) + 1
            if status_code >= 500:
                self._errors_total += 1
            for i, threshold in enumerate(self._latency_buckets_ms):
                if duration_ms <= threshold:
                    self._latency_bucket_counts[i] += 1
                    break

    def render_prometheus(self) -> str:
        lines: list[str] = [
            "# HELP loan_default_api_requests_total Total API requests received.",
            "# TYPE loan_default_api_requests_total counter",
            f"loan_default_api_requests_total {self._requests_total}",
            "# HELP loan_default_api_errors_total Total API responses with 5xx status.",
            "# TYPE loan_default_api_errors_total counter",
            f"loan_default_api_errors_total {self._errors_total}",
            "# HELP loan_default_api_request_duration_bucket Request duration histogram buckets in milliseconds.",
            "# TYPE loan_default_api_request_duration_bucket histogram",
        ]
        cumulative = 0
        for threshold, count in zip(self._latency_buckets_ms, self._latency_bucket_counts):
            cumulative += count
            le_value = "+Inf" if threshold == float("inf") else f"{threshold:.0f}"
            lines.append(f'loan_default_api_request_duration_bucket{{le="{le_value}"}} {cumulative}')
        lines.append(f"loan_default_api_request_duration_count {self._requests_total}")

        lines.extend(
            [
                "# HELP loan_default_api_requests_by_route_total Request count by route and status group.",
                "# TYPE loan_default_api_requests_by_route_total counter",
            ]
        )
        for (route, status_group), count in sorted(self._requests_by_route_status.items()):
            lines.append(
                f'loan_default_api_requests_by_route_total{{route="{route}",status_group="{status_group}"}} {count}'
            )
        return "\n".join(lines) + "\n"


_observability_store = ObservabilityStore()


def get_observability_store() -> ObservabilityStore:
    return _observability_store


def install_observability_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_request_context(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        route = request.scope.get("route")
        route_path = route.path if route and hasattr(route, "path") else request.url.path
        _observability_store.record(route=route_path, status_code=response.status_code, duration_ms=duration_ms)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request.completed method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
