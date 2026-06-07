from __future__ import annotations

from availability.dtos import CopyDTO
from availability.repositories.composite import CompositeRepository


class AvailabilityManager:
    def __init__(self) -> None:
        self._repo = CompositeRepository()

    def get_copies(self, isbn: str) -> list[CopyDTO]:
        from availability.models import Copy  # local import avoids app-registry issues

        copies = self._repo.search(isbn)
        for dto in copies:
            Copy.update_cache(dto)
        return copies
