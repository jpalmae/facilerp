from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    APP_NAME = "FacilERP"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'facilerp.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
    WTF_CSRF_TIME_LIMIT = None
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(5 * 1024 * 1024)))
    BRAND_STORAGE_BACKEND = os.getenv("BRAND_STORAGE_BACKEND", "local")
    AUTH_BACKEND = os.getenv("AUTH_BACKEND", "local")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "brand")
    SUPABASE_STORAGE_SIGNED_TTL = int(os.getenv("SUPABASE_STORAGE_SIGNED_TTL", "86400"))
    PERMANENT_SESSION_LIFETIME_HOURS = int(
        os.getenv("PERMANENT_SESSION_LIFETIME_HOURS", "8")
    )
    ENABLE_DEMO_BOOTSTRAP = env_bool("ENABLE_DEMO_BOOTSTRAP", True)
    DEFAULT_LOCALE = "es_PE"
    DEFAULT_CURRENCY = "PEN"
    UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", str(BASE_DIR / "uploads" / "brand")))
    TEMPLATES_AUTO_RELOAD = True
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    CREATE_DB_ON_START = env_bool("CREATE_DB_ON_START", True)
    AUTO_MIGRATE_ON_START = env_bool("AUTO_MIGRATE_ON_START", False)
    SUNAT_API_URL = os.getenv("SUNAT_API_URL", "https://api.sunat.gob.pe")
    SUNAT_API_TOKEN = os.getenv("SUNAT_API_TOKEN")
    BCRP_API_URL = os.getenv(
        "BCRP_API_URL", "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
    )
    BCRP_API_SERIES = os.getenv("BCRP_API_SERIES", "PD04637PD")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = os.getenv("REMEMBER_COOKIE_SAMESITE", "Lax")
    REMEMBER_COOKIE_SECURE = env_bool("REMEMBER_COOKIE_SECURE", False)
    PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "http")
    TRUST_PROXY_COUNT = int(os.getenv("TRUST_PROXY_COUNT", "0"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    ENABLE_DB_HEALTHCHECK = env_bool("ENABLE_DB_HEALTHCHECK", True)
    ENABLE_HSTS = env_bool("ENABLE_HSTS", False)
    BACKUP_DIR = os.getenv("BACKUP_DIR", str(BASE_DIR / "backups"))


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    ENABLE_DEMO_BOOTSTRAP = False
    CREATE_DB_ON_START = True


class ProductionConfig(Config):
    SECRET_KEY = os.getenv("SECRET_KEY")
    DEBUG = False
    ENABLE_DEMO_BOOTSTRAP = env_bool("ENABLE_DEMO_BOOTSTRAP", False)
    CREATE_DB_ON_START = env_bool("CREATE_DB_ON_START", False)
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", True)
    REMEMBER_COOKIE_SECURE = env_bool("REMEMBER_COOKIE_SECURE", True)
    PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https")
    TRUST_PROXY_COUNT = int(os.getenv("TRUST_PROXY_COUNT", "1"))
    ENABLE_HSTS = env_bool("ENABLE_HSTS", True)
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "redis://localhost:6379/1")

    @classmethod
    def validate_secrets(cls, app) -> None:
        if not app.config.get("SECRET_KEY"):
            raise RuntimeError(
                "FATAL: SECRET_KEY no está configurada. "
                "Defina la variable de entorno SECRET_KEY antes de ejecutar en producción."
            )


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
