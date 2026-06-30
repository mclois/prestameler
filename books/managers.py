from __future__ import annotations

from books.dtos import BookDTO, CollectionDTO
from books.repositories.hardcover import HardcoverRepository


class BookManager:
    def __init__(self) -> None:
        self._repo = HardcoverRepository()

    def get_collections(self) -> list[CollectionDTO]:
        raise NotImplementedError

    def search(self, query: str) -> list[BookDTO]:
        raise NotImplementedError

    def get_book(self, external_id: str) -> BookDTO | None:
        raise NotImplementedError
