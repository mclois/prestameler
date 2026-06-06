from __future__ import annotations

from availability.dtos import CopyDTO
from availability.repositories.composite import CompositeRepository


class AvailabilityManager:
    def __init__(self) -> None:
        self._repo = CompositeRepository()

    def get_copies(self, isbn: str) -> list[CopyDTO]:
        raise NotImplementedError
