from __future__ import annotations

from availability.dtos import CopyDTO
from availability.repositories.base import AvailabilityRepositoryBase
from availability.repositories.ebiblio_web import EbiblioWebRepository
from availability.repositories.odilo import OdiloRepository

_REGISTRY: dict[str, type[AvailabilityRepositoryBase]] = {
    "odilo": OdiloRepository,
    "web": EbiblioWebRepository,
}


class CompositeRepository(AvailabilityRepositoryBase):
    """Fans out search across all active catalogs, dispatching to the right backend."""

    def search(self, isbn: str) -> list[CopyDTO]:
        from availability.models import Catalog  # local import avoids app-registry issues

        copies: list[CopyDTO] = []
        for catalog in Catalog.objects.filter(is_active=True):
            repo_cls = _REGISTRY[catalog.backend]
            found = repo_cls(catalog).search(isbn)
            for dto in found:
                dto.catalog_id = catalog.id
                dto.source = catalog.name
            copies += found
        return copies
