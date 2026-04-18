from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from flask import current_app
from PIL import Image, UnidentifiedImageError
from supabase import create_client
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {
    "logo": {"png", "svg"},
    "favicon": {"png", "svg", "ico"},
}


class LocalBrandStorage:
    def save(self, file_storage: FileStorage, empresa_id: int, kind: str) -> str:
        extension = file_storage.filename.rsplit(".", 1)[-1].lower()
        filename = secure_filename(
            f"{kind}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.{extension}"
        )
        directory = Path(current_app.config["UPLOAD_ROOT"]) / str(empresa_id)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / filename
        file_storage.save(destination)
        # Devolver ruta relativa para servir vía endpoint autenticado
        relative_path = destination.relative_to(current_app.config["UPLOAD_ROOT"]).as_posix()
        return f"/uploads/brand/{relative_path}"


class SupabaseBrandStorage:
    def save(self, file_storage: FileStorage, empresa_id: int, kind: str) -> str:
        supabase_url = current_app.config["SUPABASE_URL"]
        service_role = current_app.config["SUPABASE_SERVICE_ROLE_KEY"]
        bucket = current_app.config["SUPABASE_STORAGE_BUCKET"]
        ttl = current_app.config["SUPABASE_STORAGE_SIGNED_TTL"]
        extension = file_storage.filename.rsplit(".", 1)[-1].lower()
        filename = secure_filename(
            f"{kind}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.{extension}"
        )
        path = f"brand/{empresa_id}/{filename}"
        payload = file_storage.stream.read()
        client = create_client(supabase_url, service_role)
        client.storage.from_(bucket).upload(
            path,
            payload,
            {"content-type": file_storage.mimetype or "application/octet-stream", "upsert": "true"},
        )
        signed = client.storage.from_(bucket).create_signed_url(path, ttl)
        file_storage.stream = BytesIO(payload)
        return signed.get("signedURL") or signed.get("signedUrl") or path


def allowed_file(filename: str, kind: str) -> bool:
    if "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[-1].lower()
    return extension in ALLOWED_EXTENSIONS[kind]


def validate_image_upload(file_storage: FileStorage, kind: str) -> None:
    if not file_storage or not getattr(file_storage, "filename", ""):
        return
    if not allowed_file(file_storage.filename, kind):
        raise ValueError("Formato de archivo no permitido.")

    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > current_app.config["MAX_CONTENT_LENGTH"]:
        raise ValueError("El archivo excede el tamaño máximo permitido.")

    extension = file_storage.filename.rsplit(".", 1)[-1].lower()
    if extension == "svg":
        chunk = file_storage.stream.read(512).decode("utf-8", errors="ignore").lower()
        file_storage.stream.seek(0)
        if "<svg" not in chunk:
            raise ValueError("El SVG no es válido.")
        return

    try:
        Image.open(file_storage.stream).verify()
    except (UnidentifiedImageError, OSError):
        raise ValueError("La imagen no es válida.")
    finally:
        file_storage.stream.seek(0)


def get_brand_storage():
    if current_app.config.get("BRAND_STORAGE_BACKEND") == "supabase":
        return SupabaseBrandStorage()
    return LocalBrandStorage()
