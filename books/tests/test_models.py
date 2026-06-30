from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from books.dtos import BookDTO, CollectionDTO, EditionDTO
from books.models import Book, Collection, CollectionBook, Edition

pytestmark = pytest.mark.django_db


@pytest.fixture
def book():
    return Book.objects.create(
        external_id="hc-12345",
        title="Cien años de soledad",
        author="Gabriel García Márquez",
        cover_image="https://hardcover.app/covers/12345.jpg",
        language="es",
        rating=4.5,
        source="hardcover",
    )


@pytest.fixture
def collection():
    return Collection.objects.create(
        external_id="hc-col-99",
        title="Grandes clásicos",
        description="Los mejores clásicos de la literatura",
        cover_image="https://hardcover.app/covers/col99.jpg",
        book_count=5,
        selection_author="Redacción",
        source="hardcover",
    )


@pytest.fixture
def edition(book):
    return Edition.objects.create(
        isbn="9788437604947",
        book=book,
        format="ebook",
        publisher="Cátedra",
        published_date="2003-01-01",
        source="hardcover",
    )


class TestCollectionCRUD:
    def test_create_with_all_fields(self):
        collection = Collection.objects.create(
            external_id="hc-col-1",
            title="Grandes clásicos",
            description="Los mejores clásicos de la literatura",
            cover_image="https://hardcover.app/covers/col1.jpg",
            book_count=5,
            selection_author="Redacción",
            source="hardcover",
        )

        collection.refresh_from_db()
        assert collection.external_id == "hc-col-1"
        assert collection.title == "Grandes clásicos"
        assert collection.description == "Los mejores clásicos de la literatura"
        assert collection.cover_image == "https://hardcover.app/covers/col1.jpg"
        assert collection.book_count == 5
        assert collection.selection_author == "Redacción"
        assert collection.source == "hardcover"

    def test_create_with_only_required_fields(self):
        collection = Collection.objects.create(
            external_id="hc-col-1",
            title="Colección mínima",
            source="hardcover",
        )

        collection.refresh_from_db()
        assert collection.cache_ttl == Collection.DEFAULT_CACHE_TTL
        assert collection.description == ""
        assert collection.cover_image == ""
        assert collection.book_count == 0
        assert collection.selection_author == ""

    def test_create_missing_required_fields_fails_validation(self):
        collection = Collection(title="Sin ID externo", source="hardcover")

        with pytest.raises(ValidationError):
            collection.full_clean()

    def test_load_existing(self, collection):
        loaded = Collection.objects.get(pk=collection.pk)

        assert loaded == collection

    def test_load_missing_raises_does_not_exist(self):
        with pytest.raises(Collection.DoesNotExist):
            Collection.objects.get(pk=999999)

    def test_update_all_fields(self, collection):
        collection.external_id = "hc-col-100"
        collection.title = "Clásicos actualizados"
        collection.description = "Nueva descripción"
        collection.cover_image = "https://hardcover.app/covers/col100.jpg"
        collection.book_count = 10
        collection.selection_author = "Equipo editorial"
        collection.source = "openlibrary"
        collection.save()

        collection.refresh_from_db()
        assert collection.external_id == "hc-col-100"
        assert collection.title == "Clásicos actualizados"
        assert collection.description == "Nueva descripción"
        assert collection.cover_image == "https://hardcover.app/covers/col100.jpg"
        assert collection.book_count == 10
        assert collection.selection_author == "Equipo editorial"
        assert collection.source == "openlibrary"

    def test_update_missing_required_fields_fails_validation(self, collection):
        collection.title = ""

        with pytest.raises(ValidationError):
            collection.full_clean()

    def test_delete_existing(self, collection):
        pk = collection.pk

        collection.delete()

        assert not Collection.objects.filter(pk=pk).exists()

    def test_delete_missing_is_noop(self):
        deleted_count, _ = Collection.objects.filter(pk=999999).delete()

        assert deleted_count == 0


