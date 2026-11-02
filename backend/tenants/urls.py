from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import FarmViewSet, MeView, RegisterView

router = SimpleRouter()
router.register("farms", FarmViewSet, basename="farm")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/me/", MeView.as_view(), name="me"),
] + router.urls
