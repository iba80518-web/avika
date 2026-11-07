from rest_framework.routers import SimpleRouter

from .views import HealthTaskViewSet, HealthTemplateItemViewSet, HealthTemplateViewSet

router = SimpleRouter()
router.register("health-templates", HealthTemplateViewSet, basename="health-template")
router.register("health-template-items", HealthTemplateItemViewSet, basename="health-template-item")
router.register("health-tasks", HealthTaskViewSet, basename="health-task")

urlpatterns = router.urls
