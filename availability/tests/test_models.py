from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from availability.dtos import CopyDTO
from availability.models import Catalog, Copy

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog():
    return Catalog.objects.create(
        name="eBiblio Galicia",
        community="Galicia",
        base_url="https://galicia.ebiblio.es",
        backend=Catalog.WEB,
        is_active=True,
    )


@pytest.fixture
def copy(catalog):
    return Copy.objects.create(
        isbn="9788491051234",
        catalog=catalog,
        source="eBiblio Galicia",
        cache_ttl=1800,
        available=True,
        borrow_url="https://galicia.ebiblio.es/prestamo/123",
    )


class TestCatalogCRUD:
    def test_create_with_all_fields(self):
        catalog = Catalog.objects.create(
            name="eBiblio Galicia",
            community="Galicia",
            base_url="https://galicia.ebiblio.es",
            backend=Catalog.WEB,
            is_active=False,
        )

        catalog.refresh_from_db()
        assert catalog.name == "eBiblio Galicia"
        assert catalog.community == "Galicia"
        assert catalog.base_url == "https://galicia.ebiblio.es"
        assert catalog.backend == Catalog.WEB
        assert catalog.is_active is False

    def test_create_with_only_required_fields(self):
        catalog = Catalog.objects.create(
            name="eBiblio Extremadura",
            community="Extremadura",
            base_url="https://extremadura.ebiblio.es",
        )

        catalog.refresh_from_db()
        assert catalog.backend == Catalog.WEB
        assert catalog.is_active is True

    def test_create_missing_required_fields_fails_validation(self):
        catalog = Catalog(community="Galicia", base_url="https://galicia.ebiblio.es")

        with pytest.raises(ValidationError):
            catalog.full_clean()

    def test_load_existing(self, catalog):
        loaded = Catalog.objects.get(pk=catalog.pk)

        assert loaded == catalog

    def test_load_missing_raises_does_not_exist(self):
        with pytest.raises(Catalog.DoesNotExist):
            Catalog.objects.get(pk=999999)

    def test_update_all_fields(self, catalog):
        catalog.name = "eBiblio Galicia (actualizado)"
        catalog.community = "Galiza"
        catalog.base_url = "https://galicia2.ebiblio.es"
        catalog.backend = Catalog.ODILO
        catalog.is_active = False
        catalog.save()

        catalog.refresh_from_db()
        assert catalog.name == "eBiblio Galicia (actualizado)"
        assert catalog.community == "Galiza"
        assert catalog.base_url == "https://galicia2.ebiblio.es"
        assert catalog.backend == Catalog.ODILO
        assert catalog.is_active is False

    def test_update_missing_required_fields_fails_validation(self, catalog):
        catalog.name = ""

        with pytest.raises(ValidationError):
            catalog.full_clean()

    def test_delete_existing(self, catalog):
        pk = catalog.pk

        catalog.delete()

        assert not Catalog.objects.filter(pk=pk).exists()

    def test_delete_missing_is_noop(self):
        deleted_count, _ = Catalog.objects.filter(pk=999999).delete()

        assert deleted_count == 0


