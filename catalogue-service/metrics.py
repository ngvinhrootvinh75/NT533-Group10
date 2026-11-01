"""Prometheus metrics theo quy ước chung của cả nhóm (xem docs/contract.md).

- http_requests_total{method,path,status}
- http_request_duration_seconds{method,path}  (histogram)
- http_requests_in_progress{method}           (gauge)

`path` luôn là mẫu route (/products/{id}) để tránh bùng nổ cardinality.
"""

import time

from fastapi import Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Gauge, Histogram

BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)

# Không đưa các endpoint hạ tầng vào thống kê.
EXCLUDED_PATHS = {"/metrics", "/health", "/ready"}

REQUESTS_TOTAL = Counter(
    "http_requests_total", "Tổng số HTTP request", ["method", "path", "status"]
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Thời gian xử lý HTTP request (giây)",
    ["method", "path"],
    buckets=BUCKETS,
)
REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress", "Số HTTP request đang xử lý", ["method"]
)


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", None) or "unmatched"


async def metrics_middleware(request: Request, call_next):
    if request.url.path in EXCLUDED_PATHS:
        return await call_next(request)

    method = request.method
    REQUESTS_IN_PROGRESS.labels(method=method).inc()
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    except Exception:  # lỗi không bắt được: vẫn đếm là 500 và trả JSON đúng contract
        import logging

        logging.getLogger("catalogue").exception("Lỗi nội bộ: %s %s", method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Lỗi nội bộ của Catalogue Service"})
    finally:
        elapsed = time.perf_counter() - start
        path = _route_path(request)
        REQUESTS_IN_PROGRESS.labels(method=method).dec()
        REQUESTS_TOTAL.labels(method=method, path=path, status=str(status)).inc()
        REQUEST_DURATION.labels(method=method, path=path).observe(elapsed)
