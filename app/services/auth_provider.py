from __future__ import annotations

from dataclasses import dataclass

from flask import current_app
from supabase import create_client

from app.models import User


@dataclass
class AuthResult:
    success: bool
    user: User | None = None
    message: str | None = None


def authenticate_credentials(email: str, password: str) -> AuthResult:
    backend = current_app.config.get("AUTH_BACKEND", "local")
    normalized_email = email.lower().strip()

    if backend == "supabase":
        supabase_url = current_app.config.get("SUPABASE_URL")
        anon_key = current_app.config.get("SUPABASE_ANON_KEY")
        if not supabase_url or not anon_key:
            return AuthResult(False, message="Falta configuración de Supabase Auth.")
        try:
            client = create_client(supabase_url, anon_key)
            client.auth.sign_in_with_password(
                {"email": normalized_email, "password": password}
            )
        except Exception:
            return AuthResult(False, message="Credenciales inválidas en Supabase.")

        user = User.query.filter_by(email=normalized_email, activo=True).first()
        if not user:
            return AuthResult(
                False,
                message="Usuario autenticado en Supabase pero sin perfil local asignado.",
            )
        return AuthResult(True, user=user)

    user = User.query.filter_by(email=normalized_email).first()
    if not user or not user.activo or not user.check_password(password):
        return AuthResult(False, message="Credenciales inválidas.")
    return AuthResult(True, user=user)