class TestBookCRUD:
    def test_create_with_all_fields(self):
        book = Book.objects.create(
            external_id="hc-12345",
            title="Cien años de soledad",
            author="Gabriel García Márquez",
            cover_image="https://hardcover.app/covers/12345.jpg",
            language="es",
            rating=4.5,
            source="hardcover",
        )

        book.refresh_from_db()
        assert book.external_id == "hc-12345"
        assert book.title == "Cien años de soledad"
        assert book.author == "Gabriel García Márquez"
        assert book.cover_image == "https://hardcover.app/covers/12345.jpg"
        assert book.language == "es"
        assert book.rating == 4.5
        assert book.source == "hardcover"

    def test_create_with_only_required_fields(self):
        book = Book.objects.create(
            external_id="hc-999",
            title="Libro sin detalles",
            source="hardcover",
        )

        book.refresh_from_db()
        assert book.cache_ttl == Book.DEFAULT_CACHE_TTL
        assert book.author == ""
        assert book.cover_image == ""
        assert book.language == ""
        assert book.rating is None

    def test_create_missing_required_fields_fails_validation(self):
        book = Book(author="Anónimo", source="hardcover")

        with pytest.raises(ValidationError):
            book.full_clean()

    def test_load_existing(self, book):
        loaded = Book.objects.get(pk=book.pk)

        assert loaded == book

    def test_load_missing_raises_does_not_exist(self):
        with pytest.raises(Book.DoesNotExist):
            Book.objects.get(pk=999999)

    def test_update_all_fields(self, book):
        book.external_id = "hc-99999"
        book.title = "Cien años de soledad (edición revisada)"
        book.author = "G. García Márquez"
        book.cover_image = "https://hardcover.app/covers/99999.jpg"
        book.language = "en"
        book.rating = 4.8
        book.source = "openlibrary"
        book.save()

        book.refresh_from_db()
        assert book.external_id == "hc-99999"
        assert book.title == "Cien años de soledad (edición revisada)"
        assert book.author == "G. García Márquez"
        assert book.cover_image == "https://hardcover.app/covers/99999.jpg"
        assert book.language == "en"
        assert book.rating == 4.8
        assert book.source == "openlibrary"

    def test_update_missing_required_fields_fails_validation(self, book):
        book.title = ""

        with pytest.raises(ValidationError):
            book.full_clean()

    def test_delete_existing(self, book):
        pk = book.pk

        book.delete()

        assert not Book.objects.filter(pk=pk).exists()

    def test_delete_missing_is_noop(self):
        deleted_count, _ = Book.objects.filter(pk=999999).delete()

        assert deleted_count == 0


