from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from tenants.api import TenantAPIMixin

from .models import HealthTask, HealthTemplate, HealthTemplateItem
from .serializers import (
    CompleteInputSerializer,
    HealthTaskInputSerializer,
    HealthTaskSerializer,
    HealthTemplateItemSerializer,
    HealthTemplateSerializer,
    ScheduleInputSerializer,
)
from .services import (
    HealthError,
    cancel_task,
    complete_task,
    create_task,
    schedule_from_template,
)
from .services import reminders as due_reminders


class _NoDeleteViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Pas de suppression : on désactive ou on corrige, on n'efface pas."""


class HealthTemplateViewSet(_NoDeleteViewSet):
    serializer_class = HealthTemplateSerializer
    permission_by_action = {
        "list": "manage_health",
        "retrieve": "manage_health",
        "create": "manage_health",
        "update": "manage_health",
        "partial_update": "manage_health",
    }

    def get_queryset(self):
        return HealthTemplate.objects.order_by("name")


class HealthTemplateItemViewSet(_NoDeleteViewSet):
    serializer_class = HealthTemplateItemSerializer
    permission_by_action = {
        "list": "manage_health",
        "retrieve": "manage_health",
        "create": "manage_health",
        "update": "manage_health",
        "partial_update": "manage_health",
    }

    def get_queryset(self):
        queryset = HealthTemplateItem.objects.order_by("template_id", "day_of_age", "id")
        template = self.request.query_params.get("template", "")
        if template.isdigit():
            queryset = queryset.filter(template_id=int(template))
        return queryset


class HealthTaskViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Tâches de santé : on les planifie, puis on les réalise ou on les annule."""

    serializer_class = HealthTaskSerializer
    permission_by_action = {
        "list": "manage_health",
        "retrieve": "manage_health",
        "create": "manage_health",
        "complete": "manage_health",
        "cancel": "manage_health",
        "schedule": "manage_health",
        "reminders": "manage_health",
    }

    def get_queryset(self):
        queryset = HealthTask.objects.select_related("cycle", "product").order_by("due_date", "id")
        params = self.request.query_params
        if params.get("cycle", "").isdigit():
            queryset = queryset.filter(cycle_id=int(params["cycle"]))
        if params.get("status") in HealthTask.Status.values:
            queryset = queryset.filter(status=params["status"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = HealthTaskInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            task, created = create_task(user=request.user, **serializer.validated_data)
        except HealthError as error:
            raise ValidationError({"detail": str(error)})
        return Response(HealthTaskSerializer(task).data, status=201 if created else 200)

    @action(detail=False, methods=["post"])
    def schedule(self, request):
        """Crée les tâches d'un calendrier type pour un cycle (sans doublon si on relance)."""
        serializer = ScheduleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tasks = schedule_from_template(user=request.user, **serializer.validated_data)
        except HealthError as error:
            raise ValidationError({"detail": str(error)})
        data = HealthTaskSerializer(tasks, many=True).data
        return Response(data, status=201 if tasks else 200)

    @action(detail=False, methods=["get"])
    def reminders(self, request):
        """Rappels : tâches en retard, du jour et du lendemain."""
        grouped = due_reminders(timezone.localdate())
        return Response({key: HealthTaskSerializer(tasks, many=True).data for key, tasks in grouped.items()})

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        task = self.get_object()
        serializer = CompleteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            done = complete_task(task, user=request.user, **serializer.validated_data)
        except HealthError as error:
            raise ValidationError({"detail": str(error)})
        return Response(HealthTaskSerializer(done).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        task = self.get_object()
        try:
            cancelled = cancel_task(task, user=request.user)
        except HealthError as error:
            raise ValidationError({"detail": str(error)})
        return Response(HealthTaskSerializer(cancelled).data)
