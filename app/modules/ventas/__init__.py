from flask import Blueprint


bp = Blueprint("ventas", __name__, template_folder="../../templates")


from app.modules.ventas import routes  # noqa: E402,F401
