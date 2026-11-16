from rest_framework import serializers

from finance.models import Payment, Sale
from tenants.fields import TenantPrimaryKeyRelatedField

from .models import Document, DocumentSettings


class DocumentSettingsSerializer(serializers.ModelSerializer):
    """Ce que l'API renvoie : jamais le chemin du fichier du logo, seulement son adresse protégée."""

    has_logo = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    defaults = serializers.SerializerMethodField()

    class Meta:
        model = DocumentSettings
        fields = [
            "business_name", "address", "phone", "email", "tax_id", "registry_id",
            "accent_color", "footer_text", "payment_terms", "invoice_prefix", "receipt_prefix",
            "has_logo", "logo_url", "defaults",
        ]
        read_only_fields = fields

    def get_has_logo(self, obj):
        return bool(obj.logo_path)

    def get_logo_url(self, obj):
        return "/api/v1/document-settings/logo/file/" if obj.logo_path else None

    def get_defaults(self, obj):
        """Valeurs de repli (celles de l'exploitation) quand un champ est laissé vide."""
        organization = obj.organization
        return {
            "name": organization.name,
            "address": organization.address,
            "phone": organization.phone,
            "currency": organization.reference_currency,
        }


class DocumentSettingsInputSerializer(serializers.Serializer):
    business_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    tax_id = serializers.CharField(max_length=60, required=False, allow_blank=True)
    registry_id = serializers.CharField(max_length=60, required=False, allow_blank=True)
    accent_color = serializers.CharField(max_length=7, required=False)
    footer_text = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    payment_terms = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    invoice_prefix = serializers.CharField(max_length=10, required=False)
    receipt_prefix = serializers.CharField(max_length=10, required=False)


class DocumentSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    sale_status = serializers.CharField(source="sale.status", read_only=True)
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "uuid", "kind", "number", "year", "sequence", "sale", "payment", "issued_on",
            "customer_name", "sale_status", "content", "pdf_url", "created_by", "created_at",
        ]
        read_only_fields = fields

    def get_customer_name(self, obj):
        customer = obj.content.get("customer")
        return customer["name"] if customer else ""

    def get_pdf_url(self, obj):
        return f"/api/v1/documents/{obj.pk}/pdf/"


class DocumentInputSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Document.Kind.choices)
    sale = TenantPrimaryKeyRelatedField(model=Sale, required=False)
    payment = TenantPrimaryKeyRelatedField(model=Payment, required=False)
    customer_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["kind"] == Document.Kind.INVOICE and "sale" not in attrs:
            raise serializers.ValidationError({"sale": "Indiquez la vente à facturer."})
        if attrs["kind"] == Document.Kind.RECEIPT and "payment" not in attrs:
            raise serializers.ValidationError({"payment": "Indiquez le paiement concerné."})
        return attrs