class TestEditionCRUD:
    def test_create_with_all_fields(self, book):
        edition = Edition.objects.create(
            isbn="9788437604947",
            book=book,
            format="ebook",
            publisher="Cátedra",
            published_date="2003-01-01",
            source="hardcover",
        )

        edition.refresh_from_db()
        assert edition.isbn == "9788437604947"
        assert edition.book == book
        assert edition.format == "ebook"
        assert edition.publisher == "Cátedra"
        assert edition.published_date == "2003-01-01"
        assert edition.source == "hardcover"

    def test_create_with_only_required_fields(self, book):
        edition = Edition.objects.create(isbn="9780000000001", book=book, source="hardcover")

        edition.refresh_from_db()
        assert edition.cache_ttl == Edition.DEFAULT_CACHE_TTL
        assert edition.format == ""
        assert edition.publisher == ""
        assert edition.published_date == ""

    def test_create_missing_required_fields_fails_validation(self, book):
        edition = Edition(book=book, format="ebook", source="hardcover")

        with pytest.raises(ValidationError):
            edition.full_clean()

    def test_load_existing(self, edition):
        loaded = Edition.objects.get(pk=edition.pk)

        assert loaded == edition

    def test_load_missing_raises_does_not_exist(self):
        with pytest.raises(Edition.DoesNotExist):
            Edition.objects.get(pk=999999)

    def test_update_all_fields(self, edition):
        other_book = Book.objects.create(
            external_id="hc-54321",
            title="El amor en los tiempos del cólera",
            source="hardcover",
        )

        edition.isbn = "9780000000099"
        edition.book = other_book
        edition.format = "pdf"
        edition.publisher = "Planeta"
        edition.published_date = "2010-06-15"
        edition.source = "openlibrary"
        edition.save()

        edition.refresh_from_db()
        assert edition.isbn == "9780000000099"
        assert edition.book == other_book
        assert edition.format == "pdf"
        assert edition.publisher == "Planeta"
        assert edition.published_date == "2010-06-15"
        assert edition.source == "openlibrary"

    def test_update_missing_required_fields_fails_validation(self, edition):
        edition.isbn = ""

        with pytest.raises(ValidationError):
            edition.full_clean()

    def test_delete_existing(self, edition):
        pk = edition.pk

        edition.delete()

        assert not Edition.objects.filter(pk=pk).exists()

    def test_delete_missing_is_noop(self):
        deleted_count, _ = Edition.objects.filter(pk=999999).delete()

        assert deleted_count == 0


class TestCollectionUpdateCache:
    def test_creates_when_no_matching_collection_exists(self, book):
        dto = CollectionDTO(
            external_id="hc-col-1",
            title="Grandes clásicos",
            description="Los mejores clásicos",
            cover_image="https://hardcover.app/covers/col1.jpg",
            book_count=1,
            selection_author="Redacción",
            source="hardcover",
        )

        collection = Collection.update_cache(dto, [book])

        assert Collection.objects.count() == 1
        collection.refresh_from_db()
        assert collection.external_id == "hc-col-1"
        assert collection.title == "Grandes clásicos"
        assert collection.source == "hardcover"
        assert list(collection.books.all()) == [book]

    def test_updates_existing_collection_for_same_external_id_and_source(self, collection):
        dto = CollectionDTO(
            external_id=collection.external_id,
            title="Título actualizado",
            description="Nueva descripción",
            book_count=99,
            source=collection.source,
        )

        updated = Collection.update_cache(dto, [])

        assert Collection.objects.count() == 1
        assert updated.pk == collection.pk
        updated.refresh_from_db()
        assert updated.title == "Título actualizado"
        assert updated.description == "Nueva descripción"
        assert updated.book_count == 99

    def test_refreshes_cached_at_for_existing_collection(self, collection):
        stale = timezone.now() - timezone.timedelta(hours=1)
        Collection.objects.filter(pk=collection.pk).update(cached_at=stale)
        dto = CollectionDTO(
            external_id=collection.external_id,
            title=collection.title,
            source=collection.source,
        )

        updated = Collection.update_cache(dto, [])

        updated.refresh_from_db()
        assert updated.cached_at > stale

    def test_replaces_books_list_on_update(self, collection, book):
        other_book = Book.objects.create(
            external_id="hc-54321",
            title="El amor en los tiempos del cólera",
            source="hardcover",
        )
        CollectionBook.objects.create(collection=collection, book=book, order=0)
        dto = CollectionDTO(
            external_id=collection.external_id,
            title=collection.title,
            source=collection.source,
        )

        Collection.update_cache(dto, [other_book])

        collection.refresh_from_db()
        assert list(collection.books.all()) == [other_book]

    def test_does_not_collide_across_sources_for_same_external_id(self, collection):
        dto = CollectionDTO(
            external_id=collection.external_id,
            title="Misma colección, otra fuente",
            source="openlibrary",
        )

        other_collection = Collection.update_cache(dto, [])

        assert other_collection.pk != collection.pk
        assert Collection.objects.filter(external_id=collection.external_id).count() == 2


