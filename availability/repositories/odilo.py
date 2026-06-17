from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

import httpx

from availability.dtos import CopyDTO
from availability.repositories.base import AvailabilityRepositoryBase

if TYPE_CHECKING:
    from availability.models import Catalog

_TIMEOUT = 10
_TOKEN_EXPIRY_MARGIN = timedelta(seconds=30)


class OdiloRepository(AvailabilityRepositoryBase):
    """Availability repository for eBiblio catalogs with an Odilo OPAC backend.

    Authenticates via OAuth2 client_credentials (Basic auth with the
    catalog's odilo_client_id/secret) against {base_url}/opac/api/v2/token,
    then searches {base_url}/opac/api/v2/records with a Bearer token.
    """

    _token_cache: ClassVar[dict[str, tuple[str, datetime]]] = {}

    def __init__(self, catalog: Catalog) -> None:
        self._base_url = catalog.base_url.rstrip("/")
        self._client_id = catalog.odilo_client_id
        self._client_secret = catalog.odilo_client_secret

    def search(self, isbn: str) -> list[CopyDTO]:
        response = httpx.get(
            f"{self._base_url}/opac/api/v2/records",
            params={
                "facets": 'format_facet_ss:"EBOOK"',
                "query": f"allfields_txt:{isbn}",
                "availability": "true",
            },
            headers={"Authorization": f"Bearer {self._get_token()}"},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        return [
            CopyDTO(
                isbn=record["isbn"],
                available=(record.get("availability") or {}).get("availableToCheckout"),
                borrow_url=f"{self._base_url}/info/{record['id']}",
            )
            for record in response.json()
            if record.get("isbn") == isbn
        ]

    def _get_token(self) -> str:
        cached = self._token_cache.get(self._base_url)
        if cached is not None and cached[1] > datetime.now(UTC):
            return cached[0]

        response = httpx.post(
            f"{self._base_url}/opac/api/v2/token",
            auth=(self._client_id, self._client_secret),
            data={"grant_type": "client_credentials"},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()

        token = payload["token"]
        expiry = datetime.now(UTC) + timedelta(seconds=payload["expiresIn"]) - _TOKEN_EXPIRY_MARGIN
        self._token_cache[self._base_url] = (token, expiry)
        return token
