# 🔍 Auditoría Completa de FacilERP — Propuestas de Mejora

_Auditoría realizada: 2026-04-30_

## Resumen Ejecutivo

El código es **sorprendentemente sólido** para un ERP en construcción. Tiene buena arquitectura, seguridad razonable, migraciones Alembic, tests funcionales, y separación por capas. Sin embargo, encontré **24 mejoras concretas** organizadas por severidad.

---

## 🔴 Severidad ALTA (bugs / seguridad / datos)

### 1. `TimestampMixin` duplicado y contradictorio
**Archivo:** `app/models/core.py` + `app/models/mixins.py`

Existen **dos versiones** de `TimestampMixin`:
- En `core.py`: usa `db.Column(db.DateTime(...))` con `default=lambda:` Python
- En `mixins.py`: usa `mapped_column(sa.DateTime)` con `server_default=sa.func.now()` (SQL server-side)

Todos los modelos heredan de la versión en `core.py`, ignorando `mixins.py`. Si alguien usa la de `mixins.py`, el comportamiento será diferente (server-side vs app-side timestamps).

**Propuesta:** Eliminar `TimestampMixin` de `core.py`, mantener solo la de `mixins.py`, y hacer que todos los modelos la importen desde allí.

---

### 2. Race condition en el dashboard principal
**Archivo:** `app/modules/core/routes.py` (dashboard)

El dashboard ejecuta **~8 queries** independientes en una sola función síncrona. Bajo carga, cada query ve un estado diferente de la BD:

```python
sales_orders = PedidoVenta.query.filter(...).all()
purchase_orders = OrdenCompra.query.filter(...).all()
receivables = DocumentoCxC.query.filter_by(...).all()
stock_rows = db.session.query(Stock, Producto).filter(...).all()
```

**Propuesta:** Refactorizar a queries agregadas que obtengan los KPIs directamente desde PostgreSQL con `func.sum()` y `GROUP BY`, eliminando la necesidad de cargar todos los registros en memoria y asegurando consistencia.

---

### 3. Saldo de tesorería sin protección de concurrencia
**Archivo:** `app/services/treasury.py`

`register_treasury_movement` modifica `treasury_account.saldo_actual` con un read-modify-write **sin lock pesimista**:

```python
treasury_account.saldo_actual = as_decimal(treasury_account.saldo_actual) + amount
```

Bajo concurrencia, dos ingresos simultáneos pueden perder uno.

**Propuesta:** Añadir `with_for_update()` como ya hace correctamente `inventory.py`:
```python
treasury_account = CuentaTesoreria.query.filter_by(id=treasury_account.id).with_for_update().first()
```

---

### 4. `build_financial_pdf` genera PDF roto como fallback
**Archivo:** `app/services/reporting.py`

El fallback cuando WeasyPrint falla genera un "PDF" a mano construyendo bytes raw que **no es un PDF válido**. Contiene el texto embebido como un string PostScript dentro de un stream PDF sin encoding correcto. En la práctica, esto produce un archivo corrupto.

**Propuesta:** Eliminar el fallback. Si WeasyPrint no está disponible, lanzar una excepción clara o retornar el HTML para descarga directa:
```python
except ImportError:
    raise RuntimeError("weasyprint no está instalado. Instálelo para generar PDFs.")
```

---

### 5. CSP permite `'unsafe-inline'` en scripts
**Archivo:** `app/__init__.py` (register_request_hooks)

```
script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net
```

Esto debilita significativamente la protección contra XSS.

**Propuesta:** Migrar los scripts inline a archivos `.js` externos (ya hay `app.js` y `forms.js`), y eliminar `'unsafe-inline'` para `script-src`. Usar `nonce-` para los casos estrictamente necesarios.

---

### 6. `login_user` sin rate limiting
**Archivo:** `app/modules/auth/routes.py`

El endpoint de login **no tiene `@limiter.limit()`**. Aunque Nginx lo protege externamente, a nivel de app es vulnerable a fuerza bruta.

