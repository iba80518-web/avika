from django.conf import settings
from django.http import FileResponse, HttpResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from tenants.api import TenantAPIMixin

from . import logo as logo_service
from .models import Document
from .pdf import render_document_pdf
from .serializers import (
    DocumentInputSerializer,
    DocumentSerializer,
    DocumentSettingsInputSerializer,
    DocumentSettingsSerializer,
)
from .services import DocumentError, get_settings, issue_invoice, issue_receipt, update_settings


class DocumentSettingsView(TenantAPIMixin, viewsets.ViewSet):
    """Personnalisation des factures et reçus : réservée à qui a le droit manage_settings."""

    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_by_action = {
        "current": "manage_settings",
        "change": "manage_settings",
        "upload_logo": "manage_settings",
        "delete_logo": "manage_settings",
        "show_logo": "manage_settings",
    }

    def current(self, request):
        return Response(DocumentSettingsSerializer(get_settings()).data)

    def change(self, request):
        serializer = DocumentSettingsInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            row = update_settings(user=request.user, **serializer.validated_data)
        except DocumentError as error:
            raise ValidationError({"detail": str(error)})
        return Response(DocumentSettingsSerializer(row).data)

    def upload_logo(self, request):
        upload = request.FILES.get("image")
        if upload is None:
            raise ValidationError({"image": "Envoyez le logo dans le champ « image »."})
        data = upload.read(settings.PHOTO_MAX_UPLOAD_BYTES + 1)
        try:
            row = logo_service.set_logo(data, user=request.user)
        except DocumentError as error:
            raise ValidationError({"detail": str(error)})
        return Response(DocumentSettingsSerializer(row).data)

    def delete_logo(self, request):
        row = logo_service.remove_logo(user=request.user)
        return Response(DocumentSettingsSerializer(row).data)

    def show_logo(self, request):
        """Le logo, servi seulement après contrôle de la connexion, de l'exploitation et du droit."""
        try:
            path = logo_service.logo_file(get_settings().logo_path)
        except DocumentError:
            raise NotFound("Aucun logo.")
        if not path.is_file():
            raise NotFound("Fichier introuvable.")
        response = FileResponse(path.open("rb"), content_type="image/png")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class DocumentViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Factures et reçus émis. Aucune modification, aucune suppression."""

    serializer_class = DocumentSerializer
    permission_by_action = {
        "list": "manage_sales",
        "retrieve": "manage_sales",
        "create": "manage_sales",
        "pdf": "manage_sales",
    }

    def get_queryset(self):
        queryset = Document.objects.select_related("sale")
        params = self.request.query_params
        if params.get("sale", "").isdigit():
            queryset = queryset.filter(sale_id=int(params["sale"]))
        if params.get("kind") in Document.Kind.values:
            queryset = queryset.filter(kind=params["kind"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = DocumentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            if values["kind"] == Document.Kind.INVOICE:
                document, created = issue_invoice(
                    values["sale"], user=request.user, customer_name=values["customer_name"]
                )
            else:
                document, created = issue_receipt(
                    values["payment"], user=request.user, customer_name=values["customer_name"]
                )
        except DocumentError as error:
            raise ValidationError({"detail": str(error)})
        return Response(DocumentSerializer(document).data, status=201 if created else 200)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        document = self.get_object()
        cancelled = document.sale.status == "cancelled"
        response = HttpResponse(
            render_document_pdf(document, cancelled=cancelled), content_type="application/pdf"
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Disposition"] = f'inline; filename="{document.number}.pdf"'
        return response
