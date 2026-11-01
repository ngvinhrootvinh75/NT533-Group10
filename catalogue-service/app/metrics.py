"""Prometheus metrics theo quy ước của api-service/API_CONTRACT.md mục 8 (TV1).

Cùng tên metric, cùng nhãn với api-service để dashboard Grafana dùng chung một bộ truy vấn:

- http_requests_total{method, route, status_code}              Counter
- http_request_duration_seconds{method, route, status_code}    Histogram (bucket mặc định như api-service)
- http_request_errors_total{method, route, status_code}        Counter, chỉ đếm status >= 400

`route` là mẫu route (/products/{product_id}), không phải đường dẫn thật, để tránh bùng nổ cardinality.
"""

import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram

log = logging.getLogger("catalogue")

# /metrics theo quy ước chung. /health và /ready được thêm vào để request của kubelet
# (mỗi vài giây) không làm nhiễu số liệu độ trễ và RPS.
EXCLUDED_PATHS = {"/metrics", "/health", "/ready"}

LABELS = ["method", "route", "status_code"]

REQUESTS = Counter("http_requests_total", "Total HTTP requests", LABELS)
DURATION = Histogram("http_request_duration_seconds", "HTTP request duration in seconds", LABELS)
ERRORS = Counter("http_request_errors_total", "Total HTTP errors (4xx and 5xx)", LABELS)


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


async def metrics_middleware(request: Request, call_next):
    if request.url.path in EXCLUDED_PATHS:
        return await call_next(request)

    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception:  # lỗi không bắt được: vẫn đếm là 500 và trả JSON đúng contract
        log.exception("Lỗi nội bộ: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Lỗi nội bộ của Catalogue Service"})
    finally:
        labels = {
            "method": request.method,
            "route": _route_path(request),
            "status_code": str(status_code),
        }
        REQUESTS.labels(**labels).inc()
        DURATION.labels(**labels).observe(time.perf_counter() - start)
        if status_code >= 400:
            ERRORS.labels(**labels).inc()
