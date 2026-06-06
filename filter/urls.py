from django.urls import path

from filter import views

app_name = "filter"

urlpatterns = [
    path("", views.index, name="index"),
    path("search/", views.search, name="search"),
    path("collections/<int:pk>/", views.collection_detail, name="collection-detail"),
    path("books/<int:pk>/", views.book_detail, name="book-detail"),
]
