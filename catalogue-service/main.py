"""Catalogue Service – CRUD danh mục sản phẩm (API Contract v1.0, port 8001)."""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import db
from .config import settings
from .metrics import metrics_middleware
from .schemas import ErrorResponse, Product, ProductIn

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("catalogue")

SERVICE_NAME = "catalogue-service"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_schema()
    db.open_pool()
    log.info("%s sẵn sàng trên cổng %s", SERVICE_NAME, settings.port)
    yield
    db.close_pool()


app = FastAPI(title="Catalogue Service", version="1.0", lifespan=lifespan)
app.middleware("http")(metrics_middleware)

_ERRORS = {
    404: {"model": ErrorResponse, "description": "Không tìm thấy sản phẩm"},
    422: {"model": ErrorResponse, "description": "Dữ liệu gửi lên không hợp lệ"},
    500: {"model": ErrorResponse, "description": "Lỗi nội bộ"},
}


# ---- Định dạng lỗi thống nhất: {"detail": "<thông báo>"} ----------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc.detail)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"] if p != "body")
        parts.append(f"{loc}: {err['msg']}" if loc else err["msg"])
    return JSONResponse(
        status_code=422,
        content={"detail": "Dữ liệu không hợp lệ - " + "; ".join(parts)},
    )


# ---- Hạ tầng ------------------------------------------------------------------------------
@app.get("/health")
def health():
    """Liveness: chỉ kiểm tra tiến trình còn sống, KHÔNG chạm DB (tránh restart dây chuyền)."""
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/ready")
def ready():
    """Readiness: kiểm tra kết nối DB. Mất DB thì Pod bị rút khỏi Service nhưng không bị restart."""
    try:
        db.ping()
    except Exception:
        log.exception("Readiness: DB không phản hồi")
        return JSONResponse(
            status_code=503, content={"detail": "Không kết nối được cơ sở dữ liệu"}
        )
    return {"status": "ready", "service": SERVICE_NAME}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---- CRUD sản phẩm ------------------------------------------------------------------------
@app.get("/products", response_model=list[Product], responses=_ERRORS)
def list_products(
    response: Response,
    limit: int = Query(settings.default_limit, ge=1, le=settings.max_limit),
    offset: int = Query(0, ge=0),
):
    """Trả về MẢNG sản phẩm (đúng contract v1.0). Tổng số bản ghi nằm ở header X-Total-Count."""
    items, total = db.list_products(limit, offset)
    response.headers["X-Total-Count"] = str(total)
    return items


@app.get("/products/{product_id}", response_model=Product, responses=_ERRORS)
def get_product(product_id: int):
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.post("/products", response_model=Product, status_code=201, responses=_ERRORS)
def create_product(body: ProductIn):
    return db.create_product(body.name, body.description, body.price, body.stock)


@app.put("/products/{product_id}", response_model=Product, responses=_ERRORS)
def update_product(product_id: int, body: ProductIn):
    product = db.update_product(
        product_id, body.name, body.description, body.price, body.stock
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.delete("/products/{product_id}", status_code=204, responses=_ERRORS)
def delete_product(product_id: int):
    if not db.delete_product(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    return Response(status_code=204)
