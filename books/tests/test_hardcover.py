from __future__ import annotations

import httpx
import pytest

from books.dtos import BookFilterDTO, CollectionFilterDTO
from books.repositories.hardcover import HardcoverRepository

_ENDPOINT = "https://api.hardcover.app/v1/graphql"


@pytest.fixture(autouse=True)
def _token(settings):
    settings.HARDCOVER_TOKEN = "test-token"


def _gql_response(data: dict) -> httpx.Response:
    response = httpx.Response(200, json={"data": data})
    response._request = httpx.Request("POST", _ENDPOINT)
    return response


def _book_node(
    id: int = 1,
    title: str = "Dune",
    author: str = "Frank Herbert",
    image_url: str = "https://example.com/dune.jpg",
    rating: float = 4.5,
    language: str = "en",
    editions: list | None = None,
) -> dict:
    node: dict = {
        "id": id,
        "title": title,
        "contributions": [{"author": {"name": author}}],
        "image": {"url": image_url},
        "rating": rating,
        "language": language,
    }
    if editions is not None:
        node["editions"] = editions
    return node


def _edition_node(
    isbn_13: str | None = "9780441013593",
    isbn_10: str | None = None,
    physical_format: str = "ebook",
    publisher: str = "Ace",
    release_date: str = "2019-01-01",
) -> dict:
    return {
        "isbn_13": isbn_13,
        "isbn_10": isbn_10,
        "physical_format": physical_format,
        "publisher": publisher,
        "release_date": release_date,
    }


def _list_node(
    id: int = 3,
    name: str = "NPR Top 100",
    description: str = "Science fiction picks",
    books_count: int = 100,
    username: str = "npr",
    books: list | None = None,
) -> dict:
    return {
        "id": id,
        "name": name,
        "description": description,
        "books_count": books_count,
        "user": {"username": username},
        "list_books": [{"book": b} for b in (books or [_book_node()])],
    }


class TestSearchByQuery:
    def test_returns_collection_with_books_from_hits(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response(
                {"search": {"results": {"hits": [{"document": _book_node()}]}}}
            ),
        )

        col = HardcoverRepository().search(BookFilterDTO(search_query="dune"))

        assert col.external_id == "search:dune"
        assert col.title == "dune"
        assert col.source == "hardcover"
        assert len(col.books) == 1
        assert col.books[0].title == "Dune"
        assert col.books[0].author == "Frank Herbert"

    def test_book_count_reflects_number_of_hits(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response(
                {"search": {"results": {"hits": [{"document": _book_node()}]}}}
            ),
        )

        col = HardcoverRepository().search(BookFilterDTO(search_query="dune"))

        assert col.book_count == 1

    def test_returns_empty_collection_when_no_hits(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"search": {"results": {"hits": []}}}),
        )

        col = HardcoverRepository().search(BookFilterDTO(search_query="xyzzy"))

        assert col.books == []
        assert col.book_count == 0

    def test_normalizes_query_for_external_id(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"search": {"results": {"hits": []}}}),
        )

        col = HardcoverRepository().search(BookFilterDTO(search_query="  Dune  "))

        assert col.external_id == "search:dune"
        assert col.title == "Dune"

    def test_sends_bearer_token(self, monkeypatch):
        captured: dict = {}

        def fake_post(*args, headers=None, **kwargs):
            captured["headers"] = headers
            return _gql_response({"search": {"results": {}}})

        monkeypatch.setattr(httpx, "post", fake_post)

        HardcoverRepository().search(BookFilterDTO(search_query="dune"))

        assert captured["headers"]["Authorization"] == "Bearer test-token"


class TestSearchByCollection:
    def test_returns_collection_dto(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"lists": [_list_node()]}),
        )

        col = HardcoverRepository().search(BookFilterDTO(collection_id="3"))

        assert col is not None
        assert col.external_id == "3"
        assert col.title == "NPR Top 100"
        assert col.description == "Science fiction picks"
        assert col.book_count == 100
        assert len(col.books) == 1

    def test_returns_none_when_not_found(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"lists": []}),
        )

        col = HardcoverRepository().search(BookFilterDTO(collection_id="99999"))

        assert col is None


