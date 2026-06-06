from __future__ import annotations

from pydantic import BaseModel


class EditionDTO(BaseModel):
    isbn: str
    format: str = ""
    publisher: str = ""
    published_date: str = ""


class BookDTO(BaseModel):
    external_id: str
    title: str
    author: str = ""
    cover_image: str = ""
    language: str = ""
    editions: list[EditionDTO] = []


class CollectionDTO(BaseModel):
    external_id: str
    title: str
    description: str = ""
    cover_image: str = ""
    book_count: int = 0
    selection_author: str = ""
    tags: list[str] = []
