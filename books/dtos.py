from __future__ import annotations

from pydantic import BaseModel


class EditionDTO(BaseModel):
    isbn: str
    source: str = ""
    format: str = ""
    publisher: str = ""
    published_date: str = ""


class BookDTO(BaseModel):
    external_id: str
    source: str = ""
    title: str
    author: str = ""
    cover_image: str = ""
    language: str = ""
    rating: float | None = None
    editions: list[EditionDTO] = []


class CollectionDTO(BaseModel):
    external_id: str
    source: str = ""
    title: str
    description: str = ""
    cover_image: str = ""
    book_count: int = 0
    selection_author: str = ""
    books: list[BookDTO] = []


class CollectionFilterDTO(BaseModel):
    category: str | None = None
    tag_ids: list[int] | None = None
    user: str | None = None
    search_query: str | None = None
    limit: int = 20

    @property
    def cache_key(self) -> str:
        parts = []
        if self.category:
            parts.append(self.category)
        if self.tag_ids:
            parts.append("ids:" + ",".join(str(i) for i in sorted(self.tag_ids)))
        if self.user:
            parts.append(f"user:{self.user}")
        if self.search_query:
            parts.append(f"q:{self.search_query}")
        return "filter:" + ":".join(parts)


class FacetDTO(BaseModel):
    slug: str
    source: str = ""
    title: str
    description: str = ""
    filter_config: CollectionFilterDTO = CollectionFilterDTO()
    collections: list[CollectionDTO] = []