**Propuesta:**
```python
from app.extensions import limiter

@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5/minute")
def login():
    ...
```

---

## 🟡 Severidad MEDIA (performance / arquitectura)

### 7. N+1 queries masivo en el context processor
**Archivo:** `app/context_processors.py`

`_visible_sidebar_sections()` llama a `current_user.has_permission()` por cada sección (11 secciones × ~3 queries c/una = ~33 queries) **en cada request**. Aunque hay cache en `g`, el context processor se ejecuta en cada render.

**Propuesta:** Precalcular las secciones visibles en el `before_request` (ya se calculan los permisos) y guardarlas en `g.sidebar_sections`.

---

### 8. `_active_admin_count` ineficiente
**Archivo:** `app/modules/seguridad/routes.py`

```python
def _active_admin_count(empresa_id: int) -> int:
    memberships = UserEmpresaRole.query.filter_by(empresa_id=empresa_id, rol=ROLE_ADMIN).all()
    return sum(1 for m in memberships if m.is_currently_active())
```

Carga **todos** los memberships admin en Python para contar los activos. Además, se llama múltiples veces en la misma request (toggle role, toggle state, etc.).

**Propuesta:** Usar una query SQL con `db.session.query(func.count(...))` o cachear el resultado en `g`.

---

### 9. `_render_dashboard` en seguridad ejecuta ~6 queries pesadas
**Archivo:** `app/modules/seguridad/routes.py`

Esta función (que se ejecuta en GET y en POST con errores) carga:
- Todos los memberships de la empresa
- Todos los grupos
- Todos los almacenes
- Para cada usuario: `groups_for_empresa()`, `allowed_warehouse_ids()`, `permissions_for_empresa()`
- Para cada grupo: cuenta miembros

Con 50 usuarios, esto puede generar **200+ queries**.

**Propuesta:** Refactorizar a queries agregadas con `JOIN` y `GROUP BY` para obtener todo en 3-4 queries.

---

### 10. Dashboard carga TODAS las órdenes del año en memoria
**Archivo:** `app/modules/core/routes.py`

```python
sales_orders = PedidoVenta.query.filter(... PedidoVenta.fecha >= year_start ...).all()
purchase_orders = OrdenCompra.query.filter(... OrdenCompra.fecha >= year_start ...).all()
```

Luego itera en Python para calcular KPIs. Con datos reales (miles de órdenes), esto será lento y consumirá mucha memoria.

**Propuesta:** Usar `db.session.query(func.sum(...), func.extract('month', ...)).group_by(...)` para obtener los agregados mensuales directamente desde PostgreSQL.

---

### 11. `as_decimal` importado circularmente
**Archivo:** `app/services/inventory.py`

```python
from app.utils.tax import as_decimal, calc_totals_with_igv
# ... pero también se define localmente en inventory.py y se re-exporta
```

El patrón de re-exportar desde `inventory.py` "para backward compatibility" es confuso. `as_decimal` aparece definido en `inventory.py` como un stub, en `utils/tax.py` como la implementación real, y se re-exporta desde `inventory.py`.

**Propuesta:** Eliminar el stub de `inventory.py` y actualizar todos los imports para que apunten directamente a `app.utils.tax.as_decimal`.

---

### 12. `bootstrap.py` es monolítico y frágil
**Archivo:** `app/services/bootstrap.py`

La función `ensure_demo_data()` tiene 200+ líneas que crean **todo** el universo demo en una sola transacción. Si un paso falla, no hay recuperación parcial. Además, la verificación de idempotencia es solo `if Empresa.query.first()` — si existe una empresa pero no los productos, no se crean.

**Propuesta:** Dividir en funciones independientes con idempotencia individual:
```python
def ensure_demo_data():
    ensure_demo_empresas()
    ensure_demo_users()
    ensure_demo_products()
    ensure_demo_operations()
```

---

### 13. `MovimientoStock` no valida `tipo` contra un enum
**Archivo:** `app/models/operations.py`

