from __future__ import annotations

from pydantic import BaseModel


class ProductSearchOut(BaseModel):
    product_id: str
    title: str
    brand: str
    category: str
    price: float | None
    currency: str | None
    product_url: str
    similarity: float
    rank: int
