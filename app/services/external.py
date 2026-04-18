from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import httpx
from flask import current_app


@dataclass
class ValidationResult:
    valid: bool
    message: str | None = None
    payload: dict | None = None


def validate_ruc_format(ruc: str) -> bool:
    return ruc.isdigit() and len(ruc) == 11


def validate_ruc(ruc: str) -> ValidationResult:
    if not validate_ruc_format(ruc):
        return ValidationResult(False, "El RUC debe tener 11 dígitos.")

    token = current_app.config.get("SUNAT_API_TOKEN")
    base_url = current_app.config.get("SUNAT_API_URL")
    if not token or not base_url:
        return ValidationResult(True, "Validación local de formato.")

    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(
                f"{base_url.rstrip('/')}/v1/contribuyente/contribuyentes/{ruc}/validarcomprobante",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return ValidationResult(True, "No se pudo validar con SUNAT; se acepta por formato.")

    estado = str(payload.get("estado") or payload.get("data", {}).get("estado", "")).lower()
    if estado and estado not in {"activo", "habido"}:
        return ValidationResult(False, f"RUC no válido en SUNAT: {estado}.", payload)
    return ValidationResult(True, "RUC validado con SUNAT.", payload)


def fetch_exchange_rate(target_date: date) -> Decimal | None:
    base_url = current_app.config.get("BCRP_API_URL")
    series = current_app.config.get("BCRP_API_SERIES")
    if not base_url or not series:
        return None

    formatted = target_date.strftime("%Y-%m-%d")
    url = f"{base_url.rstrip('/')}/{series}/{formatted}/{formatted}/json"
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return None

    periods = payload.get("periods", [])
    if not periods:
        return None
    value = periods[0].get("value")
    if isinstance(value, list):
        value = value[0]
    try:
        return Decimal(str(value))
    except Exception:
        return None
