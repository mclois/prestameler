from django.db import models


class Collection(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    cover_image = models.URLField(blank=True)
    book_count = models.PositiveIntegerField(default=0)
    selection_author = models.CharField(max_length=255, blank=True)
    external_id = models.CharField(max_length=255, blank=True, db_index=True)
    cached_at = models.DateTimeField(null=True, blank=True)
    cache_ttl = models.PositiveIntegerField(default=3600)
    tags = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return self.title


class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    cover_image = models.URLField(blank=True)
    language = models.CharField(max_length=10, blank=True)
    external_id = models.CharField(max_length=255, blank=True, db_index=True)
    cached_at = models.DateTimeField(null=True, blank=True)
    cache_ttl = models.PositiveIntegerField(default=3600)
    tags = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return self.title


class Edition(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="editions")
    isbn = models.CharField(max_length=13, db_index=True)
    format = models.CharField(max_length=50, blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    published_date = models.CharField(max_length=20, blank=True)
    cached_at = models.DateTimeField(null=True, blank=True)
    cache_ttl = models.PositiveIntegerField(default=3600)
    tags = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return f"{self.isbn} ({self.book})"
