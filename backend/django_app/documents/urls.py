from django.urls import path

from .views import DocumentDetailView, DocumentDownloadView, DocumentListCreateView, DocumentPreviewView, MeView

urlpatterns = [
    path("users/me", MeView.as_view(), name="users-me"),
    path("documents", DocumentListCreateView.as_view(), name="documents-list-create"),
    path("documents/<uuid:pk>", DocumentDetailView.as_view(), name="documents-detail"),
    path("documents/<uuid:pk>/download", DocumentDownloadView.as_view(), name="documents-download"),
    path("documents/<uuid:pk>/preview", DocumentPreviewView.as_view(), name="documents-preview"),
]
