from __future__ import annotations

from abc import ABC, abstractmethod

from availability.dtos import CopyDTO


class AvailabilityRepositoryBase(ABC):
    @abstractmethod
    def search(self, isbn: str) -> list[CopyDTO]: ...
