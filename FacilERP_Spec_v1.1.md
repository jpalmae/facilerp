# Especificación Técnica — FacilERP
**Sistema ERP para PyME | Mercado Peruano**
**Stack: Python / Flask / Supabase / Tailwind CSS / Docker**
Versión 1.1 — Marzo 2026 | CONFIDENCIAL

---

## Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Stack Tecnológico](#2-stack-tecnológico)
3. [Especificación de Módulos](#3-especificación-de-módulos)
   - 3.1 [Autenticación y Usuarios](#31-módulo-autenticación-y-usuarios)
   - 3.2 [Personalización de Marca (White-label)](#32-módulo-personalización-de-marca-white-label)
   - 3.3 [Contabilidad](#33-módulo-contabilidad)
   - 3.4 [Gestión de Ventas](#34-módulo-gestión-de-ventas)
   - 3.5 [Inventario](#35-módulo-inventario)
   - 3.6 [Compras](#36-módulo-compras)
   - 3.7 [Cuentas por Cobrar y Pagar](#37-módulo-cuentas-por-cobrar-y-pagar)
   - 3.8 [Tesorería](#38-módulo-tesorería)
   - 3.9 [Informes y Reportes](#39-módulo-informes-y-reportes)
4. [Arquitectura, Seguridad y Configuración](#4-arquitectura-seguridad-y-configuración)
5. [Diseño de Interfaz (UI/UX)](#5-diseño-de-interfaz-uiux)
6. [Plan de Desarrollo por Fases](#6-plan-de-desarrollo-por-fases)
7. [Consideraciones Específicas Mercado Peruano](#7-consideraciones-específicas-mercado-peruano)
8. [Requerimientos No Funcionales](#8-requerimientos-no-funcionales)
9. [Dependencias Python Principales](#9-dependencias-python-principales)
10. [Criterios de Aceptación](#10-criterios-de-aceptación)

---

## 1. Resumen Ejecutivo

**FacilERP** es un sistema ERP web orientado a pequeñas y medianas empresas del mercado peruano. Replica las funcionalidades core de plataformas como Defontana PE, adaptadas al contexto regulatorio y tributario de Perú (SUNAT, IGV, RUC).

El nombre **FacilERP** es el nombre técnico del producto base. Gracias al módulo de personalización de marca (white-label), cada empresa que adopte el sistema puede renombrarlo, cambiar su logo, favicon y colores de tema sin modificar el código fuente.

La facturación electrónica (integración SUNAT/OSE) está excluida de esta fase inicial y será implementada en una etapa posterior. El sistema está diseñado para recibirla sin rediseño arquitectónico.

### Módulos incluidos en esta fase

- **Personalización de marca** (white-label: nombre, logo, favicon, colores)
- Autenticación y gestión de usuarios con roles
- Contabilidad general (plan de cuentas, asientos, libros contables)
- Gestión de ventas (pedidos, clientes, ingresos — sin emisión de facturas electrónicas)
- Inventario (productos, stock, movimientos, valorizaciones)
- Compras (proveedores, órdenes de compra, recepciones)
- Cuentas por cobrar y pagar
- Tesorería (caja, bancos, conciliación)
- Gestión de clientes y proveedores (maestro centralizado / CRM básico)
- Informes financieros (Balance, P&L, flujo de caja, libros auxiliares)

### Excluido de esta fase

- Facturación electrónica (SUNAT/OSE): Fase 6 futura
- Módulo de Recursos Humanos / Nómina
- Punto de Venta (POS)
- Integración con e-commerce

---

## 2. Stack Tecnológico

### 2.1 Arquitectura general

El sistema sigue una arquitectura **monolítica modular** (Modular Monolith), lo que permite velocidad de desarrollo en etapa inicial con capacidad de extraer microservicios en el futuro si es necesario.

| Capa | Tecnología | Justificación |
|------|-----------|---------------|
| Base de datos | Supabase (PostgreSQL 15) | Managed DB, Auth nativo, RLS, migraciones |
| Autenticación | Supabase Auth | JWT, roles, multi-usuario out-of-the-box |
| Backend | Python 3.12 + Flask 3.x | Control total sobre lógica contable compleja |
| ORM | SQLAlchemy 2.x + Alembic | Modelos relacionales, migraciones versionadas |
| Frontend | Jinja2 + HTMX + Alpine.js | Server-side rendering, interactividad sin SPA |
| Estilos | Tailwind CSS 3.x | Utility-first; variables CSS para theming dinámico |
| Contenedores | Docker + Docker Compose | Portabilidad, entornos reproducibles dev/prod |
| Servidor WSGI | Gunicorn | Servidor de producción estable para Linux |
| CI/CD | GitHub Actions | Deploy automático a VPS o cloud |

### 2.2 Infraestructura con Docker

Toda la aplicación corre en contenedores Docker, garantizando que el entorno de desarrollo sea idéntico al de producción.

#### Servicios definidos en `docker-compose.yml`

| Servicio | Imagen base | Puerto | Descripción |
|----------|-------------|--------|-------------|
| `web` | `python:3.12-slim` | 5000 | Aplicación Flask (Gunicorn en producción) |
| `worker` | `python:3.12-slim` | — | Tareas en background (reportes, exports) |
| `nginx` | `nginx:alpine` | 80 / 443 | Reverse proxy, archivos estáticos, TLS |

> **Nota:** La base de datos NO se contenedoriza localmente. Se conecta siempre a Supabase (cloud) tanto en desarrollo como en producción. Esto simplifica el mantenimiento y garantiza backups gestionados.

#### Dockerfile (aplicación Flask)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema (WeasyPrint requiere libcairo)
RUN apt-get update && apt-get install -y \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Compilar Tailwind CSS (incluye variables de tema)
RUN npx tailwindcss -i ./app/static/css/input.css \
    -o ./app/static/css/output.css --minify

EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:create_app()"]
```

#### `docker-compose.yml` (desarrollo)

```yaml
version: "3.9"

services:
  web:
    build: .
    ports:
      - "5000:5000"
    env_file: .env
    volumes:
      - .:/app          # Hot reload en desarrollo
    command: flask run --host=0.0.0.0 --debug
    depends_on:
      - nginx

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf
      - ./app/static:/static
    depends_on:
      - web

  worker:
    build: .
    env_file: .env
    command: python -m app.worker
    volumes:
      - .:/app
```

### 2.3 Separación de responsabilidades Flask vs Supabase

**Supabase provee:**
- PostgreSQL gestionado (conexión vía psycopg2 / SQLAlchemy desde el contenedor)
- Supabase Auth para gestión de sesiones y tokens JWT
- Row Level Security (RLS) como capa de seguridad adicional a nivel de BD
- Supabase Storage para archivos adjuntos (logos, favicons, vouchers, documentos)

**Flask (dentro del contenedor) provee:**
- Toda la lógica de negocio: asientos contables dobles, validaciones tributarias, cierres de período
- API REST interna para endpoints HTMX
- Control de acceso basado en roles (RBAC)
- Inyección dinámica de configuración de marca en el contexto Jinja2 global
- Generación de reportes y PDFs (WeasyPrint / ReportLab)

### 2.4 Estructura de directorios del proyecto

```
faciliterp/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Configuración por entorno (dev/prod)
│   ├── extensions.py        # SQLAlchemy, LoginManager, Limiter, etc.
│   ├── context_processors.py # Inyecta marca/tema en todos los templates
│   ├── models/              # Modelos SQLAlchemy por módulo
│   ├── modules/
│   │   ├── auth/            # Autenticación y usuarios
│   │   ├── marca/           # Personalización white-label
│   │   ├── contabilidad/    # Plan de cuentas, asientos, libros
│   │   ├── ventas/          # Pedidos, clientes, ingresos
│   │   ├── inventario/      # Productos, stock, movimientos
│   │   ├── compras/         # OC, proveedores, recepciones
│   │   ├── tesoreria/       # Caja, bancos, conciliación
│   │   ├── cxc_cxp/         # Cuentas por cobrar y pagar
│   │   └── reportes/        # Generación de informes
│   ├── templates/
│   │   ├── base.html        # Template raíz — consume variables de marca
│   │   ├── components/      # Componentes reutilizables
│   │   └── [modulo]/        # Templates por módulo
│   └── static/
│       ├── css/
│       │   ├── input.css    # Tailwind entrada (incluye CSS vars de tema)
│       │   └── output.css   # CSS compilado
│       ├── js/
│       ├── img/
│       │   └── defaults/    # Logo y favicon por defecto de FacilERP
│       └── uploads/brand/   # Logos y favicons subidos por empresas
├── migrations/              # Alembic
├── tests/
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── docker-compose.prod.yml
├── Dockerfile
├── .env.example
├── .dockerignore
└── requirements.txt
```

---

## 3. Especificación de Módulos

### 3.1 Módulo: Autenticación y Usuarios

Gestión de acceso al sistema con control de roles y soporte multi-empresa.

#### Funcionalidades

- Login / logout con Supabase Auth (JWT)
- Roles: Administrador, Contador, Vendedor, Solo lectura
- Multi-empresa: un usuario puede pertenecer a múltiples empresas con roles distintos
- Perfil de usuario editable (nombre, email, contraseña)
- Auditoría de accesos (log de login/logout con IP y timestamp)
- Sesiones con expiración configurable (default: 8 horas)

#### Modelo de datos

| Tabla | Campos principales |
|-------|--------------------|
| `users` | id (UUID), email, nombre, activo, created_at |
| `empresas` | id, ruc, razon_social, logo_url, moneda, regimen_tributario |
| `user_empresa_roles` | user_id, empresa_id, rol, activo |
| `audit_log` | id, user_id, empresa_id, accion, ip, timestamp |

---

### 3.2 Módulo: Personalización de Marca (White-label)

Permite que cada empresa que use FacilERP configure su propia identidad visual sin tocar el código. La interfaz se adapta en tiempo real a la marca definida por el administrador.

#### Concepto de diseño

FacilERP es el nombre del producto base. La marca visible al usuario final (nombre, logo, colores) es completamente configurable por empresa. Si una empresa se llama "ContaFácil SAC", el sistema mostrará "ContaFácil SAC" en todos lados — sin rastro de "FacilERP" en la UI.

#### Funcionalidades

- **Nombre del sistema:** texto libre que reemplaza "FacilERP" en toda la interfaz (título de página, navbar, emails, pie de página, PDFs generados)
- **Logo principal:** carga de imagen (PNG/SVG, recomendado 200×60px) que aparece en el sidebar, login y documentos exportados
- **Favicon:** carga de imagen ICO/PNG (32×32px) que aparece en la pestaña del navegador
- **Color primario:** selector de color (hex) — afecta botones, links activos, badges y acentos principales
- **Color secundario:** selector de color (hex) — afecta sidebar, header, hover states
- **Vista previa en tiempo real:** el panel de personalización muestra un mockup de la interfaz con los cambios aplicados antes de guardar
- **Resetear a valores por defecto:** restaura la configuración visual de FacilERP en un clic
- Los cambios son **por empresa** — en entornos multi-empresa, cada empresa tiene su propia configuración de marca

#### Implementación técnica

La marca se almacena en la tabla `empresa_marca` y se inyecta en todos los templates vía un **context processor global** de Flask:

```python
# app/context_processors.py
@app.context_processor
def inject_marca():
    empresa_id = current_user.empresa_activa_id
    marca = MarcaConfig.query.filter_by(empresa_id=empresa_id).first()
    return dict(marca=marca or MarcaConfig.defaults())
```

El `base.html` consume estas variables en cada render:

```html
<!-- base.html -->
<title>{{ marca.nombre_sistema }}</title>
<link rel="icon" href="{{ marca.favicon_url }}">

<style>
  :root {
    --color-primary:   {{ marca.color_primary }};
    --color-secondary: {{ marca.color_secondary }};
  }
</style>

<img src="{{ marca.logo_url }}" alt="{{ marca.nombre_sistema }}" class="sidebar-logo">
```

Tailwind CSS usa las variables CSS `--color-primary` y `--color-secondary` como colores de tema, de modo que todo el sistema de diseño se adapta automáticamente sin recompilar el CSS.

Los archivos de logo y favicon se almacenan en **Supabase Storage** bajo el bucket `brand/{empresa_id}/`. Las URLs firmadas se guardan en la tabla de configuración.

#### Pantalla de configuración (`/configuracion/marca`)

El panel de personalización estará disponible solo para el rol **Administrador** y contendrá:

1. **Identidad** — Nombre del sistema (campo de texto)
2. **Logotipo** — Uploader con preview, restricciones de formato y tamaño
3. **Favicon** — Uploader con preview de pestaña simulada
4. **Colores** — Color picker dual (primario / secundario) con vista previa de componentes UI
5. **Botones** — Guardar cambios / Restaurar valores por defecto

#### Modelo de datos

| Tabla | Campos |
|-------|--------|
| `empresa_marca` | id, empresa_id (FK único), nombre_sistema, logo_url, favicon_url, color_primary (hex), color_secondary (hex), updated_at, updated_by |

#### Valores por defecto (FacilERP)

| Campo | Valor por defecto |
|-------|------------------|
| `nombre_sistema` | `FacilERP` |
| `logo_url` | `/static/img/defaults/facilierp-logo.svg` |
| `favicon_url` | `/static/img/defaults/favicon.ico` |
| `color_primary` | `#2563EB` (azul Tailwind blue-600) |
| `color_secondary` | `#1E3A5F` (azul oscuro) |

---

### 3.3 Módulo: Contabilidad

Contabilidad de partida doble compliant con el **Plan Contable General Empresarial (PCGE)** peruano.

#### Funcionalidades

- Plan de cuentas PCGE pre-cargado (8 elementos, cuentas hasta nivel 4)
- Registro de asientos contables con validación estricta de partida doble (debe = haber)
- Asientos automáticos generados por otros módulos (compras, ventas, tesorería)
- Libro Diario y Libro Mayor
- Balance de Comprobación (8 y 10 columnas)
- Estado de Resultados (por naturaleza y por función)
- Balance General
- Cierre de período contable (mensual/anual) con bloqueo de edición retroactiva
- Reversión de asientos con trazabilidad
- Centro de costos básico

#### Modelo de datos

| Tabla | Campos principales |
|-------|--------------------|
| `plan_cuentas` | id, empresa_id, codigo, nombre, tipo (activo/pasivo/patrimonio/ingreso/gasto), nivel, cuenta_padre_id, permite_movimiento |
| `periodos_contables` | id, empresa_id, anio, mes, estado (abierto/cerrado), fecha_cierre |
| `asientos` | id, empresa_id, periodo_id, numero, fecha, glosa, tipo (manual/automatico), estado, created_by |
| `asiento_lineas` | id, asiento_id, cuenta_id, debe, haber, referencia, centro_costo_id |

#### Consideraciones PCGE Perú

- El sistema debe venir pre-cargado con el Plan Contable General Empresarial vigente
- Cuentas de destino (elementos 6/7/9) marcadas correctamente
- IGV cuenta separada: `40111 IGV – Cuenta propia`
- Retenciones, detracciones y percepciones con cuentas dedicadas

---

### 3.4 Módulo: Gestión de Ventas

Registro y seguimiento de ventas e ingresos. La emisión de comprobantes electrónicos (SUNAT/OSE) queda **excluida de esta fase** y se integrará posteriormente.

#### Funcionalidades

- Registro de cotizaciones / proformas
- Órdenes de venta (con flujo de aprobación configurable)
- Registro de ingresos manuales (hasta que se integre facturación electrónica)
- Gestión de listas de precios (por cliente, por volumen, por período)
- Descuentos por línea y por documento
- Cálculo automático de IGV (18%), exoneradas y exportaciones (0%)
- Vinculación con inventario (reserva y despacho automático de stock)
- Vinculación automática con cuentas por cobrar
- Estadísticas de ventas por período, cliente, producto y vendedor

#### Modelo de datos

| Tabla | Campos principales |
|-------|--------------------|
| `clientes` | id, empresa_id, ruc/dni, razon_social, tipo_cliente, condicion_pago, lista_precio_id, vendedor_id |
| `pedidos_venta` | id, empresa_id, cliente_id, fecha, estado, moneda, tipo_cambio, subtotal, igv, total, observaciones |
| `pedido_lineas` | id, pedido_id, producto_id, cantidad, precio_unitario, descuento_pct, subtotal, igv_linea |
| `ingresos` | id, empresa_id, pedido_id, cliente_id, monto, fecha, tipo_pago, cuenta_banco_id, asiento_id |

---

### 3.5 Módulo: Inventario

Control de existencias con valorización y trazabilidad completa de movimientos.

#### Funcionalidades

- Catálogo de productos (con categorías, unidades de medida, código de barras)
- Gestión de almacenes y ubicaciones
- Movimientos de stock: entradas, salidas, traslados, ajustes
- Método de valorización: **Costo Promedio Ponderado (CPP)** — estándar Perú
- Stock mínimo con alertas de reposición
- Kardex valorizado por producto
- Toma de inventario físico (comparación vs stock teórico)
- Soporte para productos con y sin stock (servicios)
- Control de lotes y fechas de vencimiento (opcional por empresa)

#### Modelo de datos

| Tabla | Campos principales |
|-------|--------------------|
| `productos` | id, empresa_id, codigo, nombre, categoria_id, unidad_medida, tipo (bien/servicio), costo_promedio, precio_venta, stock_minimo, activo |
| `almacenes` | id, empresa_id, nombre, ubicacion, activo |
| `stock` | id, producto_id, almacen_id, cantidad_disponible, cantidad_reservada, updated_at |
| `movimientos_stock` | id, empresa_id, producto_id, almacen_id, tipo, cantidad, costo_unitario, costo_total, referencia_tipo, referencia_id, fecha, asiento_id |

---

### 3.6 Módulo: Compras

Gestión del ciclo completo de compras desde solicitud hasta registro contable.

#### Funcionalidades

- Registro de proveedores (RUC, condiciones de pago, cuenta bancaria, cuenta de detracción)
- Solicitudes de compra internas
- Órdenes de compra (con flujo de aprobación configurable)
- Recepción de mercadería (parcial y total)
- Registro de facturas de compra (con validación de RUC en SUNAT vía API)
- Cálculo de IGV soportado, detracciones y retenciones
- Vinculación automática con inventario y cuentas por pagar
- Generación automática de asiento contable al registrar factura
- Comparativa orden de compra vs factura recibida

#### Modelo de datos

| Tabla | Campos principales |
|-------|--------------------|
| `proveedores` | id, empresa_id, ruc, razon_social, tipo_proveedor, condicion_pago, cuenta_detraccion, activo |
| `ordenes_compra` | id, empresa_id, proveedor_id, fecha, estado, moneda, tipo_cambio, subtotal, igv, total |
| `oc_lineas` | id, oc_id, producto_id, cantidad, precio_unitario, descuento_pct, subtotal, igv_linea |
| `facturas_compra` | id, empresa_id, proveedor_id, oc_id, serie, numero, fecha_emision, fecha_vencimiento, subtotal, igv, detraccion, total, asiento_id |
| `recepciones` | id, empresa_id, oc_id, fecha, almacen_id, estado |
| `recepcion_lineas` | id, recepcion_id, producto_id, cantidad_recibida, lote, fecha_vencimiento |

---

### 3.7 Módulo: Cuentas por Cobrar y Pagar

Control de obligaciones financieras pendientes con clientes y proveedores.

#### Funcionalidades — Cuentas por Cobrar (CxC)

- Registro automático de CxC al confirmar pedido/ingreso de venta
- Seguimiento de cuotas y vencimientos
- Registro de cobros (parciales y totales)
- Gestión de mora y días de atraso
- Estado de cuenta por cliente
- Reporte de antigüedad de cartera (aging)
- Notas de crédito y débito a clientes

#### Funcionalidades — Cuentas por Pagar (CxP)

- Registro automático de CxP al registrar factura de compra
- Gestión de vencimientos por cuota
- Programación de pagos
- Registro de pagos con vinculación a tesorería
- Estado de cuenta por proveedor
- Reporte de antigüedad de deudas

#### Modelo de datos

| Tabla | Campos principales |
|-------|--------------------|
| `documentos_cxc` | id, empresa_id, cliente_id, tipo, referencia_id, monto_original, monto_pendiente, fecha_emision, fecha_vencimiento, estado |
| `cobros` | id, empresa_id, documento_cxc_id, monto, fecha, tipo_pago, cuenta_banco_id, asiento_id |
| `documentos_cxp` | id, empresa_id, proveedor_id, factura_compra_id, monto_original, monto_pendiente, fecha_emision, fecha_vencimiento, estado |
| `pagos` | id, empresa_id, documento_cxp_id, monto, fecha, tipo_pago, cuenta_banco_id, asiento_id |

---

### 3.8 Módulo: Tesorería

Control de flujo de caja, cuentas bancarias y conciliación.

#### Funcionalidades

- Gestión de cuentas bancarias y cajas chicas (múltiples cuentas, múltiples monedas)
- Registro de ingresos y egresos de tesorería
- Transferencias entre cuentas propias
- Conciliación bancaria manual con importación de extracto (CSV/Excel)
- Flujo de caja proyectado (basado en CxC y CxP pendientes)
- Posición de caja consolidada en tiempo real
- Tipos de cambio diarios (registro manual o consulta automática API BCRP)

#### Modelo de datos

| Tabla | Campos principales |
|-------|--------------------|
| `cuentas_tesoreria` | id, empresa_id, tipo (banco/caja), banco, numero_cuenta, moneda, saldo_actual, activo |
| `movimientos_tesoreria` | id, empresa_id, cuenta_id, tipo (ingreso/egreso/transferencia), monto, fecha, glosa, referencia_tipo, referencia_id, conciliado, asiento_id |
| `tipos_cambio` | id, empresa_id, moneda, fecha, compra, venta, fuente |

---

### 3.9 Módulo: Informes y Reportes

Generación de reportes financieros y operativos con exportación a PDF y Excel. Los PDFs generados incluyen el logo y nombre del sistema configurado en el módulo de marca.

#### Reportes financieros

- Balance General (activo, pasivo y patrimonio)
- Estado de Resultados (P&L) por período
- Balance de Comprobación (8 y 10 columnas)
- Libro Diario
- Libro Mayor por cuenta
- Flujo de Caja real y proyectado

#### Reportes operativos

- Ventas por período, cliente, producto, vendedor
- Compras por período, proveedor, producto
- Kardex valorizado de inventario
- Antigüedad de cartera — CxC aging
- Antigüedad de deudas — CxP aging
- Posición bancaria consolidada

#### Exportación

- **PDF:** WeasyPrint con templates Jinja2 — el header del PDF usa `marca.logo_url` y `marca.nombre_sistema`
- **Excel:** openpyxl para reportes tabulares
- Filtros por: empresa, período, cuenta, proveedor/cliente, producto

---

## 4. Arquitectura, Seguridad y Configuración

### 4.1 Control de acceso por roles (RBAC)

| Módulo | Admin | Contador | Vendedor | Solo lectura |
|--------|-------|----------|----------|--------------|
| **Personalización de marca** | R/W | — | — | — |
| Autenticación / Usuarios | R/W/D | — | — | — |
| Contabilidad | R/W/D | R/W | — | R |
| Ventas | R/W/D | R | R/W | R |
| Inventario | R/W/D | R | R | R |
| Compras | R/W/D | R/W | — | R |
| Tesorería | R/W/D | R/W | — | R |
| CxC / CxP | R/W/D | R/W | R (solo sus clientes) | R |
| Reportes | Todos | Todos financieros | Solo ventas | Todos lectura |
| Configuración general | R/W/D | — | — | — |

### 4.2 Seguridad

- Toda comunicación sobre HTTPS (TLS 1.2+), terminado en el contenedor Nginx
- Variables de entorno en `.env` (nunca en la imagen Docker ni en el repositorio)
- `.dockerignore` excluye: `.env`, `*.pyc`, `__pycache__`, `tests/`, `.git/`
- Supabase RLS activo como segunda capa de seguridad en PostgreSQL
- CSRF protection en formularios Flask (Flask-WTF)
- Rate limiting en endpoints de autenticación (Flask-Limiter)
- Logs de auditoría: toda operación crítica registrada con user_id, timestamp, IP
- Sesiones con expiración configurable (default: 8 horas)
- Backups automáticos gestionados por Supabase (point-in-time recovery)
- Imágenes Docker construidas desde base oficial `python:3.12-slim`
- Archivos de logo/favicon subidos validados por tipo MIME y tamaño máximo (2MB)
- Los archivos de marca se almacenan en Supabase Storage con URLs firmadas, no en el sistema de archivos del contenedor

### 4.3 Multi-empresa

El sistema soporta múltiples empresas desde el inicio. Cada empresa tiene su propio RUC, plan de cuentas, configuración de marca y usuarios asignados. El campo `empresa_id` es obligatorio y filtrado en todas las queries de negocio.

- Un usuario puede pertenecer a múltiples empresas con roles distintos
- El cambio de empresa activa se hace desde el header sin re-login
- Al cambiar de empresa, el tema visual (logo, colores) cambia automáticamente
- RLS de Supabase filtra por `empresa_id` como capa adicional

### 4.4 Variables de entorno requeridas

| Variable | Descripción |
|----------|-------------|
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_ANON_KEY` | Clave pública Supabase Auth |
| `SUPABASE_SERVICE_ROLE_KEY` | Clave privada para operaciones admin |
| `SUPABASE_STORAGE_BUCKET` | Nombre del bucket para archivos de marca |
| `DATABASE_URL` | Connection string PostgreSQL (psycopg2) |
| `SECRET_KEY` | Flask secret key para sesiones |
| `FLASK_ENV` | `development` / `production` |
| `SUNAT_API_URL` | Endpoint consulta RUC SUNAT |
| `BCRP_API_URL` | Endpoint tipos de cambio BCRP |

---

## 5. Diseño de Interfaz (UI/UX)

### 5.1 Stack frontend

- **Jinja2** para renderizado server-side (SSR) — servido por el contenedor Flask
- **HTMX** para actualizaciones parciales sin recargar la página (tablas, formularios, filtros, preview de marca)
- **Alpine.js** para interactividad liviana del cliente (color pickers, modales, toggles)
- **Tailwind CSS 3.x** compilado con CLI durante el build de la imagen Docker
- **Variables CSS** (`--color-primary`, `--color-secondary`) para theming dinámico sin recompilar
- **Heroicons** para iconografía (SVG inline)

### 5.2 Sistema de temas dinámico

El theming funciona mediante variables CSS inyectadas en el `<head>` de `base.html` en cada request, tomadas de la configuración de marca de la empresa activa:

```html
<style>
  :root {
    --color-primary:        {{ marca.color_primary }};
    --color-secondary:      {{ marca.color_secondary }};
    --color-primary-hover:  {{ marca.color_primary | darken(10) }};
  }
</style>
```

Tailwind CSS extiende su configuración para usar estas variables:

```javascript
// tailwind.config.js
theme: {
  extend: {
    colors: {
      brand: {
        primary:   'var(--color-primary)',
        secondary: 'var(--color-secondary)',
        hover:     'var(--color-primary-hover)',
      }
    }
  }
}
```

Todos los componentes del sistema (botones, sidebar, badges, links activos) usan las clases `bg-brand-primary`, `text-brand-secondary`, etc., que se actualizan automáticamente al cambiar los colores de marca.

### 5.3 Layout general

- Sidebar fijo a la izquierda con logo de marca y navegación por módulos
- Header con: nombre del sistema, empresa activa, usuario logueado, selector de empresa
- Breadcrumb en todas las páginas internas
- Responsive: funcional desde 1024px (tablet landscape) — no mobile-first en esta fase
- Modo claro por defecto. Modo oscuro como mejora futura

### 5.4 Componentes reutilizables requeridos

- **DataTable:** tabla con paginación server-side, búsqueda, filtros y exportación (vía HTMX)
- **Modal:** confirmación, edición rápida, visualización de detalle
- **Form genérico:** validación client-side con Alpine.js + server-side con Flask-WTF
- **Toast/Alert:** notificaciones de éxito, error, advertencia
- **Badge de estado:** Activo/Inactivo, Abierto/Cerrado, Pagado/Pendiente
- **Selector de período:** mes/año para filtros contables
- **Autocomplete:** búsqueda de cuentas, productos, clientes via endpoints HTMX
- **ColorPicker:** componente Alpine.js para selección de color primario/secundario en panel de marca
- **ImageUploader:** componente con preview, validación de tipo/tamaño y progress bar para logo y favicon

---

## 6. Plan de Desarrollo por Fases

| Fase | Módulos | Entregable | Duración estimada |
|------|---------|-----------|-------------------|
| **Fase 0** | Infraestructura base | Proyecto Flask, Docker Compose funcional, Supabase conectado, Auth, roles, multi-empresa, layout base Tailwind con sistema de temas | 1–2 semanas |
| **Fase 0.5** | Personalización de marca | Panel `/configuracion/marca`, context processor, theming dinámico, upload de logo/favicon a Supabase Storage | 1 semana |
| **Fase 1** | Inventario + Compras | CRUD completo, recepciones, movimientos de stock, asientos automáticos de compras | 3–4 semanas |
| **Fase 2** | Ventas + CxC | Pedidos de venta, ingresos, estado de cuenta clientes, aging CxC | 3–4 semanas |
| **Fase 3** | Contabilidad | Plan de cuentas PCGE, asientos manuales, Libro Diario/Mayor, Balance de Comprobación | 4–5 semanas |
| **Fase 4** | Tesorería + CxP | Cuentas bancarias, movimientos, pagos, aging CxP, conciliación básica | 2–3 semanas |
| **Fase 5** | Reportes | Balance General, P&L, Flujo de Caja, exportación PDF y Excel (con marca en header) | 2–3 semanas |
| **Fase 6 (futura)** | Facturación electrónica | Integración SUNAT vía OSE (Nubefact, Efact), comprobantes electrónicos | A definir |

### Criterios de calidad por fase

- Cada fase debe incluir tests unitarios con pytest (mínimo 70% cobertura en lógica de negocio)
- Toda la lógica contable (partida doble, asientos automáticos) debe tener tests de integración
- Los endpoints HTMX deben retornar fragmentos HTML válidos ante errores (no 500 desnudos)
- Migraciones Alembic versionadas y reversibles para cada fase
- Imagen Docker debe construirse sin errores antes de cada merge a `main`
- `docker-compose up` debe levantar el entorno completo sin pasos manuales adicionales

---

## 7. Consideraciones Específicas Mercado Peruano

### 7.1 Tributarias

- **IGV:** 18% estándar. Soporte para tasas diferenciadas (exportaciones 0%, exoneradas)
- **RUC:** validación de formato (11 dígitos) y consulta de estado activo/inactivo en API SUNAT
- **Plan Contable:** PCGE pre-cargado en seed de base de datos
- **Detracciones:** cuentas específicas y registro de depósito en cuenta corriente SUNAT
- **Retenciones:** 3% sobre proveedores en régimen de retenciones
- **Percepciones:** soporte para percepciones de IGV en compras
- **Moneda base:** Soles (PEN). Soporte para operaciones en USD con tipo de cambio diario
- **Tipos de cambio:** consulta automática API BCRP

### 7.2 Contables

- Ejercicio fiscal: enero a diciembre
- Período de cierre: mensual con validación de saldos cuadrados antes de cerrar
- Libros electrónicos PLE (formato SUNAT) — estructura lista desde el inicio, generación en fase futura
- Comprobantes: Factura, Boleta, Nota de Crédito, Nota de Débito (estructura de datos lista, emisión en Fase 6)

### 7.3 APIs externas a integrar

| API | Uso | URL base |
|-----|-----|---------|
| SUNAT — Consulta RUC | Validación de RUC de clientes y proveedores | `https://api.sunat.gob.pe` |
| BCRP — Tipo de cambio | Tipo de cambio diario PEN/USD oficial | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api` |
| OSE/SUNAT (Fase 6) | Emisión de facturas electrónicas | Vía proveedor: Nubefact o Efact |

---

## 8. Requerimientos No Funcionales

| Requerimiento | Criterio |
|---------------|---------|
| **Rendimiento** | Tiempo de respuesta < 2s para listados con hasta 10,000 registros (con paginación e índices en PostgreSQL) |
| **Disponibilidad** | 99.5% uptime en producción (Supabase SLA + VPS con monitoreo) |
| **Escalabilidad** | Arquitectura modular preparada para agregar módulos sin refactor del core |
| **Mantenibilidad** | Código documentado, linting con Ruff, formateo con Black, pre-commit hooks |
| **Portabilidad** | `docker-compose up` levanta entorno completo idéntico en cualquier máquina con Docker |
| **Backup** | Backups automáticos diarios gestionados por Supabase (point-in-time recovery 7 días) |
| **Auditoría** | Todo cambio en datos financieros queda registrado en `audit_log` con usuario, timestamp e IP |
| **Internacionalización** | Fechas en formato DD/MM/YYYY. Números con separador de miles punto y decimal coma |
| **Seguridad de imágenes** | Imágenes Docker escaneadas con Trivy o Docker Scout antes de deploy a producción |
| **Theming** | El cambio de colores de marca debe reflejarse en la UI sin recompilar CSS ni reiniciar el contenedor |
| **Archivos de marca** | Logo y favicon almacenados en Supabase Storage. Tamaño máximo: 2MB. Formatos aceptados: PNG, SVG, ICO |

---

## 9. Dependencias Python Principales

| Paquete | Versión mínima | Propósito |
|---------|---------------|-----------|
| `Flask` | 3.0 | Framework web principal |
| `SQLAlchemy` | 2.0 | ORM y query builder |
| `Alembic` | 1.13 | Migraciones de base de datos |
| `psycopg2-binary` | 2.9 | Driver PostgreSQL para Supabase |
| `Flask-Login` | 0.6 | Gestión de sesiones de usuario |
| `Flask-WTF` | 1.2 | Formularios con CSRF protection |
| `Flask-Limiter` | 3.7 | Rate limiting en endpoints |
| `python-dotenv` | 1.0 | Variables de entorno desde `.env` |
| `WeasyPrint` | 62 | Generación de PDF con logo de marca |
| `openpyxl` | 3.1 | Exportación a Excel |
| `supabase-py` | 2.x | Cliente Supabase (Auth y Storage para archivos de marca) |
| `Pillow` | 10.x | Validación y procesamiento de imágenes subidas (logo, favicon) |
| `Gunicorn` | 22 | Servidor WSGI para producción |
| `pytest` | 8.x | Testing unitario e integración |
| `pytest-flask` | 1.3 | Fixtures y helpers para testing Flask |
| `ruff` | 0.4 | Linting y formateo de código |

---

## 10. Criterios de Aceptación

### 10.1 Módulo de marca

1. El administrador puede cambiar el nombre, logo, favicon, color primario y secundario desde `/configuracion/marca`.
2. Los cambios de marca se reflejan inmediatamente en toda la interfaz sin reiniciar el servidor.
3. Los PDFs exportados muestran el logo y el nombre del sistema configurado en el header.
4. Un usuario con rol distinto a Administrador no puede acceder a `/configuracion/marca` (redirige a 403).
5. En entornos multi-empresa, cambiar de empresa activa actualiza el tema visual automáticamente.
6. La opción "Restaurar valores por defecto" vuelve a los valores de FacilERP correctamente.
7. Los archivos de logo y favicon son validados: se rechazan tipos MIME no permitidos y archivos mayores a 2MB.

### 10.2 Funcionales (ERP)

1. El sistema permite registrar asientos contables con validación de partida doble (debe = haber). Los asientos desequilibrados son rechazados con mensaje explicativo.
2. Cada operación de compra, venta o tesorería genera automáticamente el asiento contable correspondiente, sin intervención manual del usuario.
3. El Balance de Comprobación cuadra en todo momento (suma debe = suma haber en el período).
4. El stock nunca puede quedar negativo — validación en backend antes de confirmar despachos.
5. Un usuario con rol Vendedor no puede acceder a módulos de Contabilidad ni Tesorería.
6. Los reportes Balance General y Estado de Resultados coinciden con los saldos del Libro Mayor.
7. La validación de RUC consulta SUNAT y rechaza RUCs inválidos o dados de baja.

### 10.3 Técnicos / Docker

1. `docker-compose up` levanta el entorno completo sin configuración manual adicional (solo requiere `.env`).
2. `docker-compose up --build` construye la imagen sin errores desde cero.
3. Las migraciones se ejecutan con `alembic upgrade head` sin errores en base de datos limpia.
4. Cobertura de tests >= 70% en módulos de contabilidad, inventario y marca.
5. Ningún secret o credencial en el repositorio ni en la imagen Docker.
6. Tiempo de carga de listados principales < 2 segundos con 5,000 registros de prueba.
7. La imagen de producción pasa el escaneo de vulnerabilidades críticas con Trivy o Docker Scout.

### 10.4 Entregables del proyecto

- Repositorio Git con `README.md` completo (setup con Docker, variables de entorno, comandos de desarrollo y producción)
- `docker-compose.yml` para desarrollo y `docker-compose.prod.yml` para producción
- `.env.example` con todas las variables necesarias documentadas (sin valores reales)
- Script de seed con datos de prueba (empresa demo con marca configurada, plan de cuentas PCGE completo, productos, clientes, proveedores)
- Assets por defecto de FacilERP incluidos en el repositorio (`/app/static/img/defaults/`)
- Documentación del módulo de marca en `/docs/marca.md` (guía para el administrador)
- Changelog versionado por fase

---

*— Fin del documento —*

*FacilERP v1.1 | Marzo 2026 | Confidencial — Uso interno*
