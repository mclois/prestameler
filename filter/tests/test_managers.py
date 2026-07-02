from __future__ import annotations

import pytest

from availability.dtos import CopyDTO
from availability.models import Catalog, Copy
from books.dtos import BookFilterDTO, CollectionFilterDTO
from books.models import Book, Collection, CollectionBook, Edition, Facet, FacetCollection
from filter.managers import FilterManager

pytestmark = pytest.mark.django_db

_SOURCE = "hardcover"


def _book(external_id="hc-1", title="Book", source=_SOURCE) -> Book:
    return Book.objects.create(external_id=external_id, title=title, source=source)


def _edition(book: Book, isbn: str, source=_SOURCE) -> Edition:
    return Edition.objects.create(isbn=isbn, book=book, source=source)


def _catalog(name="Catalog A") -> Catalog:
    return Catalog.objects.create(
        name=name,
        community=name,
        base_url=f"https://{name.lower().replace(' ', '')}.ebiblio.es",
        backend=Catalog.WEB,
        is_active=True,
    )


def _copy(isbn: str, catalog: Catalog, available: bool | None = True) -> Copy:
    return Copy.objects.create(isbn=isbn, catalog=catalog, available=available, source=catalog.name)


class FakeBookManager:
    def __init__(self, *, facet=None, collection=None, book=None):
        self.facet, self.collection, self.book = facet, collection, book
        self.calls = {"get_collections": 0, "search": 0, "get_book": 0}
        self.last_filter_config = None

    def get_collections(self, filter_config=None):
        self.calls["get_collections"] += 1
        self.last_filter_config = filter_config
        return self.facet

    def search(self, filter_config):
        self.calls["search"] += 1
        self.last_filter_config = filter_config
        return self.collection

    def get_book(self, external_id):
        self.calls["get_book"] += 1
        return self.book


class FakeAvailabilityManager:
    def __init__(self, copies_by_isbn: dict[str, list[Copy]] | None = None):
        self._copies_by_isbn = copies_by_isbn or {}
        self.calls: list[str] = []

    def get_copies(self, isbn):
        self.calls.append(isbn)
        return self._copies_by_isbn.get(isbn, [])


def _manager(*, fake_books=None, fake_availability=None) -> FilterManager:
    manager = FilterManager()
    manager._books = fake_books if fake_books is not None else FakeBookManager()
    manager._availability = fake_availability if fake_availability is not None else FakeAvailabilityManager()
    return manager


class TestGetCollections:
    def test_translates_facet_into_facet_dto_without_calling_availability_manager(self):
        book = _book()
        _edition(book, "9788437604947")
        collection = Collection.objects.create(external_id="col-1", title="Clásicos", source=_SOURCE)
        CollectionBook.objects.create(collection=collection, book=book, order=0)
        facet = Facet.objects.create(slug="filter:featured", title="Featured", source=_SOURCE)
        FacetCollection.objects.create(facet=facet, collection=collection, order=0)
        fake_availability = FakeAvailabilityManager()

        result = _manager(fake_books=FakeBookManager(facet=facet), fake_availability=fake_availability).get_collections()

        assert result.slug == "filter:featured"
        assert result.title == "Featured"
        assert len(result.collections) == 1
        assert result.collections[0].external_id == "col-1"
        assert len(result.collections[0].books) == 1
        assert result.collections[0].books[0].external_id == "hc-1"
        assert result.collections[0].books[0].editions[0].isbn == "9788437604947"
        assert fake_availability.calls == []

    def test_forwards_filter_config_to_book_manager(self):
        facet = Facet.objects.create(slug="filter:genre", title="Genre", source=_SOURCE)
        fake_books = FakeBookManager(facet=facet)
        filter_config = CollectionFilterDTO(category="genre")

        _manager(fake_books=fake_books).get_collections(filter_config)

        assert fake_books.last_filter_config == filter_config

    def test_preserves_facet_collection_order_not_creation_order(self):
        collection_a = Collection.objects.create(external_id="col-a", title="A", source=_SOURCE)
        collection_b = Collection.objects.create(external_id="col-b", title="B", source=_SOURCE)
        facet = Facet.objects.create(slug="filter:featured", title="Featured", source=_SOURCE)
        # Created in a-then-b order, but order field says b comes first.
        FacetCollection.objects.create(facet=facet, collection=collection_a, order=1)
        FacetCollection.objects.create(facet=facet, collection=collection_b, order=0)

        result = _manager(fake_books=FakeBookManager(facet=facet)).get_collections()

        assert [c.external_id for c in result.collections] == ["col-b", "col-a"]


