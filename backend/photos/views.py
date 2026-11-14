from django.conf import settings
from django.http import FileResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from tenants.api import TenantAPIMixin

from .models import Photo
from .serializers import PhotoInputSerializer, PhotoSerializer
from .services import PhotoError, photo_file, record_photo


class PhotoViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Photos de preuve : envoyées par l'équipe, vues seulement par le propriétaire et le vétérinaire."""

    serializer_class = PhotoSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_by_action = {
        "list": "view_photos",
        "retrieve": "view_photos",
        "file": "view_photos",
        "create": "add_photos",
    }

    def get_queryset(self):
        queryset = Photo.objects.select_related("cycle").order_by("-taken_date", "-id")
        params = self.request.query_params
        if params.get("cycle", "").isdigit():
            queryset = queryset.filter(cycle_id=int(params["cycle"]))
        if params.get("kind") in Photo.Kind.values:
            queryset = queryset.filter(kind=params["kind"])
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = PhotoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        upload = values.pop("image")
        data = upload.read(settings.PHOTO_MAX_UPLOAD_BYTES + 1)
        try:
            photo, created = record_photo(user=request.user, data=data, **values)
        except PhotoError as error:
            raise ValidationError({"detail": str(error)})
        return Response(PhotoSerializer(photo).data, status=201 if created else 200)

    @action(detail=True, methods=["get"])
    def file(self, request, pk=None):
        """L'image, servie seulement après contrôle de la connexion, de l'exploitation et du droit."""
        photo = self.get_object()
        try:
            path = photo_file(photo)
        except PhotoError:
            raise NotFound("Photo introuvable.")
        if not path.is_file():
            raise NotFound("Fichier introuvable.")
        response = FileResponse(path.open("rb"), content_type="image/jpeg")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Disposition"] = f'inline; filename="photo-{photo.pk}.jpg"'
        return response
