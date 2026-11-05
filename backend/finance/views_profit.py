from rest_framework import mixins, viewsets
from rest_framework.response import Response

from farming.models import Cycle
from tenants.api import TenantAPIMixin
from tenants.permissions import has_permission

from .profitability import cycle_profitability


class ProfitabilityViewSet(TenantAPIMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """GET /profitability/<id du cycle>/ : les chiffres financiers d'un cycle.

    Le droit « voir_finances » ouvre l'écran ; le résultat et la marge exigent en plus
    « voir_bénéfices » : sans lui, ils sont renvoyés à null.
    """

    permission_by_action = {"retrieve": "view_finances"}

    def get_queryset(self):
        return Cycle.objects.all()

    def retrieve(self, request, *args, **kwargs):
        data = cycle_profitability(self.get_object())
        if not has_permission(request.membership, "view_profits"):
            data["result"] = None
            data["margin_percent"] = None
        return Response(data)
