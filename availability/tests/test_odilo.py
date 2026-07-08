from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest

from availability.repositories.odilo import OdiloRepository, _language_name

_BASE_URL = "https://biblioteca.ebiblio.cat"
_ISBN = "9788429782738"


@pytest.fixture(autouse=True)
def _reset_token_cache():
    OdiloRepository._token_cache.clear()
    yield
    OdiloRepository._token_cache.clear()


@pytest.fixture
def catalog():
    return SimpleNamespace(
        base_url=_BASE_URL,
        odilo_client_id="NgOpac",
        odilo_client_secret="kvFqFy1i0Y4eUJhM",
    )


def _record(
    isbn: str,
    available: bool = True,
    record_id: str = "00757769",
    title: str = "El Quijote",
    author: str = "Miguel de Cervantes",
    formats: list[str] | None = None,
    language: str = "spa",
    covers_url: dict | None = None,
) -> dict:
    return {
        "id": record_id,
        "isbn": isbn,
        "availability": {"availableToCheckout": available},
        "title": title,
        "author": author,
        "formats": formats if formats is not None else ["EPUB"],
        "language": language,
        "coversUrl": (
            covers_url if covers_url is not None else {"small": "https://covers.example.com/small.jpg"}
        ),
    }


def _response(json_data: object) -> httpx.Response:
    response = httpx.Response(200, json=json_data)
    response._request = httpx.Request("GET", _BASE_URL)
    return response


def _token_response(*, expires_in: int = 3600) -> httpx.Response:
    return _response({"token": "abc123", "type": "Bearer", "expiresIn": expires_in})


class TestSearch:
    def test_returns_copy_for_matching_isbn(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _token_response())
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response([_record(_ISBN, available=False)]))

        copies = OdiloRepository(catalog).search(_ISBN)

        assert len(copies) == 1
        assert copies[0].isbn == _ISBN
        assert copies[0].available is False
        assert copies[0].borrow_url == f"{_BASE_URL}/info/00757769"
        assert copies[0].title == "El Quijote"
        assert copies[0].author == "Miguel de Cervantes"
        assert copies[0].format == "EPUB"
        assert copies[0].language == "Spanish"
        assert copies[0].cover_image == "https://covers.example.com/small.jpg"

    def test_cover_image_missing_when_covers_url_absent(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _token_response())
        monkeypatch.setattr(
            httpx, "get", lambda *a, **k: _response([_record(_ISBN, covers_url={})])
        )

        copies = OdiloRepository(catalog).search(_ISBN)

        assert copies[0].cover_image is None

    def test_joins_multiple_formats_into_comma_separated_string(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _token_response())
        monkeypatch.setattr(
            httpx, "get", lambda *a, **k: _response([_record(_ISBN, formats=["EPUB", "PDF"])])
        )

        copies = OdiloRepository(catalog).search(_ISBN)

        assert copies[0].format == "EPUB, PDF"

    def test_falls_back_to_raw_code_for_unrecognized_language(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _token_response())
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response([_record(_ISBN, language="xxx")]))

        copies = OdiloRepository(catalog).search(_ISBN)

        assert copies[0].language == "xxx"

    def test_filters_non_matching_isbn(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _token_response())
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response([_record("9780000000000")]))

        copies = OdiloRepository(catalog).search(_ISBN)

        assert copies == []

    def test_returns_empty_list_for_no_results(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _token_response())
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response([]))

        copies = OdiloRepository(catalog).search(_ISBN)

        assert copies == []

    def test_returns_empty_list_for_empty_body(self, monkeypatch, catalog):
        """Odilo returns 200 with a zero-byte body (not `[]`) when there are no matches."""
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _token_response())

        def fake_get(*args, **kwargs):
            response = httpx.Response(200, content=b"")
            response._request = httpx.Request("GET", _BASE_URL)
            return response

        monkeypatch.setattr(httpx, "get", fake_get)

        copies = OdiloRepository(catalog).search(_ISBN)

        assert copies == []

    def test_sends_bearer_token_from_token_endpoint(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "post", lambda *a, **k: _token_response())
        captured_headers = {}

        def fake_get(*args, headers=None, **kwargs):
            captured_headers.update(headers or {})
            return _response([_record(_ISBN)])

        monkeypatch.setattr(httpx, "get", fake_get)

        OdiloRepository(catalog).search(_ISBN)

        assert captured_headers["Authorization"] == "Bearer abc123"


class TestLanguageName:
    def test_returns_full_name_for_known_code(self):
        assert _language_name("spa") == "Spanish"

    def test_returns_empty_string_for_empty_code(self):
        assert _language_name("") == ""

    def test_falls_back_to_raw_code_for_unknown_code(self):
        assert _language_name("zzz") == "zzz"


class TestTokenCache:
    def test_reuses_cached_token_across_searches(self, monkeypatch, catalog):
        post_calls = []
        monkeypatch.setattr(httpx, "post", lambda *a, **k: (post_calls.append(1), _token_response())[1])
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response([_record(_ISBN)]))

        repo = OdiloRepository(catalog)
        repo.search(_ISBN)
        repo.search(_ISBN)

        assert len(post_calls) == 1

    def test_refetches_token_once_expired(self, monkeypatch, catalog):
        post_calls = []
        monkeypatch.setattr(httpx, "post", lambda *a, **k: (post_calls.append(1), _token_response())[1])
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response([_record(_ISBN)]))

        repo = OdiloRepository(catalog)
        repo.search(_ISBN)

        expired = datetime.now(UTC) - timedelta(seconds=1)
        token, _ = OdiloRepository._token_cache[_BASE_URL]
        OdiloRepository._token_cache[_BASE_URL] = (token, expired)

        repo.search(_ISBN)

        assert len(post_calls) == 2

    def test_sends_basic_auth_with_catalog_credentials(self, monkeypatch, catalog):
        captured_auth = {}

        def fake_post(*args, auth=None, **kwargs):
            captured_auth["auth"] = auth
            return _token_response()

        monkeypatch.setattr(httpx, "post", fake_post)
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response([_record(_ISBN)]))

        OdiloRepository(catalog).search(_ISBN)

        assert captured_auth["auth"] == ("NgOpac", "kvFqFy1i0Y4eUJhM")
