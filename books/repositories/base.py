from __future__ import annotations

from abc import ABC, abstractmethod

from books.dtos import BookDTO, CollectionDTO, CollectionFilterDTO, FacetDTO


class BookRepositoryBase(ABC):
    @abstractmethod
    def get_collections(self, filter_config: CollectionFilterDTO | None = None) -> FacetDTO: ...

    @abstractmethod
    def search(self, query: str) -> CollectionDTO: ...

    @abstractmethod
    def get_book(self, external_id: str) -> BookDTO | None: ...

    @abstractmethod
    def get_collection(self, external_id: str) -> CollectionDTO | None: ...
