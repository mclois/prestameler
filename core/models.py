from datetime import timedelta
from typing import ClassVar, Self

from django.db import models
from django.utils import timezone


class CacheableModel(models.Model):
    DEFAULT_CACHE_TTL: int = 3600
    CID_FIELD: ClassVar[str]

    cached_at = models.DateTimeField(auto_now=True)
    cache_ttl = models.PositiveIntegerField()
    source = models.CharField(max_length=50, db_index=True)

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not cls._meta.abstract and not hasattr(cls, "CID_FIELD"):
            raise TypeError(f"{cls.__name__} debe declarar CID_FIELD")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.cache_ttl:
            self.cache_ttl = self.DEFAULT_CACHE_TTL
        super().save(*args, **kwargs)

    @property
    def cid(self) -> str:
        return str(getattr(self, self.CID_FIELD))

    @classmethod
    def get_cached(cls, cid: str) -> Self | None:
        return cls.objects.filter(**{cls.CID_FIELD: cid}).first()

    @property
    def is_stale(self) -> bool:
        expiry = self.cached_at + timedelta(seconds=self.cache_ttl)
        return timezone.now() > expiry