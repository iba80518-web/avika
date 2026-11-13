import uuid

from django.conf import settings
from django.db import models
from django.db.models import F

from farming.models import Cycle
from tenants.models import TenantModel


class EggCollection(TenantModel):
    """Ramassage d'œufs d'une bande de pondeuses, un jour donné.

    Plusieurs ramassages le même jour sont permis (matin, soir) : le total du jour est leur somme.
    `collected` est le total ramassé ; `broken` en fait partie (cassés ou perdus, donc invendables).
    """

    cycle = models.ForeignKey(Cycle, on_delete=models.PROTECT, related_name="egg_collections")
    collected_date = models.DateField("date du ramassage")
    collected = models.PositiveIntegerField("œufs ramassés")
    broken = models.PositiveIntegerField("dont cassés ou perdus", default=0)
    note = models.CharField(max_length=255, blank=True)
    uuid = models.UUIDField(default=uuid.uuid4)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "uuid"], name="unique_egg_collection_uuid"
            ),
            models.CheckConstraint(
                condition=models.Q(broken__lte=F("collected")),
                name="egg_broken_not_above_collected",
            ),
        ]
        indexes = [models.Index(fields=["organization", "cycle", "collected_date"])]

    def __str__(self):
        return f"{self.collected} œufs le {self.collected_date}"
