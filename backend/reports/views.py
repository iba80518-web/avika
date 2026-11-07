from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from farming.models import Cycle
from tenants.api import TenantAPIMixin
from tenants.permissions import has_permission

from .pdf import render_report_pdf
from .services import cycle_report_text, whatsapp_link


class ReportViewSet(TenantAPIMixin, viewsets.GenericViewSet):
    """Rapports d'un cycle : GET /reports/<id>/whatsapp/ (texte) et GET /reports/<id>/pdf/.

    Droit d'entrée : « view_dashboard ». L'argent exige « view_finances », le résultat et la marge
    « view_profits », la santé « manage_health » : sans ces droits, ces lignes sont absentes
    du texte comme du PDF.
    """

    permission_by_action = {"whatsapp": "view_dashboard", "pdf": "view_dashboard"}

    def get_queryset(self):
        return Cycle.objects.select_related("coop", "organization")

    def _text(self, request, cycle):
        membership = request.membership
        return cycle_report_text(
            cycle,
            include_finance=has_permission(membership, "view_finances"),
            include_profits=has_permission(membership, "view_profits"),
            include_health=has_permission(membership, "manage_health"),
        )

    @action(detail=True, methods=["get"])
    def whatsapp(self, request, pk=None):
        cycle = self.get_object()
        text = self._text(request, cycle)
        return Response({"cycle": cycle.pk, "text": text, "whatsapp_url": whatsapp_link(text)})

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        cycle = self.get_object()
        content = render_report_pdf(self._text(request, cycle))
        response = HttpResponse(content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="rapport-cycle-{cycle.pk}.pdf"'
        return response
