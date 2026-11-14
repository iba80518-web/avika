from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from farming.models import Cycle
from tenants.api import TenantAPIMixin

from .models import EggCollection
from .serializers import (
    EggCollectionInputSerializer,
    EggCollectionSerializer,
    EggCollectionUpdateSerializer,
)
from .services import (
    EggError,
    daily_totals,
    egg_stock,
    record_collection,
    update_collection,
)


class EggCollectionViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Ramassages d'œufs : on les enregistre et on les corrige, on ne les supprime pas."""

    serializer_class = EggCollectionSerializer
    permission_by_action = {
        "list": "manage_eggs",
        "retrieve": "manage_eggs",
        "create": "manage_eggs",
        "partial_update": "manage_eggs",
        "summary": "manage_eggs",
    }

    def get_queryset(self):
        queryset = EggCollection.objects.select_related("cycle").order_by("-collected_date", "-id")
        cycle = self.request.query_params.get("cycle", "")
        if cycle.isdigit():
            queryset = queryset.filter(cycle_id=int(cycle))
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = EggCollectionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            collection, created = record_collection(user=request.user, **serializer.validated_data)
        except EggError as error:
            raise ValidationError({"detail": str(error)})
        return Response(EggCollectionSerializer(collection).data, status=201 if created else 200)

    def partial_update(self, request, *args, **kwargs):
        collection = self.get_object()
        serializer = EggCollectionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = update_collection(collection, user=request.user, **serializer.validated_data)
        except EggError as error:
            raise ValidationError({"detail": str(error)})
        return Response(EggCollectionSerializer(updated).data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Stock d'œufs et totaux des derniers jours, avec le taux de ponte de chaque jour."""
        raw = request.query_params.get("cycle", "")
        if not raw.isdigit():
            raise ValidationError({"detail": "Indiquez la bande avec ?cycle=…"})
        cycle = Cycle.objects.filter(pk=int(raw)).first()
        if cycle is None:
            raise NotFound("Bande introuvable.")
        return Response(
            {"cycle": cycle.pk, "stock": egg_stock(cycle), "days": daily_totals(cycle, days=30)}
        )
