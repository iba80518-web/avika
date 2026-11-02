from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from core.currencies import CURRENCY_CHOICES

from .models import Farm, Membership, Organization
from .roles import Role

User = get_user_model()


class FarmSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farm
        fields = ["id", "name", "location", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value):
        # Recherche dans l'exploitation active uniquement (gestionnaire filtré).
        queryset = Farm.objects.filter(name=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Un site porte déjà ce nom.")
        return value


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    organization_name = serializers.CharField(max_length=150)
    reference_currency = serializers.ChoiceField(choices=CURRENCY_CHOICES, default="GNF")

    def validate_email(self, value):
        value = value.strip()
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Cette adresse email est déjà utilisée.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if value and User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Ce numéro de téléphone est déjà utilisé.")
        return value

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("phone"):
            raise serializers.ValidationError("Indiquez un email ou un numéro de téléphone.")
        candidate = User(
            email=attrs.get("email") or None,
            phone=attrs.get("phone") or None,
            full_name=attrs["full_name"],
        )
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": list(error.messages)})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data.get("email") or None,
            phone=validated_data.get("phone") or None,
            password=validated_data["password"],
            full_name=validated_data["full_name"],
        )
        organization = Organization.objects.create(
            name=validated_data["organization_name"],
            reference_currency=validated_data["reference_currency"],
        )
        Membership.objects.create(user=user, organization=organization, role=Role.OWNER)
        return user
