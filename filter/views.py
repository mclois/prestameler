from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from filter.managers import FilterManager

_manager = FilterManager()


def index(request: HttpRequest) -> HttpResponse:
    collections = _manager._books.get_collections()
    return render(request, "filter/index.html", {"collections": collections})


def search(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "")
    results = _manager.search(query) if query else []
    return render(request, "filter/search.html", {"query": query, "results": results})


def collection_detail(request: HttpRequest, pk: int) -> HttpResponse:
    return render(request, "filter/collection_detail.html", {"pk": pk})


def book_detail(request: HttpRequest, pk: int) -> HttpResponse:
    result = _manager.get_book_with_availability(str(pk))
    return render(request, "filter/book_detail.html", {"result": result})
