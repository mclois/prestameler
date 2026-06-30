from __future__ import annotations

import httpx
import pytest

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


class TestSearch:
    def test_returns_book_dtos_from_hits(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response(
                {"search": {"results": {"hits": [{"document": _book_node()}]}}}
            ),
        )

        books = HardcoverRepository().search("dune")

        assert len(books) == 1
        assert books[0].external_id == "1"
        assert books[0].title == "Dune"
        assert books[0].author == "Frank Herbert"
        assert books[0].source == "hardcover"

    def test_returns_empty_list_when_no_hits(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"search": {"results": {"hits": []}}}),
        )

        books = HardcoverRepository().search("xyzzy")

        assert books == []

    def test_sends_bearer_token(self, monkeypatch):
        captured: dict = {}

        def fake_post(*args, headers=None, **kwargs):
            captured["headers"] = headers
            return _gql_response({"search": {"results": {}}})

        monkeypatch.setattr(httpx, "post", fake_post)

        HardcoverRepository().search("dune")

        assert captured["headers"]["Authorization"] == "Bearer test-token"


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


class TestGetCollections:
    def test_returns_collection_list(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"lists": [_list_node()]}),
        )

        collections = HardcoverRepository().get_collections()

        assert len(collections) == 1
        col = collections[0]
        assert col.external_id == "3"
        assert col.title == "NPR Top 100"
        assert col.description == "Science fiction picks"
        assert col.book_count == 100
        assert col.selection_author == "npr"
        assert col.source == "hardcover"

    def test_includes_books_within_each_collection(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"lists": [_list_node(books=[_book_node()])]}),
        )

        col = HardcoverRepository().get_collections()[0]

        assert len(col.books) == 1
        assert col.books[0].title == "Dune"

    def test_returns_empty_list_when_no_featured_lists(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"lists": []}),
        )

        assert HardcoverRepository().get_collections() == []


class TestGetCollection:
    def test_returns_collection_dto(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "post",
            lambda *a, **k: _gql_response({"lists": [_list_node()]}),
        )

        col = HardcoverRepository().get_collection("3")

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

        col = HardcoverRepository().get_collection("99999")

        assert col is None
