from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from farming.models import Cycle
from tenants.api import TenantAPIMixin
from tenants.permissions import has_permission

from .services import cycle_report_text, whatsapp_link


class ReportViewSet(TenantAPIMixin, viewsets.GenericViewSet):
    """GET /reports/<id du cycle>/whatsapp/ : le rapport du cycle en texte, prêt pour WhatsApp.

    Droit d'entrée : « view_dashboard ». L'argent exige « view_finances », le résultat et la marge
    « view_profits », la santé « manage_health » : sans ces droits, ces lignes sont absentes du texte.
    """

    permission_by_action = {"whatsapp": "view_dashboard"}

    def get_queryset(self):
        return Cycle.objects.select_related("coop", "organization")

    @action(detail=True, methods=["get"])
    def whatsapp(self, request, pk=None):
        cycle = self.get_object()
        membership = request.membership
        text = cycle_report_text(
            cycle,
            include_finance=has_permission(membership, "view_finances"),
            include_profits=has_permission(membership, "view_profits"),
            include_health=has_permission(membership, "manage_health"),
        )
        return Response({"cycle": cycle.pk, "text": text, "whatsapp_url": whatsapp_link(text)})