class TestBookUpdateCache:
    def test_creates_when_no_matching_book_exists(self):
        dto = BookDTO(
            external_id="hc-12345",
            title="Cien años de soledad",
            author="Gabriel García Márquez",
            cover_image="https://hardcover.app/covers/12345.jpg",
            language="es",
            rating=4.5,
            source="hardcover",
        )

        book = Book.update_cache(dto)

        assert Book.objects.count() == 1
        book.refresh_from_db()
        assert book.external_id == "hc-12345"
        assert book.title == "Cien años de soledad"
        assert book.author == "Gabriel García Márquez"
        assert book.rating == 4.5
        assert book.source == "hardcover"

    def test_updates_existing_book_for_same_external_id_and_source(self, book):
        dto = BookDTO(
            external_id=book.external_id,
            title="Cien años de soledad (nueva edición)",
            author="G. García Márquez",
            rating=4.8,
            source=book.source,
        )

        updated = Book.update_cache(dto)

        assert Book.objects.count() == 1
        assert updated.pk == book.pk
        updated.refresh_from_db()
        assert updated.title == "Cien años de soledad (nueva edición)"
        assert updated.author == "G. García Márquez"
        assert updated.rating == 4.8

    def test_refreshes_cached_at_for_existing_book(self, book):
        stale = timezone.now() - timezone.timedelta(hours=1)
        Book.objects.filter(pk=book.pk).update(cached_at=stale)
        dto = BookDTO(
            external_id=book.external_id,
            title=book.title,
            source=book.source,
        )

        updated = Book.update_cache(dto)

        updated.refresh_from_db()
        assert updated.cached_at > stale

    def test_does_not_collide_across_sources_for_same_external_id(self, book):
        dto = BookDTO(
            external_id=book.external_id,
            title="Mismo libro, otra fuente",
            source="openlibrary",
        )

        other_book = Book.update_cache(dto)

        assert other_book.pk != book.pk
        assert Book.objects.filter(external_id=book.external_id).count() == 2


class TestEditionUpdateCache:
    def test_creates_when_no_matching_edition_exists(self, book):
        dto = EditionDTO(
            isbn="9788437604947",
            format="ebook",
            publisher="Cátedra",
            published_date="2003-01-01",
            source="hardcover",
        )

        edition = Edition.update_cache(dto, book)

        assert Edition.objects.count() == 1
        edition.refresh_from_db()
        assert edition.isbn == "9788437604947"
        assert edition.book == book
        assert edition.format == "ebook"
        assert edition.publisher == "Cátedra"
        assert edition.source == "hardcover"

    def test_updates_existing_edition_for_same_isbn_and_source(self, edition):
        dto = EditionDTO(
            isbn=edition.isbn,
            format="pdf",
            publisher="Planeta",
            published_date="2010-01-01",
            source=edition.source,
        )

        updated = Edition.update_cache(dto, edition.book)

        assert Edition.objects.count() == 1
        assert updated.pk == edition.pk
        updated.refresh_from_db()
        assert updated.format == "pdf"
        assert updated.publisher == "Planeta"
        assert updated.published_date == "2010-01-01"

    def test_refreshes_cached_at_for_existing_edition(self, edition):
        stale = timezone.now() - timezone.timedelta(hours=1)
        Edition.objects.filter(pk=edition.pk).update(cached_at=stale)
        dto = EditionDTO(isbn=edition.isbn, source=edition.source)

        updated = Edition.update_cache(dto, edition.book)

        updated.refresh_from_db()
        assert updated.cached_at > stale

    def test_does_not_collide_across_sources_for_same_isbn(self, edition):
        dto = EditionDTO(isbn=edition.isbn, format="epub", source="openlibrary")

        other_edition = Edition.update_cache(dto, edition.book)

        assert other_edition.pk != edition.pk
        assert Edition.objects.filter(isbn=edition.isbn).count() == 2