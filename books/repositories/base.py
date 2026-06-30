from __future__ import annotations

from abc import ABC, abstractmethod

from books.dtos import BookDTO, BookFilterDTO, CollectionDTO, CollectionFilterDTO, FacetDTO


class BookRepositoryBase(ABC):
    @abstractmethod
    def get_collections(self, filter_config: CollectionFilterDTO | None = None) -> FacetDTO: ...

    @abstractmethod
    def search(self, filter_config: BookFilterDTO) -> CollectionDTO | None: ...

    @abstractmethod
    def get_book(self, external_id: str) -> BookDTO | None: ...
