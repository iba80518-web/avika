import uuid

from django.conf import settings
from django.db import models

from eggs.models import EggCollection
from farming.models import Cycle, FlockEvent
from tenants.models import TenantModel


class Photo(TenantModel):
    """Photo de preuve : volailles mortes ou œufs ramassés. Jamais supprimée, jamais publique."""

    class Kind(models.TextChoices):
        MORTALITY = "mortality", "Volailles mortes"
        EGGS = "eggs", "Œufs ramassés"

    cycle = models.ForeignKey(Cycle, on_delete=models.PROTECT, related_name="photos")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    taken_date = models.DateField("date")
    # Chemin RELATIF dans PHOTOS_ROOT : la photo n'a aucune adresse web directe.
    path = models.CharField(max_length=255)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    size_bytes = models.PositiveIntegerField()
    egg_collection = models.ForeignKey(
        EggCollection, null=True, blank=True, on_delete=models.PROTECT, related_name="photos"
    )
    flock_event = models.ForeignKey(
        FlockEvent, null=True, blank=True, on_delete=models.PROTECT, related_name="photos"
    )
    note = models.TextField(blank=True)
    uuid = models.UUIDField(default=uuid.uuid4)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "uuid"], name="unique_photo_uuid"),
        ]
        indexes = [models.Index(fields=["organization", "cycle", "taken_date"])]

    def __str__(self):
        return f"Photo {self.pk} ({self.kind}, {self.taken_date})"
