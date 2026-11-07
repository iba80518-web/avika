from rest_framework import serializers

from farming.models import Cycle
from inventory.models import Product
from tenants.fields import TenantPrimaryKeyRelatedField

from .models import HealthKind, HealthTask, HealthTemplate, HealthTemplateItem


class HealthTemplateItemSerializer(serializers.ModelSerializer):
    template = TenantPrimaryKeyRelatedField(model=HealthTemplate)
    product = TenantPrimaryKeyRelatedField(model=Product, required=False, allow_null=True)

    class Meta:
        model = HealthTemplateItem
        fields = ["id", "template", "name", "kind", "day_of_age", "product", "note", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        instance = self.instance
        template = attrs.get("template", getattr(instance, "template", None))
        name = attrs.get("name", getattr(instance, "name", None))
        day = attrs.get("day_of_age", getattr(instance, "day_of_age", None))
        if template is not None and name is not None and day is not None:
            queryset = HealthTemplateItem.objects.filter(template=template, name=name, day_of_age=day)
            if instance is not None:
                queryset = queryset.exclude(pk=instance.pk)
            if queryset.exists():
                raise serializers.ValidationError("Cette ligne existe déjà dans ce calendrier.")
        return attrs


class HealthTemplateSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta:
        model = HealthTemplate
        fields = ["id", "name", "description", "is_active", "items", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_items(self, obj):
        items = HealthTemplateItem.objects.filter(template=obj).order_by("day_of_age", "id")
        return HealthTemplateItemSerializer(items, many=True).data

    def validate_name(self, value):
        queryset = HealthTemplate.objects.filter(name=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Un calendrier porte déjà ce nom.")
        return value


class HealthTaskSerializer(serializers.ModelSerializer):
    """Ce que l'API renvoie pour une tâche (lecture seule)."""

    cycle_name = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()

    class Meta:
        model = HealthTask
        fields = [
            "id", "uuid", "cycle", "cycle_name", "name", "kind", "due_date", "status",
            "done_date", "product", "product_name", "quantity", "note", "created_by", "created_at",
        ]
        read_only_fields = fields

    def get_cycle_name(self, obj):
        return obj.cycle.name

    def get_product_name(self, obj):
        return obj.product.name if obj.product_id else None


class HealthTaskInputSerializer(serializers.Serializer):
    uuid = serializers.UUIDField(required=False)
    cycle = TenantPrimaryKeyRelatedField(model=Cycle)
    name = serializers.CharField(max_length=150)
    kind = serializers.ChoiceField(choices=HealthKind.choices, required=False, default=HealthKind.VACCINE)
    due_date = serializers.DateField()
    product = TenantPrimaryKeyRelatedField(model=Product, required=False, allow_null=True)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class ScheduleInputSerializer(serializers.Serializer):
    cycle = TenantPrimaryKeyRelatedField(model=Cycle)
    template = TenantPrimaryKeyRelatedField(model=HealthTemplate)


class CompleteInputSerializer(serializers.Serializer):
    done_date = serializers.DateField()
    quantity = serializers.DecimalField(
        max_digits=14, decimal_places=3, required=False, allow_null=True
    )
    use_stock = serializers.BooleanField(required=False, default=False)
