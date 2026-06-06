from django.db import models


class Catalog(models.Model):
    ODILO = "odilo"
    WEB = "web"
    BACKEND_CHOICES = [(ODILO, "Odilo JSON"), (WEB, "Web scraping")]

    name = models.CharField(max_length=255)
    community = models.CharField(max_length=100)
    base_url = models.URLField()
    backend = models.CharField(max_length=20, choices=BACKEND_CHOICES, default=ODILO)
    cached_at = models.DateTimeField(null=True, blank=True)
    cache_ttl = models.PositiveIntegerField(default=3600)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class Library(models.Model):
    name = models.CharField(max_length=255)
    catalog = models.ForeignKey(Catalog, on_delete=models.CASCADE, related_name="libraries")
    cached_at = models.DateTimeField(null=True, blank=True)
    cache_ttl = models.PositiveIntegerField(default=3600)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.catalog})"

    class Meta:
        verbose_name_plural = "libraries"


class Copy(models.Model):
    isbn = models.CharField(max_length=13, db_index=True)
    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name="copies")
    available = models.BooleanField(null=True)
    borrow_url = models.URLField(blank=True)
    title = models.CharField(max_length=255, blank=True)
    author = models.CharField(max_length=255, blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    published_date = models.CharField(max_length=20, blank=True)
    cached_at = models.DateTimeField(null=True, blank=True)
    cache_ttl = models.PositiveIntegerField(default=3600)

    def __str__(self) -> str:
        return f"{self.isbn} @ {self.library}"

    class Meta:
        verbose_name_plural = "copies"
