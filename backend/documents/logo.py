import io
import os
import uuid as uuid_lib
from pathlib import Path

from django.conf import settings
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from audit.services import log_action
from photos.services import MAX_PIXELS

from .services import DocumentError, _lock_settings

LOGO_MAX_SIDE = 600  # largeur ou hauteur maximale : suffisant pour un en-tête de facture


def process_logo(data):
    """Valide l'image puis renvoie (octets PNG, largeur, hauteur) SANS aucune métadonnée."""
    if not data:
        raise DocumentError("Aucune image reçue.")
    if len(data) > settings.PHOTO_MAX_UPLOAD_BYTES:
        raise DocumentError("Image trop lourde (8 Mo au maximum).")
    try:
        image = Image.open(io.BytesIO(data))
        if image.format not in ("JPEG", "PNG", "WEBP"):
            raise DocumentError("Format refusé : envoyez un logo JPEG, PNG ou WebP.")
        if image.width * image.height > MAX_PIXELS:
            raise DocumentError("Image trop grande.")
        image = ImageOps.exif_transpose(image)
        image.load()
    except DocumentError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise DocumentError("Image illisible ou corrompue.")

    image = image.convert("RGBA")  # la transparence du logo est conservée
    image.thumbnail((LOGO_MAX_SIDE, LOGO_MAX_SIDE), Image.Resampling.LANCZOS)
    image.info = {}
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue(), image.width, image.height


def logo_file(relative_path):
    """Chemin réel du logo, avec la garantie qu'il reste dans le dossier privé."""
    root = Path(settings.PHOTOS_ROOT).resolve()
    target = (root / relative_path).resolve()
    if not relative_path or root not in target.parents:
        raise DocumentError("Chemin de logo invalide.")
    return target


@transaction.atomic
def set_logo(data, *, user=None):
    """Enregistre un nouveau logo. L'ancien fichier est GARDÉ : les factures déjà émises le citent."""
    png, _width, _height = process_logo(data)
    row = _lock_settings()
    before = row.logo_path
    relative = f"{row.organization_id}/logos/{uuid_lib.uuid4()}.png"
    target = logo_file(relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(png)
    os.replace(temporary, target)  # écriture atomique : jamais de fichier à moitié écrit
    try:
        row.logo_path = relative
        row.save(update_fields=["logo_path", "updated_at"])
        log_action(
            user=user,
            action="document_settings.logo_changed",
            obj=row,
            summary="Logo des factures et reçus modifié",
            before={"logo_path": before},
            after={"logo_path": relative},
        )
    except Exception:
        target.unlink(missing_ok=True)  # la base a échoué : on ne laisse pas de fichier orphelin
        raise
    return row


@transaction.atomic
def remove_logo(*, user=None):
    """Retire le logo des futurs documents (le fichier est gardé pour les documents déjà émis)."""
    row = _lock_settings()
    before = row.logo_path
    row.logo_path = ""
    row.save(update_fields=["logo_path", "updated_at"])
    log_action(
        user=user,
        action="document_settings.logo_removed",
        obj=row,
        summary="Logo des factures et reçus retiré",
        before={"logo_path": before},
        after={"logo_path": ""},
    )
    return row
