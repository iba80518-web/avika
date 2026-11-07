from django.urls import path

from .status import StatusView

urlpatterns = [path("status/", StatusView.as_view(), name="status")]
