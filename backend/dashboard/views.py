from rest_framework import viewsets
from rest_framework.response import Response

from tenants.api import TenantAPIMixin
from tenants.permissions import has_permission

from .services import build_dashboard


class DashboardViewSet(TenantAPIMixin, viewsets.GenericViewSet):
    """GET /dashboard/ : la vue d'ensemble de l'exploitation.

    Tout le monde ayant « view_dashboard » voit les cycles et les alertes de mortalité.
    Le stock exige « manage_feed » et les chiffres d'argent exigent « view_finances » :
    sans ces droits, les blocs correspondants sont renvoyés à null.
    """

    permission_by_action = {"list": "view_dashboard"}

    def list(self, request, *args, **kwargs):
        membership = request.membership
        data = build_dashboard(
            include_stock=has_permission(membership, "manage_feed"),
            include_finance=has_permission(membership, "view_finances"),
            include_health=has_permission(membership, "manage_health"),
        )
        return Response(data)
