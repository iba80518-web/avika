from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from tenants.api import TenantAPIMixin

from .models import Product, ProductUnit, StockMovement, Supplier
from .serializers import (
    ProductSerializer,
    ProductUnitSerializer,
    StockMovementSerializer,
    SupplierSerializer,
)
from .services import InventoryError, is_low, record_movement, stock_snapshot


class _NoDeleteViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Pas de suppression : on désactive ou on corrige, on n'efface pas."""


class SupplierViewSet(_NoDeleteViewSet):
    serializer_class = SupplierSerializer
    permission_by_action = {
        "list": "manage_suppliers",
        "retrieve": "manage_suppliers",
        "create": "manage_suppliers",
        "update": "manage_suppliers",
        "partial_update": "manage_suppliers",
    }

    def get_queryset(self):
        return Supplier.objects.order_by("name")


class ProductUnitViewSet(_NoDeleteViewSet):
    serializer_class = ProductUnitSerializer
    permission_by_action = {
        "list": "manage_feed",
        "retrieve": "manage_feed",
        "create": "manage_feed",
        "update": "manage_feed",
        "partial_update": "manage_feed",
    }

    def get_queryset(self):
        return ProductUnit.objects.select_related("product").order_by("product__name", "name")


class ProductViewSet(_NoDeleteViewSet):
    serializer_class = ProductSerializer
    permission_by_action = {
        "list": "manage_feed",
        "retrieve": "manage_feed",
        "create": "manage_feed",
        "update": "manage_feed",
        "partial_update": "manage_feed",
        "low_stock": "manage_feed",
        "movements": "manage_feed",
    }

    def get_queryset(self):
        return Product.objects.order_by("name")

    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request):
        """Produits actifs dont le stock a atteint le seuil d'alerte."""
        low = [
            product
            for product in Product.objects.filter(is_active=True).order_by("name")
            if is_low(product)
        ]
        return Response(ProductSerializer(low, many=True).data)

    @action(detail=True, methods=["get", "post"])
    def movements(self, request, pk=None):
        product = self.get_object()

        if request.method == "GET":
            queryset = StockMovement.objects.filter(product=product).order_by(
                "-movement_date", "-id"
            )
            page = self.paginate_queryset(queryset)
            return self.get_paginated_response(StockMovementSerializer(page, many=True).data)

        serializer = StockMovementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            movement, created = record_movement(
                product=product, user=request.user, **serializer.validated_data
            )
        except InventoryError as error:
            raise ValidationError({"detail": str(error)})
        return Response(StockMovementSerializer(movement).data, status=201 if created else 200)
