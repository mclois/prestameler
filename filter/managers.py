from __future__ import annotations

from availability.managers import AvailabilityManager
from books.managers import BookManager
from filter.dtos import SearchResultDTO


class FilterManager:
    def __init__(self) -> None:
        self._books = BookManager()
        self._availability = AvailabilityManager()

    def search(self, query: str) -> list[SearchResultDTO]:
        raise NotImplementedError

    def get_book_with_availability(self, external_id: str) -> SearchResultDTO | None:
        raise NotImplementedError
