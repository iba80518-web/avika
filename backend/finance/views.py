from django.db.models import BigIntegerField, F, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from tenants.api import TenantAPIMixin

from .models import Customer, Expense, Payment, Sale
from .serializers import (
    CustomerSerializer,
    ExpenseSerializer,
    PaymentInputSerializer,
    PaymentSerializer,
    SaleInputSerializer,
    SaleSerializer,
)
from .services import (
    FinanceError,
    cancel_sale,
    record_expense,
    record_payment,
    record_sale,
)


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


class SaleViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Ventes : on les crée et on les consulte ; on ne les modifie ni ne les supprime.

    Une erreur de saisie se corrige en annulant la vente puis en la ressaisissant.
    """

    serializer_class = SaleSerializer
    permission_by_action = {
        "list": "manage_sales",
        "retrieve": "manage_sales",
        "create": "manage_sales",
        "payments": "manage_sales",
        "cancel": "manage_sales",
        "receivables": "manage_sales",
    }

    def get_queryset(self):
        queryset = Sale.objects.select_related("customer").order_by("-sale_date", "-id")
        params = self.request.query_params
        if params.get("cycle", "").isdigit():
            queryset = queryset.filter(cycle_id=int(params["cycle"]))
        if params.get("customer", "").isdigit():
            queryset = queryset.filter(customer_id=int(params["customer"]))
        if params.get("status") in Sale.Status.values:
            queryset = queryset.filter(status=params["status"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = SaleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            sale, created = record_sale(user=request.user, **serializer.validated_data)
        except FinanceError as error:
            raise ValidationError({"detail": str(error)})
        return Response(SaleSerializer(sale).data, status=201 if created else 200)

    @action(detail=True, methods=["get", "post"])
    def payments(self, request, pk=None):
        sale = self.get_object()

        if request.method == "GET":
            payments = Payment.objects.filter(sale=sale).order_by("payment_date", "id")
            return Response(PaymentSerializer(payments, many=True).data)

        serializer = PaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment, created = record_payment(
                sale=sale, user=request.user, **serializer.validated_data
            )
        except FinanceError as error:
            raise ValidationError({"detail": str(error)})
        return Response(PaymentSerializer(payment).data, status=201 if created else 200)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        sale = self.get_object()
        reason = str(request.data.get("reason", ""))[:200]
        try:
            cancelled = cancel_sale(sale, user=request.user, reason=reason)
        except FinanceError as error:
            raise ValidationError({"detail": str(error)})
        return Response(SaleSerializer(cancelled).data)

    @action(detail=False, methods=["get"])
    def receivables(self, request):
        """« Argent à recevoir » : ce que chaque client doit encore, du plus gros au plus petit."""
        sales = (
            Sale.objects.filter(status=Sale.Status.ACTIVE, customer__isnull=False)
            .select_related("customer")
            .annotate(
                paid_sum=Coalesce(
                    Sum("payments__amount"), Value(0), output_field=BigIntegerField()
                )
            )
            .annotate(due=F("total_amount") - F("paid_sum"))
            .filter(due__gt=0)
        )
        # Regroupement en Python : Django refuse de sommer une valeur déjà agrégée.
        by_customer = {}
        for sale in sales:
            row = by_customer.setdefault(
                sale.customer_id,
                {
                    "customer": sale.customer_id,
                    "customer_name": sale.customer.name,
                    "total_due": 0,
                    "sales_count": 0,
                },
            )
            row["total_due"] += sale.due
            row["sales_count"] += 1
        return Response(sorted(by_customer.values(), key=lambda row: -row["total_due"]))
