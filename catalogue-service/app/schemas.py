"""Cấu trúc dữ liệu Product theo API Contract (api-service/API_CONTRACT.md).

Product trả về: id, name, description, price, stock.
created_at do PostgreSQL quản lý, chưa trả về trong API v1.x.

Giới hạn của price khớp cột NUMERIC(10, 2) trong k8s/init.sql của TV3:
tối đa 99.999.999,99. Vượt quá sẽ trả 422 thay vì để DB báo lỗi 500.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

MAX_PRICE = 99_999_999.99


class ProductIn(BaseModel):
    """Body của POST /products và PUT /products/{id}."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    price: float = Field(ge=0, le=MAX_PRICE, allow_inf_nan=False)
    stock: int = Field(default=0, ge=0, le=2_147_483_647)


class Product(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    stock: int


class ErrorResponse(BaseModel):
    detail: str
