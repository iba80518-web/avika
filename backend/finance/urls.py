from rest_framework.routers import SimpleRouter

from .views import CustomerViewSet, ExpenseViewSet

router = SimpleRouter()
router.register("customers", CustomerViewSet, basename="customer")
router.register("expenses", ExpenseViewSet, basename="expense")

urlpatterns = router.urls
