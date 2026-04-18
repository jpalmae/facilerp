# Producción

## Requisitos

- PostgreSQL accesible desde `DATABASE_URL`
- Variables de entorno completas en `.env`
- `SECRET_KEY` fuerte y única
- `CREATE_DB_ON_START=false`
- `AUTO_MIGRATE_ON_START=true`
- `SESSION_COOKIE_SECURE=true`
- `REMEMBER_COOKIE_SECURE=true`
- `PREFERRED_URL_SCHEME=https`
- `TRUST_PROXY_COUNT=1` si corres detrás de Nginx o LB

## Despliegue recomendado

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

El contenedor `web` aplica migraciones en arranque mediante `scripts/docker-entrypoint.sh` antes de iniciar Gunicorn.

## Salud

- `GET /healthz`: liveness simple
- `GET /readyz`: readiness con chequeo de base de datos

## Backups

Crear backup:

```bash
DATABASE_URL=... ./scripts/backup_db.sh
```

Restaurar backup:

```bash
DATABASE_URL=... ./scripts/restore_db.sh backups/facilerp_YYYYMMDD_HHMMSS.sql.gz
```

## Operación

- Logs HTTP salen a stdout con `request_id`, usuario, empresa y latencia.
- Nginx reenvía `X-Request-ID`.
- Gunicorn usa configuración centralizada en `gunicorn.conf.py`.
- Los headers de seguridad se emiten desde Flask y Nginx.
