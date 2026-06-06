from __future__ import annotations

from pydantic import BaseModel

from availability.dtos import CopyDTO
from books.dtos import BookDTO


class SearchResultDTO(BaseModel):
    book: BookDTO
    available_copies: list[CopyDTO] = []
