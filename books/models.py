from __future__ import annotations

from django.db import models

from books.dtos import BookDTO, BookFilterDTO, CollectionDTO, CollectionFilterDTO, EditionDTO, FacetDTO
from core.models import CacheableModel


class Collection(CacheableModel):
    CID_FIELD = "external_id"

    external_id = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    cover_image = models.URLField(blank=True)
    book_count = models.PositiveIntegerField(default=0)
    selection_author = models.CharField(max_length=255, blank=True)
    filter_config = models.JSONField(default=dict)
    books = models.ManyToManyField("Book", through="CollectionBook", related_name="collections")

    class Meta:
        unique_together = [("external_id", "source")]

    def __str__(self) -> str:
        return self.title

    @classmethod
    def update_cache(cls, dto: CollectionDTO, books: list[Book]) -> Collection:
        collection, _ = cls.objects.update_or_create(
            external_id=dto.external_id,
            source=dto.source,
            defaults={
                "title": dto.title,
                "description": dto.description,
                "cover_image": dto.cover_image,
                "book_count": dto.book_count,
                "selection_author": dto.selection_author,
                "filter_config": dto.filter_config.model_dump(),
            },
        )
        collection.collection_books.all().delete()
        CollectionBook.objects.bulk_create([
            CollectionBook(collection=collection, book=book, order=i)
            for i, book in enumerate(books)
        ])
        return collection


class Book(CacheableModel):
    CID_FIELD = "external_id"

    external_id = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    cover_image = models.URLField(blank=True)
    language = models.CharField(max_length=10, blank=True)
    rating = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = [("external_id", "source")]

    def __str__(self) -> str:
        return self.title

    @classmethod
    def update_cache(cls, dto: BookDTO) -> Book:
        book, _ = cls.objects.update_or_create(
            external_id=dto.external_id,
            source=dto.source,
            defaults={
                "title": dto.title,
                "author": dto.author,
                "cover_image": dto.cover_image,
                "language": dto.language,
                "rating": dto.rating,
            },
        )
        return book


class Edition(CacheableModel):
    CID_FIELD = "isbn"

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="editions")
    isbn = models.CharField(max_length=13, db_index=True)
    format = models.CharField(max_length=50, blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    published_date = models.CharField(max_length=20, blank=True)

    class Meta:
        unique_together = [("isbn", "source")]

    def __str__(self) -> str:
        return f"{self.isbn} ({self.book})"

    @classmethod
    def update_cache(cls, dto: EditionDTO, book: Book) -> Edition:
        edition, _ = cls.objects.update_or_create(
            isbn=dto.isbn,
            source=dto.source,
            defaults={
                "book": book,
                "format": dto.format,
                "publisher": dto.publisher,
                "published_date": dto.published_date,
            },
        )
        return edition


class CollectionBook(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name="collection_books")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="collection_books")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("collection", "book")]
        ordering = ["order"]


class Facet(CacheableModel):
    CID_FIELD = "slug"
    DEFAULT_CACHE_TTL = 3600

    slug = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    filter_config = models.JSONField(default=dict)
    collections = models.ManyToManyField(
        Collection,
        through="FacetCollection",
        related_name="facets",
        blank=True,
    )

    class Meta:
        unique_together = [("slug", "source")]

    def __str__(self) -> str:
        return self.title

    @classmethod
    def update_cache(cls, dto: FacetDTO, collections: list[Collection]) -> Facet:
        facet, _ = cls.objects.update_or_create(
            slug=dto.slug,
            source=dto.source,
            defaults={
                "title": dto.title,
                "description": dto.description,
                "filter_config": dto.filter_config.model_dump(),
            },
        )
        facet.facet_collections.all().delete()
        FacetCollection.objects.bulk_create([
            FacetCollection(facet=facet, collection=collection, order=i)
            for i, collection in enumerate(collections)
        ])
        return facet


class FacetCollection(models.Model):
    facet = models.ForeignKey(Facet, on_delete=models.CASCADE, related_name="facet_collections")
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name="facet_collections")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("facet", "collection")]
        ordering = ["order"]