from __future__ import annotations

from flask import Blueprint


bp = Blueprint("seguridad", __name__, template_folder="../../templates")


from app.modules.seguridad import routes  # noqa: E402,F401
