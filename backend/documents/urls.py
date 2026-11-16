from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import DocumentSettingsView, DocumentViewSet

router = SimpleRouter()
router.register("documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("document-settings/", DocumentSettingsView.as_view({"get": "current", "patch": "change"})),
    path(
        "document-settings/logo/",
        DocumentSettingsView.as_view({"post": "upload_logo", "delete": "delete_logo"}),
    ),
    path("document-settings/logo/file/", DocumentSettingsView.as_view({"get": "show_logo"})),
    *router.urls,
]
