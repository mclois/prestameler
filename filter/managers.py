from __future__ import annotations

from availability.dtos import CopyDTO
from availability.managers import AvailabilityManager
from availability.models import Copy
from books.dtos import BookDTO, BookFilterDTO, CollectionDTO, CollectionFilterDTO, EditionDTO, FacetDTO
from books.managers import BookManager
from books.models import Book, Collection, Edition, Facet
from filter.dtos import BookResultDTO, SearchResultDTO


class FilterManager:
    def __init__(self) -> None:
        self._books = BookManager()
        self._availability = AvailabilityManager()

    def get_collections(self, filter_config: CollectionFilterDTO | None = None) -> FacetDTO:
        facet = self._books.get_collections(filter_config)
        return self._facet_to_dto(facet)

    def search(self, filter_config: BookFilterDTO) -> SearchResultDTO | None:
        if not filter_config.cache_key:
            return None
        collection = self._books.search(filter_config)
        if collection is None:
            return None
        books = [self._to_book_result(cb.book) for cb in self._ordered_books(collection)]
        return SearchResultDTO(
            external_id=collection.external_id,
            title=collection.title,
            description=collection.description,
            cover_image=collection.cover_image,
            book_count=collection.book_count,
            selection_author=collection.selection_author,
            books=books,
        )

    def get_book_with_availability(self, external_id: str) -> BookResultDTO | None:
        book = self._books.get_book(external_id)
        if book is None:
            return None
        return self._to_book_result(book, True)

    # -- ordering fixes: ManyRelatedManager ignores the through model's Meta.ordering --

    @staticmethod
    def _ordered_books(collection: Collection):
        return collection.collection_books.select_related("book").order_by("order")

    @staticmethod
    def _ordered_collections(facet: Facet):
        return facet.facet_collections.select_related("collection").order_by("order")

    def _to_book_result(self, book: Book, fill_availability: bool = False) -> BookResultDTO:
        editions: list[EditionDTO] = []
        available_copies: list[CopyDTO] = []
        seen: set[tuple[str, int | None]] = set()
        for edition in book.editions.order_by("id"):
            editions.append(self._edition_to_dto(edition))
            if not fill_availability:
                continue
            copies = [c for c in self._availability.get_copies(edition.isbn) if c.available is True]
            for copy in copies:
                key = (copy.isbn, copy.catalog_id)
                if key not in seen:
                    seen.add(key)
                    available_copies.append(self._copy_to_dto(copy))
        return BookResultDTO(book=self._book_to_dto(book, editions), available_copies=available_copies)

    # -- pure passthrough translation, no crossing (carousels) --

    def _collection_to_dto(self, collection: Collection) -> CollectionDTO:
        books = [
            self._book_to_dto(cb.book, [self._edition_to_dto(e) for e in cb.book.editions.order_by("id")])
            for cb in self._ordered_books(collection)
        ]
        return CollectionDTO(
            external_id=collection.external_id,
            source=collection.source,
            title=collection.title,
            description=collection.description,
            cover_image=collection.cover_image,
            book_count=collection.book_count,
            selection_author=collection.selection_author,
            filter_config=collection.filter_config,
            books=books,
        )

    def _facet_to_dto(self, facet: Facet) -> FacetDTO:
        collections = [self._collection_to_dto(fc.collection) for fc in self._ordered_collections(facet)]
        return FacetDTO(
            slug=facet.slug,
            source=facet.source,
            title=facet.title,
            description=facet.description,
            filter_config=facet.filter_config,
            collections=collections,
        )

    # -- entity -> repo-facing-DTO leaf translation --

    @staticmethod
    def _book_to_dto(book: Book, editions: list[EditionDTO]) -> BookDTO:
        return BookDTO(
            external_id=book.external_id,
            source=book.source,
            title=book.title,
            author=book.author,
            cover_image=book.cover_image,
            rating=book.rating,
            editions=editions,
        )

    @staticmethod
    def _edition_to_dto(edition: Edition) -> EditionDTO:
        return EditionDTO(
            isbn=edition.isbn,
            source=edition.source,
            format=edition.format,
            language=edition.language,
            publisher=edition.publisher,
            published_date=edition.published_date,
        )

    @staticmethod
    def _copy_to_dto(copy: Copy) -> CopyDTO:
        return CopyDTO(
            isbn=copy.isbn,
            available=copy.available,
            borrow_url=copy.borrow_url,
            catalog_id=copy.catalog_id,
            source=copy.source,
        )
