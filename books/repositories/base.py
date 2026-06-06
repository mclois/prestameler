from __future__ import annotations

from abc import ABC, abstractmethod

from books.dtos import BookDTO, CollectionDTO


class BookRepositoryBase(ABC):
    @abstractmethod
    def get_collections(self) -> list[CollectionDTO]: ...

    @abstractmethod
    def search(self, query: str) -> list[BookDTO]: ...

    @abstractmethod
    def get_book(self, external_id: str) -> BookDTO | None: ...
