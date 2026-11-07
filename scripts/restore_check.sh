#!/usr/bin/env bash
# Prouve qu'une sauvegarde est restaurable : la charge dans une base TEMPORAIRE, compte les tables,
# puis supprime la base temporaire. Ne touche jamais à la vraie base.
# Usage : ./scripts/restore_check.sh backups/avika-AAAAMMJJ-HHMMSS.sql.gz
set -euo pipefail
cd "$(dirname "$0")/.."

file="${1:?Indiquez le fichier de sauvegarde (.sql.gz)}"
[ -f "$file" ] || { echo "Fichier introuvable : $file" >&2; exit 1; }

tmpdb="avika_restore_check"
psql_db() { docker compose exec -T db sh -c "psql -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" $*"; }

psql_db "-d postgres -c 'DROP DATABASE IF EXISTS $tmpdb;'" >/dev/null
psql_db "-d postgres -c 'CREATE DATABASE $tmpdb;'" >/dev/null
gunzip -c "$file" | psql_db "-d $tmpdb -q" >/dev/null
tables=$(psql_db "-d $tmpdb -t -A -c \"SELECT count(*) FROM information_schema.tables WHERE table_schema='public';\"")
psql_db "-d postgres -c 'DROP DATABASE $tmpdb;'" >/dev/null

echo "OK : sauvegarde restaurable, $tables tables retrouvées."
