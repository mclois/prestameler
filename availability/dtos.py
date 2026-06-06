from __future__ import annotations

from pydantic import BaseModel


class CopyDTO(BaseModel):
    isbn: str
    title: str = ""
    author: str = ""
    publisher: str = ""
    published_date: str = ""
    available: bool | None = None
    borrow_url: str = ""
    catalog_name: str = ""
