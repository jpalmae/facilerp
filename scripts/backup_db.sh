#!/usr/bin/env sh
set -eu

# ──────────────────────────────────────────────────────────────
# FacilERP — PostgreSQL backup with retention policy
#
# Environment variables:
#   DATABASE_URL   (required) — full connection string
#   BACKUP_DIR     (optional) — output directory (default: ./backups)
#   RETENTION_DAYS (optional) — delete backups older than N days (default: 30)
# ──────────────────────────────────────────────────────────────

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL no configurado" >&2
  exit 1
fi

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "ERROR: pg_dump no disponible" >&2
  exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
STAMP="$(date +%Y%m%d_%H%M%S)"
TARGET="${BACKUP_DIR}/facilerp_${STAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

# ── Create backup ────────────────────────────────────────────
echo "[$(date -Iseconds)] Iniciando backup..."
pg_dump "${DATABASE_URL}" | gzip -c > "${TARGET}"
SIZE=$(du -h "${TARGET}" | cut -f1)
echo "[$(date -Iseconds)] Backup creado: ${TARGET} (${SIZE})"

# ── Retention: remove old backups ────────────────────────────
DELETED=0
find "${BACKUP_DIR}" -name "facilerp_*.sql.gz" -type f -mtime +"${RETENTION_DAYS}" | while read -r old_file; do
  rm -f "${old_file}"
  echo "[$(date -Iseconds)] Eliminado (>${RETENTION_DAYS}d): ${old_file}"
  DELETED=$((DELETED + 1))
done

# ── Summary ──────────────────────────────────────────────────
TOTAL=$(find "${BACKUP_DIR}" -name "facilerp_*.sql.gz" -type f | wc -l | tr -d ' ')
echo "[$(date -Iseconds)] Total backups: ${TOTAL} (retención: ${RETENTION_DAYS} días)"
