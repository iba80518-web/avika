from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id", "created_at", "user", "user_name", "action", "object_type",
            "object_id", "summary", "before", "after",
        ]
        read_only_fields = fields

    def get_user_name(self, obj):
        return obj.user.full_name if obj.user_id else None
