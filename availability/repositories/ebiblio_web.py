from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from availability.dtos import CopyDTO
from availability.repositories.base import AvailabilityRepositoryBase

if TYPE_CHECKING:
    from availability.models import Catalog

_ANCHOR_SELECTOR = "section ul.list-details li a"
_TITLE_SELECTOR = "header h3"
_FORMAT_SELECTOR = ".details-content__aside h4"
_AUTHOR_SELECTOR = "header .contributors"
_COVER_IMAGE_SELECTOR = ".view-details__cover img"
_TIMEOUT = 10


class EbiblioWebRepository(AvailabilityRepositoryBase):
    """Availability repository for eBiblio catalogs without Odilo JSON API.

    Scrapes the public search page for borrow availability and book metadata.
    """

    def __init__(self, catalog: Catalog) -> None:
        self._base_url = catalog.base_url.rstrip("/")

    def search(self, isbn: str) -> list[CopyDTO]:
        soup = self._fetch_soup(isbn)
        borrow_url = self._extract_borrow_url(soup)
        if borrow_url is None:
            return []
        return [
            CopyDTO(
                isbn=isbn,
                borrow_url=borrow_url,
                available=True,
                title=self._extract_title(soup),
                author=self._extract_author(soup),
                format=self._extract_format(soup),
                language=self._extract_language(soup),
                cover_image=self._extract_cover_image(soup),
            )
        ]

    def _fetch_soup(self, isbn: str) -> BeautifulSoup:
        search_url = f"{self._base_url}/resources?isbn={isbn}"
        response = httpx.get(search_url, timeout=_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def _extract_borrow_url(self, soup: BeautifulSoup) -> str | None:
        """Return the borrow URL for the resource, or None if unavailable."""
        anchor = soup.select_one(_ANCHOR_SELECTOR)
        if anchor is None:
            return None

        href = anchor.get("href", "")
        # The attribute can be relative; make it absolute.
        return urljoin(self._base_url, href) if href else None

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        node = soup.select_one(_TITLE_SELECTOR)
        return node.get_text(strip=True) if node else ""

    @staticmethod
    def _extract_author(soup: BeautifulSoup) -> str:
        node = soup.select_one(_AUTHOR_SELECTOR)
        return node.get_text(strip=True) if node else ""

    @staticmethod
    def _extract_format(soup: BeautifulSoup) -> str:
        node = soup.select_one(_FORMAT_SELECTOR)
        return node.get_text(strip=True) if node else ""

    @staticmethod
    def _extract_language(soup: BeautifulSoup) -> str:
        # Not present on the search-results page eBiblio serves for `_fetch_soup`.
        return ""

    def _extract_cover_image(self, soup: BeautifulSoup) -> str:
        node = soup.select_one(_COVER_IMAGE_SELECTOR)
        if node is None:
            return ""
        src = node.get("src", "")
        return urljoin(self._base_url, src) if src else ""
