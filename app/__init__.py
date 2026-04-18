from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta
from pathlib import Path

from flask import Flask, g, render_template, request
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from app.commands import register_commands
from app.config import config_by_name
from app.context_processors import register_context_processors
from app.extensions import db, init_extensions, login_manager
from app.security import get_active_empresa_id
from app.services.bootstrap import ensure_demo_data


def create_app(config_name: str | None = None) -> Flask:
    config_key = config_name or "development"
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name[config_key])
    configure_logging(app)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_ROOT"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["BACKUP_DIR"]).mkdir(parents=True, exist_ok=True)

    if app.config["TRUST_PROXY_COUNT"] > 0:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=app.config["TRUST_PROXY_COUNT"],
            x_proto=app.config["TRUST_PROXY_COUNT"],
            x_host=app.config["TRUST_PROXY_COUNT"],
        )

    app.permanent_session_lifetime = timedelta(
        hours=app.config["PERMANENT_SESSION_LIFETIME_HOURS"]
    )

    # Validar secrets críticos en producción
    if config_key == "production":
        from app.config import ProductionConfig
        ProductionConfig.validate_secrets(app)

    init_extensions(app)
    _register_user_loader(app)
    register_blueprints(app)
    register_context_processors(app)
    register_commands(app)
    register_request_hooks(app)
    register_error_handlers(app)

    with app.app_context():
        if app.config["CREATE_DB_ON_START"]:
            db.create_all()
            if app.config["ENABLE_DEMO_BOOTSTRAP"]:
                ensure_demo_data()

    return app


def configure_logging(app: Flask) -> None:
    level = getattr(logging, app.config["LOG_LEVEL"], logging.INFO)
    app.logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            "%Y-%m-%dT%H:%M:%S%z",
        )
    )
    handler.setLevel(level)
    app.logger.addHandler(handler)
    app.logger.setLevel(level)


def register_blueprints(app: Flask) -> None:
    from app.modules.auth import bp as auth_bp
    from app.modules.compras import bp as compras_bp
    from app.modules.contabilidad import bp as contabilidad_bp
    from app.modules.core import bp as core_bp
    from app.modules.cxc_cxp import bp as cxc_cxp_bp
    from app.modules.inventario import bp as inventario_bp
    from app.modules.marca import bp as marca_bp
    from app.modules.reportes import bp as reportes_bp
    from app.modules.seguridad import bp as seguridad_bp
    from app.modules.tesoreria import bp as tesoreria_bp
    from app.modules.ventas import bp as ventas_bp

    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(inventario_bp, url_prefix="/inventario")
    app.register_blueprint(compras_bp, url_prefix="/compras")
    app.register_blueprint(ventas_bp, url_prefix="/ventas")
    app.register_blueprint(cxc_cxp_bp, url_prefix="/cxc-cxp")
    app.register_blueprint(contabilidad_bp, url_prefix="/contabilidad")
    app.register_blueprint(tesoreria_bp, url_prefix="/tesoreria")
    app.register_blueprint(reportes_bp, url_prefix="/reportes")
    app.register_blueprint(seguridad_bp, url_prefix="/seguridad")
    app.register_blueprint(marca_bp, url_prefix="/configuracion/marca")


def register_request_hooks(app: Flask) -> None:
    @app.before_request
    def load_request_context() -> None:
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        g.request_started_at = time.perf_counter()
        g.active_empresa_id = None
        g.active_role = None
        g.active_permissions = set()
        # Clear request-level caches from any previous request
        g._perm_cache = {}
        g._role_cache = {}
        g._ctx_globals = None
        if not current_user.is_authenticated:
            return
        empresa_id = get_active_empresa_id()
        g.active_empresa_id = empresa_id
        g.active_role = current_user.role_for_empresa(empresa_id)
        g.active_permissions = current_user.permissions_for_empresa(empresa_id)

    @app.after_request
    def finalize_response(response):
        response.headers.setdefault("X-Request-ID", g.get("request_id", "n/a"))
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com data:; connect-src 'self' https:; frame-ancestors 'self'; base-uri 'self'; form-action 'self'",
        )
        if app.config["ENABLE_HSTS"] and request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        if current_user.is_authenticated or request.path.startswith("/auth/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        duration_ms = (time.perf_counter() - g.get("request_started_at", time.perf_counter())) * 1000
        app.logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f user_id=%s empresa_id=%s remote_addr=%s",
            g.get("request_id"),
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            getattr(current_user, "id", None) if current_user.is_authenticated else None,
            g.get("active_empresa_id"),
            request.headers.get("X-Forwarded-For", request.remote_addr),
        )
        return response


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        app.logger.exception("Unhandled application error")
        request_id = getattr(g, "request_id", "N/A")
        return render_template("errors/500.html", request_id=request_id), 500


def _register_user_loader(app):
    from sqlalchemy.orm import selectinload

    from app.models import User
    from app.models.core import Empresa, UserEmpresaRole

    @login_manager.user_loader
    def load_user(user_id: str):
        return (
            db.session.query(User)
            .options(
                selectinload(User.memberships)
                .selectinload(UserEmpresaRole.empresa)
                .selectinload(Empresa.marca),
            )
            .get(user_id)
        )
