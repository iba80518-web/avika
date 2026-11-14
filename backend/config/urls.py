from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("tenants.urls")),
    path("api/v1/", include("farming.urls")),
    path("api/v1/", include("inventory.urls")),
    path("api/v1/", include("finance.urls")),
    path("api/v1/", include("audit.urls")),
    path("api/v1/", include("dashboard.urls")),
    path("api/v1/", include("health.urls")),
    path("api/v1/", include("eggs.urls")),
    path("api/v1/", include("reports.urls")),
    path("api/v1/", include("core.status_urls")),
]
