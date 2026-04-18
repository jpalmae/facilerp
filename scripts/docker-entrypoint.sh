#!/usr/bin/env sh
set -eu

mkdir -p /app/instance /app/backups /app/app/static/uploads/brand

if [ "${AUTO_MIGRATE_ON_START:-false}" = "true" ]; then
  flask --app "app:create_app('production')" db-upgrade
fi

if [ "${ENABLE_DEMO_BOOTSTRAP:-false}" = "true" ]; then
  flask --app "app:create_app('production')" seed-demo
fi

exec "$@"
