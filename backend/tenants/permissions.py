from .models import Membership
from .roles import DEFAULT_ROLE_PERMISSIONS, PERMISSION_CODES, Role


def has_permission(membership: Membership, code: str) -> bool:
    """Un membre n'a un droit que si son appartenance est active et que le rôle
    ou une exception individuelle le lui accorde."""
    if membership.status != Membership.Status.ACTIVE:
        return False
    if membership.role == Role.OWNER:
        return True
    override = membership.permission_overrides.filter(permission=code).first()
    if override is not None:
        return override.granted
    return code in DEFAULT_ROLE_PERMISSIONS.get(membership.role, set())


def effective_permissions(membership: Membership) -> list[str]:
    """Liste des permissions réellement accordées à ce membre."""
    return [code for code in PERMISSION_CODES if has_permission(membership, code)]
