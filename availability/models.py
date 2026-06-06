from django.db import models

from core.models import CacheableModel


class Catalog(models.Model):
    ODILO = "odilo"
    WEB = "web"
    BACKEND_CHOICES = [(ODILO, "Odilo JSON"), (WEB, "Web scraping")]

    name = models.CharField(max_length=255)
    community = models.CharField(max_length=100)
    base_url = models.URLField()
    backend = models.CharField(max_length=20, choices=BACKEND_CHOICES, default=ODILO)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class Copy(models.Model):
    isbn = models.CharField(max_length=13, db_index=True)
    catalog = models.ForeignKey(Catalog, on_delete=models.CASCADE, related_name="copies")
    available = models.BooleanField(null=True)
    borrow_url = models.URLField(blank=True)

    class Meta:
        verbose_name_plural = "copies"
        unique_together = [("isbn", "catalog", "source")]

    def __str__(self) -> str:
        return f"{self.isbn} @ {self.catalog}"