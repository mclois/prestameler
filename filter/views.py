from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from books.dtos import BookFilterDTO
from filter.managers import FilterManager

_manager = FilterManager()


def index(request: HttpRequest) -> HttpResponse:
    collections = _manager.get_collections()
    return render(request, "filter/index.html", {"collections": collections})


def search(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "")
    result = _manager.search(BookFilterDTO(search_query=query)) if query else None
    return render(request, "filter/search.html", {"query": query, "result": result})


def collection_detail(request: HttpRequest, pk: int) -> HttpResponse:
    result = _manager.search(BookFilterDTO(collection_id=str(pk)))
    return render(request, "filter/collection_detail.html", {"result": result})


def book_detail(request: HttpRequest, pk: int) -> HttpResponse:
    result = _manager.get_book_with_availability(str(pk))
    return render(request, "filter/book_detail.html", {"result": result})
