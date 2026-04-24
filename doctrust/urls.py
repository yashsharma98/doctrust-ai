from django.urls import path

from .views import (
    delete_doc_question,
    delete_document,
    doc_detail,
    index,
    upload,
)

urlpatterns = [
    path("", index, name="index"),
    path("upload/", upload, name="upload"),
    path("doc/<uuid:doc_id>/", doc_detail, name="doc_detail"),
    path("doc/<uuid:doc_id>/delete/", delete_document, name="delete_document"),
    path("session/<uuid:session_id>/delete/", delete_doc_question, name="delete_doc_question"),
]
