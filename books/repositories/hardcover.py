from __future__ import annotations

import httpx
from django.conf import settings

from books.dtos import BookDTO, CollectionDTO, EditionDTO
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
    language
    rating
    editions {
      isbn_10
      isbn_13
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

_GET_COLLECTIONS_QUERY = """
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


class HardcoverRepository(BookRepositoryBase):
    SOURCE = "hardcover"

    def __init__(self) -> None:
        self._token = settings.HARDCOVER_TOKEN

    def get_collections(self) -> list[CollectionDTO]:
        data = self._gql(_GET_COLLECTIONS_QUERY)
        return [
            CollectionDTO(
                external_id=str(lst["id"]),
                source=self.SOURCE,
                title=lst["name"],
                description=lst.get("description") or "",
                cover_image="",
                book_count=lst.get("books_count") or 0,
                selection_author=(lst.get("user") or {}).get("username") or "",
                books=[self._book_dto(node["book"]) for node in lst.get("list_books") or []],
            )
            for lst in data["lists"]
        ]

    def search(self, query: str) -> list[BookDTO]:
        data = self._gql(_SEARCH_QUERY, {"query": query})
        hits = (data["search"]["results"] or {}).get("hits") or []
        return [self._book_dto(hit["document"]) for hit in hits]

    def get_collection(self, external_id: str) -> CollectionDTO | None:
        data = self._gql(_GET_COLLECTION_QUERY, {"id": int(external_id)})
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
            books=[self._book_dto(node["book"]) for node in lst.get("list_books") or []],
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
            language=node.get("language") or "",
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