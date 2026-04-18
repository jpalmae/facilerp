# Módulo de Marca

## Qué resuelve

El módulo permite configurar identidad visual por empresa:

- Nombre visible del sistema
- Logo principal
- Favicon
- Color primario
- Color secundario

## Acceso

Sólo usuarios con rol `Administrador` sobre la empresa activa pueden entrar a `/configuracion/marca/`.

## Comportamiento actual

- La marca se carga desde `empresa_marca`.
- Si la empresa no tiene configuración, se usan los valores por defecto de FacilERP.
- El contexto Jinja inyecta `marca` y actualiza título, favicon, sidebar y acentos visuales.
- Los archivos se guardan localmente en `app/static/uploads/brand/<empresa_id>/`.

## Pendientes para cerrar la fase

- Mover uploads a Supabase Storage con URLs firmadas.
- Añadir validación MIME robusta con Pillow/SVG parsing.
- Inyectar marca en exportación PDF.
