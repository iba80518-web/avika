from rest_framework import mixins, viewsets

from tenants.api import TenantAPIMixin

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Consultation seule du journal d'audit, réservée à qui a le droit « view_audit »."""

    serializer_class = AuditLogSerializer
    permission_by_action = {"list": "view_audit", "retrieve": "view_audit"}

    def get_queryset(self):
        queryset = AuditLog.objects.select_related("user").order_by("-id")
        params = self.request.query_params
        if params.get("action"):
            queryset = queryset.filter(action=params["action"])
        if params.get("object_type"):
            queryset = queryset.filter(object_type=params["object_type"])
        if params.get("object_id", "").isdigit():
            queryset = queryset.filter(object_id=int(params["object_id"]))
        if params.get("user", "").isdigit():
            queryset = queryset.filter(user_id=int(params["user"]))
        return queryset
