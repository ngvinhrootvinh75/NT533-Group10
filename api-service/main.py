
import logging
import os
import time

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

app = FastAPI(title="NT533 Group10 - API Service")
logger = logging.getLogger("uvicorn.error")

CATALOGUE_BASE_URL = os.getenv(
    "CATALOGUE_BASE_URL",
    "http://127.0.0.1:8001"
)

# Prometheus Metrics
REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status_code"]
)

DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route", "status_code"]
)

ERRORS = Counter(
    "http_request_errors_total",
    "Total HTTP errors (4xx and 5xx)",
    ["method", "route", "status_code"]
)


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    # Khong dem request thu thap metrics
    if request.url.path == "/metrics":
        return await call_next(request)

    start = time.perf_counter()

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        status_code = 500
        logger.exception("Unhandled API error")
        raise
    finally:
        route = getattr(
            request.scope.get("route"),
            "path",
            "unmatched"
        )

        labels = {
            "method": request.method,
            "route": route,
            "status_code": str(status_code)
        }

        REQUESTS.labels(**labels).inc()
        DURATION.labels(**labels).observe(
            time.perf_counter() - start
        )

        if status_code >= 400:
            ERRORS.labels(**labels).inc()

    return response


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "api-service"
    }


@app.get("/ready")
def readiness():
    return {
        "status": "ready",
        "service": "api-service"
    }


@app.get("/products")
async def get_products():
    url = f"{CATALOGUE_BASE_URL.rstrip('/')}/products"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
            response.raise_for_status()

        logger.info(
            "Catalogue Service responded with HTTP %s",
            response.status_code
        )

        return response.json()

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Catalogue Service timeout"
        )

    except httpx.HTTPStatusError:
        raise HTTPException(
            status_code=502,
            detail="Catalogue Service returned an error"
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Catalogue Service unavailable"
        )

    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="Invalid response from Catalogue Service"
        )


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
