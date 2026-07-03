from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request


REQUEST_ID_HEADER = "X-Request-ID"
logger = logging.getLogger("api.observability")


def install_observability_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_request_context(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
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
