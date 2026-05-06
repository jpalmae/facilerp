from __future__ import annotations

from flask import current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db, limiter
from app.models import AuditLog
from app.modules.auth import bp
from app.modules.auth.forms import LoginForm
from app.services.auth_provider import authenticate_credentials


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5/minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("core.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        result = authenticate_credentials(form.email.data, form.password.data)
        if not result.success or not result.user:
            flash(result.message or "Credenciales inválidas.", "error")
            db.session.add(
                AuditLog(
                    accion="login_failed",
                    detalle=form.email.data,
                    ip=request.remote_addr,
                )
            )
            db.session.commit()
        else:
            user = result.user
            empresa_preferida = user.preferred_empresa()
            if empresa_preferida is None:
                flash("Tu acceso a empresas está inactivo o vencido.", "error")
                return render_template("auth/login.html", form=form)
            login_user(user, remember=form.remember.data)
            session["active_empresa_id"] = empresa_preferida.id
            session.permanent = True
            db.session.add(
                AuditLog(
                    user_id=user.id,
                    empresa_id=session.get("active_empresa_id"),
                    accion="login",
                    ip=request.remote_addr,
                )
            )
            db.session.commit()
            return redirect(url_for("core.dashboard"))

    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    db.session.add(
        AuditLog(
            user_id=current_user.id,
            empresa_id=session.get("active_empresa_id"),
            accion="logout",
            ip=request.remote_addr,
        )
    )
    db.session.commit()
    logout_user()
    session.clear()
    flash("Sesión cerrada.", "success")
    response = redirect(url_for("auth.login"))
    response.delete_cookie(
        current_app.config.get("SESSION_COOKIE_NAME", "session"),
        path=current_app.config.get("SESSION_COOKIE_PATH", "/"),
        domain=current_app.config.get("SESSION_COOKIE_DOMAIN"),
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
        httponly=current_app.config.get("SESSION_COOKIE_HTTPONLY", True),
        samesite=current_app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
    )
    response.delete_cookie(
        current_app.config.get("REMEMBER_COOKIE_NAME", "remember_token"),
        path=current_app.config.get("REMEMBER_COOKIE_PATH", "/"),
        domain=current_app.config.get("REMEMBER_COOKIE_DOMAIN"),
        secure=current_app.config.get("REMEMBER_COOKIE_SECURE", False),
        httponly=current_app.config.get("REMEMBER_COOKIE_HTTPONLY", True),
        samesite=current_app.config.get("REMEMBER_COOKIE_SAMESITE", "Lax"),
    )
    return response