class TestSearch:
    def test_empty_filter_config_returns_none_without_calling_book_manager(self):
        fake_books = FakeBookManager()

        result = _manager(fake_books=fake_books).search(BookFilterDTO())

        assert result is None
        assert fake_books.calls["search"] == 0

    def test_returns_none_when_book_manager_search_returns_none(self):
        result = _manager(fake_books=FakeBookManager(collection=None)).search(BookFilterDTO(search_query="dune"))

        assert result is None

    def test_forwards_filter_config_to_book_manager(self):
        collection = Collection.objects.create(external_id="search:dune", title="dune", source=_SOURCE)
        fake_books = FakeBookManager(collection=collection)
        filter_config = BookFilterDTO(search_query="dune")

        _manager(fake_books=fake_books).search(filter_config)

        assert fake_books.last_filter_config == filter_config

    def test_maps_collection_metadata_fields(self):
        collection = Collection.objects.create(
            external_id="col-1",
            title="Clásicos",
            description="desc",
            cover_image="https://example.com/cover.jpg",
            book_count=5,
            selection_author="Editorial team",
            source=_SOURCE,
        )

        result = _manager(fake_books=FakeBookManager(collection=collection)).search(
            BookFilterDTO(collection_id="col-1")
        )

        assert result.external_id == "col-1"
        assert result.title == "Clásicos"
        assert result.description == "desc"
        assert result.cover_image == "https://example.com/cover.jpg"
        assert result.book_count == 5
        assert result.selection_author == "Editorial team"

    def test_empty_collection_returns_empty_books_list_not_none(self):
        collection = Collection.objects.create(external_id="col-1", title="Clásicos", source=_SOURCE)

        result = _manager(fake_books=FakeBookManager(collection=collection)).search(
            BookFilterDTO(collection_id="col-1")
        )

        assert result is not None
        assert result.books == []

    def test_book_with_zero_available_copies_kept_with_empty_available_copies(self):
        book = _book()
        _edition(book, "9788437604947")
        collection = Collection.objects.create(external_id="col-1", title="Clásicos", source=_SOURCE)
        CollectionBook.objects.create(collection=collection, book=book, order=0)

        result = _manager(fake_books=FakeBookManager(collection=collection)).search(
            BookFilterDTO(collection_id="col-1")
        )

        assert len(result.books) == 1
        assert result.books[0].book.external_id == "hc-1"
        assert result.books[0].available_copies == []

    def test_never_calls_availability_manager_even_when_copies_exist(self):
        book = _book()
        _edition(book, "9788437604947")
        collection = Collection.objects.create(external_id="col-1", title="Clásicos", source=_SOURCE)
        CollectionBook.objects.create(collection=collection, book=book, order=0)
        catalog = _catalog()
        copy = _copy("9788437604947", catalog, available=True)
        fake_availability = FakeAvailabilityManager({"9788437604947": [copy]})

        result = _manager(
            fake_books=FakeBookManager(collection=collection), fake_availability=fake_availability
        ).search(BookFilterDTO(collection_id="col-1"))

        assert result.books[0].available_copies == []
        assert fake_availability.calls == []

    def test_preserves_collection_book_order_not_creation_order(self):
        book_a = _book(external_id="hc-a")
        book_b = _book(external_id="hc-b")
        collection = Collection.objects.create(external_id="col-1", title="Clásicos", source=_SOURCE)
        CollectionBook.objects.create(collection=collection, book=book_a, order=1)
        CollectionBook.objects.create(collection=collection, book=book_b, order=0)

        result = _manager(fake_books=FakeBookManager(collection=collection)).search(
            BookFilterDTO(collection_id="col-1")
        )

        assert [b.book.external_id for b in result.books] == ["hc-b", "hc-a"]

    def test_all_editions_kept_even_if_unavailable(self):
        book = _book()
        _edition(book, "9788437604947")
        collection = Collection.objects.create(external_id="col-1", title="Clásicos", source=_SOURCE)
        CollectionBook.objects.create(collection=collection, book=book, order=0)

        result = _manager(fake_books=FakeBookManager(collection=collection)).search(
            BookFilterDTO(collection_id="col-1")
        )

        assert len(result.books[0].book.editions) == 1
        assert result.books[0].book.editions[0].isbn == "9788437604947"

    def test_book_with_no_editions_does_not_call_availability_manager(self):
        book = _book()
        collection = Collection.objects.create(external_id="col-1", title="Clásicos", source=_SOURCE)
        CollectionBook.objects.create(collection=collection, book=book, order=0)
        fake_availability = FakeAvailabilityManager()

        result = _manager(
            fake_books=FakeBookManager(collection=collection), fake_availability=fake_availability
        ).search(BookFilterDTO(collection_id="col-1"))

        assert result.books[0].available_copies == []
        assert fake_availability.calls == []

    def test_returns_books_preserving_order_for_free_text_search(self):
        book_a = _book(external_id="hc-a")
        book_b = _book(external_id="hc-b")
        collection = Collection.objects.create(external_id="search:dune", title="dune", source=_SOURCE)
        CollectionBook.objects.create(collection=collection, book=book_a, order=1)
        CollectionBook.objects.create(collection=collection, book=book_b, order=0)

        result = _manager(fake_books=FakeBookManager(collection=collection)).search(
            BookFilterDTO(search_query="dune")
        )

        assert [b.book.external_id for b in result.books] == ["hc-b", "hc-a"]



