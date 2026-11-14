from rest_framework import serializers

from farming.models import Cycle
from tenants.fields import TenantPrimaryKeyRelatedField

from .models import EggCollection


class EggCollectionSerializer(serializers.ModelSerializer):
    """Ce que l'API renvoie pour un ramassage (lecture seule)."""

    cycle_name = serializers.SerializerMethodField()

    class Meta:
        model = EggCollection
        fields = [
            "id", "uuid", "cycle", "cycle_name", "collected_date", "collected", "broken",
            "note", "created_by", "created_at",
        ]
        read_only_fields = fields

    def get_cycle_name(self, obj):
        return obj.cycle.name


class EggCollectionInputSerializer(serializers.Serializer):
    uuid = serializers.UUIDField(required=False)
    cycle = TenantPrimaryKeyRelatedField(model=Cycle)
    collected_date = serializers.DateField()
    collected = serializers.IntegerField(min_value=0)
    broken = serializers.IntegerField(min_value=0, required=False, default=0)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class EggCollectionUpdateSerializer(serializers.Serializer):
    collected = serializers.IntegerField(min_value=0)
    broken = serializers.IntegerField(min_value=0, required=False, default=0)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
