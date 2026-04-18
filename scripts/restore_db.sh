#!/usr/bin/env sh
set -eu

if [ $# -ne 1 ]; then
  echo "Uso: $0 <archivo.sql.gz|archivo.sql>" >&2
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL no configurado" >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "psql no disponible" >&2
  exit 1
fi

SOURCE_FILE="$1"

case "${SOURCE_FILE}" in
  *.gz) gunzip -c "${SOURCE_FILE}" | psql "${DATABASE_URL}" ;;
  *) psql "${DATABASE_URL}" < "${SOURCE_FILE}" ;;
esac

echo "Restore completado desde ${SOURCE_FILE}"
