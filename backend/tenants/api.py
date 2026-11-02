from rest_framework.permissions import BasePermission, IsAuthenticated

from .context import reset_organization, set_organization
from .models import Membership, Organization
from .permissions import has_permission


def resolve_membership(request):
    """Trouve l'appartenance active de l'utilisateur connecté.

    Une seule exploitation : elle est choisie automatiquement.
    Plusieurs : l'en-tête X-Organization est obligatoire et vérifié.
    """
    queryset = Membership.objects.filter(
        user=request.user,
        status=Membership.Status.ACTIVE,
        organization__status=Organization.Status.ACTIVE,
    ).select_related("organization")

    header = request.headers.get("X-Organization")
    if header:
        try:
            organization_id = int(header)
        except ValueError:
            return None
        return queryset.filter(organization_id=organization_id).first()

    memberships = list(queryset[:2])
    return memberships[0] if len(memberships) == 1 else None


class TenantPermission(BasePermission):
    """Vérifie l'exploitation active puis le droit requis pour l'action.

    Refus par défaut : une action absente de `permission_by_action` est interdite.
    """

    message = "Accès refusé."

    def has_permission(self, request, view):
        membership = resolve_membership(request)
        if membership is None:
            self.message = (
                "Aucune exploitation active. Si vous en avez plusieurs, "
                "précisez-la avec l'en-tête X-Organization."
            )
            return False

        code = getattr(view, "permission_by_action", {}).get(getattr(view, "action", None))
        if code is None or not has_permission(membership, code):
            self.message = "Vous n'avez pas le droit d'effectuer cette action."
            return False

        request.membership = membership
        return True


class TenantAPIMixin:
    """À placer en premier dans les vues métier : active l'exploitation pour la requête."""

    permission_classes = [IsAuthenticated, TenantPermission]
    permission_by_action = {}
    _tenant_token = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)  # authentification + permissions
        self._tenant_token = set_organization(request.membership.organization_id)

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        finally:
            if self._tenant_token is not None:
                reset_organization(self._tenant_token)
                self._tenant_token = None
