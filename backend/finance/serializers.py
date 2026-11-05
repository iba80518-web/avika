from rest_framework import serializers

from farming.models import Cycle
from inventory.models import Supplier
from tenants.fields import TenantPrimaryKeyRelatedField

from .models import Customer, Expense, Payment, Sale
from .services import paid_total, sale_balance


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id", "name", "phone", "address", "customer_type", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value):
        queryset = Customer.objects.filter(name=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Un client porte déjà ce nom.")
        return value


class ExpenseSerializer(serializers.ModelSerializer):
    amount = serializers.IntegerField(min_value=1)
    supplier = TenantPrimaryKeyRelatedField(model=Supplier, required=False, allow_null=True)
    cycle = TenantPrimaryKeyRelatedField(model=Cycle, required=False, allow_null=True)

    class Meta:
        model = Expense
        fields = [
            "id", "uuid", "amount", "expense_date", "category", "description",
            "supplier", "cycle", "created_by", "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]

    def validate_cycle(self, value):
        if value is not None and value.status == Cycle.Status.CANCELLED:
            raise serializers.ValidationError("Ce cycle est annulé.")
        return value


class SaleInputSerializer(serializers.Serializer):
    """Ce que le client PEUT envoyer pour une vente. Aucun champ « total » : il est calculé."""

    uuid = serializers.UUIDField(required=False)
    cycle = TenantPrimaryKeyRelatedField(model=Cycle)
    customer = TenantPrimaryKeyRelatedField(model=Customer, required=False, allow_null=True)
    sale_date = serializers.DateField()
    sale_type = serializers.ChoiceField(choices=Sale.SaleType.choices)
    quantity = serializers.IntegerField(min_value=1)
    weight_kg = serializers.DecimalField(
        max_digits=10, decimal_places=3, required=False, allow_null=True
    )
    unit_price = serializers.IntegerField(min_value=1)
    paid_amount = serializers.IntegerField(min_value=0, required=False, default=0)
    payment_method = serializers.ChoiceField(
        choices=Payment.Method.choices, required=False, default=Payment.Method.CASH
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")


class SaleSerializer(serializers.ModelSerializer):
    """Ce que l'API renvoie pour une vente (lecture seule)."""

    customer_name = serializers.SerializerMethodField()
    paid = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            "id", "uuid", "customer", "customer_name", "cycle", "sale_date", "sale_type",
            "quantity", "weight_kg", "unit_price", "total_amount", "paid", "balance",
            "status", "note", "created_by", "created_at",
        ]
        read_only_fields = fields

    def get_customer_name(self, obj):
        return obj.customer.name if obj.customer_id else None

    def get_paid(self, obj):
        return paid_total(obj)

    def get_balance(self, obj):
        return sale_balance(obj)


class PaymentInputSerializer(serializers.Serializer):
    uuid = serializers.UUIDField(required=False)
    amount = serializers.IntegerField(min_value=1)
    payment_date = serializers.DateField()
    method = serializers.ChoiceField(
        choices=Payment.Method.choices, required=False, default=Payment.Method.CASH
    )


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id", "uuid", "sale", "amount", "payment_date", "method", "created_by", "created_at",
        ]
        read_only_fields = fields
