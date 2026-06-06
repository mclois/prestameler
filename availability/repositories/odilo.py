from __future__ import annotations

import httpx

from availability.dtos import CopyDTO
from availability.repositories.base import AvailabilityRepositoryBase

_TIMEOUT = 10


class OdiloRepository(AvailabilityRepositoryBase):
    """Availability repository for eBiblio catalogs with an Odilo JSON backend.

    Endpoint pattern: {base_url}/api/v1/resources?isbn={isbn}
    Confirm the exact response shape by inspecting DevTools → Network → Fetch/XHR.
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def search(self, isbn: str) -> list[CopyDTO]:
        url = f"{self._base_url}/api/v1/resources?isbn={isbn}"
        response = httpx.get(url, timeout=_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
        # TODO: parse response.json() once the endpoint shape is confirmed
        raise NotImplementedError
