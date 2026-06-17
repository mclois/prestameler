from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from availability.dtos import CopyDTO
from availability.managers import AvailabilityManager, _REGISTRY
from availability.models import Catalog, Copy

pytestmark = pytest.mark.django_db

_ISBN = "9788491051234"


@pytest.fixture
def catalog():
    return Catalog.objects.create(
        name="eBiblio Test",
        community="Test",
        base_url="https://test.ebiblio.es",
        backend=Catalog.WEB,
        is_active=True,
    )


@pytest.fixture
def fresh_copy(catalog):
    return Copy.objects.create(
        isbn=_ISBN,
        catalog=catalog,
        source=catalog.name,
        cache_ttl=3600,
        available=True,
        borrow_url="https://test.ebiblio.es/prestamo/1",
    )


@pytest.fixture
def stale_copy(fresh_copy):
    past = timezone.now() - timedelta(hours=2)
    Copy.objects.filter(pk=fresh_copy.pk).update(cached_at=past)
    fresh_copy.refresh_from_db()
    return fresh_copy


class FakeRepo:
    """Configurable stub for any backend repo."""

    def __init__(self, returns: list[CopyDTO]):
        self._returns = returns
        self.called = False

    def __call__(self, catalog):
        self.called = True
        return self

    def search(self, isbn: str) -> list[CopyDTO]:
        return self._returns


class TestGetCopies:
    def test_returns_empty_when_no_active_catalogs(self):
        results = AvailabilityManager().get_copies(_ISBN)

        assert results == []

    def test_skips_inactive_catalog(self, catalog):
        catalog.is_active = False
        catalog.save()

        results = AvailabilityManager().get_copies(_ISBN)

        assert results == []

    def test_returns_cached_copy_without_calling_repo(self, catalog, fresh_copy, monkeypatch):
        fake = FakeRepo(returns=[])
        monkeypatch.setitem(_REGISTRY, Catalog.WEB, fake)

        results = AvailabilityManager().get_copies(_ISBN)

        assert not fake.called
        assert results == [fresh_copy]

    def test_calls_repo_when_no_cache_exists(self, catalog, monkeypatch):
        dto = CopyDTO(isbn=_ISBN, available=False, borrow_url="https://test.ebiblio.es/prestamo/2")
        fake = FakeRepo(returns=[dto])
        monkeypatch.setitem(_REGISTRY, Catalog.WEB, fake)

        results = AvailabilityManager().get_copies(_ISBN)

        assert fake.called
        assert len(results) == 1
        assert isinstance(results[0], Copy)
        assert results[0].available is False

    def test_calls_repo_when_cache_is_stale(self, catalog, stale_copy, monkeypatch):
        dto = CopyDTO(isbn=_ISBN, available=False, borrow_url="https://test.ebiblio.es/prestamo/3")
        fake = FakeRepo(returns=[dto])
        monkeypatch.setitem(_REGISTRY, Catalog.WEB, fake)

        results = AvailabilityManager().get_copies(_ISBN)

        assert fake.called
        assert results[0].available is False

    def test_fresh_fetch_saves_to_cache(self, catalog, monkeypatch):
        dto = CopyDTO(isbn=_ISBN, available=True, borrow_url="https://test.ebiblio.es/prestamo/4")
        monkeypatch.setitem(_REGISTRY, Catalog.WEB, FakeRepo(returns=[dto]))

        AvailabilityManager().get_copies(_ISBN)

        assert Copy.objects.filter(isbn=_ISBN, catalog=catalog).exists()

    def test_fresh_fetch_sets_catalog_and_source(self, catalog, monkeypatch):
        dto = CopyDTO(isbn=_ISBN, available=True)
        monkeypatch.setitem(_REGISTRY, Catalog.WEB, FakeRepo(returns=[dto]))

        results = AvailabilityManager().get_copies(_ISBN)

        assert results[0].catalog == catalog
        assert results[0].source == catalog.name

    def test_aggregates_results_across_multiple_catalogs(self, monkeypatch):
        cat_a = Catalog.objects.create(
            name="A", community="A", base_url="https://a.ebiblio.es", backend=Catalog.WEB, is_active=True
        )
        cat_b = Catalog.objects.create(
            name="B", community="B", base_url="https://b.ebiblio.es", backend=Catalog.WEB, is_active=True
        )

        def fake_repo_cls(catalog):
            return FakeRepo(returns=[CopyDTO(isbn=_ISBN, available=True)])

        monkeypatch.setitem(_REGISTRY, Catalog.WEB, fake_repo_cls)

        results = AvailabilityManager().get_copies(_ISBN)

        assert len(results) == 2
        catalog_ids = {r.catalog_id for r in results}
        assert catalog_ids == {cat_a.pk, cat_b.pk}
