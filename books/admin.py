from django.contrib import admin

from books.models import Book, Collection, Edition

admin.site.register(Collection)
admin.site.register(Book)
admin.site.register(Edition)
