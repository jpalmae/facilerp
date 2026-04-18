from flask import Blueprint


bp = Blueprint("inventario", __name__, template_folder="../../templates")


from app.modules.inventario import routes  # noqa: E402,F401
