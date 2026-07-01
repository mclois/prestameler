from __future__ import annotations

import logging

from books.dtos import BookDTO, BookFilterDTO, CollectionDTO, CollectionFilterDTO
from books.models import Book, Collection, Edition, Facet
from books.repositories.hardcover import HardcoverRepository

logger = logging.getLogger(__name__)


class BookManager:
    def __init__(self) -> None:
        self._repo = HardcoverRepository()

    def get_collections(self, filter_config: CollectionFilterDTO | None = None) -> Facet:
        filter_config = filter_config or CollectionFilterDTO(featured=True)
        slug = filter_config.cache_key
        cached = Facet.objects.filter(source=self._repo.SOURCE, slug=slug).first()
        if cached is not None and not cached.is_stale:
            logger.debug("cache hit: facet=%s", slug)
            return cached

        reason = "stale" if cached else "miss"
        logger.debug("cache %s, fetching: facet=%s", reason, slug)
        dto = self._repo.get_collections(filter_config)
        dto.slug = slug
        collections = [self._cache_collection(c) for c in dto.collections]
        return Facet.update_cache(dto, collections)

    def _cache_collection(self, dto: CollectionDTO) -> Collection:
        books = [self._cache_book(b) for b in dto.books]
        return Collection.update_cache(dto, books)

    def _cache_book(self, dto: BookDTO) -> Book:
        book = Book.update_cache(dto)
        for edition_dto in dto.editions:
            Edition.update_cache(edition_dto, book)
        return book

    def search(self, filter_config: BookFilterDTO) -> Collection | None:
        cache_key = filter_config.cache_key
        cached = Collection.objects.filter(source=self._repo.SOURCE, external_id=cache_key).first()
        if cached is not None and not cached.is_stale:
            logger.debug("cache hit: collection=%s", cache_key)
            return cached

        reason = "stale" if cached else "miss"
        logger.debug("cache %s, fetching: collection=%s", reason, cache_key)
        dto = self._repo.search(filter_config)
        if dto is None:
            return None
        return self._cache_collection(dto)

    def get_book(self, external_id: str) -> Book | None:
        cached = Book.objects.filter(external_id=external_id, source=self._repo.SOURCE).first()
        if cached is not None and not cached.is_stale and cached.editions.exists():
            logger.debug("cache hit: book=%s", external_id)
            return cached

        reason = "stale" if cached else "miss"
        logger.debug("cache %s, fetching: book=%s", reason, external_id)
        dto = self._repo.get_book(external_id)
        if dto is None:
            return None
        return self._cache_book(dto)
