from rest_framework.routers import SimpleRouter

from .views import DashboardViewSet

router = SimpleRouter()
router.register("dashboard", DashboardViewSet, basename="dashboard")

urlpatterns = router.urls
