from rest_framework.routers import SimpleRouter

from .views import CoopViewSet, CycleViewSet

router = SimpleRouter()
router.register("coops", CoopViewSet, basename="coop")
router.register("cycles", CycleViewSet, basename="cycle")

urlpatterns = router.urls
