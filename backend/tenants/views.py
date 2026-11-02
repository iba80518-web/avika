from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .api import TenantAPIMixin
from .models import Farm, Membership
from .permissions import effective_permissions
from .serializers import FarmSerializer, RegisterSerializer


def user_data(user):
    return {"id": user.pk, "full_name": user.full_name, "email": user.email, "phone": user.phone}


def organization_data(organization):
    return {
        "id": organization.pk,
        "name": organization.name,
        "reference_currency": organization.reference_currency,
    }


class RegisterView(APIView):
    """Crée un compte, son exploitation et son rôle de propriétaire."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        membership = user.memberships.select_related("organization").get()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": user_data(user),
                "organization": organization_data(membership.organization),
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    """Profil de l'utilisateur connecté, ses exploitations et ses droits."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = Membership.objects.filter(
            user=request.user, status=Membership.Status.ACTIVE
        ).select_related("organization")
        return Response(
            {
                "user": user_data(request.user),
                "memberships": [
                    {
                        "organization": organization_data(m.organization),
                        "role": m.role,
                        "permissions": effective_permissions(m),
                    }
                    for m in memberships
                ],
            }
        )


class FarmViewSet(TenantAPIMixin, viewsets.ModelViewSet):
    serializer_class = FarmSerializer
    permission_by_action = {
        "list": "view_farming",
        "retrieve": "view_farming",
        "create": "manage_coops",
        "update": "manage_coops",
        "partial_update": "manage_coops",
        "destroy": "manage_coops",
    }

    def get_queryset(self):
        # Filtré automatiquement sur l'exploitation active.
        return Farm.objects.order_by("name")
