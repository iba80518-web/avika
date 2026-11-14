import io
import uuid as uuid_lib
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from audit.services import log_action, snapshot
from eggs.models import EggCollection
from farming.models import Cycle, FlockEvent

from .models import Photo

MAX_PIXELS = 40_000_000  # refuse les images démesurées (protection mémoire)
PHOTO_FIELDS = ["cycle_id", "kind", "taken_date", "egg_collection_id", "flock_event_id", "size_bytes"]


class PhotoError(Exception):
    """Règle non respectée ; le message est destiné à l'utilisateur."""


def process_image(data):
    """Valide l'image puis renvoie (octets JPEG, largeur, hauteur) SANS aucune métadonnée."""
    if not data:
        raise PhotoError("Aucune image reçue.")
    if len(data) > settings.PHOTO_MAX_UPLOAD_BYTES:
        raise PhotoError("Image trop lourde (8 Mo au maximum).")
    try:
        image = Image.open(io.BytesIO(data))
        if image.format not in ("JPEG", "PNG", "WEBP"):
            raise PhotoError("Format refusé : envoyez une photo JPEG, PNG ou WebP.")
        if image.width * image.height > MAX_PIXELS:
            raise PhotoError("Image trop grande.")
        image = ImageOps.exif_transpose(image)  # remet la photo à l'endroit
        image.load()
    except PhotoError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise PhotoError("Image illisible ou corrompue.")

    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.split()[-1])
        image = flat
    else:
        image = image.convert("RGB")
    image.thumbnail((settings.PHOTO_MAX_SIDE, settings.PHOTO_MAX_SIDE), Image.Resampling.LANCZOS)
    image.info = {}  # aucune métadonnée (GPS, appareil, heure) n'est conservée

    out = io.BytesIO()
    image.save(out, "JPEG", quality=80, optimize=True)
    return out.getvalue(), image.width, image.height


def photo_file(photo):
    """Chemin réel du fichier, avec la garantie qu'il reste dans le dossier privé."""
    root = Path(settings.PHOTOS_ROOT).resolve()
    target = (root / photo.path).resolve()
    if root not in target.parents:
        raise PhotoError("Chemin de photo invalide.")
    return target


@transaction.atomic
def record_photo(
    *,
    cycle,
    kind,
    taken_date,
    data,
    note="",
    egg_collection_id=None,
    flock_event_id=None,
    user=None,
    uuid=None,
):
    """Enregistre une photo. Renvoie (photo, créée) ; un uuid déjà reçu ne crée pas de doublon."""
    if uuid is not None:
        existing = Photo.objects.filter(uuid=uuid).first()
        if existing is not None:
            if (existing.cycle_id, existing.kind, existing.taken_date) != (
                cycle.pk,
                kind,
                taken_date,
            ):
                raise PhotoError("Cet identifiant d'opération a déjà servi pour autre chose.")
            return existing, False

    if kind not in Photo.Kind.values:
        raise PhotoError("Type de photo inconnu.")
    if cycle.status == Cycle.Status.CANCELLED:
        raise PhotoError("Cette bande est annulée.")
    if taken_date > timezone.localdate():
        raise PhotoError("La date ne peut pas être dans le futur.")
    if taken_date < cycle.start_date:
        raise PhotoError("La date précède le début de la bande.")
    if kind == Photo.Kind.EGGS and cycle.type != "layer":
        raise PhotoError("Les photos d'œufs concernent une bande de pondeuses.")

    collection = None
    event = None
    if egg_collection_id:
        if kind != Photo.Kind.EGGS:
            raise PhotoError("Un ramassage d'œufs ne se lie qu'à une photo d'œufs.")
        collection = EggCollection.objects.filter(pk=egg_collection_id, cycle=cycle).first()
        if collection is None:
            raise PhotoError("Ramassage introuvable pour cette bande.")
    if flock_event_id:
        if kind != Photo.Kind.MORTALITY:
            raise PhotoError("Une mortalité ne se lie qu'à une photo de volailles mortes.")
        event = FlockEvent.objects.filter(
            pk=flock_event_id, cycle=cycle, event_type=FlockEvent.EventType.MORTALITY.value
        ).first()
        if event is None:
            raise PhotoError("Mortalité introuvable pour cette bande.")

    jpeg, width, height = process_image(data)

    name = f"{cycle.organization_id}/{uuid_lib.uuid4().hex}.jpg"
    target = Path(settings.PHOTOS_ROOT) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(jpeg)
    temporary.replace(target)  # écriture atomique : jamais de fichier à moitié écrit

    extra = {"uuid": uuid} if uuid is not None else {}
    try:
        photo = Photo.objects.create(
            cycle=cycle,
            kind=kind,
            taken_date=taken_date,
            path=name,
            width=width,
            height=height,
            size_bytes=len(jpeg),
            egg_collection=collection,
            flock_event=event,
            note=note,
            created_by=user,
            **extra,
        )
        log_action(
            user=user,
            action="photo.added",
            obj=photo,
            summary=f"Photo ({photo.get_kind_display()}) de la bande {cycle.name}",
            after=snapshot(photo, PHOTO_FIELDS),
        )
    except Exception:
        target.unlink(missing_ok=True)  # pas de fichier orphelin si l'enregistrement échoue
        raise
    return photo, True
