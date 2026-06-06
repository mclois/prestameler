from django.contrib import admin

from availability.models import Catalog, Copy, Library

admin.site.register(Catalog)
admin.site.register(Library)
admin.site.register(Copy)
