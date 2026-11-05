from rest_framework import serializers

from farming.models import Cycle
from inventory.models import Supplier
from tenants.fields import TenantPrimaryKeyRelatedField

from .models import Customer, Expense


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