class TestGetBookWithAvailability:
    def test_returns_none_when_book_manager_get_book_returns_none(self):
        result = _manager(fake_books=FakeBookManager(book=None)).get_book_with_availability("missing")

        assert result is None

    def test_edition_with_available_copy_is_kept_and_copy_included(self):
        book = _book()
        _edition(book, "9788437604947")
        catalog = _catalog()
        copy = _copy("9788437604947", catalog, available=True)
        fake_availability = FakeAvailabilityManager({"9788437604947": [copy]})

        result = _manager(
            fake_books=FakeBookManager(book=book), fake_availability=fake_availability
        ).get_book_with_availability("hc-1")

        assert len(result.book.editions) == 1
        assert result.book.editions[0].isbn == "9788437604947"
        assert len(result.available_copies) == 1
        assert result.available_copies[0].isbn == "9788437604947"

    def test_edition_with_zero_available_copies_in_any_catalog_is_dropped(self):
        book = _book()
        _edition(book, "9788437604947")
        fake_availability = FakeAvailabilityManager({})

        result = _manager(
            fake_books=FakeBookManager(book=book), fake_availability=fake_availability
        ).get_book_with_availability("hc-1")

        assert result.book.editions == []
        assert result.available_copies == []

    def test_edition_available_none_in_every_catalog_is_dropped(self):
        book = _book()
        _edition(book, "9788437604947")
        catalog = _catalog()
        copy = _copy("9788437604947", catalog, available=None)
        fake_availability = FakeAvailabilityManager({"9788437604947": [copy]})

        result = _manager(
            fake_books=FakeBookManager(book=book), fake_availability=fake_availability
        ).get_book_with_availability("hc-1")

        assert result.book.editions == []
        assert result.available_copies == []

    def test_edition_available_false_in_every_catalog_is_dropped(self):
        book = _book()
        _edition(book, "9788437604947")
        catalog = _catalog()
        copy = _copy("9788437604947", catalog, available=False)
        fake_availability = FakeAvailabilityManager({"9788437604947": [copy]})

        result = _manager(
            fake_books=FakeBookManager(book=book), fake_availability=fake_availability
        ).get_book_with_availability("hc-1")

        assert result.book.editions == []
        assert result.available_copies == []

    def test_book_with_one_available_and_one_fully_unavailable_edition_keeps_only_available(self):
        book = _book()
        _edition(book, "9788437604947")
        _edition(book, "9788437604954")
        catalog = _catalog()
        available_copy = _copy("9788437604947", catalog, available=True)
        unavailable_copy = _copy("9788437604954", catalog, available=False)
        fake_availability = FakeAvailabilityManager(
            {"9788437604947": [available_copy], "9788437604954": [unavailable_copy]}
        )

        result = _manager(
            fake_books=FakeBookManager(book=book), fake_availability=fake_availability
        ).get_book_with_availability("hc-1")

        assert [e.isbn for e in result.book.editions] == ["9788437604947"]

    def test_available_copies_from_dropped_editions_do_not_leak(self):
        book = _book()
        _edition(book, "9788437604947")
        _edition(book, "9788437604954")
        catalog = _catalog()
        available_copy = _copy("9788437604947", catalog, available=True)
        unavailable_copy = _copy("9788437604954", catalog, available=False)
        fake_availability = FakeAvailabilityManager(
            {"9788437604947": [available_copy], "9788437604954": [unavailable_copy]}
        )

        result = _manager(
            fake_books=FakeBookManager(book=book), fake_availability=fake_availability
        ).get_book_with_availability("hc-1")

        assert [c.isbn for c in result.available_copies] == ["9788437604947"]

    def test_book_where_every_edition_is_unavailable_returns_dto_with_empty_editions_not_none(self):
        book = _book()
        _edition(book, "9788437604947")
        fake_availability = FakeAvailabilityManager({})

        result = _manager(
            fake_books=FakeBookManager(book=book), fake_availability=fake_availability
        ).get_book_with_availability("hc-1")

        assert result is not None
        assert result.book.editions == []
        assert result.available_copies == []

    def test_duplicate_isbn_across_two_editions_does_not_duplicate_copy(self):
        book = _book()
        _edition(book, "9788437604947", source="hardcover")
        _edition(book, "9788437604947", source="openlibrary")
        catalog = _catalog()
        copy = _copy("9788437604947", catalog, available=True)
        fake_availability = FakeAvailabilityManager({"9788437604947": [copy]})

        result = _manager(
            fake_books=FakeBookManager(book=book), fake_availability=fake_availability
        ).get_book_with_availability("hc-1")

        assert len(result.available_copies) == 1

    def test_calls_get_copies_once_per_edition_isbn(self):
        book = _book()
        _edition(book, "9788437604947")
        _edition(book, "9788437604954")
        fake_availability = FakeAvailabilityManager()

        _manager(
            fake_books=FakeBookManager(book=book), fake_availability=fake_availability
        ).get_book_with_availability("hc-1")

        assert fake_availability.calls == ["9788437604947", "9788437604954"]
