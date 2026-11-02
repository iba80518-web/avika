from rest_framework import serializers

from tenants.context import get_current_organization_id
from tenants.fields import TenantPrimaryKeyRelatedField
from tenants.models import Farm, Organization

from .models import Coop, Cycle, FlockEvent
from .services import current_count


class CoopSerializer(serializers.ModelSerializer):
    farm = TenantPrimaryKeyRelatedField(model=Farm)

    class Meta:
        model = Coop
        fields = [
            "id", "farm", "name", "capacity", "type", "location",
            "status", "description", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_capacity(self, value):
        if value < 1:
            raise serializers.ValidationError("La capacité doit être supérieure à 0.")
        return value

    def validate_name(self, value):
        queryset = Coop.objects.filter(name=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Un poulailler porte déjà ce nom.")
        return value


class CycleSerializer(serializers.ModelSerializer):
    coop = TenantPrimaryKeyRelatedField(model=Coop)
    current_count = serializers.SerializerMethodField()

    LOCKED_AFTER_START = ("coop", "start_date", "initial_count")

    class Meta:
        model = Cycle
        fields = [
            "id", "coop", "name", "type", "start_date", "end_date", "initial_count",
            "supplier_name", "unit_price", "currency", "target", "planned_sale_date",
            "status", "current_count", "created_at",
        ]
        read_only_fields = ["id", "status", "end_date", "created_at"]
        extra_kwargs = {"unit_price": {"min_value": 0}}

    def get_current_count(self, obj):
        return current_count(obj)

    def validate_initial_count(self, value):
        if value < 1:
            raise serializers.ValidationError("L'effectif initial doit être supérieur à 0.")
        return value

    def validate(self, attrs):
        instance = self.instance
        if instance is not None and instance.status != Cycle.Status.PLANNED:
            for field in self.LOCKED_AFTER_START:
                if field in attrs and attrs[field] != getattr(instance, field):
                    raise serializers.ValidationError(
                        {field: "Non modifiable après le démarrage : utilisez une correction."}
                    )

        coop = attrs.get("coop", getattr(instance, "coop", None))
        name = attrs.get("name", getattr(instance, "name", None))
        if coop is not None and name is not None:
            queryset = Cycle.objects.filter(coop=coop, name=name)
            if instance is not None:
                queryset = queryset.exclude(pk=instance.pk)
            if queryset.exists():
                raise serializers.ValidationError(
                    {"name": "Ce poulailler a déjà un cycle portant ce nom."}
                )

        if instance is None and "currency" not in attrs:
            attrs["currency"] = Organization.objects.get(
                pk=get_current_organization_id()
            ).reference_currency
        return attrs


class FlockEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlockEvent
        fields = [
            "id", "uuid", "event_type", "quantity", "event_date",
            "cause", "note", "created_by", "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]
