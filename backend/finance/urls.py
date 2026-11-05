from rest_framework.routers import SimpleRouter

from .views import CustomerViewSet, ExpenseViewSet, SaleViewSet

router = SimpleRouter()
router.register("customers", CustomerViewSet, basename="customer")
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("sales", SaleViewSet, basename="sale")

urlpatterns = router.urls
