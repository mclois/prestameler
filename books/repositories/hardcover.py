from __future__ import annotations

import httpx
from django.conf import settings

from books.dtos import BookDTO, BookFilterDTO, CollectionDTO, CollectionFilterDTO, EditionDTO, FacetDTO
from books.repositories.base import BookRepositoryBase

_ENDPOINT = "https://api.hardcover.app/v1/graphql"
_TIMEOUT = 10

_SEARCH_QUERY = """
query SearchBooks($query: String!) {
  search(query: $query, query_type: "Book", per_page: 20) {
    results
  }
}
"""

_GET_BOOK_QUERY = """
query GetBook($id: Int!) {
  books(where: {id: {_eq: $id}}, limit: 1) {
    id
    title
    contributions { author { name } }
    image { url }
    rating
    editions {
      isbn_10
      isbn_13
      language { code2 }
      physical_format
      publisher
      release_date
    }
  }
}
"""

_GET_COLLECTION_QUERY = """
query GetList($id: Int!) {
  lists(where: {id: {_eq: $id}}, limit: 1) {
    id
    name
    description
    books_count
    user { username }
    list_books(limit: 100, order_by: {position: asc}) {
      book {
        id
        title
        contributions { author { name } }
        image { url }
        rating
      }
    }
  }
}
"""

_GET_FEATURED_COLLECTIONS_QUERY = """
query GetFeaturedLists {
  lists(where: {featured: {_eq: true}}, limit: 20) {
    id
    name
    description
    books_count
    user { username }
    list_books(limit: 50, order_by: {position: asc}) {
      book {
        id
        title
        contributions { author { name } }
        image { url }
        rating
      }
    }
  }
}
"""

_GET_TAGS_QUERY = """
query GetTagsByCategory($category: String!, $limit: Int!) {
  tags(where: {tag_category: {category: {_eq: $category}}}, limit: $limit, order_by: {count: desc}) {
    id
    tag
    count
    taggings(limit: 50, where: {taggable_type: {_eq: "Book"}}) {
      book {
        id
        title
        contributions { author { name } }
        image { url }
        rating
      }
    }
  }
}
"""

_GET_TAG_QUERY = """
query GetTag($id: bigint!) {
  tags(where: {id: {_eq: $id}}, limit: 1) {
    id
    tag
    count
    taggings(limit: 50, where: {taggable_type: {_eq: "Book"}}) {
      book {
        id
        title
        contributions { author { name } }
        image { url }
        rating
      }
    }
  }
}
"""

# Maps CollectionFilterDTO.category -> (Hardcover tag_categories.category, facet slug, facet title)
_TAG_CATEGORIES = {
    "genre": ("Genre", "by-genre", "By Genre"),
    "mood": ("Mood", "by-mood", "By Mood"),
}


