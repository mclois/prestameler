from __future__ import annotations

import logging

from availability.models import Catalog, Copy
from availability.repositories.ebiblio_web import EbiblioWebRepository
from availability.repositories.odilo import OdiloRepository

logger = logging.getLogger(__name__)

_REGISTRY = {
    Catalog.ODILO: OdiloRepository,
    Catalog.WEB: EbiblioWebRepository,
}


class AvailabilityManager:
    def get_copies(self, isbn: str) -> list[Copy]:
        results: list[Copy] = []
        for catalog in Catalog.objects.filter(is_active=True):
            cached = Copy.objects.filter(isbn=isbn, catalog=catalog).first()
            if cached is not None and not cached.is_stale:
                logger.debug("cache hit: isbn=%s catalog=%s", isbn, catalog.name)
                results.append(cached)
            else:
                reason = "stale" if cached else "miss"
                logger.debug("cache %s, fetching: isbn=%s catalog=%s", reason, isbn, catalog.name)
                fresh = _REGISTRY[catalog.backend](catalog).search(isbn)
                for dto in fresh:
                    dto.catalog_id = catalog.id
                    dto.source = catalog.name
                    results.append(Copy.update_cache(dto))
        return results
