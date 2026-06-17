from __future__ import annotations

from django.db import models

from availability.dtos import CopyDTO
from core.models import CacheableModel


class Catalog(models.Model):
    ODILO = "odilo"
    WEB = "web"
    BACKEND_CHOICES = [(ODILO, "Odilo JSON"), (WEB, "Web scraping")]

    name = models.CharField(max_length=255)
    community = models.CharField(max_length=100)
    base_url = models.URLField()
    backend = models.CharField(max_length=20, choices=BACKEND_CHOICES, default=WEB)
    odilo_client_id = models.CharField(max_length=255, blank=True, default="")
    odilo_client_secret = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class Copy(CacheableModel):
    CID_FIELD = "isbn"

    isbn = models.CharField(max_length=13, db_index=True)
    catalog = models.ForeignKey(Catalog, on_delete=models.CASCADE, related_name="copies")
    available = models.BooleanField(null=True)
    borrow_url = models.URLField(blank=True)

    class Meta:
        verbose_name_plural = "copies"
        unique_together = [("isbn", "catalog")]

    def __str__(self) -> str:
        return f"{self.isbn} @ {self.catalog}"

    @classmethod
    def update_cache(cls, dto: CopyDTO) -> Copy:
        copy, _ = cls.objects.update_or_create(
            isbn=dto.isbn,
            catalog_id=dto.catalog_id,
            defaults={
                "available": dto.available,
                "borrow_url": dto.borrow_url or "",
                "source": dto.source,
            },
        )
        return copy