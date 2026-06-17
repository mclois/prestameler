from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from availability.dtos import CopyDTO
from availability.repositories.base import AvailabilityRepositoryBase

if TYPE_CHECKING:
    from availability.models import Catalog

_SELECTOR = "section ul.list-details li a"
_TIMEOUT = 10


class EbiblioWebRepository(AvailabilityRepositoryBase):
    """Availability repository for eBiblio catalogs without Odilo JSON API.

    Scrapes the public search page and returns the borrow URL for a given ISBN.
    """

    def __init__(self, catalog: Catalog) -> None:
        self._base_url = catalog.base_url.rstrip("/")

    def search(self, isbn: str) -> list[CopyDTO]:
        borrow_url = self._get_borrow_url(isbn)
        if borrow_url is None:
            return []
        return [CopyDTO(isbn=isbn, borrow_url=borrow_url, available=True)]

    def _get_borrow_url(self, isbn: str) -> str | None:
        """Return the borrow URL for *isbn*, or None if unavailable."""
        search_url = f"{self._base_url}/resources?isbn={isbn}"
        response = httpx.get(search_url, timeout=_TIMEOUT, follow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        anchor = soup.select_one(_SELECTOR)
        if anchor is None:
            return None

        href = anchor.get("href", "")
        # The attribute can be relative; make it absolute.
        return urljoin(self._base_url, href) if href else None
