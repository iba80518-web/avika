from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class StatusView(APIView):
    """GET /api/v1/status/ : « le serveur et sa base répondent-ils ? ».

    Ouvert à tous, sans jeton : c'est ce qu'interrogent Nginx, Docker et la supervision.
    Il ne renvoie aucune donnée de l'exploitation, seulement ok ou erreur.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            return Response({"status": "error", "database": "down"}, status=503)
        return Response({"status": "ok", "database": "ok"})
