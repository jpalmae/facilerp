# FacilERP

Base inicial de desarrollo para un ERP modular orientado a PyMEs peruanas. El repositorio ya cubre infraestructura base, marca white-label, inventario, compras, ventas, contabilidad, tesorería, cuentas por cobrar/pagar y reportes base a partir de la especificación [FacilERP_Spec_v1.1.md](/Users/jpalmae/dev/facilerp/FacilERP_Spec_v1.1.md).

## Incluido hoy

- App Flask con arquitectura modular (`auth`, `core`, `marca`)
- Base de datos relacional con SQLAlchemy
- Login local de desarrollo con roles y multiempresa
- Dashboard SSR con navegación por roadmap
- Configuración de marca por empresa con preview en vivo
- Inventario: productos, almacenes, stock y movimientos
- Compras: proveedores, órdenes y recepciones con impacto en stock
- Ventas: clientes, pedidos y descuento automático de stock
- Contabilidad: plan de cuentas, períodos, asientos automáticos y manuales
- Tesorería: cuentas caja/banco y movimientos con reflejo contable
- CxC / CxP: cartera de clientes, obligaciones con proveedores, cobros y pagos
- Reportes: balance de comprobación, snapshot financiero y libro diario reciente
- Exportación financiera en PDF, Excel y PLE TXT
- Backends configurables para Supabase Auth y Supabase Storage
- Integraciones encapsuladas para SUNAT (RUC) y BCRP (tipo de cambio)
- Alembic configurado con migración inicial versionada
- Bootstrap automático de datos demo
- Docker, Nginx, Gunicorn, healthchecks, backups y CI
- Pruebas para autenticación, branding, inventario, compras, ventas, contabilidad y tesorería

## Stack

- Python 3.12
- Flask 3
- SQLAlchemy 2
- Flask-WTF / Flask-Login / Flask-Limiter
- Jinja2 + HTMX + Alpine.js
- Tailwind CSS preparado vía CLI
- Docker + Docker Compose

## Arranque local

1. Crea tu archivo `.env` a partir de `.env.example`.
2. Instala dependencias Python y Node si vas a correr fuera de Docker.
3. Ejecuta:

```bash
flask --app app:create_app run --debug
```

La app crea tablas y carga datos demo automáticamente en desarrollo.

## Credenciales demo

- `admin@facilerp.pe` / `Admin123!`
- `contador@facilerp.pe` / `Contador123!`
- `ventas@facilerp.pe` / `Ventas123!`

## Docker

```bash
docker-compose up --build
```

El stack local ahora incluye PostgreSQL en contenedor y usa el archivo `.env` del repositorio para pruebas rápidas.

## Producción

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Puntos operativos:

- `web` arranca con Gunicorn y puede aplicar migraciones automáticamente.
- `GET /healthz` valida vida del servicio.
- `GET /readyz` valida vida del servicio y acceso a base de datos.
- `./scripts/backup_db.sh` y `./scripts/restore_db.sh` cubren backup/restore PostgreSQL.
- La guía de despliegue está en [docs/production.md](/Users/jpalmae/dev/facilerp/docs/production.md).

## Migraciones

```bash
flask --app app:create_app db-upgrade
```

## Integraciones opcionales

- `AUTH_BACKEND=supabase`: valida credenciales contra Supabase Auth y conserva el perfil/roles locales.
- `BRAND_STORAGE_BACKEND=supabase`: sube logos y favicons a Supabase Storage y devuelve URL firmada.
- `SUNAT_API_TOKEN`: activa consulta remota de RUC; sin token, se valida sólo formato.
- `BCRP_API_SERIES`: permite obtener tipo de cambio desde BCRP.

## Estado actual

La base ya cubre roadmap funcional Fase 0 a Fase 5 y trae artefactos mínimos de productización: migraciones, healthchecks, headers de seguridad, logs HTTP, CI y scripts de backup. Facturación electrónica SUNAT/OSE sigue fuera de este alcance.
