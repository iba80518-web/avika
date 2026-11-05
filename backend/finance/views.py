from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from tenants.api import TenantAPIMixin

from .models import Customer, Expense
from .serializers import CustomerSerializer, ExpenseSerializer
from .services import FinanceError, record_expense


class _NoDeleteViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Pas de suppression : on désactive ou on corrige, on n'efface pas."""


class CustomerViewSet(_NoDeleteViewSet):
    serializer_class = CustomerSerializer
    permission_by_action = {
        "list": "manage_customers",
        "retrieve": "manage_customers",
        "create": "manage_customers",
        "update": "manage_customers",
        "partial_update": "manage_customers",
    }

    def get_queryset(self):
        return Customer.objects.order_by("name")


class ExpenseViewSet(_NoDeleteViewSet):
    serializer_class = ExpenseSerializer
    permission_by_action = {
        "list": "manage_expenses",
        "retrieve": "manage_expenses",
        "create": "manage_expenses",
        "update": "manage_expenses",
        "partial_update": "manage_expenses",
    }

    def get_queryset(self):
        queryset = Expense.objects.order_by("-expense_date", "-id")
        cycle = self.request.query_params.get("cycle")
        category = self.request.query_params.get("category")
        if cycle and cycle.isdigit():
            queryset = queryset.filter(cycle_id=int(cycle))
        if category:
            queryset = queryset.filter(category=category)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            expense, created = record_expense(user=request.user, **serializer.validated_data)
        except FinanceError as error:
            raise ValidationError({"detail": str(error)})
        return Response(ExpenseSerializer(expense).data, status=201 if created else 200)
