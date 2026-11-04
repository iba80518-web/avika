from rest_framework.routers import SimpleRouter

from .views import ProductUnitViewSet, ProductViewSet, SupplierViewSet

router = SimpleRouter()
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("products", ProductViewSet, basename="product")
router.register("product-units", ProductUnitViewSet, basename="product-unit")

urlpatterns = router.urls
