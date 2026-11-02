from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from tenants.api import TenantAPIMixin
from tenants.permissions import has_permission

from .models import Coop, Cycle, FlockEvent
from .serializers import CoopSerializer, CycleSerializer, FlockEventSerializer
from .services import (
    FarmingError,
    cancel_cycle,
    complete_cycle,
    cycle_summary,
    record_event,
    start_cycle,
)


class CoopViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Pas de suppression : un poulailler devient « inactif »."""

    serializer_class = CoopSerializer
    permission_by_action = {
        "list": "view_farming",
        "retrieve": "view_farming",
        "create": "manage_coops",
        "update": "manage_coops",
        "partial_update": "manage_coops",
    }

    def get_queryset(self):
        return Coop.objects.select_related("farm").order_by("name")


class CycleViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Pas de suppression : un cycle se termine ou s'annule."""

    serializer_class = CycleSerializer
    permission_by_action = {
        "list": "view_farming",
        "retrieve": "view_farming",
        "summary": "view_farming",
        "events": "view_farming",  # l'enregistrement exige un droit plus précis (voir events)
        "create": "manage_cycles",
        "update": "manage_cycles",
        "partial_update": "manage_cycles",
        "start": "manage_cycles",
        "complete": "manage_cycles",
        "cancel": "manage_cycles",
    }

    def get_queryset(self):
        return Cycle.objects.select_related("coop").order_by("-start_date", "-id")

    def _transition(self, function, *args, **kwargs):
        try:
            cycle = function(*args, **kwargs)
        except FarmingError as error:
            raise ValidationError({"detail": str(error)})
        return Response(self.get_serializer(cycle).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        cycle = self.get_object()
        confirm = request.data.get("confirm_over_capacity") is True
        return self._transition(start_cycle, cycle, confirm_over_capacity=confirm)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self._transition(complete_cycle, self.get_object())

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition(cancel_cycle, self.get_object())

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        return Response(cycle_summary(self.get_object()))

    @action(detail=True, methods=["get", "post"])
    def events(self, request, pk=None):
        cycle = self.get_object()

        if request.method == "GET":
            queryset = FlockEvent.objects.filter(cycle=cycle).order_by("-event_date", "-id")
            page = self.paginate_queryset(queryset)
            return self.get_paginated_response(FlockEventSerializer(page, many=True).data)

        serializer = FlockEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        event_type = data["event_type"]
        if event_type == FlockEvent.EventType.SALE:
            raise ValidationError({"event_type": "Les ventes sont créées par le module Ventes."})
        needed = (
            "record_mortality" if event_type == FlockEvent.EventType.MORTALITY else "manage_cycles"
        )
        if not has_permission(request.membership, needed):
            raise PermissionDenied("Vous n'avez pas le droit d'enregistrer ce type d'événement.")

        try:
            event, created = record_event(cycle=cycle, user=request.user, **data)
        except FarmingError as error:
            raise ValidationError({"detail": str(error)})
        return Response(FlockEventSerializer(event).data, status=201 if created else 200)