class TestCopyCRUD:
    def test_create_with_all_fields(self, catalog):
        copy = Copy.objects.create(
            isbn="9788491051234",
            catalog=catalog,
            source="odilo",
            cache_ttl=1800,
            available=True,
            borrow_url="https://galicia.ebiblio.es/prestamo/123",
        )

        copy.refresh_from_db()
        assert copy.isbn == "9788491051234"
        assert copy.catalog == catalog
        assert copy.source == "odilo"
        assert copy.cache_ttl == 1800
        assert copy.available is True
        assert copy.borrow_url == "https://galicia.ebiblio.es/prestamo/123"

    def test_create_with_only_required_fields(self, catalog):
        copy = Copy.objects.create(isbn="9788491051234", catalog=catalog, source="odilo")

        copy.refresh_from_db()
        assert copy.cache_ttl == Copy.DEFAULT_CACHE_TTL
        assert copy.available is None
        assert copy.borrow_url == ""

    def test_create_missing_required_fields_fails_validation(self, catalog):
        copy = Copy(catalog=catalog, source="odilo", cache_ttl=3600)

        with pytest.raises(ValidationError):
            copy.full_clean()

    def test_load_existing(self, copy):
        loaded = Copy.objects.get(pk=copy.pk)

        assert loaded == copy

    def test_load_missing_raises_does_not_exist(self):
        with pytest.raises(Copy.DoesNotExist):
            Copy.objects.get(pk=999999)

    def test_update_all_fields(self, copy):
        other_catalog = Catalog.objects.create(
            name="eBiblio Extremadura",
            community="Extremadura",
            base_url="https://extremadura.ebiblio.es",
        )

        copy.isbn = "9788491059999"
        copy.catalog = other_catalog
        copy.source = "web"
        copy.cache_ttl = 7200
        copy.available = False
        copy.borrow_url = "https://extremadura.ebiblio.es/prestamo/456"
        copy.save()

        copy.refresh_from_db()
        assert copy.isbn == "9788491059999"
        assert copy.catalog == other_catalog
        assert copy.source == "web"
        assert copy.cache_ttl == 7200
        assert copy.available is False
        assert copy.borrow_url == "https://extremadura.ebiblio.es/prestamo/456"

    def test_update_missing_required_fields_fails_validation(self, copy):
        copy.isbn = ""

        with pytest.raises(ValidationError):
            copy.full_clean()

    def test_delete_existing(self, copy):
        pk = copy.pk

        copy.delete()

        assert not Copy.objects.filter(pk=pk).exists()

    def test_delete_missing_is_noop(self):
        deleted_count, _ = Copy.objects.filter(pk=999999).delete()

        assert deleted_count == 0


class TestCopyUpdateCache:
    def test_creates_when_no_matching_copy_exists(self, catalog):
        dto = CopyDTO(
            isbn="9788491051234",
            catalog_id=catalog.pk,
            available=True,
            borrow_url="https://galicia.ebiblio.es/prestamo/123",
            source="odilo",
        )

        copy = Copy.update_cache(dto)

        assert Copy.objects.count() == 1
        copy.refresh_from_db()
        assert copy.isbn == "9788491051234"
        assert copy.catalog == catalog
        assert copy.available is True
        assert copy.borrow_url == "https://galicia.ebiblio.es/prestamo/123"
        assert copy.source == "odilo"

    def test_updates_existing_copy_for_same_isbn_and_catalog(self, copy):
        dto = CopyDTO(
            isbn=copy.isbn,
            catalog_id=copy.catalog_id,
            available=False,
            borrow_url="https://galicia.ebiblio.es/prestamo/999",
            source="web",
        )

        updated = Copy.update_cache(dto)

        assert Copy.objects.count() == 1
        assert updated.pk == copy.pk
        updated.refresh_from_db()
        assert updated.available is False
        assert updated.borrow_url == "https://galicia.ebiblio.es/prestamo/999"
        assert updated.source == "web"

    def test_refreshes_cached_at_for_existing_copy(self, copy):
        stale = timezone.now() - timezone.timedelta(hours=1)
        Copy.objects.filter(pk=copy.pk).update(cached_at=stale)
        dto = CopyDTO(
            isbn=copy.isbn,
            catalog_id=copy.catalog_id,
            available=copy.available,
            borrow_url=copy.borrow_url,
            source=copy.source,
        )

        updated = Copy.update_cache(dto)

        updated.refresh_from_db()
        assert updated.cached_at > stale

    def test_does_not_collide_across_catalogs_for_same_isbn(self, copy):
        other_catalog = Catalog.objects.create(
            name="eBiblio Extremadura",
            community="Extremadura",
            base_url="https://extremadura.ebiblio.es",
        )
        dto = CopyDTO(
            isbn=copy.isbn,
            catalog_id=other_catalog.pk,
            available=True,
            borrow_url="https://extremadura.ebiblio.es/prestamo/456",
            source="web",
        )

        other_copy = Copy.update_cache(dto)

        assert other_copy.pk != copy.pk
        assert Copy.objects.filter(isbn=copy.isbn).count() == 2
