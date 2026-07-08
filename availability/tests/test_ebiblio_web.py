from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from availability.repositories.ebiblio_web import EbiblioWebRepository

_BASE_URL = "https://galicia.ebiblio.es"
_ISBN = "9788491051234"
_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "ebiblio_web"


@pytest.fixture
def catalog():
    return SimpleNamespace(base_url=_BASE_URL)


def _html(
    *,
    anchor: str = '<li><a href="/prestamo/123">Prestar</a></li>',
    title: str = "<header><h3>El Quijote</h3></header>",
    format_: str = '<div class="details-content__aside"><h4>Libro electrónico</h4></div>',
    author: str = '<header><div class="contributors"><a>Miguel de Cervantes</a></div></header>',
    cover_image: str = '<div class="view-details__cover"><img src="/covers/123-small.jpg"></div>',
) -> str:
    return f"""
    <html><body>
    <section><ul class="list-details">{anchor}</ul></section>
    {title}
    {format_}
    {author}
    {cover_image}
    </body></html>
    """


def _response(html: str) -> httpx.Response:
    response = httpx.Response(200, text=html)
    response._request = httpx.Request("GET", _BASE_URL)
    return response


class TestSearch:
    def test_returns_copy_with_all_fields_when_all_selectors_match(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response(_html()))

        copies = EbiblioWebRepository(catalog).search(_ISBN)

        assert len(copies) == 1
        copy = copies[0]
        assert copy.isbn == _ISBN
        assert copy.available is True
        assert copy.borrow_url == f"{_BASE_URL}/prestamo/123"
        assert copy.title == "El Quijote"
        assert copy.author == "Miguel de Cervantes"
        assert copy.format == "Libro electrónico"
        assert copy.language == ""
        assert copy.cover_image == f"{_BASE_URL}/covers/123-small.jpg"

    def test_returns_empty_list_when_no_anchor_found(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response(_html(anchor="")))

        copies = EbiblioWebRepository(catalog).search(_ISBN)

        assert copies == []

    def test_defaults_title_to_empty_string_when_selector_missing(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response(_html(title="")))

        copies = EbiblioWebRepository(catalog).search(_ISBN)

        assert copies[0].title == ""

    def test_defaults_format_to_empty_string_when_selector_missing(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response(_html(format_="")))

        copies = EbiblioWebRepository(catalog).search(_ISBN)

        assert copies[0].format == ""

    def test_defaults_author_to_empty_string_when_selector_missing(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response(_html(author="")))

        copies = EbiblioWebRepository(catalog).search(_ISBN)

        assert copies[0].author == ""

    def test_defaults_cover_image_to_empty_string_when_selector_missing(self, monkeypatch, catalog):
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response(_html(cover_image="")))

        copies = EbiblioWebRepository(catalog).search(_ISBN)

        assert copies[0].cover_image == ""

    def test_resolves_relative_cover_image_against_base_url(self, monkeypatch, catalog):
        monkeypatch.setattr(
            httpx,
            "get",
            lambda *a, **k: _response(
                _html(cover_image='<div class="view-details__cover"><img src="/covers/999-small.jpg"></div>')
            ),
        )

        copies = EbiblioWebRepository(catalog).search(_ISBN)

        assert copies[0].cover_image == f"{_BASE_URL}/covers/999-small.jpg"

    def test_resolves_relative_borrow_url_against_base_url(self, monkeypatch, catalog):
        monkeypatch.setattr(
            httpx,
            "get",
            lambda *a, **k: _response(_html(anchor='<li><a href="/prestamo/999">x</a></li>')),
        )

        copies = EbiblioWebRepository(catalog).search(_ISBN)

        assert copies[0].borrow_url == f"{_BASE_URL}/prestamo/999"

    def test_fetches_page_only_once_per_search(self, monkeypatch, catalog):
        call_count = {"n": 0}

        def fake_get(*args, **kwargs):
            call_count["n"] += 1
            return _response(_html())

        monkeypatch.setattr(httpx, "get", fake_get)

        EbiblioWebRepository(catalog).search(_ISBN)

        assert call_count["n"] == 1


class TestSearchRealMarkup:
    """Regression test against a real eBiblio search-results snapshot.

    Guards against selectors that only match the synthetic `_html()` fixture
    and not eBiblio's actual markup (see git history for the `spoan`/`span`
    author-selector typo this caught).
    """

    def test_extracts_fields_from_real_search_results_page(self, monkeypatch, catalog):
        html = (_FIXTURES_DIR / "isbn-results.html").read_text()
        monkeypatch.setattr(httpx, "get", lambda *a, **k: _response(html))

        copies = EbiblioWebRepository(catalog).search(_ISBN)

        assert len(copies) == 1
        copy = copies[0]
        assert copy.borrow_url == f"{_BASE_URL}/resources/65d4bb216b25ca0001140ac9"
        assert copy.title == "La Rueda del Tiempo nº 01/14 El ojo del mundo"
        assert copy.author == "Robert Jordan"
        assert copy.format == "EPUB"
        assert copy.language == ""
        assert copy.cover_image == "https://covers.feedbooks.net/item/3203457.jpg?size=large&t=1693569871"