El campo `tipo` es un `String(20)` libre. Valores válidos (`entrada`, `salida`, `recepcion_compra`, `ajuste_salida`) están dispersos en el servicio.

**Propuesta:** Definir constantes o usar un `Enum`:
```python
class MovementType(str, enum.Enum):
    ENTRADA = "entrada"
    SALIDA = "salida"
    RECEPCION_COMPRA = "recepcion_compra"
    AJUSTE_SALIDA = "ajuste_salida"
```

---

### 14. Falta índice compuesto en operaciones frecuentes
**Archivo:** `app/models/operations.py`

`MovimientoStock` se consulta frecuentemente por `(empresa_id, referencia_tipo, referencia_id)` pero no tiene índice compuesto para eso.

**Propuesta:**
```python
__table_args__ = (
    db.Index('ix_movimientos_empresa_referencia', 'empresa_id', 'referencia_tipo', 'referencia_id'),
)
```

---

### 15. `statement_snapshot` calcula patrimonio incorrectamente
**Archivo:** `app/services/accounting.py`

```python
"patrimonio": balance["activo"] + balance["pasivo"],
```

El patrimonio debería ser `activo - pasivo` (o más precisamente, calcularse como `activo - pasivo - pasivo_no_corriente`). Sumar activo + pasivo no tiene sentido contable.

**Propuesta:** Corregir a:
```python
"patrimonio": balance["activo"] - abs(balance["pasivo"]),
```
O mejor aún, incluir cuentas de patrimonio explícitamente en el catálogo contable.

---

### 16. `login` no registra intentos fallidos
**Archivo:** `app/modules/auth/routes.py`

No hay auditoría de intentos de login fallidos. El `AuditLog` solo registra logins exitosos.

**Propuesta:**
```python
if not result.success:
    db.session.add(AuditLog(accion="login_failed", detalle=result.message, ip=request.remote_addr))
    db.session.commit()
```

---

## 🟢 Severidad BAJA (calidad / DX / mantenibilidad)

### 17. Contraseñas demo hardcoded en tests
**Archivos:** `tests/test_*.py`

Los tests tienen `login(client, "admin@facilerp.pe", "Admin123!")` repetido en cada archivo (6 veces).

**Propuesta:** Mover a un helper en `conftest.py`:
```python
@pytest.fixture
def admin_client(client):
    login(client, "admin@facilerp.pe", "Admin123!")
    return client
```

---

### 18. `worker.py` es un placeholder sin funcionalidad
**Archivo:** `app/worker.py`

Es un `while True: time.sleep(60)` que corre como servicio Docker.

**Propuesta:** Eliminar el servicio del docker-compose hasta que haya tareas reales, o integrar Celery/RQ cuando se necesite.

---

### 19. Tests no aíslan datos — `ensure_demo_data` comparte estado
**Archivo:** `tests/conftest.py`

Todos los tests comparten los mismos IDs de demo data. Los tests asumen IDs específicos (ej: buscar por RUC `"20123456789"`), lo que hace que sean frágiles ante cambios en el seed.

**Propuesta:** Usar factories (ej: `factory_boy`) o al menos funciones helper que creen datos específicos por test.

---

### 20. Falta `Persona` como entidad separada
**Modelos actuales:** `Cliente` y `Proveedor`

Ambos tienen `ruc` + `razon_social` pero son entidades separadas. Un cliente puede ser también proveedor, pero no hay relación entre ellos.

**Propuesta:** Considerar crear una entidad base `Tercero` de la que hereden ambos:
```python
class Tercero(TimestampMixin, db.Model):
    ruc, razon_social, direccion, telefono, email...

class Cliente(Tercero): ...
class Proveedor(Tercero): ...
```

---

### 21. Tailwind CSS cargado desde CDN en producción
**Archivo:** `app/templates/base.html`

```html
<script src="https://cdn.tailwindcss.com?plugins=forms"></script>
```

Tailwind CDN es para desarrollo. En producción, agrega latencia y depende de un CDN externo.

