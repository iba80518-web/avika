#!/usr/bin/env bash
# Sauvegarde la base PostgreSQL dans backups/ (fichier compressé, daté). Garde les 14 dernières.
# Usage : ./scripts/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p backups
chmod 700 backups
file="backups/avika-$(date +%Y%m%d-%H%M%S).sql.gz"

# pg_dump tourne dans le conteneur de la base ; les identifiants viennent de son environnement.
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" --no-owner "$POSTGRES_DB"' | gzip > "$file"

# Une sauvegarde vide ou minuscule est un échec silencieux : on le refuse.
size=$(stat -c %s "$file")
if [ "$size" -lt 1000 ]; then
    rm -f "$file"
    echo "ERREUR : sauvegarde trop petite ($size octets), supprimée." >&2
    exit 1
fi

# Rotation : on garde les 14 plus récentes.
ls -1t backups/avika-*.sql.gz | tail -n +15 | xargs -r rm -f --
echo "OK : $file ($size octets)"
