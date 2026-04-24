from django.contrib import admin

from .models import (
    Document,
    Question,
)

admin.site.register(Document)

admin.site.register(Question)
