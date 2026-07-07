from __future__ import annotations

from pydantic import BaseModel


class CopyDTO(BaseModel):
    isbn: str
    available: bool | None = None
    borrow_url: str | None = None
    catalog_id: int | None = None
    source: str | None = None
    title: str | None = None
    author: str | None = None
    language: str | None = None
    format: str | None = None
    cover_image: str | None = None