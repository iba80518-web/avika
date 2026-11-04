from rest_framework import serializers

from farming.models import Cycle
from tenants.fields import TenantPrimaryKeyRelatedField

from .models import Product, ProductUnit, StockMovement, Supplier
from .services import is_low, stock_snapshot


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "phone", "address", "category", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value):
        queryset = Supplier.objects.filter(name=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Un fournisseur porte déjà ce nom.")
        return value


class ProductSerializer(serializers.ModelSerializer):
    stock = serializers.SerializerMethodField()
    stock_value = serializers.SerializerMethodField()
    is_low = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "name", "product_type", "base_unit", "low_stock_threshold",
            "is_active", "stock", "stock_value", "is_low", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_stock(self, obj):
        return str(stock_snapshot(obj)[0])

    def get_stock_value(self, obj):
        return stock_snapshot(obj)[1]

    def get_is_low(self, obj):
        return is_low(obj)

    def validate_low_stock_threshold(self, value):
        if value < 0:
            raise serializers.ValidationError("Le seuil ne peut pas être négatif.")
        return value

    def validate_name(self, value):
        queryset = Product.objects.filter(name=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Un produit porte déjà ce nom.")
        return value

    def validate(self, attrs):
        instance = self.instance
        if (
            instance is not None
            and "base_unit" in attrs
            and attrs["base_unit"] != instance.base_unit
            and StockMovement.objects.filter(product=instance).exists()
        ):
            raise serializers.ValidationError(
                {"base_unit": "Non modifiable : ce produit a déjà des mouvements."}
            )
        return attrs


class ProductUnitSerializer(serializers.ModelSerializer):
    product = TenantPrimaryKeyRelatedField(model=Product)

    class Meta:
        model = ProductUnit
        fields = ["id", "product", "name", "factor_to_base", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_factor_to_base(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le facteur doit être supérieur à 0.")
        return value

    def validate(self, attrs):
        instance = self.instance
        product = attrs.get("product", getattr(instance, "product", None))
        name = attrs.get("name", getattr(instance, "name", None))
        if product is not None and name is not None:
            queryset = ProductUnit.objects.filter(product=product, name=name)
            if instance is not None:
                queryset = queryset.exclude(pk=instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({"name": "Ce produit a déjà une unité de ce nom."})
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    # À l'entrée : quantité dans l'unité choisie. À la sortie : quantité en unité de base.
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, write_only=True)
    base_quantity = serializers.DecimalField(
        source="quantity", max_digits=14, decimal_places=3, read_only=True
    )
    unit = TenantPrimaryKeyRelatedField(
        model=ProductUnit, required=False, allow_null=True, write_only=True
    )
    cycle = TenantPrimaryKeyRelatedField(model=Cycle, required=False, allow_null=True)
    total_cost = serializers.IntegerField(required=False, allow_null=True, min_value=0)

    class Meta:
        model = StockMovement
        fields = [
            "id", "uuid", "movement_type", "quantity", "base_quantity", "unit",
            "total_cost", "movement_date", "cycle", "note", "created_by", "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]
