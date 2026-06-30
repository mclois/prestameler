from __future__ import annotations

from books.dtos import BookDTO, BookFilterDTO, CollectionDTO, CollectionFilterDTO
from books.repositories.base import BookRepositoryBase


class OpenLibraryRepository(BookRepositoryBase):
    """Book repository backed by the OpenLibrary REST API (no key required)."""

    BASE_URL = "https://openlibrary.org"

    def get_collections(self, filter_config: CollectionFilterDTO | None = None) -> list[CollectionDTO]:
        raise NotImplementedError

    def search(self, filter_config: BookFilterDTO) -> CollectionDTO | None:
        raise NotImplementedError

    def get_book(self, external_id: str) -> BookDTO | None:
        raise NotImplementedError
