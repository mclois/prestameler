from __future__ import annotations

from pydantic import BaseModel


class CopyDTO(BaseModel):
    isbn: str
    available: bool | None = None
    borrow_url: str | None = None
    catalog_id: int | None = None
    source: str | None = None