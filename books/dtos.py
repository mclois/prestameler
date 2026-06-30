from __future__ import annotations

from pydantic import BaseModel


class EditionDTO(BaseModel):
    isbn: str
    source: str = ""
    format: str = ""
    publisher: str = ""
    published_date: str = ""


class BookDTO(BaseModel):
    external_id: str
    source: str = ""
    title: str
    author: str = ""
    cover_image: str = ""
    language: str = ""
    rating: float | None = None
    editions: list[EditionDTO] = []


class CollectionDTO(BaseModel):
    external_id: str
    source: str = ""
    title: str
    description: str = ""
    cover_image: str = ""
    book_count: int = 0
    selection_author: str = ""
    books: list[BookDTO] = []