from .models import AuditLog


def snapshot(obj, fields):
    """Photo des champs choisis d'un objet, en valeurs simples (nombres, textes, dates en texte)."""
    data = {}
    for name in fields:
        value = getattr(obj, name)
        data[name] = value if isinstance(value, (bool, int, str)) or value is None else str(value)
    return data


def log_action(*, user, action, obj=None, summary="", before=None, after=None):
    """Ajoute une ligne au journal d'audit de l'exploitation active."""
    return AuditLog.objects.create(
        user=user,
        action=action,
        object_type=obj.__class__.__name__ if obj is not None else "",
        object_id=obj.pk if obj is not None else None,
        summary=summary[:255],
        before=before,
        after=after,
    )
