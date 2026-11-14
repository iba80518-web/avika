from rest_framework.routers import SimpleRouter

from .views import PhotoViewSet

router = SimpleRouter()
router.register("photos", PhotoViewSet, basename="photo")

urlpatterns = router.urls
