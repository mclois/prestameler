from __future__ import annotations

from pydantic import BaseModel

from availability.dtos import CopyDTO
from books.dtos import BookDTO


class BookResultDTO(BaseModel):
    book: BookDTO
    available_copies: list[CopyDTO] = []


class SearchResultDTO(BaseModel):
    external_id: str
    title: str
    description: str = ""
    cover_image: str = ""
    book_count: int = 0
    selection_author: str = ""
    books: list[BookResultDTO] = []
