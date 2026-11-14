from rest_framework.routers import SimpleRouter

from .views import EggCollectionViewSet

router = SimpleRouter()
router.register("egg-collections", EggCollectionViewSet, basename="egg-collection")

urlpatterns = router.urls
