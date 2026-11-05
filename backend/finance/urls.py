from rest_framework.routers import SimpleRouter

from .views import CustomerViewSet, ExpenseViewSet, SaleViewSet
from .views_profit import ProfitabilityViewSet

router = SimpleRouter()
router.register("customers", CustomerViewSet, basename="customer")
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("sales", SaleViewSet, basename="sale")
router.register("profitability", ProfitabilityViewSet, basename="profitability")

urlpatterns = router.urls
