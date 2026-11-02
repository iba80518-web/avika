from contextlib import contextmanager
from contextvars import ContextVar

_current_organization_id = ContextVar("current_organization_id", default=None)


class TenantContextMissing(Exception):
    """Aucune exploitation active : la requête aurait pu mélanger des données."""


class CrossTenantError(Exception):
    """Tentative d'écrire un objet qui appartient à une autre exploitation."""


def get_current_organization_id():
    return _current_organization_id.get()


def set_organization(organization):
    """Active une exploitation et renvoie un jeton pour la désactiver ensuite."""
    return _current_organization_id.set(getattr(organization, "pk", organization))


def reset_organization(token):
    _current_organization_id.reset(token)


@contextmanager
def organization_context(organization):
    """Active une exploitation (objet ou identifiant) le temps d'un bloc `with`."""
    token = set_organization(organization)
    try:
        yield
    finally:
        reset_organization(token)