class TestSearchByTag:
    def test_returns_collection_dto(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"tags": [_tag_node()]}),
        )

        col = HardcoverRepository().search(BookFilterDTO(tag_id=7))

        assert col is not None
        assert col.external_id == "tag:7"
        assert col.title == "Fantasy"
        assert col.book_count == 42
        assert col.filter_config.tag_id == 7
        assert len(col.books) == 1
        assert col.books[0].title == "Dune"

    def test_returns_none_when_not_found(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"tags": []}),
        )

        col = HardcoverRepository().search(BookFilterDTO(tag_id=99999))

        assert col is None


class TestGetBook:
    def test_returns_book_dto_with_editions(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"books": [_book_node(editions=[_edition_node()])]}),
        )

        book = HardcoverRepository().get_book("1")

        assert book is not None
        assert book.title == "Dune"
        assert book.language == "en"
        assert len(book.editions) == 1
        assert book.editions[0].isbn == "9780441013593"
        assert book.editions[0].format == "ebook"
        assert book.editions[0].publisher == "Ace"

    def test_prefers_isbn_13_over_isbn_10(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({
                "books": [_book_node(editions=[_edition_node(isbn_13="9780441013593", isbn_10="0441013591")])]
            }),
        )

        book = HardcoverRepository().get_book("1")

        assert book.editions[0].isbn == "9780441013593"

    def test_filters_editions_without_isbn(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({
                "books": [_book_node(editions=[
                    _edition_node(isbn_13=None, isbn_10=None),
                    _edition_node(isbn_13="9780441013593"),
                ])]
            }),
        )

        book = HardcoverRepository().get_book("1")

        assert len(book.editions) == 1
        assert book.editions[0].isbn == "9780441013593"

    def test_returns_none_when_not_found(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"books": []}),
        )

        book = HardcoverRepository().get_book("99999")

        assert book is None


def _tag_node(
    id: int = 7,
    tag: str = "Fantasy",
    count: int = 42,
    books: list | None = None,
) -> dict:
    return {
        "id": id,
        "tag": tag,
        "count": count,
        "taggings": [{"book": b} for b in (books if books is not None else [_book_node()])],
    }


class TestGetCollections:
    def test_returns_featured_facet(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"lists": [_list_node()]}),
        )

        facet = HardcoverRepository().get_collections()

        assert facet.slug == "featured"
        assert facet.source == "hardcover"
        assert facet.filter_config.featured is True

    def test_facet_contains_collections(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"lists": [_list_node()]}),
        )

        facet = HardcoverRepository().get_collections()

        assert len(facet.collections) == 1
        col = facet.collections[0]
        assert col.external_id == "3"
        assert col.title == "NPR Top 100"
        assert col.book_count == 100
        assert col.selection_author == "npr"
        assert col.filter_config.collection_id == "3"

    def test_includes_books_within_each_collection(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"lists": [_list_node(books=[_book_node()])]}),
        )

        col = HardcoverRepository().get_collections().collections[0]

        assert len(col.books) == 1
        assert col.books[0].title == "Dune"

    def test_returns_empty_facet_when_no_featured_lists(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"lists": []}),
        )

        facet = HardcoverRepository().get_collections()

        assert facet.collections == []


class TestGetCollectionsByTagCategory:
    def test_returns_by_genre_facet(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"tags": [_tag_node()]}),
        )

        facet = HardcoverRepository().get_collections(CollectionFilterDTO(category="genre"))

        assert facet.slug == "by-genre"
        assert facet.source == "hardcover"
        assert facet.filter_config.category == "genre"

    def test_returns_by_mood_facet(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"tags": [_tag_node()]}),
        )

        facet = HardcoverRepository().get_collections(CollectionFilterDTO(category="mood"))

        assert facet.slug == "by-mood"
        assert facet.filter_config.category == "mood"

    def test_facet_contains_one_collection_per_tag(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"tags": [_tag_node()]}),
        )

        facet = HardcoverRepository().get_collections(CollectionFilterDTO(category="genre"))

        assert len(facet.collections) == 1
        col = facet.collections[0]
        assert col.external_id == "tag:7"
        assert col.title == "Fantasy"
        assert col.book_count == 42
        assert col.filter_config.tag_id == 7
        assert len(col.books) == 1
        assert col.books[0].title == "Dune"

    def test_returns_empty_facet_when_no_tags(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"tags": []}),
        )

        facet = HardcoverRepository().get_collections(CollectionFilterDTO(category="genre"))

        assert facet.collections == []