class HardcoverRepository(BookRepositoryBase):
    SOURCE = "hardcover"

    def __init__(self) -> None:
        self._token = settings.HARDCOVER_TOKEN

    def get_collections(self, filter_config: CollectionFilterDTO | None = None) -> FacetDTO:
        filter_config = filter_config or CollectionFilterDTO(featured=True)
        if filter_config.category in _TAG_CATEGORIES:
            return self._get_by_tag_category(filter_config)
        return self._get_featured(filter_config)

    def _get_featured(self, filter_config: CollectionFilterDTO) -> FacetDTO:
        data = self._gql(_GET_FEATURED_COLLECTIONS_QUERY)
        collections = [
            CollectionDTO(
                external_id=str(lst["id"]),
                source=self.SOURCE,
                title=lst["name"],
                description=lst.get("description") or "",
                cover_image="",
                book_count=lst.get("books_count") or 0,
                selection_author=(lst.get("user") or {}).get("username") or "",
                filter_config=BookFilterDTO(collection_id=str(lst["id"])),
                books=[self._book_dto(node["book"]) for node in lst.get("list_books") or []],
            )
            for lst in data["lists"]
        ]
        return FacetDTO(
            slug="featured",
            source=self.SOURCE,
            title="Featured",
            filter_config=filter_config,
            collections=collections,
        )

    def _get_by_tag_category(self, filter_config: CollectionFilterDTO) -> FacetDTO:
        category, slug, title = _TAG_CATEGORIES[filter_config.category]
        data = self._gql(_GET_TAGS_QUERY, {"category": category, "limit": filter_config.limit})
        collections = [
            CollectionDTO(
                external_id=f"tag:{tag['id']}",
                source=self.SOURCE,
                title=tag["tag"],
                book_count=tag.get("count") or 0,
                filter_config=BookFilterDTO(tag_id=tag["id"]),
                books=[self._book_dto(node["book"]) for node in tag.get("taggings") or []],
            )
            for tag in data["tags"]
        ]
        return FacetDTO(
            slug=slug,
            source=self.SOURCE,
            title=title,
            filter_config=filter_config,
            collections=collections,
        )

    def search(self, filter_config: BookFilterDTO) -> CollectionDTO | None:
        if filter_config.collection_id:
            return self._search_by_collection(filter_config)
        if filter_config.tag_id:
            return self._search_by_tag(filter_config)
        return self._search_by_query(filter_config)

    def _search_by_collection(self, filter_config: BookFilterDTO) -> CollectionDTO | None:
        data = self._gql(_GET_COLLECTION_QUERY, {"id": int(filter_config.collection_id)})
        lists = data.get("lists") or []
        if not lists:
            return None
        lst = lists[0]
        return CollectionDTO(
            external_id=str(lst["id"]),
            source=self.SOURCE,
            title=lst["name"],
            description=lst.get("description") or "",
            cover_image="",
            book_count=lst.get("books_count") or 0,
            selection_author=(lst.get("user") or {}).get("username") or "",
            filter_config=BookFilterDTO(collection_id=str(lst["id"])),
            books=[self._book_dto(node["book"]) for node in lst.get("list_books") or []],
        )

    def _search_by_tag(self, filter_config: BookFilterDTO) -> CollectionDTO | None:
        data = self._gql(_GET_TAG_QUERY, {"id": filter_config.tag_id})
        tags = data.get("tags") or []
        if not tags:
            return None
        tag = tags[0]
        return CollectionDTO(
            external_id=f"tag:{tag['id']}",
            source=self.SOURCE,
            title=tag["tag"],
            description=f'Books tagged "{tag["tag"]}"',
            book_count=tag.get("count") or 0,
            filter_config=BookFilterDTO(tag_id=tag["id"]),
            books=[self._book_dto(node["book"]) for node in tag.get("taggings") or []],
        )

    def _search_by_query(self, filter_config: BookFilterDTO) -> CollectionDTO:
        query = (filter_config.search_query or "").strip()
        data = self._gql(_SEARCH_QUERY, {"query": query})
        hits = (data["search"]["results"] or {}).get("hits") or []
        books = [self._book_dto(hit["document"]) for hit in hits]
        return CollectionDTO(
            external_id=f"search:{query.lower()}",
            source=self.SOURCE,
            title=query,
            description=f'Books matching "{query}"',
            cover_image="",
            book_count=len(books),
            filter_config=BookFilterDTO(search_query=query),
            books=books,
        )

    def get_book(self, external_id: str) -> BookDTO | None:
        data = self._gql(_GET_BOOK_QUERY, {"id": int(external_id)})
        books = data.get("books") or []
        return self._book_dto(books[0]) if books else None

    def _book_dto(self, node: dict) -> BookDTO:
        contributions = node.get("contributions") or []
        author = contributions[0]["author"]["name"] if contributions else ""
        editions = [
            EditionDTO(
                isbn=ed.get("isbn_13") or ed.get("isbn_10") or "",
                source=self.SOURCE,
                language=(ed.get("language") or {}).get("code2") or "",
                format=ed.get("physical_format") or "",
                publisher=ed.get("publisher") or "",
                published_date=ed.get("release_date") or "",
            )
            for ed in node.get("editions") or []
            if ed.get("isbn_13") or ed.get("isbn_10")
        ]
        return BookDTO(
            external_id=str(node["id"]),
            source=self.SOURCE,
            title=node.get("title") or "",
            author=author,
            cover_image=(node.get("image") or {}).get("url") or "",
            rating=node.get("rating"),
            editions=editions,
        )

    def _gql(self, query: str, variables: dict | None = None) -> dict:
        response = httpx.post(
            _ENDPOINT,
            json={"query": query, "variables": variables or {}},
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if errors := payload.get("errors"):
            raise RuntimeError(f"Hardcover GraphQL error: {errors}")
        return payload["data"]