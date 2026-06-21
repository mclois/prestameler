from __future__ import annotations

from books.dtos import BookDTO, CollectionDTO
from books.repositories.base import BookRepositoryBase


class HardcoverRepository(BookRepositoryBase):
    """Book repository backed by the Hardcover GraphQL API."""

    def get_collections(self) -> list[CollectionDTO]:
        raise NotImplementedError

    def search(self, query: str) -> list[BookDTO]:
        raise NotImplementedError

    def get_book(self, hardcover_id: str) -> BookDTO | None:
        raise NotImplementedError
