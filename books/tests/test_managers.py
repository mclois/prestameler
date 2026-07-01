from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from books.dtos import (
    BookDTO,
    BookFilterDTO,
    CollectionDTO,
    CollectionFilterDTO,
    EditionDTO,
    FacetDTO,
)
from books.managers import BookManager
from books.models import Book, Collection, Edition, Facet

pytestmark = pytest.mark.django_db

_SOURCE = "hardcover"


def _book_dto(external_id="hc-1", with_edition=True) -> BookDTO:
    editions = [EditionDTO(isbn="9788437604947", source=_SOURCE)] if with_edition else []
    return BookDTO(external_id=external_id, source=_SOURCE, title="Cien años de soledad", editions=editions)


def _collection_dto(external_id="hc-col-1", books=None) -> CollectionDTO:
    return CollectionDTO(
        external_id=external_id,
        source=_SOURCE,
        title="Grandes clásicos",
        filter_config=BookFilterDTO(collection_id=external_id),
        books=books if books is not None else [_book_dto()],
    )


class FakeRepo:
    """Configurable stub standing in for HardcoverRepository."""

    SOURCE = _SOURCE

    def __init__(self, get_collections=None, search=None, get_book=None):
        self._get_collections_returns = get_collections
        self._search_returns = search
        self._get_book_returns = get_book
        self.calls = {"get_collections": 0, "search": 0, "get_book": 0}

    def get_collections(self, filter_config: CollectionFilterDTO) -> FacetDTO:
        self.calls["get_collections"] += 1
        self.last_filter_config = filter_config
        return self._get_collections_returns

    def search(self, filter_config: BookFilterDTO) -> CollectionDTO | None:
        self.calls["search"] += 1
        self.last_filter_config = filter_config
        return self._search_returns

    def get_book(self, external_id: str) -> BookDTO | None:
        self.calls["get_book"] += 1
        return self._get_book_returns


def _manager(fake: FakeRepo) -> BookManager:
    manager = BookManager()
    manager._repo = fake
    return manager


def _make_stale(instance) -> None:
    past = timezone.now() - timedelta(hours=2)
    type(instance).objects.filter(pk=instance.pk).update(cached_at=past)
    instance.refresh_from_db()


class TestGetCollections:
    def test_cache_hit_returns_cached_facet_without_calling_repo(self):
        cached = Facet.objects.create(slug="filter:featured", title="Featured", source=_SOURCE)
        fake = FakeRepo()

        result = _manager(fake).get_collections()

        assert fake.calls["get_collections"] == 0
        assert result == cached

    def test_cache_miss_calls_repo_and_caches_collections_books_and_editions(self):
        dto = FacetDTO(slug="ignored", source=_SOURCE, title="Featured", collections=[_collection_dto()])
        fake = FakeRepo(get_collections=dto)

        result = _manager(fake).get_collections()

        assert fake.calls["get_collections"] == 1
        assert isinstance(result, Facet)
        assert result.slug == "filter:featured"
        assert Collection.objects.filter(external_id="hc-col-1", source=_SOURCE).exists()
        assert Book.objects.filter(external_id="hc-1", source=_SOURCE).exists()
        assert Edition.objects.filter(isbn="9788437604947", source=_SOURCE).exists()

    def test_stale_cache_calls_repo_again(self):
        cached = Facet.objects.create(slug="filter:featured", title="Featured", source=_SOURCE)
        _make_stale(cached)
        dto = FacetDTO(slug="ignored", source=_SOURCE, title="Featured", collections=[])
        fake = FakeRepo(get_collections=dto)

        _manager(fake).get_collections()

        assert fake.calls["get_collections"] == 1

    def test_defaults_to_featured_filter_when_none_given(self):
        dto = FacetDTO(slug="ignored", source=_SOURCE, title="Featured", collections=[])
        fake = FakeRepo(get_collections=dto)

        _manager(fake).get_collections()

        assert fake.last_filter_config == CollectionFilterDTO(featured=True)


class TestSearch:
    def test_cache_hit_returns_cached_collection_without_calling_repo(self):
        cached = Collection.objects.create(external_id="search:dune", title="dune", source=_SOURCE)
        fake = FakeRepo()

        result = _manager(fake).search(BookFilterDTO(search_query="dune"))

        assert fake.calls["search"] == 0
        assert result == cached

    def test_cache_miss_calls_repo_and_caches_result(self):
        dto = _collection_dto(external_id="search:dune")
        fake = FakeRepo(search=dto)

        result = _manager(fake).search(BookFilterDTO(search_query="dune"))

        assert fake.calls["search"] == 1
        assert isinstance(result, Collection)
        assert Collection.objects.filter(external_id="search:dune", source=_SOURCE).exists()

    def test_stale_cache_calls_repo_again(self):
        cached = Collection.objects.create(external_id="search:dune", title="dune", source=_SOURCE)
        _make_stale(cached)
        fake = FakeRepo(search=_collection_dto(external_id="search:dune"))

        _manager(fake).search(BookFilterDTO(search_query="dune"))

        assert fake.calls["search"] == 1

    def test_repo_returning_none_is_propagated_without_caching(self):
        fake = FakeRepo(search=None)

        result = _manager(fake).search(BookFilterDTO(search_query="no-such-book"))

        assert result is None
        assert not Collection.objects.filter(external_id="search:no-such-book").exists()


class TestGetBook:
    def test_cache_hit_with_editions_returns_cached_book_without_calling_repo(self):
        book = Book.objects.create(external_id="hc-1", title="Cien años de soledad", source=_SOURCE)
        Edition.objects.create(isbn="9788437604947", book=book, source=_SOURCE)
        fake = FakeRepo()

        result = _manager(fake).get_book("hc-1")

        assert fake.calls["get_book"] == 0
        assert result == book

    def test_cache_hit_without_editions_calls_repo_again(self):
        Book.objects.create(external_id="hc-1", title="Cien años de soledad", source=_SOURCE)
        fake = FakeRepo(get_book=_book_dto())

        _manager(fake).get_book("hc-1")

        assert fake.calls["get_book"] == 1

    def test_cache_miss_calls_repo_and_caches_book_and_editions(self):
        fake = FakeRepo(get_book=_book_dto())

        result = _manager(fake).get_book("hc-1")

        assert fake.calls["get_book"] == 1
        assert isinstance(result, Book)
        assert Book.objects.filter(external_id="hc-1", source=_SOURCE).exists()
        assert Edition.objects.filter(isbn="9788437604947", source=_SOURCE).exists()

    def test_stale_cache_calls_repo_again(self):
        book = Book.objects.create(external_id="hc-1", title="Cien años de soledad", source=_SOURCE)
        Edition.objects.create(isbn="9788437604947", book=book, source=_SOURCE)
        _make_stale(book)
        fake = FakeRepo(get_book=_book_dto())

        _manager(fake).get_book("hc-1")

        assert fake.calls["get_book"] == 1

    def test_repo_returning_none_is_propagated_without_caching(self):
        fake = FakeRepo(get_book=None)

        result = _manager(fake).get_book("missing")

        assert result is None
        assert not Book.objects.filter(external_id="missing").exists()