**Propuesta:** Compilar Tailwind como parte del build (ya existe `tailwind.config.js` y `input.css`/`output.css`). Reemplazar el CDN con el CSS compilado.

---

### 22. Imágenes SVG inline en base.html
**Archivo:** `app/templates/base.html`

La macro `nav_icon` tiene **~120 líneas de SVG inline** para 10 iconos, evaluándose en cada render.

**Propuesta:** Mover a un archivo de partials Jinja (`components/icons.html`) o usar un sprite SVG.

---

### 23. Faltan `updated_at` con timezone consistente
**Archivo:** `app/models/mixins.py`

`ExpirableMixin.expires_at` usa `sa.DateTime(timezone=True)` pero el `TimestampMixin` alternativo en `mixins.py` usa `sa.DateTime` **sin timezone**. La mezcla causa confusión.

**Propuesta:** Estandarizar todos los campos `DateTime` para usar `timezone=True`.

---

### 24. No hay CI/CD configurado
**Archivo:** `.github/` existe pero está vacío

Hay un directorio `.github` sin workflows. El proyecto tiene tests funcionales que podrían correrse automáticamente.

**Propuesta:** Crear `.github/workflows/test.yml`:
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest --tb=short -q
```

---

## 📊 Resumen de Prioridades

| # | Severidad | Issue | Esfuerzo | Estado |
|---|-----------|-------|----------|--------|
| 1 | 🔴 ALTA | TimestampMixin duplicado | 30 min | ⬜ Pendiente |
| 2 | 🔴 ALTA | Race condition dashboard | 2 hrs | ⬜ Pendiente |
| 3 | 🔴 ALTA | Saldo tesorería sin lock | 15 min | ⬜ Pendiente |
| 4 | 🔴 ALTA | PDF fallback roto | 30 min | ⬜ Pendiente |
| 5 | 🔴 ALTA | CSP unsafe-inline | 3 hrs | ⬜ Pendiente |
| 6 | 🔴 ALTA | Login sin rate limit | 10 min | ⬜ Pendiente |
| 7 | 🟡 MEDIA | N+1 en context processor | 1 hr | ⬜ Pendiente |
| 8 | 🟡 MEDIA | _active_admin_count ineficiente | 30 min | ⬜ Pendiente |
| 9 | 🟡 MEDIA | _render_dashboard N+1 | 2 hrs | ⬜ Pendiente |
| 10 | 🟡 MEDIA | Dashboard carga todo en memoria | 2 hrs | ⬜ Pendiente |
| 11 | 🟡 MEDIA | as_decimal import circular | 30 min | ⬜ Pendiente |
| 12 | 🟡 MEDIA | bootstrap monolítico | 2 hrs | ⬜ Pendiente |
| 13 | 🟡 MEDIA | Tipo movimiento sin enum | 1 hr | ⬜ Pendiente |
| 14 | 🟡 MEDIA | Índices faltantes | 30 min | ⬜ Pendiente |
| 15 | 🟡 MEDIA | Patrimonio calculado mal | 15 min | ⬜ Pendiente |
| 16 | 🟡 MEDIA | Sin auditoría login fallido | 30 min | ⬜ Pendiente |
| 17 | 🟢 BAJA | Contraseñas demo en tests | 30 min | ⬜ Pendiente |
| 18 | 🟢 BAJA | Worker placeholder | 15 min | ⬜ Pendiente |
| 19 | 🟢 BAJA | Tests sin aislamiento | 1 hr | ⬜ Pendiente |
| 20 | 🟢 BAJA | Falta entidad Tercero | 2 hrs | ⬜ Pendiente |
| 21 | 🟢 BAJA | Tailwind desde CDN | 1 hr | ⬜ Pendiente |
| 22 | 🟢 BAJA | SVG inline en base | 30 min | ⬜ Pendiente |
| 23 | 🟢 BAJA | Timezone inconsistente | 30 min | ⬜ Pendiente |
| 24 | 🟢 BAJA | Sin CI/CD | 30 min | ⬜ Pendiente |
