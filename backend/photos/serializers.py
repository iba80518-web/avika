from rest_framework import serializers

from farming.models import Cycle
from tenants.fields import TenantPrimaryKeyRelatedField

from .models import Photo


class PhotoSerializer(serializers.ModelSerializer):
    """Ce que l'API renvoie (lecture seule). L'image elle-même passe par file_url."""

    cycle_name = serializers.CharField(source="cycle.name", read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = [
            "id", "uuid", "cycle", "cycle_name", "kind", "taken_date", "width", "height",
            "size_bytes", "note", "egg_collection", "flock_event", "file_url",
            "created_by", "created_at",
        ]
        read_only_fields = fields

    def get_file_url(self, obj):
        return f"/api/v1/photos/{obj.pk}/file/"


class PhotoInputSerializer(serializers.Serializer):
    uuid = serializers.UUIDField(required=False)
    cycle = TenantPrimaryKeyRelatedField(model=Cycle)
    kind = serializers.ChoiceField(choices=Photo.Kind.choices)
    taken_date = serializers.DateField()
    note = serializers.CharField(required=False, allow_blank=True, default="")
    egg_collection = serializers.IntegerField(
        required=False, allow_null=True, default=None, source="egg_collection_id"
    )
    flock_event = serializers.IntegerField(
        required=False, allow_null=True, default=None, source="flock_event_id"
    )
    # Lien par uuid : sert aux photos envoyées après coup, quand l'identifiant serveur n'existe pas encore.
    egg_collection_uuid = serializers.UUIDField(required=False, allow_null=True, default=None)
    flock_event_uuid = serializers.UUIDField(required=False, allow_null=True, default=None)
    image = serializers.FileField()
