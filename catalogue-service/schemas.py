"""Cấu trúc dữ liệu Product theo API Contract v1.0.

Product trả về: id, name, description, price, stock.
created_at/updated_at do PostgreSQL quản lý, chưa trả về trong API v1.0.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProductIn(BaseModel):
    """Body của POST /products và PUT /products/{id}."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    price: float = Field(ge=0)
    stock: int = Field(default=0, ge=0)


class Product(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    stock: int


class ErrorResponse(BaseModel):
    detail: str
